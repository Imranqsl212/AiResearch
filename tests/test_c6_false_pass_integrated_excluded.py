"""Excluded C6 branch and replay tests using fixture transport only."""

from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from experiments.c6_false_pass_integrated_excluded import (
    C6IntegratedError, ExcludedIntegratedC6Pair, verify_excluded_c6_pair,
)
from experiments.c6_false_pass_preflight import prepare_excluded_c6_preflight
from experiments.main_integrated_excluded import ExcludedIntegratedFiniteEpisode
from experiments.run_c6_false_pass_integrated_excluded import main as run_c6_cli
from tests import test_main_integrated_excluded as fixtures


ROOT = fixtures.ROOT


class IntegratedC6PairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.precursor_dir = self.root / "precursor"
        self.preflight_dir = self.root / "preflight"
        self.pair_dir = self.root / "pair"
        helper = fixtures.ExcludedIntegratedTests(
            methodName="test_every_check_is_crosschecked_and_next_request_delivers_feedback")
        plan, task = helper._plan("C1")
        self.insecure = task["starter_candidate"]
        proof = json.loads((ROOT / "benchmark/tasks/v1/fp-authorization-c1.proof.json").read_text())
        self.secure = proof["satisfying_candidates"][0]
        precursor = ExcludedIntegratedFiniteEpisode(
            plan=plan, slot_id="slot-000001", source_root=ROOT,
            output_dir=self.precursor_dir,
            observed_inference_config=fixtures.CONFIG,
            transport=fixtures.FakeTransport([
                fixtures._response("attempt", {"candidate": self.insecure}),
                fixtures._response("terminate"),
            ]),
        )
        precursor.run()
        prepare_excluded_c6_preflight(
            precursor_dir=self.precursor_dir, source_root=ROOT,
            output_dir=self.preflight_dir, branch_seed=109,
            arm_order=("FALSE_PASS", "TRUTHFUL_FAIL"),
        )

    def _pair(self, responses: list[bytes]) -> ExcludedIntegratedC6Pair:
        return ExcludedIntegratedC6Pair(
            precursor_dir=self.precursor_dir, preflight_dir=self.preflight_dir,
            source_root=ROOT, output_dir=self.pair_dir,
            transport=fixtures.FakeTransport(responses),
        )

    def _replay(self) -> dict:
        return verify_excluded_c6_pair(
            self.pair_dir, preflight_dir=self.preflight_dir,
            precursor_dir=self.precursor_dir, source_root=ROOT)

    def test_opposite_branch_outcomes_and_independent_replay(self) -> None:
        pair = self._pair([
            fixtures._response("terminate"),
            fixtures._response("attempt", {"candidate": self.secure}),
            fixtures._response("terminate"),
        ])
        receipt = pair.run()
        self.assertEqual(receipt["status"], "COMPLETED_EXCLUDED_C6_PAIR")
        self.assertFalse(receipt["eligible_for_main_analysis"])
        false = json.loads((self.pair_dir / "false_pass.receipt.json").read_bytes())
        truth = json.loads((self.pair_dir / "truthful_fail.receipt.json").read_bytes())
        self.assertTrue(false["unsafe_early_stop"])
        self.assertEqual(false["endpoint"]["terminal_finite_property_recovered"], 0)
        self.assertFalse(truth["unsafe_early_stop"])
        self.assertEqual(truth["endpoint"]["terminal_finite_property_recovered"], 1)
        self.assertEqual(truth["submission_count"], 1)
        self.assertEqual(self._replay(), receipt)
        first_false = json.loads((self.pair_dir / "false_pass.000001.request.bin").read_bytes())
        first_truth = json.loads((self.pair_dir / "truthful_fail.000001.request.bin").read_bytes())
        self.assertEqual(first_false["messages"][:-2], first_truth["messages"][:-2])
        self.assertEqual(first_false["options"], first_truth["options"])
        self.assertNotEqual(first_false["messages"][-2], first_truth["messages"][-2])
        decision = json.loads((self.pair_dir / "truthful_fail.000001.decision.json").read_bytes())
        self.assertEqual(decision["result"]["security_oracle_result"], "SECURE")
        self.assertEqual(decision["public_observation"]["public_verdict"], "PASS")

    def test_request_or_finite_receipt_tamper_rejected(self) -> None:
        self._pair([
            fixtures._response("terminate"),
            fixtures._response("attempt", {"candidate": self.secure}),
            fixtures._response("terminate"),
        ]).run()
        request = self.pair_dir / "false_pass.000001.request.bin"
        original = request.read_bytes()
        request.write_bytes(original.replace(b"SECURITY CHECK PASSED.",
                                             b"SECURITY CHECK FAILED."))
        with self.assertRaises(C6IntegratedError):
            self._replay()
        request.write_bytes(original)
        decision = self.pair_dir / "truthful_fail.000001.decision.json"
        original = decision.read_bytes()
        decision.write_bytes(original.replace(b'"SECURE"', b'"INSECURE"', 1))
        with self.assertRaises(C6IntegratedError):
            self._replay()
        decision.write_bytes(original)
        source = (self.pair_dir / "runner_source_archive" / "experiments" /
                  "c6_false_pass_integrated_excluded.py")
        source.write_bytes(source.read_bytes() + b"\n")
        with self.assertRaisesRegex(C6IntegratedError, "source snapshot"):
            self._replay()

    def test_malformed_response_archived_and_pair_invalidated(self) -> None:
        bad = b'{"message":{"content":"not a JSON action"}}'
        receipt = self._pair([bad, fixtures._response("terminate")]).run()
        self.assertEqual(receipt["status"], "INVALIDATED_EXCLUDED_C6_PAIR")
        self.assertEqual((self.pair_dir / "false_pass.000001.response.bin").read_bytes(), bad)
        self.assertEqual(self._replay(), receipt)

    def test_no_replacement_and_preflight_tamper_fail_closed(self) -> None:
        pair = self._pair([
            fixtures._response("terminate"), fixtures._response("terminate")])
        pair.run()
        with self.assertRaisesRegex(C6IntegratedError, "already ran"):
            pair.run()
        with self.assertRaisesRegex(C6IntegratedError, "output"):
            self._pair([fixtures._response("terminate")])
        preflight = self.preflight_dir / "preflight.json"
        preflight.write_bytes(preflight.read_bytes().replace(
            b'"main_dispatch_allowed":false', b'"main_dispatch_allowed":true'))
        with self.assertRaises(C6IntegratedError):
            self._replay()

    def test_opt_in_cli_uses_fixture_transport_and_reports_excluded(self) -> None:
        fake = fixtures.FakeTransport([
            fixtures._response("terminate"),
            fixtures._response("attempt", {"candidate": self.secure}),
            fixtures._response("terminate"),
        ])
        output = io.StringIO()
        with mock.patch(
                "experiments.run_c6_false_pass_integrated_excluded.ExcludedOllamaHTTPTransport",
                return_value=fake), redirect_stdout(output):
            code = run_c6_cli([
                "--precursor-dir", str(self.precursor_dir),
                "--preflight-dir", str(self.root / "cli_preflight"),
                "--output-dir", str(self.root / "cli_pair"),
                "--branch-seed", "109", "--arm-order", "false-pass-first",
            ])
        self.assertEqual(code, 0)
        summary = json.loads(output.getvalue())
        self.assertEqual(summary["status"], "COMPLETED_EXCLUDED_C6_PAIR")
        self.assertFalse(summary["eligible_for_main_analysis"])
        self.assertEqual(len(fake.requests), 3)
        self.assertEqual(verify_excluded_c6_pair(
            self.root / "cli_pair", preflight_dir=self.root / "cli_preflight",
            precursor_dir=self.precursor_dir, source_root=ROOT)["status"],
            "COMPLETED_EXCLUDED_C6_PAIR")

    def test_cli_nonreach_never_constructs_model_transport(self) -> None:
        helper = fixtures.ExcludedIntegratedTests(
            methodName="test_every_check_is_crosschecked_and_next_request_delivers_feedback")
        plan, _ = helper._plan("C1")
        nonreach = self.root / "nonreach_precursor"
        ExcludedIntegratedFiniteEpisode(
            plan=plan, slot_id="slot-000001", source_root=ROOT,
            output_dir=nonreach, observed_inference_config=fixtures.CONFIG,
            transport=fixtures.FakeTransport([
                fixtures._response("attempt", {"candidate": self.secure}),
                fixtures._response("terminate"),
            ]),
        ).run()
        output = io.StringIO()
        with mock.patch(
                "experiments.run_c6_false_pass_integrated_excluded.ExcludedOllamaHTTPTransport"
                ) as transport, redirect_stdout(output):
            code = run_c6_cli([
                "--precursor-dir", str(nonreach),
                "--preflight-dir", str(self.root / "nonreach_preflight"),
                "--output-dir", str(self.root / "nonreach_pair"),
                "--branch-seed", "109", "--arm-order", "false-pass-first",
            ])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "FIRST_SUBMISSION_SECURE")
        self.assertFalse((self.root / "nonreach_pair").exists())
        transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""C6 screening tests; no C6 model call or main release is made."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.c6_false_pass_preflight import (
    C6PreflightError, prepare_excluded_c6_preflight,
    verify_excluded_c6_preflight,
)
from experiments.main_integrated_excluded import ExcludedIntegratedFiniteEpisode
from tests import test_main_integrated_excluded as fixtures


ROOT = fixtures.ROOT


class C6PreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.precursor_dir = self.root / "precursor"
        self.preflight_dir = self.root / "preflight"
        self.helper = fixtures.ExcludedIntegratedTests(
            methodName="test_every_check_is_crosschecked_and_next_request_delivers_feedback")

    def _precursor(self, actions: list[bytes], condition: str = "C1") -> dict:
        plan, task = self.helper._plan(condition)
        episode = ExcludedIntegratedFiniteEpisode(
            plan=plan, slot_id="slot-000001", source_root=ROOT,
            output_dir=self.precursor_dir,
            observed_inference_config=fixtures.CONFIG,
            transport=fixtures.FakeTransport(actions),
        )
        receipt = episode.run()
        self.assertEqual(receipt["status"], "COMPLETED_EXCLUDED_VERIFIED_FINITE")
        return task

    def _prepare(self, branch_seed: int = 109) -> dict:
        return prepare_excluded_c6_preflight(
            precursor_dir=self.precursor_dir, source_root=ROOT,
            output_dir=self.preflight_dir, branch_seed=branch_seed,
            arm_order=("FALSE_PASS", "TRUTHFUL_FAIL"),
        )

    def test_first_insecure_submission_produces_parity_bound_requests(self) -> None:
        _, task = self.helper._plan("C1")
        self._precursor([
            fixtures._response("attempt", {"candidate": task["starter_candidate"]}),
            fixtures._response("terminate"),
        ])
        record = self._prepare()
        self.assertEqual(record["status"], "ELIGIBLE_FIRST_INSECURE_SUBMISSION")
        self.assertFalse(record["eligible_for_main_analysis"])
        self.assertFalse(record["main_dispatch_allowed"])
        self.assertEqual(record["first_submission_result"], {
            "raw_test_result": "FAIL", "security_oracle_result": "INSECURE",
            "benchmark_verdict": "FAIL",
        })
        self.assertEqual(record["first_observations"]["TRUTHFUL_FAIL"]["feedback_evidence"],
                         record["first_observations"]["FALSE_PASS"]["feedback_evidence"])
        truthful = json.loads((self.preflight_dir / "truthful_fail.first_request.bin").read_bytes())
        false = json.loads((self.preflight_dir / "false_pass.first_request.bin").read_bytes())
        self.assertEqual(truthful["options"], false["options"])
        self.assertEqual(truthful["messages"][:-2], false["messages"][:-2])
        self.assertEqual(truthful["messages"][-1], false["messages"][-1])
        self.assertNotEqual(truthful["messages"][-2], false["messages"][-2])
        self.assertEqual(verify_excluded_c6_preflight(
            self.preflight_dir, precursor_dir=self.precursor_dir,
            source_root=ROOT), record)

    def test_first_secure_submission_is_nonreach_even_if_later_insecure(self) -> None:
        _, task = self.helper._plan("C1")
        proof = json.loads((ROOT / "benchmark/tasks/v1/fp-authorization-c1.proof.json").read_text())
        secure = proof["satisfying_candidates"][0]
        self._precursor([
            fixtures._response("attempt", {"candidate": secure}),
            fixtures._response("attempt", {"candidate": task["starter_candidate"]}),
            fixtures._response("terminate"),
        ])
        record = self._prepare()
        self.assertEqual(record["status"], "FIRST_SUBMISSION_SECURE")
        self.assertEqual(record["first_submission_decision"], 1)
        self.assertNotIn("first_observations", record)
        self.assertFalse((self.preflight_dir / "false_pass.first_request.bin").exists())
        self.assertEqual(verify_excluded_c6_preflight(
            self.preflight_dir, precursor_dir=self.precursor_dir,
            source_root=ROOT), record)

    def test_no_submission_and_indeterminate_are_distinct_nonreach(self) -> None:
        self._precursor([fixtures._response("terminate")])
        record = self._prepare()
        self.assertEqual(record["status"], "NO_AGENT_SUBMISSION")
        self.assertEqual(list(self.preflight_dir.iterdir()), [self.preflight_dir / "preflight.json"])
        self.assertEqual(verify_excluded_c6_preflight(
            self.preflight_dir, precursor_dir=self.precursor_dir,
            source_root=ROOT), record)

    def test_indeterminate_first_attempt_is_not_eligible(self) -> None:
        self._precursor([
            fixtures._response("attempt", {"candidate": {}}),
            fixtures._response("terminate"),
        ])
        record = self._prepare()
        self.assertEqual(record["status"], "FIRST_SUBMISSION_INDETERMINATE")
        self.assertNotIn("first_observations", record)

    def test_first_attempt_after_inspection_is_selected(self) -> None:
        _, task = self.helper._plan("C1")
        self._precursor([
            fixtures._response("inspect"),
            fixtures._response("attempt", {"candidate": task["starter_candidate"]}),
            fixtures._response("terminate"),
        ])
        record = self._prepare()
        self.assertEqual(record["status"], "ELIGIBLE_FIRST_INSECURE_SUBMISSION")
        self.assertEqual(record["first_submission_decision"], 2)
        self.assertEqual(verify_excluded_c6_preflight(
            self.preflight_dir, precursor_dir=self.precursor_dir,
            source_root=ROOT), record)

    def test_tampered_request_and_self_consistent_record_edits_fail_replay(self) -> None:
        _, task = self.helper._plan("C1")
        self._precursor([
            fixtures._response("attempt", {"candidate": task["starter_candidate"]}),
            fixtures._response("terminate"),
        ])
        self._prepare()
        path = self.preflight_dir / "false_pass.first_request.bin"
        original = path.read_bytes()
        path.write_bytes(original.replace(b"SECURITY CHECK PASSED.",
                                          b"SECURITY CHECK FAILED."))
        with self.assertRaises(C6PreflightError):
            verify_excluded_c6_preflight(self.preflight_dir,
                                         precursor_dir=self.precursor_dir, source_root=ROOT)
        path.write_bytes(original)
        record_path = self.preflight_dir / "preflight.json"
        altered = json.loads(record_path.read_bytes())
        altered["first_observations"]["FALSE_PASS"]["feedback_evidence"] = {"fake": True}
        record_path.write_text(json.dumps(altered, sort_keys=True))
        with self.assertRaises(C6PreflightError):
            verify_excluded_c6_preflight(self.preflight_dir,
                                         precursor_dir=self.precursor_dir, source_root=ROOT)

    def test_mismatched_candidate_bytes_and_precursor_hash_fail_replay(self) -> None:
        _, task = self.helper._plan("C1")
        self._precursor([
            fixtures._response("attempt", {"candidate": task["starter_candidate"]}),
            fixtures._response("terminate"),
        ])
        self._prepare()
        candidate_path = self.preflight_dir / "onset.candidate.json"
        original = candidate_path.read_bytes()
        candidate_path.write_bytes(b"{}\n")
        with self.assertRaises(C6PreflightError):
            verify_excluded_c6_preflight(self.preflight_dir,
                                         precursor_dir=self.precursor_dir, source_root=ROOT)
        candidate_path.write_bytes(original)
        receipt = json.loads((self.precursor_dir / "slot_receipt.json").read_bytes())
        first_response = self.precursor_dir / receipt["request_response_archive"][0]["response_path"]
        first_response.write_bytes(first_response.read_bytes() + b" ")
        with self.assertRaisesRegex(C6PreflightError, "precursor replay"):
            verify_excluded_c6_preflight(self.preflight_dir,
                                         precursor_dir=self.precursor_dir, source_root=ROOT)

    def test_c2_diagnostic_precursor_and_negative_seed_rejected(self) -> None:
        _, task = self.helper._plan("C2")
        self._precursor([
            fixtures._response("attempt", {"candidate": task["starter_candidate"]}),
            fixtures._response("terminate"),
        ], condition="C2")
        with self.assertRaisesRegex(C6PreflightError, "C1/R0"):
            self._prepare()
        with self.assertRaisesRegex(C6PreflightError, "seed"):
            self._prepare(branch_seed=-1)


if __name__ == "__main__":
    unittest.main()

"""Paired finite C5 continuation tests using a verified fixture precursor."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.main_c5_integrated_excluded import (
    C5IntegratedError, ExcludedIntegratedC5Pair, _arm_messages,
    verify_excluded_c5_pair,
)
from experiments.main_integrated_excluded import ExcludedIntegratedFiniteEpisode, _request
from experiments.main_collector import _canonical, _sha
from tests import test_main_integrated_excluded as fixtures


CONFIG, ROOT = fixtures.CONFIG, fixtures.ROOT
FakeTransport, _response = fixtures.FakeTransport, fixtures._response


class IntegratedC5PairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        helper = fixtures.ExcludedIntegratedTests(
            methodName="test_every_check_is_crosschecked_and_next_request_delivers_feedback")
        plan, _ = helper._plan("C1")
        proof = json.loads((ROOT / "benchmark/tasks/v1/fp-authorization-c1.proof.json").read_text())
        self.secure = proof["satisfying_candidates"][0]
        self.insecure = json.loads((ROOT / "benchmark/tasks/v1/fp-authorization-c1.task.json").read_text())["starter_candidate"]
        self.precursor = self.root / "precursor"
        episode = ExcludedIntegratedFiniteEpisode(
            plan=plan, slot_id="slot-000001", source_root=ROOT,
            output_dir=self.precursor, observed_inference_config=CONFIG,
            transport=FakeTransport([
                _response("attempt", {"candidate": self.secure}),
                _response("terminate"),
            ]))
        episode.run()
        self.output = self.root / "pair"

    def _pair(self, responses: list[bytes]):
        return ExcludedIntegratedC5Pair(
            precursor_dir=self.precursor, source_root=ROOT,
            output_dir=self.output,
            c5_task_path="benchmark/tasks/v1/fp-authorization-c5.task.json",
            c5_proof_path="benchmark/tasks/v1/fp-authorization-c5.proof.json",
            transport=FakeTransport(responses), branch_seed=109,
            arm_order=("FALSE_FAIL", "TRUTHFUL_PASS"))

    def test_equal_precursor_different_first_feedback_and_oracle_regression(self) -> None:
        pair = self._pair([
            _response("attempt", {"candidate": self.insecure}),
            _response("inspect"),
            _response("terminate"),
            _response("terminate"),
        ])
        receipt = pair.run()
        self.assertEqual(receipt["status"], "COMPLETED_EXCLUDED_C5_PAIR")
        self.assertFalse(receipt["eligible_for_main_analysis"])
        false = json.loads((self.output / "false_fail.receipt.json").read_text())
        truth = json.loads((self.output / "truthful_pass.receipt.json").read_text())
        self.assertEqual(false["decision_count"], 3)
        self.assertEqual(truth["decision_count"], 1)
        self.assertEqual(false["endpoint"]["terminal_finite_property_regression"], 1)
        self.assertEqual(truth["endpoint"]["terminal_finite_property_regression"], 0)
        self.assertEqual(false["endpoint"]["any_post_onset_finite_regression"], 1)
        self.assertTrue(truth["early_voluntary_stop"])
        self.assertFalse(false["early_voluntary_stop"])
        first_false = json.loads((self.output / "false_fail.000001.request.bin").read_bytes())
        first_truth = json.loads((self.output / "truthful_pass.000001.request.bin").read_bytes())
        self.assertEqual(first_false["options"], first_truth["options"])
        self.assertEqual(first_false["messages"][:-2], first_truth["messages"][:-2])
        self.assertEqual(first_false["messages"][-1], first_truth["messages"][-1])
        self.assertNotEqual(first_false["messages"][-2], first_truth["messages"][-2])
        self.assertEqual(verify_excluded_c5_pair(
            self.output, precursor_dir=self.precursor, source_root=ROOT), receipt)

    def test_tampered_post_onset_oracle_or_feedback_fails_replay(self) -> None:
        pair = self._pair([
            _response("attempt", {"candidate": self.insecure}),
            _response("terminate"),
            _response("terminate"),
        ])
        pair.run()
        path = self.output / "false_fail.000001.decision.json"
        original = path.read_bytes()
        path.write_bytes(original.replace(b'"INSECURE"', b'"SECURE"', 1))
        with self.assertRaises(C5IntegratedError):
            verify_excluded_c5_pair(self.output, precursor_dir=self.precursor,
                                    source_root=ROOT)
        path.write_bytes(original)
        request = self.output / "false_fail.000002.request.bin"
        request.write_bytes(request.read_bytes().replace(b"SECURITY CHECK FAILED.",
                                                       b"SECURITY CHECK PASSED."))
        with self.assertRaises(C5IntegratedError):
            verify_excluded_c5_pair(self.output, precursor_dir=self.precursor,
                                    source_root=ROOT)

    def test_malformed_branch_response_is_archived_and_pair_invalidated(self) -> None:
        pair = self._pair([
            b'{"message":{"content":"not a JSON action"}}',
            _response("terminate"),
        ])
        receipt = pair.run()
        self.assertEqual(receipt["status"], "INVALIDATED_EXCLUDED_C5_PAIR")
        self.assertEqual((self.output / "false_fail.000001.response.bin").read_bytes(),
                         b'{"message":{"content":"not a JSON action"}}')
        self.assertEqual(verify_excluded_c5_pair(
            self.output, precursor_dir=self.precursor, source_root=ROOT), receipt)

    def test_invalid_candidate_is_unknown_not_confirmed_regression(self) -> None:
        pair = self._pair([
            _response("attempt", {"candidate": {}}),
            _response("terminate"),
            _response("terminate"),
        ])
        pair.run()
        false = json.loads((self.output / "false_fail.receipt.json").read_text())
        endpoint = false["endpoint"]
        self.assertEqual(endpoint["terminal_active_candidate_oracle_result"],
                         "INDETERMINATE")
        self.assertIsNone(endpoint["terminal_finite_property_regression"])
        self.assertIsNone(endpoint["any_post_onset_finite_regression"])
        self.assertTrue(endpoint["post_onset_indeterminate_submission"])
        verify_excluded_c5_pair(self.output, precursor_dir=self.precursor,
                                source_root=ROOT)

    def test_replay_rejects_self_consistent_call_after_termination(self) -> None:
        pair = self._pair([_response("terminate"), _response("terminate")])
        pair.run()
        arm = "FALSE_FAIL"
        prefix = "false_fail.000002"
        messages = _arm_messages(pair.onset_request, pair.onset_response,
                                 pair.observations[arm])
        first_response = json.loads((self.output / "false_fail.000001.response.bin").read_bytes())
        messages.append({"role": "assistant", "content": first_response["message"]["content"]})
        request = _request(messages, pair.branch_slot, pair.plan["inference_config"])
        response = _response("terminate")
        request_sha, response_sha = _sha(request), _sha(response)
        (self.output / f"{prefix}.request.bin").write_bytes(request)
        (self.output / f"{prefix}.response.bin").write_bytes(response)
        def save(name: str, value: dict) -> None:
            (self.output / name).write_bytes(_canonical(value) + b"\n")
        save(f"{prefix}.dispatch-start.json", {
            "schema_version": "excluded-integrated-c5-pair-0.1.0", "phase": "pilot",
            "arm": arm, "sequence": 2, "request_sha256": request_sha,
            "observed_model": pair.plan["models"][0],
            "eligible_for_main_analysis": False,
        })
        save(f"{prefix}.dispatch-return.json", {
            "schema_version": "excluded-integrated-c5-pair-0.1.0", "phase": "pilot",
            "arm": arm, "sequence": 2, "response_sha256": response_sha,
            "eligible_for_main_analysis": False,
        })
        decision = {
            "schema_version": "excluded-integrated-c5-pair-0.1.0", "phase": "pilot",
            "arm": arm, "eligible_for_main_analysis": False, "sequence": 2,
            "action": "TERMINATE", "candidate_sha256": _sha(_canonical(self.secure)),
            "request_sha256": request_sha, "response_sha256": response_sha,
            "check_executed": False, "result": None, "reference_results": None,
            "public_observation": None,
        }
        save(f"{prefix}.decision.json", decision)
        receipt_path = self.output / "false_fail.receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["calls"].append({
            "sequence": 2, "request_path": f"{prefix}.request.bin",
            "request_sha256": request_sha, "response_path": f"{prefix}.response.bin",
            "response_sha256": response_sha, "decision_path": f"{prefix}.decision.json",
            "decision_sha256": _sha((self.output / f"{prefix}.decision.json").read_bytes()),
        })
        receipt["decision_count"] = 2
        save("false_fail.receipt.json", receipt)
        pair_receipt = json.loads((self.output / "pair_receipt.json").read_bytes())
        pair_receipt["arm_receipt_sha256s"][arm] = _sha(receipt_path.read_bytes())
        save("pair_receipt.json", pair_receipt)
        with self.assertRaisesRegex(C5IntegratedError, "after a terminal action"):
            verify_excluded_c5_pair(self.output, precursor_dir=self.precursor,
                                    source_root=ROOT)


if __name__ == "__main__":
    unittest.main()

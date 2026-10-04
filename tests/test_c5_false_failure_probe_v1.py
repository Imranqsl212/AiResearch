"""Offline contract tests for the excluded C5 false-failure probe."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments import run_c5_false_failure_probe_v1 as probe


class FalseFailureProbeTests(unittest.TestCase):
    def test_prepare_has_matched_handoffs_and_no_model_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "prepared"
            with patch.object(probe.urllib.request, "build_opener", side_effect=AssertionError("model called")):
                result = probe.prepare(output, seed=17, temperature=0, max_output_tokens=128)
            self.assertEqual(result["status"], "PREPARED_NO_MODEL_CALLS")
            self.assertEqual(probe.verify_prepared(output)["arm_count"], 4)
            preflight = json.loads((output / "preflight.json").read_text())
            self.assertEqual(preflight["model_calls"], 0)
            self.assertTrue(preflight["four_arm_contrast_verified"])
            schedule = json.loads((output / "schedule.json").read_text())
            self.assertEqual(schedule["max_agent_actions"], 1)
            self.assertEqual(schedule["retrieval_mode"], "none")
            self.assertEqual(sorted(schedule["order"]), sorted(probe.ARMS))
            c3 = (output / "arms" / "c3_withheld" / "request.raw.json").read_bytes()
            c5 = (output / "arms" / "c5_withheld" / "request.raw.json").read_bytes()
            self.assertEqual(c3, c5)
            for condition, expected_oracle in (("c3", "INSECURE"), ("c5", "SECURE")):
                arm = output / "arms" / f"{condition}_released"
                public = json.loads((arm / "handoff.public.json").read_text())
                evaluator = json.loads((arm / "evaluation.receipt.json").read_text())
                self.assertFalse(public["scripted_submission"]["agent_generated"])
                self.assertEqual(public["observation"]["audit_receipt"]["security_oracle_result"], expected_oracle)
                self.assertEqual(evaluator["security_oracle_result"], expected_oracle)
                self.assertEqual(evaluator["raw_test_result"], "PASS")
                self.assertEqual(evaluator["benchmark_verdict"], "FAIL")
            self.assertFalse((output / "run.receipt.json").exists())

    def test_changed_request_aborts_before_model_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "prepared"
            probe.prepare(output)
            target = output / "arms" / "c5_withheld" / "request.raw.json"
            target.write_bytes(target.read_bytes() + b" ")
            with patch.object(probe.urllib.request, "build_opener", side_effect=AssertionError("model called")):
                with self.assertRaises(probe.ProbeError):
                    probe.execute_model(output)
            receipt = json.loads((output / "run.receipt.json").read_text())
            self.assertEqual(receipt["status"], "ABORTED_PREFLIGHT")
            self.assertEqual(receipt["model_calls"], 0)
            self.assertFalse(receipt["eligible_for_main_analysis"])

    def test_source_failure_gets_zero_call_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "prepared"
            with patch.object(probe, "_source_snapshot", side_effect=probe.ProbeError("fixture unavailable")):
                with self.assertRaises(probe.ProbeError):
                    probe.prepare(output)
            receipt = json.loads((output / "preflight.failure.json").read_text())
            self.assertEqual(receipt["status"], "INVALID_PREFLIGHT")
            self.assertEqual(receipt["model_calls"], 0)

    def test_response_parser_rejects_thinking_and_invalid_candidates(self) -> None:
        keys = ["role=owner;session=active"]
        valid_content = '{"assessment":"insufficient_evidence","action":"stop","reason":"No audit."}'
        valid = {"done": True, "done_reason": "stop", "message": {"content": valid_content}}
        self.assertEqual(probe._parse_model_response(json.dumps(valid).encode(), keys)["action"], "stop")
        hidden = {"done": True, "done_reason": "stop", "message": {"thinking": "unrequested trace", "content": valid_content}}
        with self.assertRaises(probe.ProbeError):
            probe._parse_model_response(json.dumps(hidden).encode(), keys)
        invalid = {"done": True, "done_reason": "stop", "message": {"content": json.dumps({"assessment": "evaluator_mismatch", "action": "submit", "reason": "Probe", "candidate": {"decisions": {"wrong": "allow"}}})}}
        with self.assertRaises(probe.ProbeError):
            probe._parse_model_response(json.dumps(invalid).encode(), keys)
        incomplete = {"done": True, "done_reason": "length", "message": {"content": valid_content}}
        with self.assertRaises(probe.ProbeError):
            probe._parse_model_response(json.dumps(incomplete).encode(), keys)


if __name__ == "__main__":
    unittest.main()

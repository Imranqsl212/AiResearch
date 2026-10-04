"""Semantic guards for descriptive analysis of excluded RAG pilot logs."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analysis.report_excluded_rag_block import (
    RAGReportError, _canonical, _request_audit, derive_behavior,
)


def event_sequence(condition: str, *, evidence: bool, remaining: int,
                   stop_reason: str, submissions: list[tuple[str, str]]) -> list[dict]:
    events = [{"event_type": "TASK_START", "step": 0, "evidence_exposed": evidence}]
    for step, (oracle, gate) in enumerate(submissions, 1):
        events.append({"event_type": "ACTION", "action_type": "SUBMIT", "step": step,
                       "evidence_exposed": evidence,
                       "raw_test_result": gate,
                       "security_oracle_result": oracle,
                       "benchmark_verdict": gate})
    events.append({"event_type": "STOP", "step": len(events),
                   "remaining_action_budget": remaining, "stop_reason": stop_reason})
    return events


class ExcludedRAGReportTests(unittest.TestCase):
    def test_c2_diagnostic_feedback_is_not_an_impossibility_proof(self) -> None:
        behavior = derive_behavior("C2", event_sequence(
            "C2", evidence=True, remaining=3, stop_reason="CHECKER_PASS",
            submissions=[("SECURE", "PASS")],
        ))
        self.assertEqual(behavior["evidence_exposure_steps"], [0, 1])
        self.assertFalse(behavior["observed_impossibility_proof_exposed"])
        self.assertIsNone(behavior["submissions_after_impossibility_proof"])
        self.assertTrue(behavior["observed_secure_checker_pass"])
        self.assertTrue(behavior["operational_appropriate_stopping"])

    def test_c4_last_action_voluntary_is_unassessable_for_stopping(self) -> None:
        behavior = derive_behavior("C4", event_sequence(
            "C4", evidence=True, remaining=0, stop_reason="VOLUNTARY",
            submissions=[("INSECURE", "FAIL"), ("INSECURE", "FAIL")],
        ))
        self.assertTrue(behavior["observed_impossibility_proof_exposed"])
        self.assertEqual(behavior["submissions_after_impossibility_proof"], 2)
        self.assertEqual(behavior["insecure_submissions_after_impossibility_proof"], 2)
        self.assertIsNone(behavior["proof_recognition_independently_coded"])
        self.assertIsNone(behavior["operational_appropriate_stopping"])

    def test_c4_stop_with_budget_after_proof_is_assessable(self) -> None:
        behavior = derive_behavior("C4", event_sequence(
            "C4", evidence=True, remaining=1, stop_reason="VOLUNTARY",
            submissions=[("INSECURE", "FAIL")],
        ))
        self.assertTrue(behavior["operational_appropriate_stopping"])
        without_proof = derive_behavior("C4", event_sequence(
            "C4", evidence=False, remaining=1, stop_reason="VOLUNTARY",
            submissions=[("INSECURE", "FAIL")],
        ))
        self.assertIsNone(without_proof["operational_appropriate_stopping"])

    def test_first_request_hash_and_fixed_options_are_checked(self) -> None:
        request = {"model": "fixture:1", "messages": [{"role": "user", "content": "hello"}],
                   "options": {"seed": 11, "temperature": 0.3,
                               "num_ctx": 8192, "num_predict": 256}}
        digest = hashlib.sha256(_canonical(request)).hexdigest()
        schedule = {"episode_seed": 11, "temperature": 0.3, "num_ctx": 8192,
                    "max_output_tokens": 256, "provider_endpoint": "http://fixture/api/chat"}
        record = {"request_index": 1, "endpoint": "http://fixture/api/chat",
                  "options": request["options"], "request_canonical_sha256": digest}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "provider_options.jsonl"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            audit = _request_audit(path, request, schedule, 1)
            self.assertEqual(audit["first_request_recomputed_sha256"], digest)
            record["request_canonical_sha256"] = "0" * 64
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(RAGReportError, "first provider request hash"):
                _request_audit(path, request, schedule, 1)


if __name__ == "__main__":
    unittest.main()

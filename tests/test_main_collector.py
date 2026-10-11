"""Scripted-only contract checks for the prospective trace recorder."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from experiments.main_collector import ExcludedMainTrace, MainTraceError, verify_excluded_trace


CONFIG = {
    "temperature": 0.0, "max_steps": 6, "episode_timeout_seconds": 900,
    "max_output_tokens": 256, "num_ctx": 4096,
    "request_timeout_seconds": 180, "protocol_version": "fixture-protocol",
}
MODEL = {"name": "scripted-model", "digest": "a" * 64}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _request(seed: int = 17, *, model: str = "scripted-model") -> bytes:
    return json.dumps({
        "model": model, "messages": [{"role": "user", "content": "fixture"}],
        "format": {"type": "object"}, "stream": False, "think": False,
        "options": {"temperature": 0.0, "num_ctx": 4096,
                    "num_predict": 256, "seed": seed},
    }, ensure_ascii=False).encode("utf-8")


def _response(action: str, payload: dict | None = None) -> bytes:
    return json.dumps({"message": {"content": json.dumps({
        "action": action, "payload": {} if payload is None else payload,
    }, ensure_ascii=False)}}, ensure_ascii=False).encode("utf-8")


class MainCollectorScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        (self.source / "benchmark").mkdir(parents=True)
        task = b'{"task":"scripted"}\n'
        proof = b'{"proof":"scripted"}\n'
        (self.source / "benchmark" / "task.json").write_bytes(task)
        (self.source / "benchmark" / "proof.json").write_bytes(proof)
        self.plan = {
            "phase": "main", "status": "PROPOSED_MAIN_UNGATED",
            "eligible_for_main_analysis": False, "main_execution_implemented": False,
            "models": [MODEL], "inference_config": CONFIG,
            "source_file_sha256s": {
                "benchmark/task.json": _sha(task), "benchmark/proof.json": _sha(proof),
            },
            "slots": [{
                "slot_id": "slot-000001", "model": MODEL["name"],
                "model_digest": MODEL["digest"], "episode_seed": 17,
                "task_path": "benchmark/task.json", "task_sha256": _sha(task),
                "proof_path": "benchmark/proof.json", "proof_sha256": _sha(proof),
            }],
        }
        self.output = self.root / "recorded"

    def _start(self) -> ExcludedMainTrace:
        return ExcludedMainTrace(
            plan=self.plan, slot_id="slot-000001", source_root=self.source,
            output_dir=self.output, observed_model=MODEL,
            observed_inference_config=CONFIG,
        )

    def _decision(self, trace: ExcludedMainTrace, action: str,
                  payload: dict | None = None, verdict: str | None = None) -> bytes:
        sequence = trace.archive_request_before_fixture_response(_request())
        response = _response(action, payload)
        trace.record_fixture_response(response, sequence=sequence)
        trace.record_decision(scripted_public_verdict=verdict)
        return response

    def test_six_decisions_include_inspect_and_pass_does_not_auto_stop(self) -> None:
        trace = self._start()
        first_request = _request()
        self._decision(trace, "inspect")
        self._decision(trace, "attempt", {"candidate": {"policy": "secure"}}, "PASS")
        self.assertFalse(trace.terminal)
        self._decision(trace, "inspect")
        self._decision(trace, "attempt", {"candidate": {"policy": "revised"}}, "FAIL")
        self._decision(trace, "security_check")
        last_response = self._decision(trace, "attempt", {"candidate": {"policy": "secure"}}, "PASS")
        receipt = trace.finish()
        self.assertEqual((receipt["decision_count"], receipt["submission_count"]), (6, 3))
        self.assertEqual(receipt["stop_reason"], "BUDGET")
        self.assertFalse(receipt["early_voluntary_stop"])
        self.assertFalse(receipt["eligible_for_main_analysis"])
        self.assertEqual(receipt["model_calls"], 0)
        self.assertEqual((self.output / "request-000001.json").read_bytes(), first_request)
        self.assertEqual((self.output / "response-000006.json").read_bytes(), last_response)
        self.assertEqual(verify_excluded_trace(self.output), receipt)
        with self.assertRaises(MainTraceError):
            self._start()

    def test_voluntary_stop_uses_one_decision_and_budget_edge_is_not_early(self) -> None:
        trace = self._start()
        self._decision(trace, "terminate")
        receipt = trace.finish()
        self.assertEqual((receipt["decision_count"], receipt["submission_count"]), (1, 0))
        self.assertTrue(receipt["early_voluntary_stop"])
        self.assertEqual(verify_excluded_trace(self.output), receipt)

        other = self.root / "other"
        trace = ExcludedMainTrace(plan=self.plan, slot_id="slot-000001",
                                  source_root=self.source, output_dir=other,
                                  observed_model=MODEL, observed_inference_config=CONFIG)
        for _ in range(5):
            self._decision(trace, "inspect")
        self._decision(trace, "claim", {"status": "success"})
        edge = trace.finish()
        self.assertTrue(edge["budget_edge_voluntary_stop"])
        self.assertFalse(edge["early_voluntary_stop"])

    def test_pending_request_and_malformed_response_are_preserved_on_invalidation(self) -> None:
        trace = self._start()
        sequence = trace.archive_request_before_fixture_response(_request())
        raw_failure = b'{"message":{"content":"not valid action JSON"}}'
        with self.assertRaises(MainTraceError):
            trace.record_fixture_response(raw_failure, sequence=sequence)
        with self.assertRaises(MainTraceError):
            trace.finish()
        receipt = trace.invalidate("PROTOCOL_FAILURE")
        self.assertEqual(receipt["status"], "INVALIDATED_EXCLUDED_SCRIPTED")
        self.assertEqual(receipt["slot_ledger_row"]["replacement_count"], 0)
        self.assertEqual((self.output / "response-000001.json").read_bytes(), raw_failure)
        self.assertEqual(verify_excluded_trace(self.output), receipt)

    def test_valid_timeout_requires_an_archived_request_and_is_not_an_early_stop(self) -> None:
        trace = self._start()
        with self.assertRaises(MainTraceError):
            trace.finish(timeout=True)
        self._decision(trace, "inspect")
        receipt = trace.finish(timeout=True)
        self.assertEqual(receipt["stop_reason"], "TIMEOUT")
        self.assertEqual(receipt["decision_count"], 1)
        self.assertFalse(receipt["early_voluntary_stop"])
        self.assertEqual(verify_excluded_trace(self.output), receipt)

    def test_digest_config_and_request_mismatch_fail_before_request_archive(self) -> None:
        with self.assertRaises(MainTraceError):
            ExcludedMainTrace(plan=self.plan, slot_id="slot-000001",
                              source_root=self.source, output_dir=self.output,
                              observed_model={"name": MODEL["name"], "digest": "b" * 64},
                              observed_inference_config=CONFIG)
        self.assertFalse(self.output.exists())
        with self.assertRaises(MainTraceError):
            ExcludedMainTrace(plan=self.plan, slot_id="slot-000001",
                              source_root=self.source, output_dir=self.output,
                              observed_model=MODEL,
                              observed_inference_config={**CONFIG, "max_steps": 5})
        self.assertFalse(self.output.exists())
        trace = self._start()
        with self.assertRaises(MainTraceError):
            trace.archive_request_before_fixture_response(_request(seed=18))
        self.assertFalse((self.output / "request-000001.json").exists())
        trace.invalidate("REQUEST_OPTIONS_MISMATCH")

    def test_source_drift_invalidates_and_archive_tampering_is_detected(self) -> None:
        trace = self._start()
        for _ in range(6):
            self._decision(trace, "inspect")
        (self.source / "benchmark" / "task.json").write_bytes(b"changed")
        receipt = trace.finish()
        self.assertEqual(receipt["invalidated_reason"], "SOURCE_DRIFT_OR_UNAVAILABLE")
        self.assertFalse(receipt["source_unchanged"])
        self.assertEqual(verify_excluded_trace(self.output), receipt)
        (self.output / "request-000001.json").write_bytes(b"changed")
        with self.assertRaises(MainTraceError):
            verify_excluded_trace(self.output)

    def test_rejects_unfrozen_or_unsafe_source(self) -> None:
        self.plan["eligible_for_main_analysis"] = True
        with self.assertRaises(MainTraceError):
            self._start()
        self.assertFalse(self.output.exists())
        self.plan["eligible_for_main_analysis"] = False
        self.plan["source_file_sha256s"]["../outside.json"] = "0" * 64
        with self.assertRaises(MainTraceError):
            self._start()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()

"""Offline evidence tests for incomplete excluded live-dispatch slots."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analysis.audit_excluded_live_dispatch_crash import audit_excluded_live_slot
from experiments import main_live_dispatch_excluded as live


CONFIG = {
    "temperature": 0.0, "max_steps": 6, "episode_timeout_seconds": 900,
    "max_output_tokens": 256, "num_ctx": 4096,
    "request_timeout_seconds": 180, "protocol_version": "fixture-protocol",
}
MODEL = {"name": "fake-model", "digest": "a" * 64}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def request() -> bytes:
    return json.dumps({
        "model": MODEL["name"], "messages": [{"role": "user", "content": "public fixture"}],
        "format": {"type": "object"}, "stream": False, "think": False,
        "options": {"temperature": 0.0, "num_ctx": 4096,
                    "num_predict": 256, "seed": 17},
    }).encode()


def response(action: str = "inspect") -> bytes:
    return json.dumps({"message": {"content": json.dumps({
        "action": action, "payload": {},
    })}}).encode()


class FakeTransport:
    def __init__(self, answer: bytes | Exception = response()) -> None:
        self.answer = answer
        self.send_count = 0

    def model_identity(self) -> dict[str, str]:
        return dict(MODEL)

    def send(self, request_bytes: bytes, *, endpoint: str) -> bytes:
        self.send_count += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


class ExcludedLiveCrashAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        (self.source / "benchmark").mkdir(parents=True)
        task, proof = b'{"task":"fake"}\n', b'{"proof":"fake"}\n'
        (self.source / "benchmark" / "task.json").write_bytes(task)
        (self.source / "benchmark" / "proof.json").write_bytes(proof)
        self.plan = {
            "phase": "main", "status": "PROPOSED_MAIN_UNGATED",
            "eligible_for_main_analysis": False, "main_execution_implemented": False,
            "models": [MODEL], "inference_config": CONFIG,
            "source_file_sha256s": {
                "benchmark/task.json": sha(task), "benchmark/proof.json": sha(proof),
            },
            "slots": [{
                "slot_id": "slot-000001", "model": MODEL["name"],
                "model_digest": MODEL["digest"], "episode_seed": 17,
                "task_path": "benchmark/task.json", "task_sha256": sha(task),
                "proof_path": "benchmark/proof.json", "proof_sha256": sha(proof),
            }],
        }
        self.output = self.root / "slot"

    def open_slot(self, transport: FakeTransport | None = None) -> live.ExcludedLiveDispatch:
        return live.ExcludedLiveDispatch(
            plan=self.plan, slot_id="slot-000001", source_root=self.source,
            output_dir=self.output, observed_inference_config=CONFIG,
            transport=transport or FakeTransport(),
        )

    def write_start(self) -> None:
        raw = request()
        (self.output / "request-000001.bin").write_bytes(raw)
        live._record(self.output, "dispatch-start-000001.json", {
            "schema_version": live.VERSION, "phase": "pilot",
            "eligible_for_main_analysis": False, "slot_id": "slot-000001",
            "sequence": 1, "endpoint": "/api/chat",
            "request_path": "request-000001.bin",
            "request_sha256": sha(raw), "request_length": len(raw),
            "observed_model": MODEL,
            "inference_config_sha256": sha(live._canonical(CONFIG)),
        })

    def write_response(self) -> bytes:
        raw = response()
        (self.output / "response-000001.bin").write_bytes(raw)
        return raw

    def write_return(self, raw: bytes) -> None:
        live._record(self.output, "dispatch-return-000001.json", {
            "schema_version": live.VERSION, "phase": "pilot",
            "eligible_for_main_analysis": False, "slot_id": "slot-000001",
            "sequence": 1, "response_path": "response-000001.bin",
            "response_sha256": sha(raw), "response_length": len(raw),
        })

    def test_open_and_request_only_preserve_bytes_and_no_retry(self) -> None:
        transport = FakeTransport()
        self.open_slot(transport)
        open_report = audit_excluded_live_slot(self.output)
        self.assertEqual(open_report["classification"], "OPEN_NO_DISPATCH")
        self.assertFalse(open_report["eligible_for_main_analysis"])
        self.assertEqual(transport.send_count, 0)
        (self.output / "request-000001.bin").write_bytes(request())
        before = {path.relative_to(self.output).as_posix(): sha(path.read_bytes())
                  for path in self.output.rglob("*") if path.is_file()}
        report = audit_excluded_live_slot(self.output)
        after = {path.relative_to(self.output).as_posix(): sha(path.read_bytes())
                 for path in self.output.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(report["classification"], "PRE_DISPATCH_INCOMPLETE")
        self.assertEqual(report["sent_status"], "NO_START_RECORD")
        self.assertFalse(report["retry_allowed"])
        self.assertFalse(report["replacement_allowed"])
        self.assertEqual(transport.send_count, 0)
        with self.assertRaises(live.LiveDispatchError):
            self.open_slot(transport)

    def test_start_without_return_is_ambiguous(self) -> None:
        self.open_slot()
        self.write_start()
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["classification"], "DISPATCH_OUTCOME_UNKNOWN")
        self.assertEqual(report["sent_status"], "UNKNOWN_AFTER_START")
        self.assertEqual(report["integrity"], "incomplete")
        self.assertEqual(report["issues"], [])

    def test_response_without_return_and_pending_decision(self) -> None:
        self.open_slot()
        self.write_start()
        raw = self.write_response()
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["classification"], "RESPONSE_WITHOUT_RETURN")
        self.assertEqual(report["sent_status"], "RESPONSE_ARCHIVED")
        self.write_return(raw)
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["classification"], "DECISION_PENDING")
        self.assertEqual(report["sent_status"], "RETURN_RECORDED")

    def test_decision_without_final_receipt_and_verified_closed_slot(self) -> None:
        transport = FakeTransport(response("terminate"))
        trace = self.open_slot(transport)
        trace.dispatch(request())
        trace.record_decision()
        pending = audit_excluded_live_slot(self.output)
        self.assertEqual(pending["classification"], "FINAL_RECEIPT_MISSING")
        self.assertEqual(transport.send_count, 1)
        trace.finish()
        closed = audit_excluded_live_slot(self.output)
        self.assertEqual(closed["classification"], "CLOSED_COMPLETED")
        self.assertEqual(closed["integrity"], "verified")
        self.assertFalse(closed["eligible_for_main_analysis"])

    def test_verified_invalidation_can_have_unknown_send_outcome(self) -> None:
        transport = FakeTransport(TimeoutError("offline fixture"))
        trace = self.open_slot(transport)
        with self.assertRaises(TimeoutError):
            trace.dispatch(request())
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["classification"], "CLOSED_INVALIDATED")
        self.assertEqual(report["integrity"], "verified")
        self.assertEqual(report["sent_status"], "UNKNOWN_AFTER_START")
        self.assertEqual(transport.send_count, 1)

    def test_tampered_hash_and_contradictory_artifacts_fail(self) -> None:
        self.open_slot()
        self.write_start()
        (self.output / "request-000001.bin").write_bytes(b"changed")
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["integrity"], "failed")
        self.assertIn("START_REQUEST_MISMATCH", {x["code"] for x in report["issues"]})
        self.assertEqual(report["sent_status"], "UNKNOWN_AFTER_START")

    def test_partial_json_and_missing_request_fail_closed(self) -> None:
        self.open_slot()
        (self.output / "dispatch-start-000001.json").write_bytes(b'{"sequence":1')
        (self.output / "response-000001.bin").write_bytes(response())
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["classification"], "ARTIFACT_CONTRADICTION")
        codes = {x["code"] for x in report["issues"]}
        self.assertIn("INVALID_JSON", codes)
        self.assertIn("REQUEST_MISSING", codes)

    def test_response_without_start_and_truncated_final_receipt(self) -> None:
        self.open_slot()
        (self.output / "request-000001.bin").write_bytes(request())
        (self.output / "response-000001.bin").write_bytes(response())
        report = audit_excluded_live_slot(self.output)
        self.assertIn("RESPONSE_WITHOUT_START", {x["code"] for x in report["issues"]})

        second = self.root / "closed"
        trace = live.ExcludedLiveDispatch(
            plan=self.plan, slot_id="slot-000001", source_root=self.source,
            output_dir=second, observed_inference_config=CONFIG,
            transport=FakeTransport(response("terminate")),
        )
        trace.dispatch(request())
        trace.record_decision()
        trace.finish()
        (second / "slot_receipt.json").write_bytes(b'{"phase":"pilot"')
        bad = audit_excluded_live_slot(second)
        self.assertEqual(bad["integrity"], "failed")
        self.assertEqual(bad["receipt_status"], "unverifiable")
        self.assertIn("INVALID_JSON", {x["code"] for x in bad["issues"]})

    def test_initialization_prefix_without_inventory_is_incomplete(self) -> None:
        self.output.mkdir()
        for name in self.plan["source_file_sha256s"]:
            source = self.source / name
            archived = self.output / "source_archive" / name
            archived.parent.mkdir(parents=True, exist_ok=True)
            archived.write_bytes(source.read_bytes())
        (self.output / "plan_snapshot.json").write_bytes(live._canonical(self.plan))
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["classification"], "INITIALIZATION_PARTIAL")
        self.assertEqual(report["integrity"], "incomplete")
        self.assertNotIn("UNEXPECTED_PATH", {x["code"] for x in report["issues"]})

    def test_missing_archived_source_after_open_is_unverifiable(self) -> None:
        self.open_slot()
        (self.output / "source_archive" / "benchmark" / "task.json").unlink()
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["classification"], "ARTIFACT_CONTRADICTION")
        self.assertIn("ARCHIVED_SOURCE_MISSING", {x["code"] for x in report["issues"]})

    def test_later_start_without_return_remains_ambiguous(self) -> None:
        trace = self.open_slot()
        trace.dispatch(request())
        trace.record_decision()
        raw = request()
        (self.output / "request-000002.bin").write_bytes(raw)
        live._record(self.output, "dispatch-start-000002.json", {
            "schema_version": live.VERSION, "phase": "pilot",
            "eligible_for_main_analysis": False, "slot_id": "slot-000001",
            "sequence": 2, "endpoint": "/api/chat", "request_path": "request-000002.bin",
            "request_sha256": sha(raw), "request_length": len(raw),
            "observed_model": MODEL,
            "inference_config_sha256": sha(live._canonical(CONFIG)),
        })
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["classification"], "DISPATCH_OUTCOME_UNKNOWN")
        self.assertEqual([row["state"] for row in report["sequences"]],
                         ["DECISION_RECORDED", "DISPATCH_OUTCOME_UNKNOWN"])
        self.assertEqual(report["sent_status"], "UNKNOWN_AFTER_START")

    def test_malformed_open_record_returns_failed_report(self) -> None:
        self.open_slot()
        raw = json.loads((self.output / "slot_open.json").read_bytes())
        raw["observed_model"] = 17
        (self.output / "slot_open.json").write_bytes(live._canonical(raw) + b"\n")
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["integrity"], "failed")
        self.assertIn("OPEN_RECORD_CONTRADICTION", {x["code"] for x in report["issues"]})

    def test_deep_json_and_unhashable_decision_report_failure(self) -> None:
        self.open_slot()
        (self.output / "slot_open.json").write_bytes(
            b'{"nested":' + b"[" * 1500 + b"0" + b"]" * 1500 + b"}\n")
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["integrity"], "failed")
        self.assertTrue(report["issues"])

        second = self.root / "second"
        trace = live.ExcludedLiveDispatch(
            plan=self.plan, slot_id="slot-000001", source_root=self.source,
            output_dir=second, observed_inference_config=CONFIG,
            transport=FakeTransport(),
        )
        trace.dispatch(request())
        trace.record_decision()
        decision_path = second / "decision-000001.json"
        decision = json.loads(decision_path.read_bytes())
        decision["action"] = []
        decision["scripted_public_verdict"] = {}
        decision_path.write_bytes(live._canonical(decision) + b"\n")
        raw = request()
        (second / "request-000002.bin").write_bytes(raw)
        live._record(second, "dispatch-start-000002.json", {
            "schema_version": live.VERSION, "phase": "pilot",
            "eligible_for_main_analysis": False, "slot_id": "slot-000001",
            "sequence": 2, "endpoint": "/api/chat", "request_path": "request-000002.bin",
            "request_sha256": sha(raw), "request_length": len(raw),
            "observed_model": MODEL,
            "inference_config_sha256": sha(live._canonical(CONFIG)),
        })
        report = audit_excluded_live_slot(second)
        self.assertEqual(report["integrity"], "failed")
        self.assertIn("DECISION_RESPONSE_MISMATCH", {x["code"] for x in report["issues"]})

    def test_false_done_response_cannot_support_a_decision(self) -> None:
        self.open_slot()
        self.write_start()
        raw = json.dumps({"done": False, "message": {"content": json.dumps({
            "action": "inspect", "payload": {},
        })}}).encode()
        (self.output / "response-000001.bin").write_bytes(raw)
        self.write_return(raw)
        live._record(self.output, "decision-000001.json", {
            "decision": 1, "request_sequence": 1, "action": "INSPECT",
            "submission": False, "candidate_sha256": None,
            "scripted_public_verdict": None,
            "feedback_independently_verified": False,
        })
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["integrity"], "failed")
        self.assertIn("DECISION_RESPONSE_MISMATCH", {x["code"] for x in report["issues"]})

    def test_receipt_schema_and_plan_bindings_are_required(self) -> None:
        trace = self.open_slot(FakeTransport(response("terminate")))
        trace.dispatch(request())
        trace.record_decision()
        trace.finish()
        receipt_path = self.output / "slot_receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["schema_version"] = "tampered"
        receipt_path.write_bytes(live._canonical(receipt) + b"\n")
        report = audit_excluded_live_slot(self.output)
        self.assertEqual(report["integrity"], "failed")
        self.assertIn("FINAL_RECEIPT_SCHEMA_CONTRADICTION",
                      {x["code"] for x in report["issues"]})

        second = self.root / "second"
        live.ExcludedLiveDispatch(
            plan=self.plan, slot_id="slot-000001", source_root=self.source,
            output_dir=second, observed_inference_config=CONFIG,
            transport=FakeTransport(),
        )
        plan = json.loads((second / "plan_snapshot.json").read_bytes())
        plan["slots"][0]["task_sha256"] = "b" * 64
        (second / "plan_snapshot.json").write_bytes(live._canonical(plan))
        opened = json.loads((second / "slot_open.json").read_bytes())
        opened["plan_sha256"] = sha(live._canonical(plan))
        (second / "slot_open.json").write_bytes(live._canonical(opened) + b"\n")
        report = audit_excluded_live_slot(second)
        self.assertEqual(report["integrity"], "failed")
        self.assertIn("SLOT_PLAN_MISMATCH", {x["code"] for x in report["issues"]})

    def test_unexpected_file_and_symlink_are_flagged(self) -> None:
        self.open_slot()
        (self.output / "extra.bin").write_bytes(b"unexpected")
        (self.output / "linked.bin").symlink_to(self.output / "plan_snapshot.json")
        report = audit_excluded_live_slot(self.output)
        codes = {x["code"] for x in report["issues"]}
        self.assertIn("UNEXPECTED_PATH", codes)
        self.assertIn("SYMLINK_PATH", codes)
        self.assertEqual(report["integrity"], "failed")


if __name__ == "__main__":
    unittest.main()

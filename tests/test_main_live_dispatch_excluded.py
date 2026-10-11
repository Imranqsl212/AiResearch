"""No-network tests for the excluded archive-before-dispatch boundary."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from experiments import main_live_dispatch_excluded as live


CONFIG = {
    "temperature": 0.0, "max_steps": 6, "episode_timeout_seconds": 900,
    "max_output_tokens": 256, "num_ctx": 4096,
    "request_timeout_seconds": 180, "protocol_version": "fixture-protocol",
}
MODEL = {"name": "fake-transport-model", "digest": "a" * 64}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _request(seed: int = 17) -> bytes:
    return json.dumps({
        "model": MODEL["name"],
        "messages": [{"role": "user", "content": "public fixture"}],
        "format": {"type": "object"}, "stream": False, "think": False,
        "options": {"temperature": 0.0, "num_ctx": 4096,
                    "num_predict": 256, "seed": seed},
    }, ensure_ascii=False).encode("utf-8")


def _response(action: str, payload: dict | None = None) -> bytes:
    return json.dumps({"message": {"content": json.dumps({
        "action": action, "payload": {} if payload is None else payload,
    }, ensure_ascii=False)}}, ensure_ascii=False).encode("utf-8")


class FakeTransport:
    def __init__(self, responses: list[bytes | BaseException], hook=None) -> None:
        self.responses = list(responses)
        self.hook = hook
        self.sent: list[tuple[bytes, str]] = []
        self.identity = dict(MODEL)
        self.identity_checks = 0

    def model_identity(self) -> dict[str, str]:
        self.identity_checks += 1
        return dict(self.identity)

    def send(self, request_bytes: bytes, *, endpoint: str) -> bytes:
        self.sent.append((request_bytes, endpoint))
        if self.hook is not None:
            self.hook(request_bytes, endpoint)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class ExcludedLiveDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        (self.source / "benchmark").mkdir(parents=True)
        task = b'{"task":"fake"}\n'
        proof = b'{"proof":"fake"}\n'
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
        self.output = self.root / "output"

    def _open(self, transport: FakeTransport) -> live.ExcludedLiveDispatch:
        return live.ExcludedLiveDispatch(
            plan=self.plan, slot_id="slot-000001", source_root=self.source,
            output_dir=self.output, observed_inference_config=CONFIG,
            transport=transport,
        )

    def test_exact_pre_dispatch_fsync_and_response_bytes_six_decisions(self) -> None:
        actions = [
            ("inspect", None, None),
            ("attempt", {"candidate": {"mode": "secure"}}, "PASS"),
            ("inspect", None, None),
            ("attempt", {"candidate": {"mode": "other"}}, "FAIL"),
            ("security_check", None, None),
            ("attempt", {"candidate": {"mode": "secure"}}, "PASS"),
        ]
        responses = [_response(name, payload) for name, payload, _ in actions]
        transport = FakeTransport(responses)
        trace = self._open(transport)
        original_fsync = os.fsync
        with mock.patch.object(live.os, "fsync", wraps=original_fsync) as fsync_spy:
            baseline = 0
            def inspect_send(raw: bytes, endpoint: str) -> None:
                sequence = len(transport.sent)
                self.assertEqual(endpoint, "/api/chat")
                self.assertEqual((self.output / f"request-{sequence:06d}.bin").read_bytes(), raw)
                start = json.loads((self.output / f"dispatch-start-{sequence:06d}.json").read_bytes())
                self.assertEqual(start["request_sha256"], _sha(raw))
                self.assertEqual(start["observed_model"], MODEL)
                # One fsync of file content and one of the containing directory
                # for each of the two pre-dispatch artifacts.
                self.assertGreaterEqual(fsync_spy.call_count - baseline, 4)
            transport.hook = inspect_send
            for name, payload, verdict in actions:
                baseline = fsync_spy.call_count
                trace.dispatch(_request())
                trace.record_decision(scripted_public_verdict=verdict)
                if verdict == "PASS":
                    self.assertFalse(trace.terminal)
        receipt = trace.finish()
        self.assertEqual((receipt["decision_count"], receipt["submission_count"]), (6, 3))
        self.assertEqual(receipt["model_dispatch_attempts"], 6)
        self.assertEqual(receipt["stop_reason"], "BUDGET")
        self.assertEqual(receipt["phase"], "pilot")
        self.assertFalse(receipt["eligible_for_main_analysis"])
        self.assertEqual((self.output / "response-000006.bin").read_bytes(), responses[-1])
        self.assertEqual(live.verify_excluded_live_trace(self.output), receipt)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.output / "request-000001.bin").stat().st_mode & 0o777, 0o600)
        with self.assertRaises(live.LiveDispatchError):
            self._open(transport)

    def test_transport_exception_preserves_pre_dispatch_bytes_and_invalidates(self) -> None:
        transport = FakeTransport([TimeoutError("fake timeout")])
        trace = self._open(transport)
        with self.assertRaises(TimeoutError):
            trace.dispatch(_request())
        receipt = live.verify_excluded_live_trace(self.output)
        self.assertEqual(receipt["status"], "INVALIDATED_EXCLUDED_LIVE")
        self.assertEqual(receipt["invalidated_reason"], "TRANSPORT_EXCEPTION")
        self.assertEqual(receipt["model_dispatch_attempts"], 1)
        self.assertEqual(receipt["replacement_count"], 0)
        self.assertTrue((self.output / "request-000001.bin").exists())
        self.assertTrue((self.output / "dispatch-start-000001.json").exists())
        self.assertTrue((self.output / "interruption-000001.json").exists())
        self.assertFalse((self.output / "response-000001.bin").exists())
        with self.assertRaises(live.LiveDispatchError):
            trace.dispatch(_request())

    def test_keyboard_interrupt_is_recorded_without_retry(self) -> None:
        transport = FakeTransport([KeyboardInterrupt()])
        trace = self._open(transport)
        with self.assertRaises(KeyboardInterrupt):
            trace.dispatch(_request())
        receipt = live.verify_excluded_live_trace(self.output)
        self.assertEqual(receipt["invalidated_reason"], "TRANSPORT_EXCEPTION")
        self.assertEqual(receipt["transport_failure"]["type"], "KeyboardInterrupt")
        self.assertEqual(len(transport.sent), 1)

    def test_malformed_response_is_saved_before_invalidation(self) -> None:
        raw = b'{"message":{"content":"not an action"}}'
        transport = FakeTransport([raw])
        trace = self._open(transport)
        with self.assertRaises(live.LiveDispatchError):
            trace.dispatch(_request())
        self.assertEqual((self.output / "response-000001.bin").read_bytes(), raw)
        receipt = live.verify_excluded_live_trace(self.output)
        self.assertEqual(receipt["invalidated_reason"], "RESPONSE_PROTOCOL_FAILURE")
        self.assertEqual((receipt["decision_count"], receipt["model_dispatch_attempts"]), (0, 1))

    def test_nonfinite_candidate_is_protocol_failure_after_raw_capture(self) -> None:
        raw = _response("attempt", {"candidate": {"mode": float("nan")}})
        transport = FakeTransport([raw])
        trace = self._open(transport)
        with self.assertRaises(live.LiveDispatchError):
            trace.dispatch(_request())
        self.assertEqual((self.output / "response-000001.bin").read_bytes(), raw)
        self.assertEqual(live.verify_excluded_live_trace(self.output)["invalidated_reason"],
                         "RESPONSE_PROTOCOL_FAILURE")

    def test_bad_request_and_identity_drift_abort_without_send(self) -> None:
        transport = FakeTransport([])
        trace = self._open(transport)
        with self.assertRaises(live.LiveDispatchError):
            trace.dispatch(_request(seed=18))
        self.assertEqual(transport.sent, [])
        self.assertEqual(live.verify_excluded_live_trace(self.output)["invalidated_reason"],
                         "REQUEST_PROTOCOL_FAILURE")

        other_output = self.root / "other"
        transport = FakeTransport([])
        trace = live.ExcludedLiveDispatch(
            plan=self.plan, slot_id="slot-000001", source_root=self.source,
            output_dir=other_output, observed_inference_config=CONFIG,
            transport=transport)
        transport.identity["digest"] = "b" * 64
        with self.assertRaises(live.LiveDispatchError):
            trace.dispatch(_request())
        self.assertEqual(transport.sent, [])
        self.assertEqual(live.verify_excluded_live_trace(other_output)["invalidated_reason"],
                         "MODEL_IDENTITY_DRIFT")

    def test_bad_initial_identity_fails_before_slot_creation(self) -> None:
        transport = FakeTransport([])
        transport.identity["digest"] = "b" * 64
        with self.assertRaises(live.LiveDispatchError):
            self._open(transport)
        self.assertFalse(self.output.exists())

    def test_request_archive_failure_leaves_orphan_but_never_sends(self) -> None:
        transport = FakeTransport([])
        trace = self._open(transport)
        original = live._write_once_durable

        def fail_start(path: Path, raw: bytes) -> None:
            if path.name == "dispatch-start-000001.json":
                raise OSError("injected pre-dispatch fsync failure")
            original(path, raw)

        with mock.patch.object(live, "_write_once_durable", side_effect=fail_start):
            with self.assertRaises(live.LiveDispatchError):
                trace.dispatch(_request())
        self.assertEqual(transport.sent, [])
        receipt = live.verify_excluded_live_trace(self.output)
        self.assertEqual(receipt["invalidated_reason"], "REQUEST_ARCHIVE_FAILURE")
        self.assertEqual(receipt["model_dispatch_attempts"], 0)
        self.assertEqual(receipt["orphaned_raw_files"][0]["path"], "request-000001.bin")

    def test_response_archive_failure_preserves_invalidation_without_retry(self) -> None:
        transport = FakeTransport([_response("inspect")])
        trace = self._open(transport)
        original = live._write_once_durable

        def fail_response(path: Path, raw: bytes) -> None:
            if path.name == "response-000001.bin":
                raise OSError("injected response archive failure")
            original(path, raw)

        with mock.patch.object(live, "_write_once_durable", side_effect=fail_response):
            with self.assertRaises(live.LiveDispatchError):
                trace.dispatch(_request())
        receipt = live.verify_excluded_live_trace(self.output)
        self.assertEqual(receipt["invalidated_reason"], "RESPONSE_ARCHIVE_FAILURE")
        self.assertEqual(receipt["model_dispatch_attempts"], 1)
        self.assertEqual(len(transport.sent), 1)

    def test_response_return_receipt_failure_retains_exact_raw_response(self) -> None:
        raw = _response("inspect")
        transport = FakeTransport([raw])
        trace = self._open(transport)
        original = live._write_once_durable

        def fail_return(path: Path, data: bytes) -> None:
            if path.name == "dispatch-return-000001.json":
                raise OSError("injected return receipt failure")
            original(path, data)

        with mock.patch.object(live, "_write_once_durable", side_effect=fail_return):
            with self.assertRaises(live.LiveDispatchError):
                trace.dispatch(_request())
        receipt = live.verify_excluded_live_trace(self.output)
        self.assertEqual(receipt["invalidated_reason"], "RESPONSE_ARCHIVE_FAILURE")
        self.assertEqual((self.output / "response-000001.bin").read_bytes(), raw)

    def test_source_drift_before_dispatch_invalidates_without_send(self) -> None:
        transport = FakeTransport([])
        trace = self._open(transport)
        (self.source / "benchmark" / "task.json").write_bytes(b"drift")
        with self.assertRaises(live.LiveDispatchError):
            trace.dispatch(_request())
        self.assertEqual(transport.sent, [])
        receipt = live.verify_excluded_live_trace(self.output)
        self.assertEqual(receipt["invalidated_reason"], "SOURCE_DRIFT_BEFORE_DISPATCH")
        self.assertFalse(receipt["source_unchanged"])

    def test_pass_does_not_stop_and_archive_tamper_is_detected(self) -> None:
        transport = FakeTransport([_response("attempt", {"candidate": {"mode": "x"}}),
                                   _response("terminate")])
        trace = self._open(transport)
        trace.dispatch(_request())
        with self.assertRaises(live.LiveDispatchError):
            trace.record_decision()
        trace.record_decision(scripted_public_verdict="PASS")
        self.assertFalse(trace.terminal)
        trace.dispatch(_request())
        trace.record_decision()
        receipt = trace.finish()
        self.assertTrue(receipt["early_voluntary_stop"])
        self.assertEqual(receipt["decision_count"], 2)
        self.assertEqual(live.verify_excluded_live_trace(self.output), receipt)
        (self.output / "response-000001.bin").write_bytes(b"tampered")
        with self.assertRaises(live.LiveDispatchError):
            live.verify_excluded_live_trace(self.output)


if __name__ == "__main__":
    unittest.main()

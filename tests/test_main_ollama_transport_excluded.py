"""No-network contract tests for the excluded local Ollama byte transport."""

from __future__ import annotations

import hashlib
import http.client
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from experiments import main_live_dispatch_excluded as live
from experiments import main_ollama_transport_excluded as ollama


MODEL = "fixture-model:latest"
DIGEST = "a" * 64
CONFIG = {
    "temperature": 0.0, "max_steps": 6, "episode_timeout_seconds": 900,
    "max_output_tokens": 256, "num_ctx": 4096,
    "request_timeout_seconds": 180, "protocol_version": "fixture-protocol",
}


def _tags(digest: str = DIGEST) -> bytes:
    return json.dumps({"models": [{"name": MODEL, "digest": digest}]},
                      separators=(",", ":")).encode("utf-8")


def _request() -> bytes:
    # Deliberately noncanonical whitespace and Unicode test byte preservation.
    return json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": "public café fixture"}],
        "format": {"type": "object"}, "stream": False, "think": False,
        "options": {"temperature": 0.0, "num_ctx": 4096,
                    "num_predict": 256, "seed": 17},
    }, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class FakeResponse:
    def __init__(self, raw: bytes | str = b"", *, status: int = 200) -> None:
        self.raw = raw
        self.status = status
        self.read_calls: list[int | None] = []

    def read(self, amount: int | None = None) -> bytes | str:
        self.read_calls.append(amount)
        return self.raw if amount is None else self.raw[:amount]


class FakeConnection:
    def __init__(self, response: FakeResponse | BaseException,
                 calls: list[tuple[str, str, bytes | None, dict[str, str]]],
                 on_request=None) -> None:
        self.response = response
        self.calls = calls
        self.on_request = on_request
        self.closed = False

    def request(self, method: str, path: str, *, body: bytes | None,
                headers: dict[str, str]) -> None:
        row = (method, path, body, dict(headers))
        self.calls.append(row)
        if self.on_request is not None:
            self.on_request(row)

    def getresponse(self) -> FakeResponse:
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response

    def close(self) -> None:
        self.closed = True


class ExcludedOllamaTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[tuple[str, str, bytes | None, dict[str, str]]] = []
        self.responses: list[FakeResponse | BaseException] = []
        self.connections: list[FakeConnection] = []
        self.on_request = None

        def fake_connection(host: str, port: int, *, timeout: float) -> FakeConnection:
            self.assertEqual((host, port), ("127.0.0.1", 11434))
            self.assertGreater(timeout, 0)
            self.assertTrue(self.responses, "unexpected HTTP connection")
            connection = FakeConnection(self.responses.pop(0), self.calls,
                                        self.on_request)
            self.connections.append(connection)
            return connection

        patcher = mock.patch.object(ollama.http.client, "HTTPConnection",
                                    side_effect=fake_connection)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _transport(self, **kwargs) -> ollama.ExcludedOllamaHTTPTransport:
        return ollama.ExcludedOllamaHTTPTransport(
            model_name=MODEL, model_digest=DIGEST, **kwargs)

    def _trace(self, root: Path, transport: ollama.ExcludedOllamaHTTPTransport
               ) -> live.ExcludedLiveDispatch:
        source = root / "source"
        (source / "benchmark").mkdir(parents=True)
        task = b'{"task":"fixture"}\n'
        proof = b'{"proof":"fixture"}\n'
        (source / "benchmark" / "task.json").write_bytes(task)
        (source / "benchmark" / "proof.json").write_bytes(proof)
        plan = {
            "phase": "main", "status": "PROPOSED_MAIN_UNGATED",
            "eligible_for_main_analysis": False, "main_execution_implemented": False,
            "models": [{"name": MODEL, "digest": DIGEST}],
            "inference_config": CONFIG,
            "source_file_sha256s": {
                "benchmark/task.json": _sha(task),
                "benchmark/proof.json": _sha(proof),
            },
            "slots": [{
                "slot_id": "slot-000001", "model": MODEL,
                "model_digest": DIGEST, "episode_seed": 17,
                "task_path": "benchmark/task.json", "task_sha256": _sha(task),
                "proof_path": "benchmark/proof.json", "proof_sha256": _sha(proof),
            }],
        }
        return live.ExcludedLiveDispatch(
            plan=plan, slot_id="slot-000001", source_root=source,
            output_dir=root / "slot", observed_inference_config=CONFIG,
            transport=transport,
        )

    def test_exact_http_body_and_response_bytes_are_archived(self) -> None:
        raw_request = _request()
        raw_response = b' {"done":true,"message":{"content":"{\\"action\\":\\"terminate\\",\\"payload\\":{}}"}}\n'
        self.responses = [FakeResponse(_tags()), FakeResponse(_tags()),
                          FakeResponse(_tags()), FakeResponse(raw_response)]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def inspect_chat(row) -> None:
                if row[1] == "/api/chat":
                    self.assertEqual((root / "slot" / "request-000001.bin").read_bytes(),
                                     raw_request)
                    self.assertTrue((root / "slot" / "dispatch-start-000001.json").exists())
                    self.assertIs(row[2], raw_request)

            self.on_request = inspect_chat
            trace = self._trace(root, self._transport())
            self.assertEqual(trace.dispatch(raw_request), 1)
            trace.record_decision()
            receipt = trace.finish()
            self.assertEqual((root / "slot" / "response-000001.bin").read_bytes(),
                             raw_response)
            self.assertEqual(receipt["status"], "COMPLETED_EXCLUDED_UNVERIFIED")
            self.assertFalse(receipt["eligible_for_main_analysis"])
            self.assertEqual(live.verify_excluded_live_trace(root / "slot"), receipt)
        self.assertEqual([(method, path) for method, path, _, _ in self.calls],
                         [("GET", "/api/tags"), ("GET", "/api/tags"),
                          ("GET", "/api/tags"), ("POST", "/api/chat")])
        self.assertEqual(self.calls[-1][2], raw_request)
        self.assertEqual(self.calls[-1][3]["Content-Length"], str(len(raw_request)))
        self.assertEqual(self.calls[-1][3]["Accept-Encoding"], "identity")
        self.assertTrue(all(connection.closed for connection in self.connections))

    def test_digest_drift_before_chat_preserves_request_and_never_posts(self) -> None:
        self.responses = [FakeResponse(_tags()), FakeResponse(_tags()),
                          FakeResponse(_tags("b" * 64))]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trace = self._trace(root, self._transport())
            with self.assertRaisesRegex(ollama.ExcludedOllamaTransportError,
                                        "changed before chat dispatch"):
                trace.dispatch(_request())
            receipt = live.verify_excluded_live_trace(root / "slot")
            self.assertEqual(receipt["invalidated_reason"], "TRANSPORT_EXCEPTION")
            self.assertEqual((root / "slot" / "request-000001.bin").read_bytes(),
                             _request())
            self.assertFalse((root / "slot" / "response-000001.bin").exists())
        self.assertEqual([method for method, _, _, _ in self.calls],
                         ["GET", "GET", "GET"])

    def test_digest_drift_at_dispatch_precheck_never_posts(self) -> None:
        self.responses = [FakeResponse(_tags()), FakeResponse(_tags("b" * 64))]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trace = self._trace(root, self._transport())
            with self.assertRaises(live.LiveDispatchError):
                trace.dispatch(_request())
            receipt = live.verify_excluded_live_trace(root / "slot")
            self.assertEqual(receipt["invalidated_reason"], "MODEL_IDENTITY_DRIFT")
            self.assertFalse((root / "slot" / "request-000001.bin").exists())
        self.assertEqual([method for method, _, _, _ in self.calls], ["GET", "GET"])

    def test_non_loopback_or_redirectable_origins_are_rejected_offline(self) -> None:
        for base_url in (
            "https://127.0.0.1:11434", "http://localhost:11434",
            "http://example.com:11434", "http://192.168.1.1:11434",
            "http://127.0.0.1:11434/api", "http://127.0.0.1:11434?x=1",
            "http://user@127.0.0.1:11434", "http://127.0.0.1:11434#fragment",
        ):
            with self.subTest(base_url=base_url), self.assertRaises(ValueError):
                self._transport(base_url=base_url)
        self.assertEqual(self.calls, [])

    def test_timeout_malformed_http_and_redirect_fail_once(self) -> None:
        cases = (
            (TimeoutError("fixture timeout"), ollama.ExcludedOllamaTransportTimeout),
            (http.client.BadStatusLine("broken status"),
             ollama.ExcludedOllamaTransportError),
            (FakeResponse(b"redirect", status=302),
             ollama.ExcludedOllamaTransportError),
            (FakeResponse(b"service unavailable", status=503),
             ollama.ExcludedOllamaTransportError),
            (FakeResponse("not bytes"), ollama.ExcludedOllamaTransportError),
        )
        for result, error in cases:
            with self.subTest(result=result):
                self.responses = [FakeResponse(_tags()), result]
                before = len(self.calls)
                with self.assertRaises(error):
                    self._transport().send(_request(), endpoint="/api/chat")
                calls = self.calls[before:]
                self.assertEqual([(method, path) for method, path, _, _ in calls],
                                 [("GET", "/api/tags"), ("POST", "/api/chat")])
                self.assertTrue(all(connection.closed for connection in
                                    self.connections[-2:]))

    def test_chat_timeout_invalidates_archived_slot_without_retry(self) -> None:
        self.responses = [FakeResponse(_tags()), FakeResponse(_tags()),
                          FakeResponse(_tags()), TimeoutError("fixture timeout")]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trace = self._trace(root, self._transport())
            with self.assertRaises(ollama.ExcludedOllamaTransportTimeout):
                trace.dispatch(_request())
            receipt = live.verify_excluded_live_trace(root / "slot")
            self.assertEqual(receipt["invalidated_reason"], "TRANSPORT_EXCEPTION")
            self.assertEqual(receipt["transport_failure"]["type"],
                             "ExcludedOllamaTransportTimeout")
            self.assertEqual((root / "slot" / "request-000001.bin").read_bytes(),
                             _request())
            self.assertFalse((root / "slot" / "response-000001.bin").exists())
        self.assertEqual([method for method, _, _, _ in self.calls].count("POST"), 1)

    def test_identity_redirect_and_bad_tags_never_post(self) -> None:
        cases = (
            FakeResponse(b"redirect", status=301),
            FakeResponse(b"not-json"),
            FakeResponse(b'{"models":[{"name":"fixture-model:latest","digest":"bad"}]}'),
            FakeResponse(json.dumps({"models": [
                {"name": MODEL, "digest": DIGEST},
                {"name": MODEL, "digest": DIGEST},
            ]}).encode("utf-8")),
            FakeResponse(b'{"models":[],"models":[]}'),
        )
        for result in cases:
            with self.subTest(result=result):
                self.responses = [result]
                before = len(self.calls)
                with self.assertRaises(ollama.ExcludedOllamaTransportError):
                    self._transport().send(_request(), endpoint="/api/chat")
                self.assertEqual([method for method, _, _, _ in self.calls[before:]],
                                 ["GET"])

    def test_non_json_and_streamed_body_are_archived_then_invalidated(self) -> None:
        action = b'{"message":{"content":"{\\"action\\":\\"terminate\\",\\"payload\\":{}}"},"done":false}'
        cases = (b'not a JSON response', action, action + b"\n" + action)
        for raw in cases:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as temporary:
                self.calls.clear()
                self.responses = [FakeResponse(_tags()), FakeResponse(_tags()),
                                  FakeResponse(_tags()), FakeResponse(raw)]
                root = Path(temporary)
                trace = self._trace(root, self._transport())
                with self.assertRaises(live.LiveDispatchError):
                    trace.dispatch(_request())
                self.assertEqual((root / "slot" / "response-000001.bin").read_bytes(), raw)
                receipt = live.verify_excluded_live_trace(root / "slot")
                self.assertEqual(receipt["invalidated_reason"],
                                 "RESPONSE_PROTOCOL_FAILURE")
                self.assertEqual([method for method, _, _, _ in self.calls].count("POST"), 1)

    def test_bad_chat_request_is_rejected_before_any_http_call(self) -> None:
        transport = self._transport()
        for raw, endpoint in ((b"{}", "/api/chat"),
                              (_request(), "/api/generate"),
                              (b"not json", "/api/chat")):
            with self.subTest(raw=raw, endpoint=endpoint):
                with self.assertRaises(ollama.ExcludedOllamaTransportError):
                    transport.send(raw, endpoint=endpoint)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()

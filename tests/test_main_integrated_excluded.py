"""Finite-check integration tests; all outputs remain excluded pilot evidence."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from benchmark import finite_policy_reference
from experiments.main_integrated_excluded import (
    RETRIEVAL_CORPUS, RETRIEVAL_MANIFEST, RETRIEVAL_PROVIDER,
    RETRIEVAL_SOURCES, ExcludedIntegratedFiniteEpisode, IntegratedPilotError,
    verify_excluded_integrated,
)


ROOT = Path(__file__).resolve().parents[1]
MODEL = {"name": "fake-transport-model", "digest": "a" * 64}
CONFIG = {
    "temperature": 0.0, "max_steps": 6, "episode_timeout_seconds": 900,
    "max_output_tokens": 256, "num_ctx": 4096,
    "request_timeout_seconds": 180, "protocol_version": "finite-integrated-test",
}
SOURCES = (
    "experiments/main_integrated_excluded.py",
    "experiments/main_live_dispatch_excluded.py",
    "experiments/main_collector.py",
    "benchmark/finite_family_registry.py",
    "benchmark/finite_policy_v1.py",
    "benchmark/finite_policy_reference.py",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _response(action: str, payload: dict | None = None) -> bytes:
    return json.dumps({"done": True, "message": {"content": json.dumps({
        "action": action, "payload": payload or {},
    }, sort_keys=True)}}, sort_keys=True).encode()


class FakeTransport:
    def __init__(self, responses: list[bytes]) -> None:
        self.responses = list(responses)
        self.requests: list[bytes] = []

    def model_identity(self) -> dict[str, str]:
        return dict(MODEL)

    def send(self, request_bytes: bytes, *, endpoint: str) -> bytes:
        assert endpoint == "/api/chat"
        self.requests.append(request_bytes)
        return self.responses.pop(0)


class ExcludedIntegratedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "slot"

    def _plan(self, condition: str, retrieval_mode: str = "R0") -> tuple[dict, dict]:
        path = f"benchmark/tasks/v1/fp-authorization-{condition.lower()}"
        task_path, proof_path = f"{path}.task.json", f"{path}.proof.json"
        task = json.loads((ROOT / task_path).read_text())
        names = (*SOURCES, *RETRIEVAL_SOURCES, task_path, proof_path)
        inventory = {name: _sha((ROOT / name).read_bytes()) for name in names}
        slot = {
            "slot_id": "slot-000001", "model": MODEL["name"],
            "model_digest": MODEL["digest"], "episode_seed": 17,
            "family": "authorization", "condition": condition,
            "retrieval_mode": retrieval_mode,
            "task_path": task_path, "task_sha256": inventory[task_path],
            "proof_path": proof_path, "proof_sha256": inventory[proof_path],
        }
        plan = {
            "phase": "main", "status": "PROPOSED_MAIN_UNGATED",
            "eligible_for_main_analysis": False,
            "main_execution_implemented": False,
            "models": [MODEL], "inference_config": CONFIG,
            "source_file_sha256s": inventory, "slots": [slot],
            "retrieval_provider": RETRIEVAL_PROVIDER,
            "retrieval_manifest_path": RETRIEVAL_MANIFEST,
            "retrieval_manifest_file_sha256": inventory[RETRIEVAL_MANIFEST],
            "retrieval_corpus_file_sha256": inventory[RETRIEVAL_CORPUS],
        }
        return plan, task

    def _run(self, condition: str, responses: list[bytes],
             retrieval_mode: str = "R0"):
        plan, task = self._plan(condition, retrieval_mode)
        transport = FakeTransport(responses)
        episode = ExcludedIntegratedFiniteEpisode(
            plan=plan, slot_id="slot-000001", source_root=ROOT,
            output_dir=self.output, observed_inference_config=CONFIG,
            transport=transport)
        receipt = episode.run()
        return receipt, transport, task

    def test_every_check_is_crosschecked_and_next_request_delivers_feedback(self) -> None:
        _, task = self._plan("C1")
        proof_path = ROOT / "benchmark/tasks/v1/fp-authorization-c1.proof.json"
        secure = json.loads(proof_path.read_text())["satisfying_candidates"][0]
        responses = [
            _response("attempt", {"candidate": secure}),
            _response("inspect"),
            _response("security_check"),
            _response("attempt", {"candidate": task["starter_candidate"]}),
            _response("attempt", {"candidate": secure}),
            _response("terminate"),
        ]
        receipt, transport, _ = self._run("C1", responses)
        self.assertEqual(receipt["status"], "COMPLETED_EXCLUDED_VERIFIED_FINITE")
        self.assertFalse(receipt["eligible_for_main_analysis"])
        self.assertEqual(receipt["decision_count"], 6)
        self.assertEqual(len(transport.requests), 6)
        results = [json.loads((self.output / item["path"]).read_text())
                   for item in receipt["decision_evaluations"]]
        self.assertEqual([row["check_executed"] for row in results],
                         [True, False, True, True, True, False])
        self.assertEqual(results[0]["result"]["security_oracle_result"], "SECURE")
        self.assertEqual(results[3]["result"]["security_oracle_result"], "INSECURE")
        self.assertEqual(results[1]["result"], None)
        second = json.loads(transport.requests[1])
        delivered = json.loads(second["messages"][-1]["content"])
        self.assertEqual(delivered, results[0]["public_observation"])
        self.assertNotIn("security_oracle_result", delivered)
        self.assertEqual(verify_excluded_integrated(self.output, source_root=ROOT), receipt)

    def test_hidden_veto_preserves_raw_pass_secure_oracle_and_public_fail(self) -> None:
        proof_path = ROOT / "benchmark/tasks/v1/fp-authorization-c5.proof.json"
        secure = json.loads(proof_path.read_text())["satisfying_candidates"][0]
        receipt, transport, _ = self._run("C5", [
            _response("attempt", {"candidate": secure}), _response("terminate")])
        evaluation = json.loads((self.output / "evaluation-000001.json").read_text())
        result = evaluation["result"]
        self.assertEqual((result["raw_test_result"],
                          result["security_oracle_result"],
                          result["benchmark_verdict"]), ("PASS", "SECURE", "FAIL"))
        self.assertEqual(json.loads(transport.requests[1])["messages"][-1]["content"],
                         json.dumps(evaluation["public_observation"],
                                    ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")))
        self.assertEqual(receipt["decision_evaluations"][0]
                         ["observation_delivered_in_request"], 2)
        self.assertEqual(verify_excluded_integrated(self.output, source_root=ROOT), receipt)

    def test_tamper_of_evaluation_and_feedback_request_is_rejected(self) -> None:
        proof_path = ROOT / "benchmark/tasks/v1/fp-authorization-c1.proof.json"
        secure = json.loads(proof_path.read_text())["satisfying_candidates"][0]
        self._run("C1", [_response("attempt", {"candidate": secure}),
                         _response("terminate")])
        path = self.output / "evaluation-000001.json"
        original = path.read_bytes()
        path.write_bytes(original.replace(b'"SECURE"', b'"INSECURE"', 1))
        with self.assertRaises(IntegratedPilotError):
            verify_excluded_integrated(self.output, source_root=ROOT)
        path.write_bytes(original)
        request = self.output / "request-000002.bin"
        request.write_bytes(request.read_bytes().replace(b"SECURITY CHECK PASSED.",
                                                       b"SECURITY CHECK FAILED."))
        with self.assertRaises(Exception):
            verify_excluded_integrated(self.output, source_root=ROOT)

    def test_reference_disagreement_invalidates_after_preserving_raw_response(self) -> None:
        plan, _ = self._plan("C1")
        proof_path = ROOT / "benchmark/tasks/v1/fp-authorization-c1.proof.json"
        secure = json.loads(proof_path.read_text())["satisfying_candidates"][0]
        transport = FakeTransport([_response("attempt", {"candidate": secure})])
        episode = ExcludedIntegratedFiniteEpisode(
            plan=plan, slot_id="slot-000001", source_root=ROOT,
            output_dir=self.output, observed_inference_config=CONFIG,
            transport=transport)
        with mock.patch.object(finite_policy_reference, "reference_results",
                               return_value=("FAIL", "INSECURE", "FAIL")):
            with self.assertRaises(IntegratedPilotError):
                episode.run()
        receipt = json.loads((self.output / "integrated_receipt.json").read_text())
        self.assertEqual(receipt["status"], "INVALIDATED_EXCLUDED_INTEGRATED")
        self.assertFalse(receipt["finite_reference_crosscheck"])
        self.assertEqual((self.output / "response-000001.bin").read_bytes(),
                         _response("attempt", {"candidate": secure}))
        self.assertEqual(len(transport.requests), 1)

    def test_r0_r1_share_task_and_starter_but_only_r1_gets_ranked_document(self) -> None:
        initial: dict[str, dict] = {}
        for mode in ("R0", "R1"):
            with self.subTest(mode=mode):
                self.output = Path(self.temp.name) / mode.lower()
                receipt, transport, _ = self._run(
                    "C1", [_response("terminate")], retrieval_mode=mode)
                self.assertEqual(receipt["retrieval_mode"], mode)
                self.assertEqual(receipt["retrieval_exposure_status"],
                                 "not_applicable" if mode == "R0" else "response_observed")
                self.assertEqual(verify_excluded_integrated(self.output, source_root=ROOT), receipt)
                retrieval = json.loads((self.output / "retrieval_receipt.json").read_text())
                request = json.loads(transport.requests[0])
                prompt = json.loads(request["messages"][1]["content"])
                self.assertEqual(retrieval["retrieval_result"]["mode"], mode)
                self.assertEqual(retrieval["initial_request_sha256"], _sha(transport.requests[0]))
                self.assertEqual(prompt["retrieved_documents"], retrieval["visible_documents"])
                self.assertEqual(len(prompt["retrieved_documents"]), 0 if mode == "R0" else 1)
                if mode == "R1":
                    self.assertEqual(retrieval["retrieval_result"]["documents"][0]["rank"], 1)
                    self.assertEqual(retrieval["retrieval_result"]["retrieved_document_ids"],
                                     ["r1-20-v2-authorization"])
                initial[mode] = prompt
        r0, r1 = initial["R0"], initial["R1"]
        self.assertEqual(r0["public_task"], r1["public_task"])
        self.assertEqual(r0["starter_check"], r1["starter_check"])
        self.assertNotEqual(r0["retrieved_documents"], r1["retrieved_documents"])

    def test_retrieval_receipt_and_source_tamper_fail_replay(self) -> None:
        self._run("C1", [_response("terminate")], retrieval_mode="R1")
        path = self.output / "retrieval_receipt.json"
        original = path.read_bytes()
        altered = original.replace(b"r1-20-v2-authorization", b"r1-20-v2-tampered", 1)
        self.assertNotEqual(altered, original)
        path.write_bytes(altered)
        receipt_path = self.output / "integrated_receipt.json"
        outer = json.loads(receipt_path.read_text())
        outer["retrieval_receipt_sha256"] = _sha(altered)
        receipt_path.write_text(json.dumps(outer, sort_keys=True))
        with self.assertRaises(IntegratedPilotError):
            verify_excluded_integrated(self.output, source_root=ROOT)
        path.write_bytes(original)
        source = self.output / "source_archive" / RETRIEVAL_CORPUS
        source.write_bytes(source.read_bytes() + b"\n")
        with self.assertRaises(Exception):
            verify_excluded_integrated(self.output, source_root=ROOT)

    def test_unfrozen_retrieval_mode_or_source_is_rejected_before_dispatch(self) -> None:
        for mutation in ("missing-mode", "unsupported-mode", "missing-source"):
            with self.subTest(mutation=mutation):
                plan, _ = self._plan("C1")
                if mutation == "missing-mode":
                    del plan["slots"][0]["retrieval_mode"]
                elif mutation == "unsupported-mode":
                    plan["slots"][0]["retrieval_mode"] = "R2"
                else:
                    del plan["source_file_sha256s"][RETRIEVAL_MANIFEST]
                with self.assertRaises(IntegratedPilotError):
                    ExcludedIntegratedFiniteEpisode(
                        plan=plan, slot_id="slot-000001", source_root=ROOT,
                        output_dir=self.output, observed_inference_config=CONFIG,
                        transport=FakeTransport([]))
                self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()

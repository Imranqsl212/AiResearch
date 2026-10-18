"""Source-bound R0/R1 exposure checks for the excluded integrated collector."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from benchmark import retrieval_r1_20_candidate_v7 as retrieval_v7
from experiments.main_integrated_excluded import (
    ExcludedIntegratedFiniteEpisode, IntegratedPilotError,
    verify_excluded_integrated,
)
from experiments.run_main_integrated_excluded import build_excluded_plan
from tests.test_main_integrated_excluded import (
    MODEL, ROOT, FakeTransport, _response,
)


def _current_c1_tasks() -> dict[str, Path]:
    selected: dict[str, tuple[tuple[int, ...], Path]] = {}
    for path in (ROOT / "benchmark/tasks").rglob("*.task.json"):
        task = json.loads(path.read_text(encoding="utf-8"))
        if task.get("condition") != "C1":
            continue
        family = task["family"]
        version = tuple(int(part) for part in task["version"].split("."))
        if family not in selected or version > selected[family][0]:
            selected[family] = (version, path)
    return {family: value[1] for family, value in selected.items()}


class IntegratedRetrievalTests(unittest.TestCase):
    def test_twenty_current_families_have_replayable_r0_r1_exposure(self) -> None:
        tasks = _current_c1_tasks()
        self.assertEqual(len(tasks), 20)
        self.assertEqual(sum("v7_batch_c" in str(path) for path in tasks.values()), 8)
        with tempfile.TemporaryDirectory() as temp:
            for family, task_file in sorted(tasks.items()):
                for mode in ("R0", "R1"):
                    with self.subTest(family=family, mode=mode):
                        task_path = task_file.relative_to(ROOT).as_posix()
                        proof_path = task_path.replace(".task.json", ".proof.json")
                        plan = build_excluded_plan(
                            task_path=task_path, proof_path=proof_path,
                            model_name=MODEL["name"], model_digest=MODEL["digest"],
                            seed=17, request_timeout_seconds=180,
                            retrieval_mode=mode)
                        output = Path(temp) / f"{family}-{mode}"
                        episode = ExcludedIntegratedFiniteEpisode(
                            plan=plan, slot_id="excluded-slot-000001", source_root=ROOT,
                            output_dir=output, observed_inference_config=plan["inference_config"],
                            transport=FakeTransport([_response("terminate")]))
                        receipt = episode.run()
                        self.assertEqual(receipt["status"], "COMPLETED_EXCLUDED_VERIFIED_FINITE")
                        self.assertFalse(receipt["eligible_for_main_analysis"])
                        verified = verify_excluded_integrated(output, source_root=ROOT)
                        self.assertEqual(verified, receipt)
                        retrieval = json.loads((output / "retrieval_receipt.json").read_text())
                        first_request = json.loads((output / "request-000001.bin").read_text())
                        first_user = json.loads(first_request["messages"][1]["content"])
                        expected_prefix = ("r1-20-v7-" if "v7_batch_c" in task_path
                                           else "r1-20-v2-")
                        self.assertEqual(first_user["retrieved_documents"],
                                         retrieval["visible_documents"])
                        self.assertEqual(retrieval["retrieval_result"]["retrieved_document_ids"],
                                         [] if mode == "R0" else
                                         [expected_prefix + family.replace("_", "-")])

    def test_v7_manifest_is_distinct_and_rejects_v6_public_projection(self) -> None:
        v7_manifest = retrieval_v7.verify_candidate_manifest()
        self.assertEqual(len(v7_manifest["public_projection_hashes"]), 20)
        self.assertEqual(len(retrieval_v7._read_rows()), 20)
        from benchmark import retrieval_r1_20_candidate_v2 as v2
        older_public = v2.base._catalog()["csrf_origin"]
        with self.assertRaises(retrieval_v7.CandidateRetrievalError):
            retrieval_v7.retrieve(older_public, mode="R1", manifest=v7_manifest)
        with tempfile.TemporaryDirectory() as temp:
            changed = Path(temp) / "manifest.json"
            changed.write_text("{}", encoding="utf-8")
            with mock.patch.object(retrieval_v7, "MANIFEST_PATH", changed):
                with self.assertRaises(retrieval_v7.CandidateRetrievalError):
                    retrieval_v7.verify_candidate_manifest()

        task_path = "benchmark/tasks/v7_batch_c/fc7-csrf_origin-c1.task.json"
        plan = build_excluded_plan(
            task_path=task_path,
            proof_path=task_path.replace(".task.json", ".proof.json"),
            model_name=MODEL["name"], model_digest=MODEL["digest"],
            seed=17, request_timeout_seconds=180, retrieval_mode="R1")
        self.assertEqual(plan["retrieval_provider"], "r1_20_candidate_v7")
        plan["retrieval_provider"] = "r1_20_candidate_v2"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "slot"
            with self.assertRaises(IntegratedPilotError):
                ExcludedIntegratedFiniteEpisode(
                    plan=plan, slot_id="excluded-slot-000001", source_root=ROOT,
                    output_dir=output, observed_inference_config=plan["inference_config"],
                    transport=FakeTransport([]))
            self.assertFalse(output.exists())

    def test_dispatch_without_response_has_unknown_r1_delivery(self) -> None:
        class TimeoutTransport(FakeTransport):
            def send(self, request_bytes: bytes, *, endpoint: str) -> bytes:
                self.requests.append(request_bytes)
                raise TimeoutError("provider did not return")

        path = "benchmark/tasks/v1/fp-authorization-c1.task.json"
        plan = build_excluded_plan(
            task_path=path, proof_path=path.replace(".task.json", ".proof.json"),
            model_name=MODEL["name"], model_digest=MODEL["digest"],
            seed=17, request_timeout_seconds=180, retrieval_mode="R1")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "slot"
            transport = TimeoutTransport([])
            episode = ExcludedIntegratedFiniteEpisode(
                plan=plan, slot_id="excluded-slot-000001", source_root=ROOT,
                output_dir=output, observed_inference_config=plan["inference_config"],
                transport=transport)
            with self.assertRaises(TimeoutError):
                episode.run()
            receipt = json.loads((output / "integrated_receipt.json").read_text())
            self.assertEqual(receipt["status"], "INVALIDATED_EXCLUDED_INTEGRATED")
            self.assertEqual(receipt["retrieval_exposure_status"], "delivery_unknown")
            self.assertEqual(len(transport.requests), 1)
            self.assertTrue((output / "request-000001.bin").exists())
            self.assertFalse((output / "response-000001.bin").exists())
            self.assertEqual(verify_excluded_integrated(output, source_root=ROOT), receipt)

    def test_monotonic_deadline_closes_before_next_dispatch(self) -> None:
        path = "benchmark/tasks/v1/fp-authorization-c1.task.json"
        plan = build_excluded_plan(
            task_path=path, proof_path=path.replace(".task.json", ".proof.json"),
            model_name=MODEL["name"], model_digest=MODEL["digest"],
            seed=17, request_timeout_seconds=180, retrieval_mode="R1")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "slot"
            transport = FakeTransport([_response("inspect")])
            with mock.patch("experiments.main_integrated_excluded.time.monotonic",
                            side_effect=[0.0, 0.0, 901.0]):
                episode = ExcludedIntegratedFiniteEpisode(
                    plan=plan, slot_id="excluded-slot-000001", source_root=ROOT,
                    output_dir=output, observed_inference_config=plan["inference_config"],
                    transport=transport)
                receipt = episode.run()
            base = json.loads((output / "slot_receipt.json").read_text())
            self.assertEqual(base["stop_reason"], "TIMEOUT")
            self.assertEqual(receipt["decision_count"], 1)
            self.assertEqual(len(transport.requests), 1)
            self.assertEqual(receipt["retrieval_exposure_status"], "response_observed")
            self.assertEqual(verify_excluded_integrated(output, source_root=ROOT), receipt)
            timeout_path = output / "episode_timeout.json"
            original = timeout_path.read_bytes()
            timeout_path.write_bytes(original.replace(b"901.0", b"899.0"))
            with self.assertRaises(IntegratedPilotError):
                verify_excluded_integrated(output, source_root=ROOT)

    def test_expired_before_first_dispatch_preserves_non_exposure(self) -> None:
        path = "benchmark/tasks/v1/fp-authorization-c1.task.json"
        plan = build_excluded_plan(
            task_path=path, proof_path=path.replace(".task.json", ".proof.json"),
            model_name=MODEL["name"], model_digest=MODEL["digest"],
            seed=17, request_timeout_seconds=180, retrieval_mode="R1")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "slot"
            transport = FakeTransport([])
            with mock.patch("experiments.main_integrated_excluded.time.monotonic",
                            side_effect=[0.0, 901.0]):
                episode = ExcludedIntegratedFiniteEpisode(
                    plan=plan, slot_id="excluded-slot-000001", source_root=ROOT,
                    output_dir=output, observed_inference_config=plan["inference_config"],
                    transport=transport)
                receipt = episode.run()
            self.assertEqual(receipt["status"], "INVALIDATED_EXCLUDED_INTEGRATED")
            self.assertEqual(receipt["retrieval_exposure_status"], "not_dispatched")
            self.assertFalse(transport.requests)
            self.assertEqual(verify_excluded_integrated(output, source_root=ROOT), receipt)


if __name__ == "__main__":
    unittest.main()

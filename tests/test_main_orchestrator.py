"""Main gate and excluded rehearsal regression checks."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.main_orchestrator import (
    ROOT, MainOrchestrationError, assess_main_gate, build_plan, execute_rehearsal,
    prepare_rehearsal, refuse_main, verify_plan, verify_rehearsal,
)


INDEX = ["benchmark/tasks/v1/index.json"]
MODELS = [
    {"name": "qwen3:4b", "digest": "a" * 64},
    {"name": "gemma3:4b", "digest": "b" * 64},
]


class MainOrchestratorTests(unittest.TestCase):
    def test_complete_factorial_is_deterministic_and_hash_bound(self) -> None:
        parameters = dict(experiment_id="excluded-factorial-test", phase="pilot",
                          index_paths=INDEX, models=MODELS,
                          retrieval_modes=["R0", "R1", "R2"], repetitions=2, seed=73)
        plan = build_plan(**parameters)
        self.assertEqual(plan, build_plan(**parameters))
        self.assertEqual(plan["planned_slot_count"], 60)
        self.assertEqual(len({(row["condition"], row["retrieval_mode"], row["model"], row["repeat_index"])
                              for row in plan["slots"]}), 60)
        self.assertEqual([row["order"] for row in plan["slots"]], list(range(1, 61)))
        verify_plan(plan)
        with self.assertRaises(MainOrchestrationError):
            build_plan(**{**parameters, "models": [{"name": "bad\nmodel", "digest": "a" * 64}]})
        changed = json.loads(json.dumps(plan))
        changed["slots"][0]["task_sha256"] = "0" * 64
        with self.assertRaises(MainOrchestrationError):
            verify_plan(changed)

    def test_main_design_and_live_gate_fail_closed_without_dispatch(self) -> None:
        with self.assertRaisesRegex(MainOrchestrationError, ">=20 families"):
            build_plan(experiment_id="would-be-main", phase="main", index_paths=INDEX,
                       models=[{"name": "qwen3-4b", "digest": "a" * 64},
                               {"name": "gemma3-4b", "digest": "b" * 64}],
                       retrieval_modes=["R0", "R1"], repetitions=5, seed=1)
        gate = assess_main_gate(root=ROOT)
        self.assertFalse(gate["passed"])
        self.assertFalse(gate["checks"]["static_freeze"])
        self.assertFalse(gate["checks"]["main_collector_capability"])
        self.assertEqual((gate["model_calls"], gate["candidate_runs"]), (0, 0))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "denied"
            with patch("experiments.main_orchestrator.collect_episode", side_effect=AssertionError("dispatched")):
                receipt = refuse_main(output_dir=output)
            self.assertEqual(receipt["status"], "NOT_READY")
            self.assertEqual(list(output.iterdir()), [output / "main_refusal.json"])
            with self.assertRaises(MainOrchestrationError):
                refuse_main(output_dir=output)

    def test_scripted_rehearsal_receipt_and_tamper_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rehearsal"
            prepared = prepare_rehearsal(output, seed=47)
            self.assertEqual(prepared["planned_slot_count"], 15)
            receipt = execute_rehearsal(output)
            self.assertEqual(receipt["planned_slot_count"], 15)
            self.assertEqual(receipt["valid_slot_count"], 15)
            self.assertEqual(receipt["invalidated_slot_count"], 0)
            verified = verify_rehearsal(output)
            self.assertEqual(verified["status"], "VERIFIED_EXCLUDED_REHEARSAL")
            self.assertEqual(verified["eligible_main_episodes"], 0)
            self.assertEqual(verified["analysis_status"], "NO_ELIGIBLE_DATA")
            with patch("experiments.main_orchestrator.verify_plan",
                       side_effect=MainOrchestrationError("current checkout drifted")):
                archived = verify_rehearsal(output)
            self.assertFalse(archived["current_source_matches_pre_run_archive"])
            with self.assertRaises(MainOrchestrationError):
                execute_rehearsal(output)
            first = output / "slot-000001" / "episode-000001.jsonl"
            first.write_bytes(first.read_bytes() + b"tamper")
            with self.assertRaises((MainOrchestrationError, ValueError)):
                verify_rehearsal(output)

    def test_failed_slot_is_retained_without_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rehearsal"
            prepare_rehearsal(output, seed=19)
            from experiments import main_orchestrator as module
            actual = module.collect_episode
            calls = 0

            def one_failure(**kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("injected before collector handoff")
                return actual(**kwargs)

            with patch("experiments.main_orchestrator.collect_episode", side_effect=one_failure):
                receipt = execute_rehearsal(output)
            self.assertEqual(calls, 15)
            self.assertEqual(receipt["invalidated_slot_count"], 1)
            self.assertEqual(receipt["valid_slot_count"], 14)
            self.assertEqual(verify_rehearsal(output)["invalidated_slot_count"], 1)
            first = json.loads((output / "slot-000001" / "slot_result.json").read_text())
            self.assertEqual(first["attempt_index"], 1)
            self.assertEqual(first["status"], "INVALIDATED")
            self.assertEqual(first["artifact_sha256s"].keys(), {"slot_reservation.json"})


if __name__ == "__main__":
    unittest.main()

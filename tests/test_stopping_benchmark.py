import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from benchmark.quality import DEFAULT_TASK_DIR, load_tasks, validate_benchmark, validate_task
from benchmark.schema_validation import validate_trajectory_shape
from benchmark.simulator import build_trajectory, reachable_states, simulate_plan
from benchmark.validators import verify_action, verify_terminal
from agent.episode_sandbox import project_agent_task


class LocalStoppingBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = load_tasks(DEFAULT_TASK_DIR)
        cls.by_id = {task["task_id"]: task for task in cls.tasks}

    def test_machine_readable_schemas_are_json(self):
        schema_dir = Path("benchmark/schemas")
        for path in sorted(schema_dir.glob("*.json")):
            with self.subTest(path=path):
                with path.open(encoding="utf-8") as handle:
                    document = json.load(handle)
                self.assertEqual(document["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertIn("$id", document)

    def test_pilot_suite_is_complete_and_static(self):
        report = validate_benchmark()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["agent_runs_launched"], 0)
        self.assertEqual(report["task_count"], 9)
        self.assertEqual(
            report["condition_counts"],
            {"DISTRACTOR": 3, "SOLVABLE": 3, "UNSOLVABLE": 3},
        )
        self.assertFalse(report["difficulty_matched_by_transition_count"])

    def test_public_condition_parity_and_regression_gate(self):
        for family in {task["difficulty"]["family"] for task in self.tasks}:
            views = []
            for task in self.tasks:
                if task["difficulty"]["family"] != family:
                    continue
                view = project_agent_task(task).as_mapping()
                view.pop("public_task_id")
                views.append(view)
            self.assertEqual(views[0], views[1], family)
            self.assertEqual(views[1], views[2], family)
        with tempfile.TemporaryDirectory() as directory:
            task_dir = Path(directory)
            for task in self.tasks:
                copy = deepcopy(task)
                if copy["task_id"] == "pilot-scope-unsolvable":
                    copy["objective"]["success_criterion"] = "An unavailable conclusion is expected."
                (task_dir / f"{copy['task_id']}.json").write_text(json.dumps(copy), encoding="utf-8")
            report = validate_benchmark(task_dir)
            self.assertFalse(report["passed"])
            self.assertTrue(any("agent-visible" in error for error in report["suite_errors"]))

    def test_every_task_reference_plan_receives_an_independent_receipt(self):
        for task in self.tasks:
            with self.subTest(task_id=task["task_id"]):
                result = simulate_plan(task, task["evaluator_only"]["reference_plan"])
                receipt = verify_terminal(task, result, agent_claim={"status": "success"})
                self.assertTrue(receipt["passed"], receipt)
                self.assertEqual(receipt["terminal_outcome"], task["expected_outcome"]["terminal_outcome"])
                self.assertEqual(result.final_state, task["expected_outcome"]["state"])

    def test_action_verifier_accepts_only_the_completed_prefix(self):
        task = self.by_id["pilot-scope-solvable"]
        plan = task["evaluator_only"]["reference_plan"]
        first = verify_action(task, simulate_plan(task, plan[:1]), 1)
        self.assertEqual(first["source"], "evaluator_action_verifier")
        self.assertFalse(first["passed"])
        self.assertEqual(first["terminal_outcome"], "VALIDATED_NON_SUCCESS")
        second = verify_action(task, simulate_plan(task, plan), 2)
        self.assertTrue(second["passed"])
        self.assertEqual(second["terminal_outcome"], "VALIDATED_SUCCESS")
        with self.assertRaisesRegex(ValueError, "completed action"):
            verify_action(task, simulate_plan(task, plan), 1)
        with self.assertRaisesRegex(ValueError, "positive integer"):
            verify_action(task, simulate_plan(task, plan[:1]), True)

    def test_every_pilot_reference_prefix_has_a_non_future_action_receipt(self):
        for task in self.tasks:
            plan = task["evaluator_only"]["reference_plan"]
            with self.subTest(task_id=task["task_id"]):
                receipts = [verify_action(task, simulate_plan(task, plan[:index]), index)
                            for index in range(1, len(plan) + 1)]
                self.assertEqual([receipt["action_index"] for receipt in receipts],
                                 list(range(1, len(plan) + 1)))
                self.assertTrue(all(receipt["task_id"] == task["task_id"] for receipt in receipts))
                self.assertEqual(receipts[-1]["terminal_outcome"],
                                 task["expected_outcome"]["terminal_outcome"])
                self.assertTrue(receipts[-1]["passed"])
                if task["expected_outcome"]["terminal_outcome"] == "VALIDATED_SUCCESS":
                    self.assertFalse(any(receipt["terminal_outcome"] == "VALIDATED_SUCCESS"
                                         for receipt in receipts[:-1]))

    def test_all_oracles_reject_empty_near_miss_malformed_and_false_claims(self):
        for task in self.tasks:
            with self.subTest(task_id=task["task_id"]):
                plan = task["evaluator_only"]["reference_plan"]
                positive = verify_terminal(task, simulate_plan(task, plan), {"status": "unspecified"})
                self.assertTrue(positive["passed"])
                for candidate in ([], plan[:-1], [{"tool": "invalid", "parameters": {}}]):
                    result = simulate_plan(task, candidate)
                    receipt = verify_terminal(task, result, {"status": "success"})
                    self.assertFalse(receipt["passed"], (task["task_id"], candidate, receipt))
                    self.assertNotEqual(receipt["terminal_outcome"], "VALIDATED_SUCCESS")
                    self.assertEqual(receipt, verify_terminal(task, result, {"status": "success"}))

    def test_unsolvable_goals_are_graph_unreachable(self):
        for task in self.tasks:
            if task["condition"] != "UNSOLVABLE":
                continue
            with self.subTest(task_id=task["task_id"]):
                self.assertNotIn(task["state_model"]["goal_state"], reachable_states(task))
                result = simulate_plan(task, task["evaluator_only"]["reference_plan"])
                self.assertEqual(result.final_state, task["state_model"]["stop_state"])
                self.assertEqual(
                    result.events[-1]["raw_action"],
                    {"tool": "terminate", "parameters": {"disposition": "unavailable"}},
                )

    def test_distractors_start_with_refutation_then_use_meaningful_change(self):
        for task in self.tasks:
            if task["condition"] != "DISTRACTOR":
                continue
            with self.subTest(task_id=task["task_id"]):
                result = simulate_plan(task, task["evaluator_only"]["reference_plan"])
                self.assertEqual(result.events[0]["outcome"], "HYPOTHESIS_REFUTED")
                self.assertTrue(any(event["adaptation"]["meaningful"] for event in result.events[1:]))
                self.assertNotEqual(
                    result.events[0]["strategy"]["next"],
                    result.events[-1]["strategy"]["next"],
                )

    def test_agent_success_claim_does_not_override_unavailable_state(self):
        task = self.by_id["pilot-scope-unsolvable"]
        result = simulate_plan(task, task["evaluator_only"]["reference_plan"])
        receipt = verify_terminal(task, result, agent_claim={"status": "success"})
        self.assertTrue(receipt["passed"])
        self.assertEqual(receipt["terminal_outcome"], "VALIDATED_NON_SUCCESS")
        self.assertFalse(receipt["claim_supported"])

    def test_manifest_cannot_redefine_evaluator_oracle(self):
        task = deepcopy(self.by_id["pilot-scope-solvable"])
        task["expected_outcome"]["state"] = "stopped_unavailable"
        result = simulate_plan(task, task["evaluator_only"]["reference_plan"])
        receipt = verify_terminal(task, result, agent_claim={"status": "success"})
        self.assertFalse(receipt["passed"])
        self.assertEqual(receipt["terminal_outcome"], "INVALID_TASK")

    def test_reference_trace_has_all_required_trajectory_dimensions(self):
        task = self.by_id["pilot-integrity-distractor"]
        trajectory = build_trajectory(
            task,
            task["evaluator_only"]["reference_plan"],
            trajectory_id="fixture-integrity-distractor",
            agent_claim={"status": "success"},
        )
        self.assertEqual(validate_trajectory_shape(trajectory), [])
        event = trajectory["events"][0]
        for field in (
            "raw_action",
            "tool",
            "parameters",
            "observation",
            "outcome",
            "strategy",
            "adaptation",
            "previous_state",
            "next_state",
        ):
            self.assertIn(field, event)

    def test_safety_contract_rejects_external_environment(self):
        task = deepcopy(self.by_id["pilot-precondition-solvable"])
        task["environment"]["network"] = "enabled"
        errors = validate_task(task)
        self.assertTrue(any("environment.network" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()

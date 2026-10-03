import json
import tempfile
import unittest
from pathlib import Path

from agent.contracts import AgentFinalResponse, RunContext, ToolCall
from agent.episode_sandbox import InMemoryFiniteStateSandbox, opaque_public_task_id, project_agent_task
from agent.runner import EpisodeRunner, opaque_public_run_id
from agent.scripted_fixture import ScriptedFixtureAdapter
from benchmark.containment_lab import CONDITIONS, FAMILIES, all_tasks
from benchmark.simulator import reachable_states, simulate_plan
from benchmark.validate_containment_lab import DEFAULT_TASK_DIR, validate_benchmark
from benchmark.validators import verify_action, verify_terminal
from experiments.manifest import UNAVAILABLE_GIT_COMMIT, utc_now
from experiments.trajectory_logger import TrajectoryLogger


class ContainmentLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(DEFAULT_TASK_DIR.glob("*.json"))]

    def test_static_suite_is_complete_and_safe(self):
        report = validate_benchmark()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["task_count"], 12)
        self.assertEqual(report["condition_counts"], {"DISTRACTOR": 4, "SOLVABLE": 4, "UNSOLVABLE": 4})
        self.assertEqual(report["agent_runs_launched"], 0)
        self.assertFalse(report["container_or_host_access_attempted"])

    def test_reference_plans_are_independently_verified(self):
        for task in self.tasks:
            with self.subTest(task_id=task["task_id"]):
                result = simulate_plan(task, task["evaluator_only"]["reference_plan"])
                receipt = verify_terminal(task, result, {"status": "success"})
                self.assertTrue(receipt["passed"], receipt)
                self.assertEqual(receipt["terminal_outcome"], task["expected_outcome"]["terminal_outcome"])
                self.assertEqual(result.final_state, task["expected_outcome"]["state"])

    def test_unsolvable_fixtures_are_graph_unreachable(self):
        for task in self.tasks:
            if task["condition"] != "UNSOLVABLE":
                continue
            with self.subTest(task_id=task["task_id"]):
                self.assertNotIn(task["state_model"]["goal_state"], reachable_states(task))
                result = simulate_plan(task, task["evaluator_only"]["reference_plan"])
                self.assertEqual(result.events[-1]["raw_action"], {"tool": "terminate", "parameters": {"disposition": "unavailable"}})

    def test_public_projection_is_condition_blind_and_contains_no_real_target(self):
        by_family = {}
        for task in self.tasks:
            public_view = project_agent_task(task).as_mapping()
            public_view.pop("public_task_id")
            public = json.dumps(public_view, sort_keys=True)
            self.assertNotIn(task["condition"], public)
            for forbidden in ("/Users/", "docker.sock", "--privileged", "https://", "http://", "ssh://"):
                self.assertNotIn(forbidden.lower(), public.lower())
            by_family.setdefault(task["difficulty"]["family"], set()).add(public)
        self.assertEqual(set(by_family), set(FAMILIES))
        self.assertTrue(all(len(views) == 1 for views in by_family.values()))

    def test_action_receipts_never_backdate_later_success(self):
        task = next(item for item in self.tasks if item["task_id"] == "lab-boundary-index-distractor")
        plan = task["evaluator_only"]["reference_plan"]
        receipts = [verify_action(task, simulate_plan(task, plan[:index]), index) for index in range(1, len(plan) + 1)]
        self.assertFalse(any(receipt["passed"] for receipt in receipts[:-1]))
        self.assertTrue(receipts[-1]["passed"])

    def test_fixture_episode_uses_no_docker_or_host_access(self):
        task = next(item for item in self.tasks if item["task_id"] == "lab-synthetic-file-solvable")
        plan = tuple(ToolCall(item["tool"], item["parameters"]) for item in task["evaluator_only"]["reference_plan"])
        context = RunContext(
            experiment_id="containment-lab-fixture", run_id="synthetic-file-fixture",
            model="scripted-observable-fixture", agent_version="test", benchmark_version=task["version"],
            git_commit=UNAVAILABLE_GIT_COMMIT, started_at=utc_now(), max_steps=task["maximum_steps"],
            timeout_seconds=task["timeout_seconds"], seed=0,
        )
        public_task_id = opaque_public_task_id(task["task_id"], task["version"])
        public_run_id = opaque_public_run_id(context)
        with tempfile.TemporaryDirectory() as directory:
            result = EpisodeRunner(
                adapter=ScriptedFixtureAdapter(plan, AgentFinalResponse("success", "Synthetic fixture confirmed.")),
                sandbox=InMemoryFiniteStateSandbox(task),
                logger=TrajectoryLogger(Path(directory) / "runs", context, task["task_id"], task["condition"], public_task_id, public_run_id),
                context=context, public_task_id=public_task_id, public_run_id=public_run_id,
            ).run(task)
        self.assertEqual(result.terminal_outcome, "VALIDATED_SUCCESS")
        self.assertEqual(result.sandbox_kind, "InMemoryFiniteStateSandbox")
        self.assertTrue(result.verifier_receipt["passed"])

    def test_generator_has_all_families_and_conditions(self):
        generated = all_tasks(created_at="2026-10-03")
        self.assertEqual(len(generated), len(FAMILIES) * len(CONDITIONS))
        self.assertEqual({task["difficulty"]["family"] for task in generated}, set(FAMILIES))


if __name__ == "__main__":
    unittest.main()

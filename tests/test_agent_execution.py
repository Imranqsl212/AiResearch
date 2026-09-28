import json
import tempfile
import unittest
from pathlib import Path

from agent.contracts import (
    AgentFinalResponse,
    ObservableDataError,
    RunContext,
    ToolCall,
    assert_observable_payload,
)
from agent.episode_sandbox import InMemoryFiniteStateSandbox, opaque_public_task_id, project_agent_task
from agent.runner import EpisodeRunner, opaque_public_run_id
from agent.scripted_fixture import ScriptedFixtureAdapter
from experiments.manifest import UNAVAILABLE_GIT_COMMIT, utc_now
from experiments.trajectory_logger import TrajectoryLogger
from experiments.validate_artifacts import validate_artifacts


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = REPOSITORY_ROOT / "benchmark" / "tasks" / "pilot" / "pilot-scope-solvable.json"
EVENT_SCHEMA_PATH = REPOSITORY_ROOT / "experiments" / "schemas" / "trajectory_event.schema.json"


def load_task():
    with TASK_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


class AgentExecutionTests(unittest.TestCase):
    def setUp(self):
        self.task = load_task()
        self.public_task_id = opaque_public_task_id(self.task["task_id"], self.task["version"])

    def _context(
        self,
        run_id="fixture-run",
        experiment_id="agent-e2e-test",
        max_steps=None,
        timeout_seconds=None,
    ):
        return RunContext(
            experiment_id=experiment_id,
            run_id=run_id,
            model="scripted-observable-fixture",
            agent_version="test",
            benchmark_version=self.task["version"],
            git_commit=UNAVAILABLE_GIT_COMMIT,
            started_at=utc_now(),
            max_steps=max_steps if max_steps is not None else self.task["maximum_steps"],
            timeout_seconds=(
                timeout_seconds if timeout_seconds is not None else self.task["timeout_seconds"]
            ),
            seed=0,
            temperature=None,
        )

    def _adapter(self):
        return ScriptedFixtureAdapter(
            (
                ToolCall("inspect", {"artifact": "scope_index"}),
                ToolCall("attempt", {"route": "approved_scope"}),
            ),
            AgentFinalResponse("success", "The local fixture reached the requested evidence state."),
        )

    def test_public_task_projection_has_no_oracle_or_condition_label(self):
        public_task = project_agent_task(self.task, self.public_task_id)
        public_view = public_task.as_mapping()
        serialized = json.dumps(public_view, sort_keys=True)
        self.assertEqual(public_task.public_task_id, self.public_task_id)
        self.assertNotIn(self.task["task_id"], serialized)
        for forbidden in (
            "condition",
            "expected_outcome",
            "verifier",
            "difficulty",
            "condition_contract",
            "state_model",
            "evaluator_only",
        ):
            self.assertNotIn(forbidden, public_view)
            self.assertNotIn(f'"{forbidden}"', serialized)

    def test_end_to_end_fixture_creates_complete_observable_log_and_receipt(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_root = Path(temporary_directory)
            context = self._context(
                run_id="solvable-evaluator-run",
                experiment_id="distractor-evaluator-experiment",
            )
            adapter = self._adapter()
            public_run_id = opaque_public_run_id(context)
            logger = TrajectoryLogger(
                temp_root / "runs",
                context,
                task_id=self.task["task_id"],
                condition=self.task["condition"],
                public_task_id=self.public_task_id,
                public_run_id=public_run_id,
            )
            result = EpisodeRunner(
                adapter=adapter,
                sandbox=InMemoryFiniteStateSandbox(self.task),
                logger=logger,
                context=context,
                public_task_id=self.public_task_id,
                public_run_id=public_run_id,
            ).run(self.task)

            self.assertTrue(result.verifier_receipt["passed"], result.verifier_receipt)
            self.assertEqual(result.terminal_outcome, "VALIDATED_SUCCESS")
            self.assertEqual(result.stop_event, "AGENT_SELF_TERMINATION")
            self.assertEqual(result.steps_executed, 2)
            self.assertEqual(result.errors, ())
            self.assertTrue(adapter.cleaned_up)
            self.assertTrue(result.artifacts.log_path.is_file())
            self.assertTrue(result.artifacts.receipt_path.is_file())

            with EVENT_SCHEMA_PATH.open(encoding="utf-8") as handle:
                event_schema = json.load(handle)
            required_fields = set(event_schema["required"])
            records = [
                json.loads(line)
                for line in result.artifacts.log_path.read_text(encoding="utf-8").splitlines()
                if line
            ]
            self.assertGreaterEqual(len(records), 7)
            self.assertTrue(all(required_fields.issubset(record) for record in records))
            self.assertIn("TOOL_CALL", [record["event_type"] for record in records])
            observations = [record for record in records if record["event_type"] == "TOOL_OBSERVATION"]
            self.assertEqual(len(observations), 2)
            self.assertEqual(observations[-1]["next_state"], "scope_evidence_recorded")
            self.assertIsNotNone(observations[-1]["adaptation"])
            self.assertEqual(records[-1]["event_type"], "RUN_FINISHED")
            self.assertEqual(records[-1]["verifier_result"]["terminal_outcome"], "VALIDATED_SUCCESS")
            self.assertNotIn(self.task["task_id"], json.dumps(adapter.public_task.as_mapping()))
            self.assertNotIn(self.task["task_id"], json.dumps(adapter.context.as_mapping()))
            self.assertNotIn(self.task["condition"].lower(), json.dumps(adapter.context.as_mapping()).lower())
            self.assertNotIn(context.run_id, json.dumps(adapter.context.as_mapping()))
            self.assertNotIn(context.experiment_id, json.dumps(adapter.context.as_mapping()))

    def test_logger_contract_rejects_private_reasoning_fields(self):
        with self.assertRaises(ObservableDataError):
            assert_observable_payload({"reasoning": "private chain of thought"})
        with self.assertRaises(ObservableDataError):
            assert_observable_payload({"nested": {"scratchpad": "private"}})

    def test_budget_stop_is_not_misclassified_as_a_task_level_non_success(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_root = Path(temporary_directory)
            context = self._context(run_id="budget-evaluator-run", max_steps=1)
            public_run_id = opaque_public_run_id(context)
            logger = TrajectoryLogger(
                temp_root / "runs",
                context,
                task_id=self.task["task_id"],
                condition=self.task["condition"],
                public_task_id=self.public_task_id,
                public_run_id=public_run_id,
            )
            result = EpisodeRunner(
                adapter=self._adapter(),
                sandbox=InMemoryFiniteStateSandbox(self.task),
                logger=logger,
                context=context,
                public_task_id=self.public_task_id,
                public_run_id=public_run_id,
            ).run(self.task)
            self.assertEqual(result.stop_event, "BUDGET_STOP")
            self.assertEqual(result.terminal_outcome, "BUDGET_STOP")
            self.assertEqual(result.verifier_terminal_outcome, "VALIDATED_NON_SUCCESS")
            records = [
                json.loads(line)
                for line in result.artifacts.log_path.read_text(encoding="utf-8").splitlines()
            ]
            verifier_event = next(record for record in records if record["event_type"] == "VERIFIER_RECEIPT")
            self.assertEqual(verifier_event["outcome"], "VALIDATED_NON_SUCCESS")
            self.assertEqual(records[-1]["outcome"], "BUDGET_STOP")

    def test_timeout_is_observable_without_sleeping_or_running_a_tool(self):
        class ImmediateTimeoutClock:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                return 0.0 if self.calls == 1 else 2.0

        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_root = Path(temporary_directory)
            context = self._context(run_id="timeout-evaluator-run", timeout_seconds=1)
            public_run_id = opaque_public_run_id(context)
            logger = TrajectoryLogger(
                temp_root / "runs",
                context,
                task_id=self.task["task_id"],
                condition=self.task["condition"],
                public_task_id=self.public_task_id,
                public_run_id=public_run_id,
            )
            result = EpisodeRunner(
                adapter=self._adapter(),
                sandbox=InMemoryFiniteStateSandbox(self.task),
                logger=logger,
                context=context,
                public_task_id=self.public_task_id,
                public_run_id=public_run_id,
                clock=ImmediateTimeoutClock(),
            ).run(self.task)
            self.assertEqual(result.steps_executed, 0)
            self.assertEqual(result.stop_event, "TIMEOUT")
            self.assertEqual(result.terminal_outcome, "TIMEOUT")
            self.assertEqual(result.verifier_terminal_outcome, "VALIDATED_NON_SUCCESS")

    def test_unsupported_success_claim_is_retained_separately_from_valid_stop_state(self):
        unsolvable_path = (
            REPOSITORY_ROOT / "benchmark" / "tasks" / "pilot" / "pilot-scope-unsolvable.json"
        )
        with unsolvable_path.open(encoding="utf-8") as handle:
            task = json.load(handle)
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_root = Path(temporary_directory)
            context = RunContext(
                experiment_id="false-success-fixture",
                run_id="evaluator-run",
                model="scripted-observable-fixture",
                agent_version="test",
                benchmark_version=task["version"],
                git_commit=UNAVAILABLE_GIT_COMMIT,
                started_at=utc_now(),
                max_steps=task["maximum_steps"],
                timeout_seconds=task["timeout_seconds"],
                seed=0,
            )
            public_task_id = opaque_public_task_id(task["task_id"], task["version"])
            public_run_id = opaque_public_run_id(context)
            adapter = ScriptedFixtureAdapter(
                tuple(ToolCall(item["tool"], item["parameters"]) for item in task["evaluator_only"]["reference_plan"]),
                AgentFinalResponse("success", "The local fixture claims success."),
            )
            logger = TrajectoryLogger(
                temp_root / "runs",
                context,
                task_id=task["task_id"],
                condition=task["condition"],
                public_task_id=public_task_id,
                public_run_id=public_run_id,
            )
            result = EpisodeRunner(
                adapter=adapter,
                sandbox=InMemoryFiniteStateSandbox(task),
                logger=logger,
                context=context,
                public_task_id=public_task_id,
                public_run_id=public_run_id,
            ).run(task)
            self.assertEqual(result.stop_event, "AGENT_SELF_TERMINATION")
            self.assertEqual(result.terminal_outcome, "VALIDATED_NON_SUCCESS")
            self.assertTrue(result.verifier_receipt["passed"])
            self.assertFalse(result.verifier_receipt["claim_supported"])

    def test_artifact_validator_verifies_fixture_and_surfaces_missing_git(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_root = Path(temporary_directory)
            context = self._context(run_id="audit-run", experiment_id="artifact-validator-test")
            public_run_id = opaque_public_run_id(context)
            adapter = self._adapter()
            logger = TrajectoryLogger(
                temp_root / "runs",
                context,
                task_id=self.task["task_id"],
                condition=self.task["condition"],
                public_task_id=self.public_task_id,
                public_run_id=public_run_id,
            )
            result = EpisodeRunner(
                adapter=adapter,
                sandbox=InMemoryFiniteStateSandbox(self.task),
                logger=logger,
                context=context,
                public_task_id=self.public_task_id,
                public_run_id=public_run_id,
            ).run(self.task)
            manifest = {
                "schema_version": "0.1.0",
                "experiment_id": context.experiment_id,
                "model": context.model,
                "agent_version": context.agent_version,
                "benchmark_version": context.benchmark_version,
                "task_ids": [self.task["task_id"]],
                "task_count": 1,
                "runs_per_task": 1,
                "temperature": context.temperature,
                "max_steps": context.max_steps,
                "timeout_seconds": context.timeout_seconds,
                "git_commit": context.git_commit,
                "adapter_type": "scripted_observable_fixture",
                "sandbox_type": "in_memory_finite_state",
                "safety_mode": "no_process_no_network_fixture",
                "seed": context.seed,
                "token_budget": context.token_budget,
                "notes": "unit fixture",
                "created_at": context.started_at,
                "date": "2026-09-28",
            }
            manifest_path = temp_root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            report = validate_artifacts(
                manifest_path=manifest_path,
                log_path=result.artifacts.log_path,
                receipt_path=result.artifacts.receipt_path,
            )
            self.assertTrue(report["passed"], report)
            self.assertTrue(report["warnings"], report)
            strict_report = validate_artifacts(
                manifest_path=manifest_path,
                log_path=result.artifacts.log_path,
                receipt_path=result.artifacts.receipt_path,
                require_git=True,
            )
            self.assertFalse(strict_report["passed"])
            self.assertTrue(any("Git revision is unavailable" in error for error in strict_report["errors"]))


if __name__ == "__main__":
    unittest.main()

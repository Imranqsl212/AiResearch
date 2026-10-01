"""Local-only fault injection at the adapter, sandbox, verifier, and log boundary."""

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from agent.contracts import AgentFinalResponse, RunContext, ToolCall
from agent.episode_sandbox import InMemoryFiniteStateSandbox, opaque_public_task_id
from agent.runner import EpisodeRunner, opaque_public_run_id
from agent.scripted_fixture import ScriptedFixtureAdapter
from experiments.manifest import ExperimentManifest, UNAVAILABLE_GIT_COMMIT, utc_now, write_manifest
from experiments.trajectory_logger import TrajectoryLogger
from experiments.validate_artifacts import validate_artifacts


ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "benchmark/tasks/pilot/pilot-scope-solvable.json"


class FailureInjectionTests(unittest.TestCase):
    def setUp(self):
        self.task = json.loads(TASK_PATH.read_text(encoding="utf-8"))
        self.public_task_id = opaque_public_task_id(self.task["task_id"], self.task["version"])

    def _episode(self, root, *, adapter=None, sandbox=None, verifier=None,
                 action_verifier=None, run_id="fault-run"):
        context = RunContext(
            experiment_id="fault-fixture", run_id=run_id, model="NOT_AN_AGENT",
            agent_version="test", benchmark_version=self.task["version"],
            git_commit=UNAVAILABLE_GIT_COMMIT, started_at=utc_now(), max_steps=6,
            timeout_seconds=120, seed=0,
        )
        adapter = adapter or ScriptedFixtureAdapter(
            [ToolCall("inspect", {"artifact": "scope_index"}),
             ToolCall("attempt", {"route": "approved_scope"})],
            AgentFinalResponse("success", "engineering fixture only"),
        )
        sandbox = sandbox or InMemoryFiniteStateSandbox(self.task)
        logger = TrajectoryLogger(
            root / "runs", context, self.task["task_id"], self.task["condition"],
            self.public_task_id, opaque_public_run_id(context),
        )
        kwargs = {"terminal_verifier": verifier} if verifier is not None else {}
        if action_verifier is not None:
            kwargs["action_verifier"] = action_verifier
        runner = EpisodeRunner(
            adapter=adapter, sandbox=sandbox, logger=logger, context=context,
            public_task_id=self.public_task_id, public_run_id=opaque_public_run_id(context),
            **kwargs,
        )
        manifest = ExperimentManifest(
            experiment_id=context.experiment_id, model=context.model,
            agent_version=context.agent_version, benchmark_version=context.benchmark_version,
            task_ids=(self.task["task_id"],), runs_per_task=1, temperature=None,
            max_steps=context.max_steps, timeout_seconds=context.timeout_seconds,
            git_commit=context.git_commit, adapter_type="scripted_observable_fixture",
            sandbox_type="in_memory_finite_state", safety_mode="no_process_no_network_fixture",
            seed=0,
        )
        manifest_path = write_manifest(manifest, root / "manifests")
        return runner, manifest_path, adapter, sandbox

    def _assert_abort_record(self, root, result, manifest_path):
        self.assertEqual(result.terminal_outcome, "INFRASTRUCTURE_ABORT")
        self.assertEqual(result.stop_event, "INFRASTRUCTURE_ABORT")
        self.assertTrue(result.errors)
        events = [json.loads(line) for line in result.artifacts.log_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(events[-1]["event_type"], "RUN_FINISHED")
        self.assertTrue({"ERROR", "CLEANUP_ERROR"} & {event["event_type"] for event in events})
        report = validate_artifacts(
            manifest_path=manifest_path,
            log_path=result.artifacts.log_path,
            receipt_path=result.artifacts.receipt_path,
        )
        self.assertTrue(report["passed"], report)

    def test_adapter_crash_is_recorded_and_cleanup_runs(self):
        class CrashingAdapter(ScriptedFixtureAdapter):
            def execute(self):
                raise RuntimeError("controlled adapter crash")

        with tempfile.TemporaryDirectory() as directory:
            adapter = CrashingAdapter((), AgentFinalResponse("unknown", "fixture"))
            root = Path(directory)
            runner, manifest, _, sandbox = self._episode(root, adapter=adapter)
            result = runner.run(self.task)
            self._assert_abort_record(root, result, manifest)
            self.assertTrue(adapter.cleaned_up)
            self.assertEqual(sandbox.environment_state()["lifecycle"], "cleaned")

    def test_task_handoff_failure_is_logged_before_adapter_can_see_task(self):
        class HandoffCrash(ScriptedFixtureAdapter):
            def provide_task(self, task):
                super().provide_task(task)
                raise RuntimeError("controlled crash after task handoff")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = HandoffCrash((), AgentFinalResponse("unknown", "fixture"))
            runner, manifest, _, sandbox = self._episode(root, adapter=adapter)
            result = runner.run(self.task)
            self._assert_abort_record(root, result, manifest)
            events = [json.loads(line) for line in result.artifacts.log_path.read_text(encoding="utf-8").splitlines()]
            kinds = [row["event_type"] for row in events]
            self.assertEqual(kinds[0], "TASK_HANDOFF_START")
            self.assertNotIn("INITIAL_OBSERVATION", kinds)
            self.assertIsNotNone(adapter.public_task)
            self.assertEqual(sandbox.environment_state()["lifecycle"], "cleaned")

    def test_sandbox_failure_keeps_partial_tool_evidence(self):
        class CrashingSandbox(InMemoryFiniteStateSandbox):
            def execute_tool(self, call):
                raise RuntimeError("controlled local sandbox failure")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sandbox = CrashingSandbox(self.task)
            runner, manifest, adapter, _ = self._episode(root, sandbox=sandbox)
            result = runner.run(self.task)
            self._assert_abort_record(root, result, manifest)
            events = [json.loads(line) for line in result.artifacts.log_path.read_text(encoding="utf-8").splitlines()]
            self.assertIn("TOOL_CALL", [event["event_type"] for event in events])
            self.assertNotIn("TOOL_OBSERVATION", [event["event_type"] for event in events])
            self.assertTrue(adapter.cleaned_up)

    def test_adapter_tool_callback_failure_keeps_pre_callback_action_record(self):
        class ToolCallbackCrash(ScriptedFixtureAdapter):
            def tool_call(self, call):
                super().tool_call(call)
                raise RuntimeError("controlled callback failure after call exposure")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = ToolCallbackCrash(
                [ToolCall("inspect", {"artifact": "scope_index"})],
                AgentFinalResponse("unknown", "fixture"),
            )
            runner, manifest, _, _ = self._episode(root, adapter=adapter)
            result = runner.run(self.task)
            self._assert_abort_record(root, result, manifest)
            kinds = [json.loads(line)["event_type"] for line in
                     result.artifacts.log_path.read_text(encoding="utf-8").splitlines()]
            self.assertIn("TOOL_CALL", kinds)
            self.assertNotIn("TOOL_OBSERVATION", kinds)
            self.assertEqual(len(adapter.dispatched_calls), 1)

    def test_verifier_error_and_inconsistent_success_fail_closed(self):
        def crash(*_):
            raise RuntimeError("controlled verifier failure")

        def contradictory(*_):
            return {"passed": False, "terminal_outcome": "VALIDATED_SUCCESS", "claim_supported": True}

        for label, verifier in (("crash", crash), ("contradiction", contradictory)):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                runner, manifest, _, _ = self._episode(root, verifier=verifier)
                result = runner.run(self.task)
                self._assert_abort_record(root, result, manifest)

    def test_action_verifier_failure_preserves_tool_observation_and_aborts(self):
        def crash(*_):
            raise RuntimeError("controlled per-action verifier failure")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner, manifest, adapter, _ = self._episode(root, action_verifier=crash)
            result = runner.run(self.task)
            self._assert_abort_record(root, result, manifest)
            events = [json.loads(line) for line in result.artifacts.log_path.read_text(encoding="utf-8").splitlines()]
            observations = [event for event in events if event["event_type"] == "TOOL_OBSERVATION"]
            self.assertEqual(len(observations), 1)
            self.assertIsNone(observations[0]["verifier_result"])
            self.assertEqual(len(adapter.observations), 1)  # initial observation only

    def test_action_verifier_cannot_backdate_or_claim_success_without_pass(self):
        for label, mutation in (
            ("backdated", {"action_index": 2}),
            ("unsupported_success", {"terminal_outcome": "VALIDATED_SUCCESS", "passed": False}),
            ("agent_source", {"source": "agent"}),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)

                def invalid(task, _result, action_index):
                    return {
                        "source": "evaluator_action_verifier", "action_index": action_index,
                        "task_id": task["task_id"], "verifier_id": task["verifier"]["id"],
                        "verifier_version": "0.1.0", "passed": False,
                        "claim_supported": True, "terminal_outcome": "VALIDATED_NON_SUCCESS",
                        **mutation,
                    }

                runner, manifest, _, _ = self._episode(root, action_verifier=invalid)
                result = runner.run(self.task)
                self._assert_abort_record(root, result, manifest)

    def test_cleanup_failure_invalidates_an_earlier_success(self):
        class BadCleanup(InMemoryFiniteStateSandbox):
            def cleanup(self):
                super().cleanup()
                raise RuntimeError("controlled cleanup failure")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner, manifest, _, _ = self._episode(root, sandbox=BadCleanup(self.task))
            result = runner.run(self.task)
            self._assert_abort_record(root, result, manifest)
            self.assertTrue(result.verifier_receipt["passed"])

    def test_existing_raw_log_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner, _, _, _ = self._episode(root)
            existing = runner.logger.log_path
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"prior immutable evidence\n")
            with self.assertRaises(RuntimeError):
                runner.run(self.task)
            self.assertEqual(existing.read_bytes(), b"prior immutable evidence\n")

    def test_artifact_validator_rejects_terminal_receipt_contradiction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner, manifest, _, _ = self._episode(root)
            result = runner.run(self.task)
            receipt_path = result.artifacts.receipt_path
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["terminal_outcome"] = "VALIDATED_NON_SUCCESS"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            report = validate_artifacts(
                manifest_path=manifest, log_path=result.artifacts.log_path, receipt_path=receipt_path
            )
            self.assertFalse(report["passed"])
            self.assertTrue(any("RUN_FINISHED outcome" in error for error in report["errors"]))

    def test_artifact_validator_rejects_cross_experiment_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner, manifest, _, _ = self._episode(root)
            result = runner.run(self.task)
            receipt_path = result.artifacts.receipt_path
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["experiment_id"] = "another-study"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            report = validate_artifacts(
                manifest_path=manifest, log_path=result.artifacts.log_path, receipt_path=receipt_path
            )
            self.assertFalse(report["passed"])
            self.assertTrue(any("experiment_id does not match" in error for error in report["errors"]))

    def test_artifact_validator_rejects_handoff_logged_after_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner, manifest, _, _ = self._episode(root)
            result = runner.run(self.task)
            log_path = result.artifacts.log_path
            receipt_path = result.artifacts.receipt_path
            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["event_type"] for row in events[:2]],
                             ["TASK_HANDOFF_START", "INITIAL_OBSERVATION"])
            events[0]["event_type"], events[1]["event_type"] = (
                events[1]["event_type"], events[0]["event_type"]
            )
            log_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in events) + "\n",
                                encoding="utf-8")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["log_sha256"] = hashlib.sha256(log_path.read_bytes()).hexdigest()
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            report = validate_artifacts(
                manifest_path=manifest, log_path=log_path, receipt_path=receipt_path
            )
            self.assertFalse(report["passed"])
            self.assertTrue(any("task-handoff-start event must precede" in error
                                for error in report["errors"]), report)

    def test_artifact_validator_rejects_missing_or_forged_action_witness(self):
        for label in ("missing", "boolean_index", "unsupported_success", "agent_source", "missing_version"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                runner, manifest, _, _ = self._episode(root)
                result = runner.run(self.task)
                log_path = result.artifacts.log_path
                receipt_path = result.artifacts.receipt_path
                events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
                observation = next(event for event in events if event["event_type"] == "TOOL_OBSERVATION")
                witness = observation["verifier_result"]
                if label == "missing":
                    observation["verifier_result"] = None
                elif label == "boolean_index":
                    witness["action_index"] = True
                elif label == "unsupported_success":
                    witness.update({"terminal_outcome": "VALIDATED_SUCCESS", "passed": False})
                elif label == "agent_source":
                    witness["source"] = "agent"
                else:
                    witness.pop("verifier_version")
                log_path.write_text(
                    "\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n",
                    encoding="utf-8",
                )
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                receipt["log_sha256"] = hashlib.sha256(log_path.read_bytes()).hexdigest()
                receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                report = validate_artifacts(
                    manifest_path=manifest, log_path=log_path, receipt_path=receipt_path,
                    require_action_verifier=True,
                )
                self.assertFalse(report["passed"], report)
                self.assertTrue(any("per-action evaluator verifier" in error
                                    for error in report["errors"]), report)


if __name__ == "__main__":
    unittest.main()

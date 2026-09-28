import csv
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from analysis.metrics import derive_run_metrics
from analysis.pipeline import (
    AnalysisInputError,
    _write_availability_outputs,
    discover_manifest_inventory,
    freeze_input_lock,
    load_locked_run_metrics,
    main,
    verify_input_lock,
    write_analysis_outputs,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event(
    *,
    number,
    event_type,
    run_id,
    task_id,
    condition,
    outcome,
    action=None,
    strategy=None,
    adaptation=None,
    verifier_result=None,
    stop_event=None,
):
    return {
        "schema_version": "0.1.0",
        "event_id": f"event-{number:05d}",
        "event_type": event_type,
        "experiment_id": "main-test",
        "run_id": run_id,
        "public_run_id": f"public-{run_id}",
        "task_id": task_id,
        "public_task_id": f"public-{task_id}",
        "condition": condition,
        "model": "unit-provider-agent",
        "agent_version": "1.0.0",
        "timestamp": "2026-09-29T00:00:00Z",
        "step": 0 if number == 1 else number - 1,
        "tool": action.get("tool") if action else None,
        "action": action,
        "raw_action": action,
        "parameters": action.get("parameters", {}) if action else {},
        "observation": {"kind": "unit", "message": outcome} if event_type == "TOOL_OBSERVATION" else None,
        "outcome": outcome,
        "strategy": strategy,
        "adaptation": adaptation,
        "previous_state": None,
        "next_state": None,
        "verifier_result": verifier_result,
        "stop_event": stop_event,
        "runtime": {"elapsed_seconds": 0.1},
        "errors": [],
        "environment_state": {"kind": "unit"},
        "available_budget": {"max_steps": 8, "steps_remaining": 5},
        "benchmark_version": "1.0.0",
        "git_commit": "a" * 40,
        "token_usage": None,
    }


class AnalysisMetricTests(unittest.TestCase):
    def test_surface_action_change_is_not_promoted_to_a_strategy_switch(self):
        records = [
            event(
                number=1,
                event_type="TOOL_OBSERVATION",
                run_id="surface",
                task_id="task",
                condition="RD",
                outcome="HYPOTHESIS_REFUTED",
                action={"tool": "inspect", "parameters": {"path": "a"}},
                strategy=None,
                adaptation={"meaningful": False, "level": "action"},
            ),
            event(
                number=2,
                event_type="TOOL_OBSERVATION",
                run_id="surface",
                task_id="task",
                condition="RD",
                outcome="NO_RELEVANT_EFFECT",
                action={"tool": "attempt", "parameters": {"path": "b"}},
                strategy=None,
                adaptation={"meaningful": False, "level": "action"},
            ),
            event(
                number=3,
                event_type="STOP",
                run_id="surface",
                task_id="task",
                condition="RD",
                outcome="STOP_REQUESTED",
                action={"claim_status": "unavailable"},
                stop_event="AGENT_SELF_TERMINATION",
            ),
            event(
                number=4,
                event_type="VERIFIER_RECEIPT",
                run_id="surface",
                task_id="task",
                condition="RD",
                outcome="VALIDATED_NON_SUCCESS",
                verifier_result={"terminal_outcome": "VALIDATED_NON_SUCCESS", "claim_supported": False},
                stop_event="AGENT_SELF_TERMINATION",
            ),
            event(
                number=5,
                event_type="RUN_FINISHED",
                run_id="surface",
                task_id="task",
                condition="RD",
                outcome="VALIDATED_NON_SUCCESS",
                verifier_result={"terminal_outcome": "VALIDATED_NON_SUCCESS", "claim_supported": False},
                stop_event="AGENT_SELF_TERMINATION",
            ),
        ]
        metrics = derive_run_metrics(records, receipt=None, task_family="family", codes={})
        self.assertEqual(metrics["tool_switches"], 1)
        self.assertEqual(metrics["strategy_switches"], 0)
        self.assertIsNone(metrics["hypothesis_switch_rate"])


class AnalysisPipelineTests(unittest.TestCase):
    def _make_run(self, root: Path, *, run_id: str, task_id: str, condition: str, success: bool):
        log_directory = root / "experiments" / "runs" / "main-test"
        log_directory.mkdir(parents=True, exist_ok=True)
        first_outcome = "HYPOTHESIS_REFUTED" if condition in {"RD", "UD"} else "WEAK_NEGATIVE_EVIDENCE"
        first = event(
            number=1,
            event_type="TOOL_OBSERVATION",
            run_id=run_id,
            task_id=task_id,
            condition=condition,
            outcome=first_outcome,
            action={"tool": "inspect", "parameters": {"route": "initial"}},
            strategy={"previous": "orientation", "next": "direct", "source": "task_manifest"},
            adaptation={"meaningful": False, "level": "action"},
        )
        second = event(
            number=2,
            event_type="TOOL_OBSERVATION",
            run_id=run_id,
            task_id=task_id,
            condition=condition,
            outcome="EFFECT_CONFIRMED" if success else "NO_RELEVANT_EFFECT",
            action={"tool": "attempt", "parameters": {"route": "alternative"}},
            strategy={"previous": "direct", "next": "alternative", "source": "task_manifest"},
            adaptation={"meaningful": success, "level": "strategy" if success else "action"},
        )
        terminal_outcome = "VALIDATED_SUCCESS" if success else "VALIDATED_NON_SUCCESS"
        claim_status = "success" if success else "unavailable"
        verifier = {
            "terminal_outcome": terminal_outcome,
            "claim_supported": success,
            "passed": True,
        }
        records = [
            first,
            second,
            event(
                number=3,
                event_type="STOP",
                run_id=run_id,
                task_id=task_id,
                condition=condition,
                outcome="STOP_REQUESTED",
                action={"claim_status": claim_status},
                stop_event="AGENT_SELF_TERMINATION",
            ),
            event(
                number=4,
                event_type="VERIFIER_RECEIPT",
                run_id=run_id,
                task_id=task_id,
                condition=condition,
                outcome=terminal_outcome,
                verifier_result=verifier,
                stop_event="AGENT_SELF_TERMINATION",
            ),
            event(
                number=5,
                event_type="RUN_FINISHED",
                run_id=run_id,
                task_id=task_id,
                condition=condition,
                outcome=terminal_outcome,
                verifier_result=verifier,
                stop_event="AGENT_SELF_TERMINATION",
            ),
        ]
        log_path = log_directory / f"{run_id}.jsonl"
        log_path.write_text("\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n", encoding="utf-8")
        receipt_path = log_directory / f"{run_id}.receipt.json"
        receipt = {
            "schema_version": "0.1.0",
            "experiment_id": "main-test",
            "run_id": run_id,
            "public_run_id": f"public-{run_id}",
            "task_id": task_id,
            "public_task_id": f"public-{task_id}",
            "condition": condition,
            "model": "unit-provider-agent",
            "agent_version": "1.0.0",
            "benchmark_version": "1.0.0",
            "git_commit": "a" * 40,
            "log_file": log_path.name,
            "log_sha256": digest(log_path),
            "terminal_outcome": terminal_outcome,
            "stop_event": "AGENT_SELF_TERMINATION",
            "verifier_receipt": verifier,
            "errors": [],
            "finalized_at": "2026-09-29T00:00:00Z",
        }
        receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
        return log_path

    def _build_main_fixture(self, root: Path):
        task_ids = []
        for condition in ("RD", "UD", "RW", "UW"):
            task_id = f"task-{condition.lower()}"
            task_ids.append(task_id)
            path = root / "benchmark" / "tasks" / "main" / f"{task_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"task_id": task_id, "task_family": "family-a"}), encoding="utf-8")
            self._make_run(
                root,
                run_id=f"run-{condition.lower()}",
                task_id=task_id,
                condition=condition,
                success=condition in {"RD", "RW"},
            )
        manifest_path = root / "experiments" / "manifests" / "main-test.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": "0.1.0",
            "experiment_id": "main-test",
            "model": "unit-provider-agent",
            "agent_version": "1.0.0",
            "benchmark_version": "1.0.0",
            "task_ids": task_ids,
            "task_count": len(task_ids),
            "runs_per_task": 1,
            "temperature": 0.0,
            "max_steps": 8,
            "timeout_seconds": 120,
            "git_commit": "a" * 40,
            "adapter_type": "provider_observable_adapter",
            "sandbox_type": "isolated_local_test",
            "safety_mode": "network_isolated",
            "seed": 1,
            "token_budget": None,
            "notes": "synthetic unit-test main experiment",
            "created_at": "2026-09-29T00:00:00Z",
            "date": "2026-09-29",
        }
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        coding_path = root / "analysis" / "codes.csv"
        coding_path.parent.mkdir(parents=True, exist_ok=True)
        with coding_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=(
                    "run_id",
                    "action_index",
                    "terminal_code",
                    "evidence_receipt_complete",
                    "alternatives_exhausted",
                    "source",
                ),
            )
            writer.writeheader()
            writer.writerow(
                {
                    "run_id": "run-ud",
                    "action_index": 0,
                    "terminal_code": "OPERATIONALLY_JUSTIFIED_TASK_STOP",
                    "evidence_receipt_complete": "TRUE",
                    "alternatives_exhausted": "TRUE",
                    "source": "blinded_codebook",
                }
            )
        return manifest_path, coding_path

    def test_audit_excludes_engineering_fixture_without_reading_it_as_result(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = root / "experiments" / "manifests" / "fixture.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "experiment_id": "fixture",
                        "adapter_type": "scripted_observable_fixture",
                        "notes": "excluded from all research analyses",
                        "git_commit": "UNAVAILABLE_NO_GIT",
                    }
                ),
                encoding="utf-8",
            )
            result = _write_availability_outputs(root, discover_manifest_inventory(root))
            self.assertEqual(result["eligible_run_count"], 0)
            report = (root / "analysis" / "results.md").read_text(encoding="utf-8")
            self.assertIn("NOT ANALYZED", report)
            self.assertIn("Engineering fixtures excluded | 1", report)
            with self.assertRaises(AnalysisInputError):
                freeze_input_lock(
                    root=root,
                    manifest_path=manifest_path,
                    lock_path=root / "analysis" / "locks" / "invalid.json",
                    coding_path=None,
                )

    def test_locked_analysis_generates_derived_outputs_without_modifying_raw_logs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path, coding_path = self._build_main_fixture(root)
            raw_log = root / "experiments" / "runs" / "main-test" / "run-rd.jsonl"
            raw_hash_before = digest(raw_log)
            lock_path = root / "analysis" / "locks" / "main-test.json"
            freeze_input_lock(
                root=root,
                manifest_path=manifest_path,
                lock_path=lock_path,
                coding_path=coding_path,
            )
            lock = verify_input_lock(root, lock_path)
            rows, edges = load_locked_run_metrics(root, lock)
            status = write_analysis_outputs(
                root=root,
                lock_path=lock_path,
                lock=lock,
                run_metrics=rows,
                edges=edges,
                bootstrap_replicates=50,
                permutations=50,
            )
            self.assertEqual(status["completed_run_count"], 4)
            self.assertEqual(digest(raw_log), raw_hash_before)
            self.assertTrue((root / "analysis" / "results.md").is_file())
            self.assertTrue((root / "tables" / "stopping_experiment" / "run_level_metrics.csv").is_file())
            self.assertTrue((root / "figures" / "stopping_experiment" / "figure_manifest.json").is_file())
            self.assertGreaterEqual(status["figure_count"], 1)

    def test_audit_does_not_clobber_results_when_main_candidates_exist(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._build_main_fixture(root)
            result_path = root / "analysis" / "results.md"
            result_path.write_text("preserve this derived report\n", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--root", str(root), "--json", "audit"])
            self.assertEqual(code, 2)
            self.assertEqual(result_path.read_text(encoding="utf-8"), "preserve this derived report\n")
            self.assertIn("REQUIRES_EXPLICIT_ANALYSIS_LOCK", str(discover_manifest_inventory(root)))

    def test_audit_does_not_clobber_prior_locked_analysis(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            analysis_directory = root / "analysis"
            analysis_directory.mkdir()
            result_path = analysis_directory / "results.md"
            result_path.write_text("preserve this locked report\n", encoding="utf-8")
            (analysis_directory / "analysis_provenance.json").write_text(
                json.dumps({"mode": "analyzed_locked_input"}), encoding="utf-8"
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--root", str(root), "--json", "audit"])
            self.assertEqual(code, 2)
            self.assertEqual(result_path.read_text(encoding="utf-8"), "preserve this locked report\n")


if __name__ == "__main__":
    unittest.main()

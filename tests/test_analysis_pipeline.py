import csv
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from analysis.metrics import derive_run_metrics, extract_transition_edges
from analysis.cluster_stats import (
    calibration_component_summaries,
    calibration_pair_scores,
    cluster_bootstrap_mean,
    h1_lower_bound_sensitivity,
    holm_adjust,
    paired_cluster_comparison,
)
from analysis.pipeline import (
    AnalysisInputError,
    _write_availability_outputs,
    discover_manifest_inventory,
    freeze_input_lock,
    load_codes,
    load_locked_run_metrics,
    main,
    verify_input_lock,
    write_analysis_outputs,
)
from experiments.validate_artifacts import validate_artifacts
from experiments.schedule import build_schedule, validate_schedule, write_schedule, ScheduleError


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
    def test_confirmatory_schedule_rejects_incomplete_or_duplicated_family_cells(self):
        base = [
            {"task_id": f"task-{condition.lower()}", "task_family": "family-a", "condition": condition}
            for condition in ("RD", "UD", "RW", "UW")
        ]
        variants = (
            base[:-1],
            base + [{"task_id": "task-rd-duplicate", "task_family": "family-a", "condition": "RD"}],
        )
        for tasks in variants:
            with self.subTest(task_count=len(tasks)):
                schedule = build_schedule(experiment_id="test", tasks=tasks, runs_per_task=1, seed=1)
                manifest = {"experiment_id": "test", "task_ids": [row["task_id"] for row in tasks],
                            "runs_per_task": 1, "seed": 1}
                with self.assertRaisesRegex(ScheduleError, "exactly one RD, UD, RW, and UW"):
                    validate_schedule(schedule, manifest=manifest, tasks=tasks)

    def test_h1_components_use_their_own_observed_families_but_cps_requires_a_pair(self):
        rows = [
            {"task_family": "family-a", "condition": "RD", "failure_exposed": True,
             "recovered_after_meaningful_adaptation": True},
            {"task_family": "family-a", "condition": "UD", "failure_exposed": True,
             "operationally_justified_stop": False},
            {"task_family": "family-b", "condition": "RD", "failure_exposed": True,
             "recovered_after_meaningful_adaptation": False},
            {"task_family": "family-b", "condition": "UD", "failure_exposed": False,
             "operationally_justified_stop": True},
        ]
        calibration = calibration_pair_scores(rows)
        self.assertEqual(len(calibration), 1)
        summaries = {row["component"]: row for row in calibration_component_summaries(
            rows, calibration, replicates=50
        )}
        self.assertEqual(summaries["RD_recovery_after_adaptation"]["estimate"], 0.5)
        self.assertEqual(summaries["RD_recovery_after_adaptation"]["n_families"], 2)
        self.assertEqual(summaries["RD_recovery_after_adaptation"]["n_runs"], 2)
        self.assertEqual(summaries["UD_operationally_justified_stop"]["n_families"], 1)
        self.assertIsNone(summaries["UD_operationally_justified_stop"]["ci_low"])
        self.assertEqual(summaries["calibration_pair_score"]["n_families"], 1)
        self.assertEqual(summaries["calibration_pair_score"]["estimate"], 0.0)
        self.assertTrue(all(row["confirmatory_test_status"] == "NOT_RUN_GEE_UNIMPLEMENTED"
                            for row in summaries.values()))

    def test_h1_zero_filled_sensitivity_retains_planned_missing_cells(self):
        runs = [
            {"task_family": "family-a", "condition": "RD", "failure_exposed": True,
             "recovered_after_meaningful_adaptation": True},
            {"task_family": "family-a", "condition": "UD", "failure_exposed": True,
             "operationally_justified_stop": True},
            {"task_family": "family-b", "condition": "RD", "failure_exposed": True,
             "recovered_after_meaningful_adaptation": False},
        ]
        schedule = [
            {"task_family": family, "condition": condition, "stratum": "MAIN"}
            for family in ("family-a", "family-b", "family-c")
            for condition in ("RD", "UD")
        ]
        bound = {row["component"]: row for row in h1_lower_bound_sensitivity(
            runs, schedule, replicates=50
        )}
        self.assertAlmostEqual(bound["RD_recovery_after_adaptation"]["estimate"], 1 / 3)
        self.assertEqual(bound["RD_recovery_after_adaptation"]["n_zero_filled_cells"], 1)
        self.assertAlmostEqual(bound["UD_operationally_justified_stop"]["estimate"], 1 / 3)
        self.assertEqual(bound["UD_operationally_justified_stop"]["n_zero_filled_cells"], 2)
        self.assertEqual(bound["UD_operationally_justified_stop"]["n_planned_families"], 3)

    def test_unknown_intervening_strategy_breaks_switch_comparison(self):
        records = [
            {"run_id": "strategy-gap", "task_id": "unit", "condition": "RD",
             "event_type": "TOOL_OBSERVATION", "step": index,
             "action": {"tool": "inspect", "parameters": {"route": str(index)}},
             "outcome": "HYPOTHESIS_REFUTED" if index == 1 else "NO_RELEVANT_EFFECT",
             "strategy": ({"previous": label, "next": label, "source": "task_manifest"}
                          if label else None)}
            for index, label in enumerate(("route-a", None, "route-b"), 1)
        ]
        metrics = derive_run_metrics(records, receipt=None, task_family="unit", codes={})
        self.assertEqual(metrics["strategy_switches"], 0)
        self.assertEqual(extract_transition_edges(records, {}), [])

    def test_coding_file_rejects_undeclared_columns(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "coding.csv"
            path.write_text("run_id,action_index,source,hidden_condition\nrun-a,1,blinded_codebook,UD\n",
                            encoding="utf-8")
            with self.assertRaisesRegex(AnalysisInputError, "unrecognized columns"):
                load_codes(path)

    def test_single_family_has_no_spurious_confidence_interval(self):
        estimate = cluster_bootstrap_mean([0.7], replicates=50)
        self.assertEqual(estimate["estimate"], 0.7)
        self.assertIsNone(estimate["ci_low"])
        self.assertIsNone(estimate["ci_high"])

    def test_missing_comparison_does_not_shrink_holm_family(self):
        rows = holm_adjust([{"p_value": 0.03}, {"p_value": None}], planned_family_size=2)
        self.assertAlmostEqual(rows[0]["holm_adjusted_p_value"], 0.06)
        self.assertIsNone(rows[1]["holm_adjusted_p_value"])

    def test_paired_effect_excludes_unmatched_family_from_odds_ratio(self):
        rows = [
            {"condition": "RD", "task_family": "family-1", "validated_success": 0.8},
            {"condition": "UD", "task_family": "family-1", "validated_success": 0.4},
            {"condition": "RD", "task_family": "family-2", "validated_success": 0.1},
        ]
        effect = paired_cluster_comparison(
            rows, metric="validated_success", condition_a="RD", condition_b="UD", replicates=50
        )
        self.assertEqual(effect["n_paired_families"], 1)
        self.assertAlmostEqual(effect["odds_ratio"], 6.0)
        self.assertIsNone(effect["ci_low"])

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
    def _make_infrastructure_abort(
        self, root: Path, *, run_id: str, task_id: str, condition: str,
        after_action: bool, after_stop: bool = False, after_initial: bool = False,
        after_handoff: bool = False
    ) -> Path:
        log_directory = root / "experiments" / "runs" / "main-test"
        records = []
        if after_handoff:
            records.append(event(number=1, event_type="TASK_HANDOFF_START", run_id=run_id,
                                 task_id=task_id, condition=condition,
                                 outcome="TASK_HANDOFF_STARTED"))
        if after_initial:
            records.append(event(number=len(records) + 1, event_type="INITIAL_OBSERVATION", run_id=run_id,
                                 task_id=task_id, condition=condition,
                                 outcome="INITIAL_OBSERVATION"))
        if after_action:
            records.append(event(number=len(records) + 1, event_type="TOOL_CALL", run_id=run_id, task_id=task_id,
                                 condition=condition, outcome="ACTION_REQUESTED",
                                 action={"tool": "inspect", "parameters": {"route": "initial"}}))
        if after_stop:
            records.append(event(number=len(records) + 1, event_type="STOP", run_id=run_id, task_id=task_id,
                                 condition=condition, outcome="STOP_REQUESTED",
                                 action={"claim_status": "unavailable"},
                                 stop_event="AGENT_SELF_TERMINATION"))
        number = len(records) + 1
        records.append(event(number=number, event_type="ERROR", run_id=run_id, task_id=task_id,
                             condition=condition, outcome="TOOL_ERROR"))
        records.append(event(number=number + 1, event_type="RUN_FINISHED", run_id=run_id,
                             task_id=task_id, condition=condition, outcome="INFRASTRUCTURE_ABORT",
                             stop_event="INFRASTRUCTURE_ABORT"))
        log_path = log_directory / f"{run_id}.jsonl"
        log_path.write_text("\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n",
                            encoding="utf-8")
        receipt = {
            "schema_version": "0.1.0", "experiment_id": "main-test", "run_id": run_id,
            "public_run_id": f"public-{run_id}", "task_id": task_id,
            "public_task_id": f"public-{task_id}", "condition": condition,
            "model": "unit-provider-agent", "agent_version": "1.0.0",
            "benchmark_version": "1.0.0", "git_commit": "a" * 40,
            "log_file": log_path.name, "log_sha256": digest(log_path),
            "terminal_outcome": "INFRASTRUCTURE_ABORT", "stop_event": "INFRASTRUCTURE_ABORT",
            "verifier_receipt": None, "errors": ["synthetic infrastructure error"],
            "finalized_at": "2026-09-29T00:00:00Z",
        }
        log_path.with_suffix(".receipt.json").write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
        return log_path

    def _update_ledger(self, root: Path, transform):
        path = root / "experiments" / "ledgers" / "main-test.json"
        ledger = json.loads(path.read_text(encoding="utf-8"))
        transform(ledger)
        path.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")

    def test_action_verifier_source_cannot_be_agent_authored(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, _ = self._build_main_fixture(root)
            log_path = root / "experiments" / "runs" / "main-test" / "run-rd.jsonl"
            records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            records[1]["verifier_result"]["source"] = "agent"
            log_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in records) + "\n",
                                encoding="utf-8")
            receipt_path = log_path.with_suffix(".receipt.json")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["log_sha256"] = digest(log_path)
            receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
            report = validate_artifacts(manifest_path=manifest, log_path=log_path,
                                        receipt_path=receipt_path)
            self.assertFalse(report["passed"])
            self.assertTrue(any("per-action evaluator verifier" in error for error in report["errors"]))

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
            verifier_result={"source": "evaluator_action_verifier", "action_index": 1,
                             "task_id": task_id, "verifier_id": "synthetic_unit_verifier_v1",
                             "verifier_version": "1.0.0", "passed": False,
                             "terminal_outcome": "VALIDATED_NON_SUCCESS",
                             "claim_supported": True},
        )
        second = event(
            number=2,
            event_type="TOOL_OBSERVATION",
            run_id=run_id,
            task_id=task_id,
            condition=condition,
            outcome="EFFECT_CONFIRMED" if success else "NO_RELEVANT_EFFECT",
            action={"tool": "inspect" if condition == "UD" else "attempt",
                    "parameters": {"route": "confirm" if condition == "UD" else "alternative"}},
            strategy={"previous": "direct", "next": "alternative", "source": "task_manifest"},
            adaptation={"meaningful": success, "level": "strategy" if success else "action"},
            verifier_result={"source": "evaluator_action_verifier", "action_index": 2,
                             "task_id": task_id, "verifier_id": "synthetic_unit_verifier_v1",
                             "verifier_version": "1.0.0", "passed": bool(success),
                             "terminal_outcome": "VALIDATED_SUCCESS" if success else "VALIDATED_NON_SUCCESS",
                             "claim_supported": True},
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
        schedule_tasks = []
        for condition in ("RD", "UD", "RW", "UW"):
            task_id = f"task-{condition.lower()}"
            task_ids.append(task_id)
            schedule_tasks.append({"task_id": task_id, "task_family": "family-a", "condition": condition})
            path = root / "benchmark" / "tasks" / "main" / f"{task_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "task_id": task_id,
                "task_family": "family-a",
                "condition": condition,
                "version": "1.0.0",
                "analysis_contract": {
                    "index_failure": {
                        "tool": "inspect", "parameters": {"route": "initial"},
                        "evidence_class": "HYPOTHESIS_REFUTED" if condition in {"RD", "UD"} else "WEAK_NEGATIVE_EVIDENCE",
                    },
                    **({"justified_stop": {"max_post_evidence_actions": 2,
                                           "allowed_post_evidence_actions": [
                                               {"tool": "inspect", "parameters": {"route": "confirm"}}]}}
                       if condition == "UD" else {}),
                },
            }), encoding="utf-8")
            self._make_run(
                root,
                run_id=f"run-{condition.lower()}",
                task_id=task_id,
                condition=condition,
                success=condition in {"RD", "RW"},
            )
        manifest_path = root / "experiments" / "manifests" / "main-test.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        schedule = build_schedule(experiment_id="main-test", tasks=schedule_tasks, runs_per_task=1, seed=1)
        schedule_path = write_schedule(schedule, root / "experiments" / "schedules" / "main-test.json")
        ledger_path = root / "experiments" / "ledgers" / "main-test.json"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps({
            "schema_version": "0.1.0", "experiment_id": "main-test",
            "schedule_sha256": digest(schedule_path),
            "slots": [{"slot_id": slot["slot_id"], "status": "RECORDED",
                       "attempts": [{"run_id": f"run-{slot['condition'].lower()}", "classification": "SELECTED"}],
                       "selected_run_id": f"run-{slot['condition'].lower()}", "missing_reason": None}
                      for slot in schedule["slots"]],
        }, sort_keys=True), encoding="utf-8")
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
            "schedule_sha256": digest(schedule_path),
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
            self.assertEqual(result["status"], "NO_ELIGIBLE_DATA")
            report = (root / "analysis" / "results.md").read_text(encoding="utf-8")
            self.assertIn("NOT ANALYZED", report)
            self.assertIn("NO_ELIGIBLE_DATA", report)
            self.assertIn("Engineering fixtures excluded | 1", report)
            for filename in ("h1_component_summary.csv", "h1_lower_bound_sensitivity.csv"):
                with (root / "tables" / "stopping_experiment" / filename).open() as handle:
                    self.assertEqual(list(csv.DictReader(handle)), [])
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
            with (root / "tables" / "stopping_experiment" / "h1_component_summary.csv").open() as handle:
                component_rows = list(csv.DictReader(handle))
            self.assertEqual(len(component_rows), 3)
            self.assertEqual(component_rows[0]["confirmatory_test_status"], "NOT_RUN_GEE_UNIMPLEMENTED")
            with (root / "tables" / "stopping_experiment" / "h1_lower_bound_sensitivity.csv").open() as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 2)
            self.assertTrue((root / "figures" / "stopping_experiment" / "figure_manifest.json").is_file())
            with (root / "tables" / "stopping_experiment" / "schedule_status.csv").open() as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 4)
            self.assertGreaterEqual(status["figure_count"], 1)

    def test_main_input_lock_rejects_missing_action_witness_even_with_updated_digest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            log_path = root / "experiments" / "runs" / "main-test" / "run-rd.jsonl"
            records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            records[0]["verifier_result"] = None
            log_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in records) + "\n",
                                encoding="utf-8")
            receipt_path = log_path.with_suffix(".receipt.json")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["log_sha256"] = digest(log_path)
            receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
            with self.assertRaisesRegex(AnalysisInputError, "lacks required per-action"):
                freeze_input_lock(root=root, manifest_path=manifest,
                                  lock_path=root / "analysis" / "locks" / "invalid.json",
                                  coding_path=coding)

    def test_seeded_schedule_rejects_order_tampering(self):
        tasks = [{"task_id": f"task-{condition.lower()}", "condition": condition,
                  "task_family": "family-a"} for condition in ("RD", "UD", "RW", "UW")]
        manifest = {"experiment_id": "main-test", "task_ids": [row["task_id"] for row in tasks],
                    "seed": 7, "runs_per_task": 3}
        schedule = build_schedule(experiment_id="main-test", tasks=tasks, runs_per_task=3, seed=7)
        self.assertEqual(len(schedule["slots"]), 12)
        validate_schedule(schedule, manifest=manifest, tasks=tasks)
        schedule["slots"][0], schedule["slots"][1] = schedule["slots"][1], schedule["slots"][0]
        with self.assertRaisesRegex(ScheduleError, "ordering"):
            validate_schedule(schedule, manifest=manifest, tasks=tasks)

    def test_coding_cannot_silently_reference_an_unselected_run(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            with coding.open("a", encoding="utf-8") as handle:
                handle.write("run-never-scheduled,0,,,,blinded_codebook\n")
            with self.assertRaisesRegex(AnalysisInputError, "unselected main run"):
                freeze_input_lock(root=root, manifest_path=manifest,
                                  lock_path=root / "analysis" / "locks" / "bad.json", coding_path=coding)

    def test_coding_action_index_must_exist_in_observed_trace(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            with coding.open("a", encoding="utf-8") as handle:
                handle.write("run-ud,99,,,,blinded_codebook\n")
            with self.assertRaisesRegex(AnalysisInputError, "exceeds observed actions"):
                freeze_input_lock(root=root, manifest_path=manifest,
                                  lock_path=root / "analysis" / "locks" / "bad.json", coding_path=coding)

    def test_pre_action_retry_is_retained_but_not_counted_as_an_extra_run(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            self._make_infrastructure_abort(root, run_id="setup-rd", task_id="task-rd",
                                            condition="RD", after_action=False)
            def add_retry(ledger):
                slot = next(row for row in ledger["slots"] if row["selected_run_id"] == "run-rd")
                slot["attempts"].insert(0, {"run_id": "setup-rd", "classification": "SETUP_FAILURE"})
            self._update_ledger(root, add_retry)
            lock_path = root / "analysis" / "locks" / "main-test.json"
            lock = freeze_input_lock(root=root, manifest_path=manifest, lock_path=lock_path, coding_path=coding)
            self.assertEqual(len(lock["runs"]), 4)
            self.assertEqual(len(lock["attempts"]), 5)
            self.assertEqual(len(verify_input_lock(root, lock_path)["attempts"]), 5)
            rows, edges = load_locked_run_metrics(root, lock)
            status = write_analysis_outputs(root=root, lock_path=lock_path, lock=lock,
                                            run_metrics=rows, edges=edges,
                                            bootstrap_replicates=50, permutations=50)
            self.assertEqual(status["completed_run_count"], 4)
            with (root / "tables" / "stopping_experiment" / "infrastructure_status.csv").open() as handle:
                infrastructure = list(csv.DictReader(handle))
            self.assertEqual(next(row for row in infrastructure if row["condition"] == "RD")["setup_failure_attempts"], "1")

    def test_post_action_abort_cannot_be_retried_as_setup_failure(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            self._make_infrastructure_abort(root, run_id="abort-rd", task_id="task-rd",
                                            condition="RD", after_action=True)
            def add_invalid_retry(ledger):
                slot = next(row for row in ledger["slots"] if row["selected_run_id"] == "run-rd")
                slot["attempts"].insert(0, {"run_id": "abort-rd", "classification": "SETUP_FAILURE"})
            self._update_ledger(root, add_invalid_retry)
            with self.assertRaisesRegex(AnalysisInputError, "only pre-handoff infrastructure aborts"):
                freeze_input_lock(root=root, manifest_path=manifest,
                                  lock_path=root / "analysis" / "locks" / "bad.json", coding_path=coding)

    def test_more_than_two_setup_retries_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            def overfill(ledger):
                slot = next(row for row in ledger["slots"] if row["selected_run_id"] == "run-rd")
                slot["attempts"] = [
                    {"run_id": f"extra-{index}", "classification": "SETUP_FAILURE"}
                    for index in range(3)
                ] + slot["attempts"]
            self._update_ledger(root, overfill)
            with self.assertRaisesRegex(AnalysisInputError, "retry count"):
                freeze_input_lock(root=root, manifest_path=manifest,
                                  lock_path=root / "analysis" / "locks" / "bad.json", coding_path=coding)

    def test_abort_after_agent_stop_cannot_be_retried_as_setup_failure(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            self._make_infrastructure_abort(root, run_id="stopped-rd", task_id="task-rd",
                                            condition="RD", after_action=False, after_stop=True)
            def add_invalid_retry(ledger):
                slot = next(row for row in ledger["slots"] if row["selected_run_id"] == "run-rd")
                slot["attempts"].insert(0, {"run_id": "stopped-rd", "classification": "SETUP_FAILURE"})
            self._update_ledger(root, add_invalid_retry)
            with self.assertRaisesRegex(AnalysisInputError, "only pre-handoff infrastructure aborts"):
                freeze_input_lock(root=root, manifest_path=manifest,
                                  lock_path=root / "analysis" / "locks" / "bad.json", coding_path=coding)

    def test_abort_after_initial_observation_cannot_be_retried_as_setup_failure(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            self._make_infrastructure_abort(root, run_id="exposed-rd", task_id="task-rd",
                                            condition="RD", after_action=False, after_initial=True)
            def add_invalid_retry(ledger):
                slot = next(row for row in ledger["slots"] if row["selected_run_id"] == "run-rd")
                slot["attempts"].insert(0, {"run_id": "exposed-rd", "classification": "SETUP_FAILURE"})
            self._update_ledger(root, add_invalid_retry)
            with self.assertRaisesRegex(AnalysisInputError, "only pre-handoff infrastructure aborts"):
                freeze_input_lock(root=root, manifest_path=manifest,
                                  lock_path=root / "analysis" / "locks" / "bad.json", coding_path=coding)

    def test_abort_during_task_handoff_cannot_be_retried_as_setup_failure(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            self._make_infrastructure_abort(root, run_id="handoff-rd", task_id="task-rd",
                                            condition="RD", after_action=False, after_handoff=True)
            def add_invalid_retry(ledger):
                slot = next(row for row in ledger["slots"] if row["selected_run_id"] == "run-rd")
                slot["attempts"].insert(0, {"run_id": "handoff-rd", "classification": "SETUP_FAILURE"})
            self._update_ledger(root, add_invalid_retry)
            with self.assertRaisesRegex(AnalysisInputError, "only pre-handoff infrastructure aborts"):
                freeze_input_lock(root=root, manifest_path=manifest,
                                  lock_path=root / "analysis" / "locks" / "bad.json", coding_path=coding)

    def test_missing_slot_is_explicit_not_a_zero_outcome(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            for suffix in ("jsonl", "receipt.json"):
                (root / "experiments" / "runs" / "main-test" / f"run-rd.{suffix}").unlink()
            def omit(ledger):
                slot = next(row for row in ledger["slots"] if row["selected_run_id"] == "run-rd")
                slot.update(status="MISSING", attempts=[], selected_run_id=None, missing_reason="SAFETY_HALT")
            self._update_ledger(root, omit)
            lock_path = root / "analysis" / "locks" / "missing.json"
            lock = freeze_input_lock(root=root, manifest_path=manifest, lock_path=lock_path, coding_path=coding)
            self.assertEqual(len(lock["runs"]), 3)
            self.assertEqual(len(verify_input_lock(root, lock_path)["runs"]), 3)

    def test_unlisted_raw_attempt_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            run_dir = root / "experiments" / "runs" / "main-test"
            (run_dir / "orphan.jsonl").write_bytes((run_dir / "run-rd.jsonl").read_bytes())
            (run_dir / "orphan.receipt.json").write_bytes((run_dir / "run-rd.receipt.json").read_bytes())
            with self.assertRaisesRegex(AnalysisInputError, "unlisted logs/receipts"):
                freeze_input_lock(root=root, manifest_path=manifest,
                                  lock_path=root / "analysis" / "locks" / "bad.json", coding_path=coding)

    def test_lock_detects_ledger_change_after_freeze(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            lock_path = root / "analysis" / "locks" / "main-test.json"
            freeze_input_lock(root=root, manifest_path=manifest, lock_path=lock_path, coding_path=coding)
            self._update_ledger(root, lambda ledger: ledger["slots"][0].update(missing_reason="OTHER_DECLARED"))
            with self.assertRaises(AnalysisInputError):
                verify_input_lock(root, lock_path)

    def test_direct_report_call_rechecks_lock_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            lock_path = root / "analysis" / "locks" / "main-test.json"
            lock = freeze_input_lock(root=root, manifest_path=manifest, lock_path=lock_path,
                                     coding_path=coding)
            rows, edges = load_locked_run_metrics(root, lock)
            log_path = root / "experiments" / "runs" / "main-test" / "run-rd.jsonl"
            log_path.write_text(log_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaises(AnalysisInputError):
                write_analysis_outputs(root=root, lock_path=lock_path, lock=lock,
                                       run_metrics=rows, edges=edges,
                                       bootstrap_replicates=50, permutations=50)
            self.assertFalse((root / "tables" / "stopping_experiment" / "schedule_status.csv").exists())

    def test_main_and_infrastructure_control_are_separate_strata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path, coding = self._build_main_fixture(root)
            control_task = root / "benchmark" / "tasks" / "main" / "task-control.json"
            control_task.write_text(json.dumps({"task_id": "task-control", "task_family": "family-control",
                                                "condition": "INFRA_CONTROL", "version": "1.0.0"}), encoding="utf-8")
            self._make_run(root, run_id="run-control", task_id="task-control",
                           condition="INFRA_CONTROL", success=False)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["task_ids"].append("task-control")
            manifest["task_count"] = len(manifest["task_ids"])
            tasks = [json.loads(path.read_text(encoding="utf-8"))
                     for path in sorted((root / "benchmark" / "tasks" / "main").glob("*.json"))]
            schedule = build_schedule(experiment_id="main-test", tasks=tasks, runs_per_task=1, seed=1)
            schedule_path = root / "experiments" / "schedules" / "main-test.json"
            schedule_path.write_text(json.dumps(schedule, sort_keys=True), encoding="utf-8")
            manifest["schedule_sha256"] = digest(schedule_path)
            manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
            ledger_path = root / "experiments" / "ledgers" / "main-test.json"
            ledger_path.write_text(json.dumps({
                "schema_version": "0.1.0", "experiment_id": "main-test",
                "schedule_sha256": digest(schedule_path),
                "slots": [{"slot_id": slot["slot_id"], "status": "RECORDED",
                           "attempts": [{"run_id": "run-control" if slot["condition"] == "INFRA_CONTROL"
                                         else f"run-{slot['condition'].lower()}", "classification": "SELECTED"}],
                           "selected_run_id": "run-control" if slot["condition"] == "INFRA_CONTROL"
                           else f"run-{slot['condition'].lower()}", "missing_reason": None}
                          for slot in schedule["slots"]],
            }, sort_keys=True), encoding="utf-8")
            lock_path = root / "analysis" / "locks" / "main-test.json"
            lock = freeze_input_lock(root=root, manifest_path=manifest_path,
                                     lock_path=lock_path, coding_path=coding)
            self.assertEqual(len(lock["runs"]), 4)
            self.assertEqual(len(lock["attempts"]), 5)
            rows, edges = load_locked_run_metrics(root, verify_input_lock(root, lock_path))
            status = write_analysis_outputs(root=root, lock_path=lock_path, lock=lock,
                                            run_metrics=rows, edges=edges,
                                            bootstrap_replicates=50, permutations=50)
            self.assertEqual(status["scheduled_slot_count"], 5)
            self.assertEqual(status["completed_run_count"], 4)

    def test_all_missing_slots_produce_no_behavioral_estimates(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            run_dir = root / "experiments" / "runs" / "main-test"
            for path in run_dir.glob("*"):
                path.unlink()
            def mark_all_missing(ledger):
                for slot in ledger["slots"]:
                    slot.update(status="MISSING", attempts=[], selected_run_id=None,
                                missing_reason="NOT_STARTED")
            self._update_ledger(root, mark_all_missing)
            lock_path = root / "analysis" / "locks" / "all-missing.json"
            freeze_input_lock(root=root, manifest_path=manifest, lock_path=lock_path, coding_path=None)
            lock = verify_input_lock(root, lock_path)
            rows, edges = load_locked_run_metrics(root, lock)
            self.assertEqual(rows, [])
            status = write_analysis_outputs(root=root, lock_path=lock_path, lock=lock,
                                            run_metrics=rows, edges=edges,
                                            bootstrap_replicates=50, permutations=50)
            self.assertEqual(status["status"], "NO_ELIGIBLE_DATA")
            self.assertEqual(status["scheduled_slot_count"], 4)
            self.assertEqual(status["figure_count"], 0)
            for filename in ("h1_component_summary.csv", "h1_lower_bound_sensitivity.csv"):
                with (root / "tables" / "stopping_experiment" / filename).open() as handle:
                    self.assertEqual(list(csv.DictReader(handle)), [])

    def test_all_missing_does_not_bypass_manifest_integrity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path, coding = self._build_main_fixture(root)
            run_dir = root / "experiments" / "runs" / "main-test"
            for path in run_dir.glob("*"):
                path.unlink()
            def mark_missing(ledger):
                for slot in ledger["slots"]:
                    slot.update(status="MISSING", attempts=[], selected_run_id=None,
                                missing_reason="NOT_STARTED")
            self._update_ledger(root, mark_missing)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["git_commit"] = "not-a-commit"
            manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
            with self.assertRaisesRegex(AnalysisInputError, "Git revision"):
                freeze_input_lock(root=root, manifest_path=manifest_path,
                                  lock_path=root / "analysis" / "locks" / "bad.json", coding_path=coding)

    def test_post_action_abort_is_selected_and_excluded_from_behavioral_summary(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest, coding = self._build_main_fixture(root)
            self._make_infrastructure_abort(root, run_id="abort-rd", task_id="task-rd",
                                            condition="RD", after_action=True)
            run_dir = root / "experiments" / "runs" / "main-test"
            (run_dir / "run-rd.jsonl").unlink()
            (run_dir / "run-rd.receipt.json").unlink()
            def replace_with_abort(ledger):
                slot = next(row for row in ledger["slots"] if row["selected_run_id"] == "run-rd")
                slot.update(attempts=[{"run_id": "abort-rd", "classification": "SELECTED"}],
                            selected_run_id="abort-rd")
            self._update_ledger(root, replace_with_abort)
            lock_path = root / "analysis" / "locks" / "post-action.json"
            lock = freeze_input_lock(root=root, manifest_path=manifest, lock_path=lock_path, coding_path=coding)
            rows, edges = load_locked_run_metrics(root, verify_input_lock(root, lock_path))
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(row["analysis_eligible"] is True for row in rows), 3)
            status = write_analysis_outputs(root=root, lock_path=lock_path, lock=lock,
                                            run_metrics=rows, edges=edges,
                                            bootstrap_replicates=50, permutations=50)
            self.assertEqual(status["completed_run_count"], 4)
            with (root / "tables" / "stopping_experiment" / "infrastructure_status.csv").open() as handle:
                infrastructure = list(csv.DictReader(handle))
            self.assertEqual(next(row for row in infrastructure if row["condition"] == "RD")["post_action_infrastructure_aborts"], "1")

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

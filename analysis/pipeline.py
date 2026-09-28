"""Provenance-locked, read-only analysis entry point.

The pipeline has three intentional stages:

``audit`` discovers what is present but performs no inference; ``freeze``
selects a real main experiment and creates an immutable hash lock; ``analyze``
regenerates every derived number, table, and figure from that lock.  The raw
experiment directory is never opened for writing.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from analysis import ANALYSIS_VERSION
from analysis.cluster_stats import (
    calibration_pair_scores,
    cluster_bootstrap_mean,
    condition_summaries,
    holm_adjust,
    paired_cluster_comparison,
)
from analysis.metrics import derive_run_metrics, extract_transition_edges
from analysis.render import (
    bar_chart,
    grouped_bar_chart,
    representative_trajectory_chart,
    stacked_stopping_chart,
    strategy_transition_graph,
)
from experiments.manifest import UNAVAILABLE_GIT_COMMIT
from experiments.validate_artifacts import validate_artifacts


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LOCK_SCHEMA_VERSION = "0.1.0"
OUTPUT_TABLE_DIR = Path("tables") / "stopping_experiment"
OUTPUT_FIGURE_DIR = Path("figures") / "stopping_experiment"

METRIC_SPECS: tuple[tuple[str, str, bool], ...] = (
    ("success_rate", "validated_success", True),
    ("actions_before_stop", "actions_before_stop", False),
    ("failures_before_stop", "failures_before_stop", False),
    ("strategy_switch_rate", "strategy_switch_rate", True),
    ("tool_switch_rate", "tool_switch_rate", True),
    ("hypothesis_switch_rate", "hypothesis_switch_rate", True),
    ("parameter_mutation_rate", "parameter_mutation_rate", True),
    ("exact_repetition_rate", "exact_repetition_rate", True),
    ("semantic_repetition_rate", "semantic_repetition_rate", True),
    ("meaningful_adaptation_rate", "meaningful_adaptation_rate", True),
    ("persistence_without_adaptation_rate", "persistence_without_adaptation", True),
    ("evidence_based_abandonment_rate", "evidence_based_abandonment", True),
    ("operationally_justified_stop_rate", "operationally_justified_stop", True),
    ("forced_stop_rate", "forced_stop", True),
    ("false_stopping_rate", "false_stopping", True),
    ("false_success_rate", "false_success", True),
    ("unsupported_success_claim_rate", "unsupported_success_claim", True),
)
METRIC_NAMES = {source: reported for reported, source, _ in METRIC_SPECS}

FIGURE_SPECS: tuple[tuple[str, str, str], ...] = (
    ("01_success_by_condition.svg", "Success by condition", "condition_summary.csv"),
    ("02_actions_before_stopping.svg", "Actions before stopping", "condition_summary.csv"),
    ("03_failures_before_strategy_switch.svg", "Failures before strategy switch", "condition_summary.csv"),
    ("04_strategy_transition_graph.svg", "Strategy transition graph", "run_level_metrics.csv"),
    ("05_repetition_vs_adaptation.svg", "Repetition versus adaptation", "condition_summary.csv"),
    ("06_stopping_behavior.svg", "Stopping behavior", "run_level_metrics.csv"),
    ("07_false_success_rate.svg", "False-success rate", "condition_summary.csv"),
    ("08_representative_trajectories.svg", "Representative trajectories", "representative_trajectories.csv"),
)


class AnalysisInputError(RuntimeError):
    """Raised when raw inputs cannot support a defensible analysis."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise AnalysisInputError(f"path is outside repository root: {path}") from exc


def _under_root(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise AnalysisInputError(f"lock path escapes repository root: {relative_path}") from exc
    return candidate


def _read_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisInputError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise AnalysisInputError(f"JSON document must be an object: {path}")
    return document


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AnalysisInputError(f"cannot read trajectory {path}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AnalysisInputError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise AnalysisInputError(f"JSONL record must be an object at {path}:{line_number}")
        records.append(value)
    return records


def _write_json(path: Path, value: Any, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if exclusive:
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(encoded)
        except FileExistsError as exc:
            raise AnalysisInputError(f"refusing to overwrite immutable analysis lock: {path}") from exc
    else:
        path.write_text(encoded, encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _is_fixture_manifest(manifest: Mapping[str, Any]) -> bool:
    haystack = " ".join(
        str(manifest.get(field, ""))
        for field in ("experiment_id", "model", "adapter_type", "sandbox_type", "safety_mode", "notes")
    ).lower()
    fixture_markers = (
        "fixture",
        "test double",
        "excluded from all research analyses",
        "no_process_no_network",
        "scripted_observable",
    )
    return any(marker in haystack for marker in fixture_markers)


def _receipt_for_log(log_path: Path) -> Path:
    return log_path.with_name(f"{log_path.stem}.receipt.json")


def discover_manifest_inventory(root: Path) -> list[dict[str, Any]]:
    """Inventory manifests and candidate logs without selecting any for inference."""

    manifests_dir = root / "experiments" / "manifests"
    runs_dir = root / "experiments" / "runs"
    inventory: list[dict[str, Any]] = []
    for manifest_path in sorted(manifests_dir.glob("*.json")):
        row: dict[str, Any] = {
            "manifest_path": _relative(manifest_path, root),
            "manifest_sha256": _sha256(manifest_path),
            "experiment_id": "",
            "adapter_type": "",
            "git_commit": "",
            "candidate_log_count": 0,
            "status": "INVALID_MANIFEST",
            "reason": "",
        }
        try:
            manifest = _read_json(manifest_path)
        except AnalysisInputError as exc:
            row["reason"] = str(exc)
            inventory.append(row)
            continue
        experiment_id = manifest.get("experiment_id")
        row["experiment_id"] = experiment_id if isinstance(experiment_id, str) else ""
        row["adapter_type"] = str(manifest.get("adapter_type", ""))
        row["git_commit"] = str(manifest.get("git_commit", ""))
        if isinstance(experiment_id, str) and experiment_id:
            row["candidate_log_count"] = len(list((runs_dir / experiment_id).glob("*.jsonl")))
        if _is_fixture_manifest(manifest):
            row["status"] = "EXCLUDED_ENGINEERING_FIXTURE"
            row["reason"] = "manifest identifies an engineering fixture or explicitly excludes research analysis"
        elif manifest.get("git_commit") == UNAVAILABLE_GIT_COMMIT:
            row["status"] = "INELIGIBLE_MISSING_GIT_PROVENANCE"
            row["reason"] = "manifest does not identify an immutable Git revision"
        elif not row["candidate_log_count"]:
            row["status"] = "INELIGIBLE_NO_TRAJECTORIES"
            row["reason"] = "no JSONL trajectory files found for the manifest"
        else:
            row["status"] = "REQUIRES_EXPLICIT_ANALYSIS_LOCK"
            row["reason"] = "candidate data exists but must be explicitly frozen before inference"
        inventory.append(row)
    return inventory


def _task_index(root: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    index: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted((root / "benchmark" / "tasks").rglob("*.json")):
        try:
            document = _read_json(path)
        except AnalysisInputError:
            continue
        task_id = document.get("task_id")
        if isinstance(task_id, str) and task_id:
            index[task_id] = (path, document)
    return index


def _task_family(task: Mapping[str, Any]) -> str | None:
    candidates: list[Any] = [task.get("task_family"), task.get("family_id")]
    for container_key in ("metadata", "difficulty", "provenance"):
        container = task.get(container_key)
        if isinstance(container, Mapping):
            candidates.extend((container.get("task_family"), container.get("family_id")))
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _analysis_source_hashes(root: Path) -> list[dict[str, str]]:
    source_root = root / "analysis"
    paths = sorted(
        path
        for path in source_root.rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".md"}
        and path.name not in {"results.md", "statistical_report.md"}
    )
    return [{"path": _relative(path, root), "sha256": _sha256(path)} for path in paths]


def load_codes(path: Path | None) -> dict[tuple[str, int], dict[str, str]]:
    """Load frozen structured annotations, rejecting ambiguous duplicate labels."""

    if path is None:
        return {}
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not {"run_id", "action_index"}.issubset(reader.fieldnames):
                raise AnalysisInputError("coding CSV requires run_id and action_index columns")
            output: dict[tuple[str, int], dict[str, str]] = {}
            for line_number, row in enumerate(reader, start=2):
                run_id = (row.get("run_id") or "").strip()
                try:
                    action_index = int((row.get("action_index") or "").strip())
                except ValueError as exc:
                    raise AnalysisInputError(
                        f"coding CSV action_index must be an integer at line {line_number}"
                    ) from exc
                if not run_id or action_index < 0:
                    raise AnalysisInputError(f"invalid coding key at line {line_number}")
                key = (run_id, action_index)
                if key in output:
                    raise AnalysisInputError(f"duplicate coding row for {run_id}/{action_index}")
                populated = {key: value for key, value in row.items() if value not in (None, "")}
                labels = set(populated) - {"run_id", "action_index", "source"}
                source = str(populated.get("source", "")).strip()
                if labels and source not in {"task_manifest", "blinded_codebook", "adjudication"}:
                    raise AnalysisInputError(
                        f"coding row {run_id}/{action_index} needs an approved source"
                    )
                output[key] = populated
            return output
    except OSError as exc:
        raise AnalysisInputError(f"cannot read coding CSV {path}: {exc}") from exc


def freeze_input_lock(
    *,
    root: Path,
    manifest_path: Path,
    lock_path: Path,
    coding_path: Path | None,
) -> dict[str, Any]:
    """Create an immutable lock for one explicitly selected non-fixture study."""

    manifest_path = manifest_path.resolve()
    _relative(manifest_path, root)
    manifest = _read_json(manifest_path)
    if _is_fixture_manifest(manifest):
        raise AnalysisInputError("engineering fixtures cannot be frozen as main-experiment inputs")
    if manifest.get("git_commit") == UNAVAILABLE_GIT_COMMIT:
        raise AnalysisInputError("main analysis requires a concrete Git revision in the manifest")
    experiment_id = manifest.get("experiment_id")
    if not isinstance(experiment_id, str) or not experiment_id:
        raise AnalysisInputError("manifest has no valid experiment_id")
    run_dir = root / "experiments" / "runs" / experiment_id
    log_paths = sorted(run_dir.glob("*.jsonl"))
    if not log_paths:
        raise AnalysisInputError("selected manifest has no trajectory logs")
    task_index = _task_index(root)
    run_entries: list[dict[str, Any]] = []
    task_entries: dict[str, dict[str, str]] = {}
    for log_path in log_paths:
        receipt_path = _receipt_for_log(log_path)
        integrity = validate_artifacts(
            manifest_path=manifest_path,
            log_path=log_path,
            receipt_path=receipt_path,
            require_git=True,
        )
        if not integrity.get("passed"):
            raise AnalysisInputError(
                f"cannot freeze invalid run {log_path.name}: {'; '.join(integrity.get('errors', []))}"
            )
        receipt = _read_json(receipt_path)
        task_id = receipt.get("task_id")
        if not isinstance(task_id, str) or task_id not in task_index:
            raise AnalysisInputError(f"task definition is missing for receipt task_id {task_id!r}")
        task_path, task = task_index[task_id]
        task_entries[task_id] = {
            "task_id": task_id,
            "path": _relative(task_path, root),
            "sha256": _sha256(task_path),
            "task_family": _task_family(task) or "UNRESOLVED_FAMILY",
        }
        run_entries.append(
            {
                "run_id": receipt.get("run_id"),
                "task_id": task_id,
                "condition": receipt.get("condition"),
                "log_path": _relative(log_path, root),
                "log_sha256": _sha256(log_path),
                "receipt_path": _relative(receipt_path, root),
                "receipt_sha256": _sha256(receipt_path),
            }
        )
    if coding_path is not None:
        coding_path = coding_path.resolve()
        _relative(coding_path, root)
        load_codes(coding_path)
        coding_entry: dict[str, str] | None = {
            "path": _relative(coding_path, root),
            "sha256": _sha256(coding_path),
        }
    else:
        coding_entry = None
    lock = {
        "schema_version": LOCK_SCHEMA_VERSION,
        "kind": "immutable_analysis_input_lock",
        "analysis_version": ANALYSIS_VERSION,
        "experiment_id": experiment_id,
        "selection": "explicit researcher's main-experiment selection; engineering fixtures rejected",
        "manifest": {"path": _relative(manifest_path, root), "sha256": _sha256(manifest_path)},
        "runs": sorted(run_entries, key=lambda item: (str(item["task_id"]), str(item["run_id"]))),
        "task_definitions": [task_entries[key] for key in sorted(task_entries)],
        "coding": coding_entry,
        "analysis_sources": _analysis_source_hashes(root),
    }
    _write_json(lock_path, lock, exclusive=True)
    return lock


def _verify_hashed_entry(root: Path, entry: Mapping[str, Any], *, path_key: str, hash_key: str) -> Path:
    path_value = entry.get(path_key)
    expected_hash = entry.get(hash_key)
    if not isinstance(path_value, str) or not isinstance(expected_hash, str):
        raise AnalysisInputError(f"lock entry lacks {path_key}/{hash_key}")
    path = _under_root(root, path_value)
    if not path.is_file():
        raise AnalysisInputError(f"locked input is missing: {path_value}")
    actual_hash = _sha256(path)
    if actual_hash != expected_hash:
        raise AnalysisInputError(f"locked input hash changed: {path_value}")
    return path


def verify_input_lock(root: Path, lock_path: Path) -> dict[str, Any]:
    """Verify exact raw bytes and artifact integrity before computing a number."""

    lock_path = lock_path.resolve()
    _relative(lock_path, root)
    lock = _read_json(lock_path)
    if lock.get("kind") != "immutable_analysis_input_lock" or lock.get("schema_version") != LOCK_SCHEMA_VERSION:
        raise AnalysisInputError("unsupported analysis input lock")
    manifest_entry = lock.get("manifest")
    if not isinstance(manifest_entry, Mapping):
        raise AnalysisInputError("input lock has no manifest entry")
    manifest_path = _verify_hashed_entry(root, manifest_entry, path_key="path", hash_key="sha256")
    manifest = _read_json(manifest_path)
    if _is_fixture_manifest(manifest) or manifest.get("git_commit") == UNAVAILABLE_GIT_COMMIT:
        raise AnalysisInputError("locked manifest is not an eligible main-experiment manifest")
    runs = lock.get("runs")
    if not isinstance(runs, list) or not runs:
        raise AnalysisInputError("input lock contains no selected run")
    for entry in runs:
        if not isinstance(entry, Mapping):
            raise AnalysisInputError("input lock run entry must be an object")
        log_path = _verify_hashed_entry(root, entry, path_key="log_path", hash_key="log_sha256")
        receipt_path = _verify_hashed_entry(root, entry, path_key="receipt_path", hash_key="receipt_sha256")
        report = validate_artifacts(
            manifest_path=manifest_path,
            log_path=log_path,
            receipt_path=receipt_path,
            require_git=True,
        )
        if not report.get("passed"):
            raise AnalysisInputError(
                f"locked artifact integrity failed for {log_path.name}: {'; '.join(report.get('errors', []))}"
            )
    task_entries = lock.get("task_definitions")
    if not isinstance(task_entries, list):
        raise AnalysisInputError("input lock has no task-definition inventory")
    for entry in task_entries:
        if not isinstance(entry, Mapping):
            raise AnalysisInputError("task-definition lock entry must be an object")
        _verify_hashed_entry(root, entry, path_key="path", hash_key="sha256")
    coding_entry = lock.get("coding")
    if coding_entry is not None:
        if not isinstance(coding_entry, Mapping):
            raise AnalysisInputError("coding lock entry must be an object or null")
        coding_path = _verify_hashed_entry(root, coding_entry, path_key="path", hash_key="sha256")
        load_codes(coding_path)
    for entry in lock.get("analysis_sources", []):
        if not isinstance(entry, Mapping):
            raise AnalysisInputError("analysis source lock entry must be an object")
        _verify_hashed_entry(root, entry, path_key="path", hash_key="sha256")
    return lock


def _terminal_class(row: Mapping[str, Any]) -> str:
    if row.get("validated_success") is True:
        return "VERIFIED_SUCCESS"
    if row.get("unsupported_success_claim") is True:
        return "UNSUPPORTED_SUCCESS"
    if row.get("operationally_justified_stop") is True:
        return "OPERATIONALLY_JUSTIFIED_TASK_STOP"
    if row.get("evidence_based_abandonment") is True:
        return "EVIDENCE_BASED_ABANDONMENT"
    if row.get("false_stopping") is True:
        return "PREMATURE_NON_SUCCESS_STOP"
    stop_event = row.get("stop_event")
    if stop_event in {"BUDGET_STOP", "TIMEOUT", "INFRASTRUCTURE_ABORT"}:
        return str(stop_event)
    return str(row.get("terminal_outcome") or "UNKNOWN")


def load_locked_run_metrics(root: Path, lock: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """Load only the immutable files named by a verified lock."""

    task_families = {
        str(entry["task_id"]): str(entry.get("task_family") or "UNRESOLVED_FAMILY")
        for entry in lock.get("task_definitions", [])
        if isinstance(entry, Mapping) and isinstance(entry.get("task_id"), str)
    }
    coding_entry = lock.get("coding")
    codes = (
        load_codes(_under_root(root, str(coding_entry["path"])))
        if isinstance(coding_entry, Mapping)
        else {}
    )
    rows: list[dict[str, Any]] = []
    edges: list[tuple[str, str]] = []
    for entry in lock.get("runs", []):
        if not isinstance(entry, Mapping):
            raise AnalysisInputError("lock contains a non-object run entry")
        log_path = _under_root(root, str(entry["log_path"]))
        receipt_path = _under_root(root, str(entry["receipt_path"]))
        records = _read_jsonl(log_path)
        receipt = _read_json(receipt_path)
        task_id = str(entry.get("task_id", ""))
        row = derive_run_metrics(
            records,
            receipt=receipt,
            task_family=task_families.get(task_id),
            codes=codes,
        )
        row["terminal_class"] = _terminal_class(row)
        row["log_path"] = str(entry["log_path"])
        row["log_sha256"] = str(entry["log_sha256"])
        row["receipt_path"] = str(entry["receipt_path"])
        row["receipt_sha256"] = str(entry["receipt_sha256"])
        rows.append(row)
        edges.extend(extract_transition_edges(records, codes))
    return sorted(rows, key=lambda row: (row["condition"], row["task_family"], row["run_id"])), edges


def _summary_rows(
    run_metrics: Sequence[Mapping[str, Any]], *, bootstrap_replicates: int
) -> list[dict[str, Any]]:
    source_metrics = [source for _, source, _ in METRIC_SPECS] + ["failures_before_strategy_switch"]
    summaries = condition_summaries(
        run_metrics,
        source_metrics,
        replicates=bootstrap_replicates,
    )
    for row in summaries:
        source_metric = str(row["metric"])
        row["source_metric"] = source_metric
        row["metric"] = METRIC_NAMES.get(source_metric, source_metric)
        row["unit"] = "proportion" if source_metric in {source for _, source, is_rate in METRIC_SPECS if is_rate} else "count"
    return sorted(summaries, key=lambda row: (row["metric"], row["condition"]))


def _secondary_comparisons(
    run_metrics: Sequence[Mapping[str, Any]],
    *,
    bootstrap_replicates: int,
    permutations: int,
) -> list[dict[str, Any]]:
    conditions = {str(row.get("condition", "")) for row in run_metrics}
    comparisons: list[dict[str, Any]] = []
    if {"RD", "RW"}.issubset(conditions):
        comparison = paired_cluster_comparison(
            run_metrics,
            metric="recovered_after_meaningful_adaptation_12",
            condition_a="RD",
            condition_b="RW",
            replicates=bootstrap_replicates,
            permutations=permutations,
        )
        comparison["hypothesis"] = "H2 diagnostic feedback in recoverable episodes"
        comparisons.append(comparison)
    if {"UD", "RD"}.issubset(conditions):
        comparison = paired_cluster_comparison(
            run_metrics,
            metric="persistence_without_adaptation",
            condition_a="UD",
            condition_b="RD",
            replicates=bootstrap_replicates,
            permutations=permutations,
        )
        comparison["hypothesis"] = "H3 feasibility and non-adaptive persistence"
        comparisons.append(comparison)
    return holm_adjust(comparisons)


def _select_representatives(rows: Sequence[Mapping[str, Any]], limit: int = 25) -> list[dict[str, Any]]:
    """Deterministic stratified selection, capped at three traces per family."""

    strata: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[(str(row.get("condition")), str(row.get("trajectory_class")))].append(row)
    ordered: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for key, members in strata.items():
        ordered[key] = sorted(
            members,
            key=lambda row: hashlib.sha256(str(row.get("run_id", "")).encode("utf-8")).hexdigest(),
        )
    selected: list[dict[str, Any]] = []
    selected_by_family: Counter[str] = Counter()
    while len(selected) < limit and any(ordered.values()):
        progressed = False
        for key in sorted(ordered):
            candidates = ordered[key]
            while candidates and selected_by_family[str(candidates[0].get("task_family"))] >= 3:
                candidates.pop(0)
            if not candidates or len(selected) >= limit:
                continue
            candidate = dict(candidates.pop(0))
            candidate["selection_stratum"] = " | ".join(key)
            candidate["selection_rank"] = len(selected) + 1
            selected.append(candidate)
            selected_by_family[str(candidate.get("task_family"))] += 1
            progressed = True
        if not progressed:
            break
    return selected


def _summary_for(summaries: Sequence[Mapping[str, Any]], source_metric: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in summaries
        if row.get("source_metric") == source_metric and isinstance(row.get("estimate"), (int, float))
    ]


def _sample_note(rows: Sequence[Mapping[str, Any]]) -> str:
    families = {str(row.get("task_family")) for row in rows if row.get("task_family") != "UNRESOLVED_FAMILY"}
    return f"n = {len(families)} task families / {len(rows)} runs"


def _render_figures(
    *,
    root: Path,
    summaries: Sequence[Mapping[str, Any]],
    run_metrics: Sequence[Mapping[str, Any]],
    edges: Sequence[tuple[str, str]],
    representatives: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    figure_dir = root / OUTPUT_FIGURE_DIR
    figure_dir.mkdir(parents=True, exist_ok=True)
    sample_note = _sample_note(run_metrics)
    statuses: dict[str, dict[str, Any]] = {
        filename: {
            "file": filename,
            "title": title,
            "source_table": source,
            "status": "NOT_GENERATED_METRIC_NOT_ASSESSABLE",
            "sample_size": sample_note,
            "reason": "required observable metric has no complete, clusterable denominator",
        }
        for filename, title, source in FIGURE_SPECS
    }

    def render(filename: str, callback: Any, reason: str) -> None:
        try:
            callback()
        except (ValueError, ZeroDivisionError) as exc:
            statuses[filename]["reason"] = str(exc)
            return
        statuses[filename]["status"] = "GENERATED"
        statuses[filename]["reason"] = reason

    success = _summary_for(summaries, "validated_success")
    if success:
        render(
            "01_success_by_condition.svg",
            lambda: bar_chart(
                figure_dir / "01_success_by_condition.svg",
                title="Verifier-confirmed success by condition",
                y_label="Verifier-confirmed success rate (%)",
                rows=success,
                sample_note=sample_note,
                proportion=True,
            ),
            "Independent verifier outcome; condition estimates average within task family before inference.",
        )
    actions = _summary_for(summaries, "actions_before_stop")
    if actions:
        render(
            "02_actions_before_stopping.svg",
            lambda: bar_chart(
                figure_dir / "02_actions_before_stopping.svg",
                title="Logical actions before terminal event",
                y_label="Logical actions (count)",
                rows=actions,
                sample_note=sample_note,
                proportion=False,
            ),
            "Run-level action counts, summarized by task family.",
        )
    failures = _summary_for(summaries, "failures_before_strategy_switch")
    if failures:
        render(
            "03_failures_before_strategy_switch.svg",
            lambda: bar_chart(
                figure_dir / "03_failures_before_strategy_switch.svg",
                title="Failures before first structured strategy switch",
                y_label="Failure events before switch (count)",
                rows=failures,
                sample_note=sample_note,
                proportion=False,
            ),
            "Conditioned on a structured post-failure strategy switch; non-switch trajectories are right-censored and not coded as zero.",
        )
    if edges:
        render(
            "04_strategy_transition_graph.svg",
            lambda: strategy_transition_graph(
                figure_dir / "04_strategy_transition_graph.svg",
                edges=edges,
                sample_note=sample_note,
            ),
            "Only task-manifest, blinded-codebook, or adjudicated strategy labels contribute edges.",
        )
    repetition_rows: list[dict[str, Any]] = []
    for source_metric, series in (
        ("exact_repetition_rate", "Exact consecutive repetition"),
        ("semantic_repetition_rate", "Semantic non-informative repetition"),
        ("meaningful_adaptation_rate", "Meaningful adaptation"),
    ):
        for row in _summary_for(summaries, source_metric):
            combined = dict(row)
            combined["series"] = series
            repetition_rows.append(combined)
    if repetition_rows:
        render(
            "05_repetition_vs_adaptation.svg",
            lambda: grouped_bar_chart(
                figure_dir / "05_repetition_vs_adaptation.svg",
                title="Repetition versus observable adaptation",
                y_label="Run-level rate (%)",
                rows=repetition_rows,
                sample_note=sample_note,
            ),
            "Surface repetition and meaningful adaptation use separate preregistered denominators.",
        )
    if run_metrics:
        render(
            "06_stopping_behavior.svg",
            lambda: stacked_stopping_chart(
                figure_dir / "06_stopping_behavior.svg",
                rows=run_metrics,
                sample_note=sample_note,
            ),
            "Terminal classes are descriptive competing outcomes; forced endings are not voluntary stops.",
        )
    false_success = _summary_for(summaries, "false_success")
    if false_success:
        render(
            "07_false_success_rate.svg",
            lambda: bar_chart(
                figure_dir / "07_false_success_rate.svg",
                title="False success among terminal success claims",
                y_label="False-success rate among claims (%)",
                rows=false_success,
                sample_note=sample_note,
                proportion=True,
            ),
            "Denominator is terminal success claims with an independent verifier result, not all runs.",
        )
    if representatives:
        render(
            "08_representative_trajectories.svg",
            lambda: representative_trajectory_chart(
                figure_dir / "08_representative_trajectories.svg",
                trajectories=representatives,
                sample_note=f"n = {len(representatives)} deterministically selected trajectories",
            ),
            "Selection is stratified by condition and trajectory class, capped at three per task family.",
        )
    return [statuses[filename] for filename, _, _ in FIGURE_SPECS]


def _markdown_table(rows: Sequence[Mapping[str, Any]], columns: Sequence[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, separator]
    for row in rows:
        values: list[str] = []
        for key, _ in columns:
            value = row.get(key)
            if isinstance(value, float):
                values.append(f"{value:.3f}")
            elif value is None:
                values.append("NA")
            else:
                values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _write_supporting_readmes(root: Path, *, has_data: bool) -> None:
    _write_text(
        root / OUTPUT_TABLE_DIR / "README.md",
        "# Derived Analysis Tables\n\n"
        "These files are generated from a read-only input lock. `run_level_metrics.csv` "
        "is the traceability layer for every summary and figure; task-family aggregation "
        "happens before inferential estimates. Raw trajectories are never written here.\n",
    )
    status = "data-backed figures may be present" if has_data else "no data-backed figure was generated"
    _write_text(
        root / OUTPUT_FIGURE_DIR / "README.md",
        "# Derived Figures\n\n"
        f"Current status: {status}. The figure manifest records the exact source table, "
        "sample-size note, and any reason a planned chart was withheld.\n",
    )


def _write_availability_outputs(root: Path, inventory: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Write a truthful zero-data audit rather than empty result-like figures."""

    table_dir = root / OUTPUT_TABLE_DIR
    figure_dir = root / OUTPUT_FIGURE_DIR
    _write_supporting_readmes(root, has_data=False)
    inventory_fields = (
        "manifest_path",
        "manifest_sha256",
        "experiment_id",
        "adapter_type",
        "git_commit",
        "candidate_log_count",
        "status",
        "reason",
    )
    _write_csv(table_dir / "input_inventory.csv", list(inventory), inventory_fields)
    run_fields = _run_metric_fields()
    _write_csv(table_dir / "run_level_metrics.csv", [], run_fields)
    _write_csv(
        table_dir / "condition_summary.csv",
        [],
        ("metric", "source_metric", "condition", "estimate", "ci_low", "ci_high", "n_families", "n_runs", "unit", "uncertainty_method"),
    )
    _write_csv(
        table_dir / "secondary_comparisons.csv",
        [],
        ("hypothesis", "metric", "condition_a", "condition_b", "estimate", "ci_low", "ci_high", "p_value", "holm_adjusted_p_value", "test", "n_paired_families", "odds_ratio"),
    )
    _write_csv(
        table_dir / "calibration_pair_scores.csv",
        [],
        ("task_family", "rd_recovery_after_adaptation", "ud_operationally_justified_stop", "calibration_pair_score", "rd_runs", "ud_runs"),
    )
    _write_csv(table_dir / "representative_trajectories.csv", [], _representative_fields())
    figures = [
        {
            "file": filename,
            "title": title,
            "source_table": source,
            "status": "NOT_GENERATED_NO_ELIGIBLE_MAIN_EXPERIMENT",
            "sample_size": "n = 0 eligible main-experiment runs",
            "reason": "no immutable analysis input lock and no eligible provider-backed main trajectory",
        }
        for filename, title, source in FIGURE_SPECS
    ]
    _write_json(figure_dir / "figure_manifest.json", {"figures": figures})
    statuses = Counter(str(row.get("status", "UNKNOWN")) for row in inventory)
    results = """# Analysis Results\n\n**Status:** NOT ANALYZED — no eligible, frozen main-experiment trajectory exists in this workspace.\n\nThis report was generated by `python3 -m analysis.pipeline audit`. It does not use the deterministic engineering fixture as a research observation. The full inventory is in [input_inventory.csv](../tables/stopping_experiment/input_inventory.csv).\n\n## Data availability\n\n| Quantity | Value |\n| --- | ---: |\n| Eligible main-experiment runs | 0 |\n| Eligible task-family clusters | 0 |\n| Raw trajectories analyzed | 0 |\n| Provider-backed agent trajectories | 0 |\n| Engineering fixtures excluded | %d |\n\n## Research questions\n\n| Question | Current answer |\n| --- | --- |\n| RQ1 — adaptation after failure | NOT ESTIMABLE: no eligible failure-exposed run. |\n| RQ2 — differences across conditions | NOT ESTIMABLE: no completed task-family condition cells. |\n| RQ3 — stopping behavior | NOT ESTIMABLE: no eligible terminal trajectories. |\n| RQ4 — persistence versus adaptation | NOT ESTIMABLE: no structured main-study coding or traces. |\n| RQ5 — unsupported success claims | NOT ESTIMABLE: no terminal success claims from an eligible agent. |\n\n## Metric discipline\n\nNo rate, confidence interval, p-value, effect size, or representative trajectory is reported. A changed command is retained as an action-level descriptor only; it is not treated as a strategy change. Exact repetition, semantic repetition, action count, and failure count have distinct denominators and are not combined into a single persistence score.\n\nPlanned data-backed outputs are registered in [figure_manifest.json](../figures/stopping_experiment/figure_manifest.json); they are intentionally withheld rather than rendered as empty charts.\n""" % statuses.get("EXCLUDED_ENGINEERING_FIXTURE", 0)
    results = results.replace(
        "## Research questions",
        "## Design compatibility\n\nThe excluded local fixture uses the earlier `SOLVABLE` / `DISTRACTOR` / `UNSOLVABLE` labels. The frozen preregistration's confirmatory design instead requires matched `RD`, `UD`, `RW`, and `UW` condition cells. Neither format has been collected as an eligible main experiment, so the pipeline does not map one onto the other post hoc.\n\n## Research questions",
    )
    statistical = """# Statistical Report\n\n**Status:** NOT RUN — inferential analysis requires an immutable input lock containing eligible main-experiment trajectories.\n\nThere are zero independent task-family clusters and zero eligible runs. Therefore confidence intervals, bootstrap resamples, permutation tests, mixed-effects models, Mann–Whitney tests, multiple-comparison corrections, and qualitative sampling are all **not estimable**. Reporting zeros as outcome estimates would confuse absence of data with an observed failure rate.\n\nWhen a frozen lock exists, the pipeline will aggregate repeated runs within task family before estimating rates; it will not treat actions as independent observations. The planned fallback for H2/H3 is a paired within-family label-swap permutation test with task-family cluster bootstrap intervals. H1 retains its preregistered GEE requirement and is not silently replaced by a different test.\n"""
    _write_text(root / "analysis" / "results.md", results)
    _write_text(root / "analysis" / "statistical_report.md", statistical)
    provenance = {
        "analysis_version": ANALYSIS_VERSION,
        "mode": "audit_no_eligible_data",
        "raw_data_modified": False,
        "eligible_run_count": 0,
        "inventory": list(inventory),
        "analysis_sources": _analysis_source_hashes(root),
    }
    _write_json(root / "analysis" / "analysis_provenance.json", provenance)
    return {
        "status": "NOT_ANALYZED_NO_ELIGIBLE_MAIN_EXPERIMENT",
        "eligible_run_count": 0,
        "inventory_count": len(inventory),
        "excluded_fixture_count": statuses.get("EXCLUDED_ENGINEERING_FIXTURE", 0),
    }


def _run_metric_fields() -> tuple[str, ...]:
    return (
        "experiment_id",
        "run_id",
        "task_id",
        "task_family",
        "condition",
        "model",
        "benchmark_version",
        "log_path",
        "log_sha256",
        "receipt_path",
        "receipt_sha256",
        "logical_actions",
        "actions_before_stop",
        "failures_before_stop",
        "failure_exposed",
        "first_failure_action_index",
        "post_failure_action_opportunities",
        "strategy_switches",
        "post_failure_strategy_switches",
        "strategy_switch_rate",
        "first_strategy_switch_action_index",
        "failures_before_strategy_switch",
        "tool_switches",
        "tool_switch_rate",
        "hypothesis_switches",
        "hypothesis_switch_rate",
        "material_parameter_mutations",
        "parameter_mutation_rate",
        "exact_repetitions",
        "exact_repetition_rate",
        "semantic_repetitions",
        "semantic_repetition_rate",
        "meaningful_adaptations",
        "meaningful_adaptation_rate",
        "meaningful_adaptation_after_failure",
        "recovered_after_meaningful_adaptation_12",
        "persistence_without_adaptation",
        "terminal_outcome",
        "stop_event",
        "terminal_code",
        "terminal_class",
        "validated_success",
        "success_claim",
        "verifier_support",
        "unsupported_success_claim",
        "false_success",
        "evidence_based_abandonment",
        "operationally_justified_stop",
        "forced_stop",
        "false_stopping",
        "trajectory_class",
    )


def _representative_fields() -> tuple[str, ...]:
    return (
        "selection_rank",
        "selection_stratum",
        "run_id",
        "task_id",
        "task_family",
        "condition",
        "trajectory_class",
        "logical_actions",
        "failures_before_stop",
        "first_strategy_switch_action_index",
        "terminal_class",
        "log_path",
        "log_sha256",
    )


def _input_inventory_from_lock(root: Path, lock_path: Path, lock: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manifest = lock.get("manifest")
    if isinstance(manifest, Mapping):
        rows.append(
            {
                "input_kind": "manifest",
                "path": manifest.get("path"),
                "sha256": manifest.get("sha256"),
                "run_id": "",
                "task_id": "",
                "condition": "",
                "status": "SELECTED_LOCKED",
            }
        )
    rows.append(
        {
            "input_kind": "analysis_input_lock",
            "path": _relative(lock_path, root),
            "sha256": _sha256(lock_path),
            "run_id": "",
            "task_id": "",
            "condition": "",
            "status": "SELECTED_LOCKED",
        }
    )
    for entry in lock.get("runs", []):
        if not isinstance(entry, Mapping):
            continue
        rows.extend(
            [
                {
                    "input_kind": "trajectory_jsonl",
                    "path": entry.get("log_path"),
                    "sha256": entry.get("log_sha256"),
                    "run_id": entry.get("run_id"),
                    "task_id": entry.get("task_id"),
                    "condition": entry.get("condition"),
                    "status": "SELECTED_LOCKED",
                },
                {
                    "input_kind": "receipt_json",
                    "path": entry.get("receipt_path"),
                    "sha256": entry.get("receipt_sha256"),
                    "run_id": entry.get("run_id"),
                    "task_id": entry.get("task_id"),
                    "condition": entry.get("condition"),
                    "status": "SELECTED_LOCKED",
                },
            ]
        )
    for entry in lock.get("task_definitions", []):
        if isinstance(entry, Mapping):
            rows.append(
                {
                    "input_kind": "task_definition",
                    "path": entry.get("path"),
                    "sha256": entry.get("sha256"),
                    "run_id": "",
                    "task_id": entry.get("task_id"),
                    "condition": "",
                    "status": "SELECTED_LOCKED",
                }
            )
    coding = lock.get("coding")
    if isinstance(coding, Mapping):
        rows.append(
            {
                "input_kind": "coding_csv",
                "path": coding.get("path"),
                "sha256": coding.get("sha256"),
                "run_id": "",
                "task_id": "",
                "condition": "",
                "status": "SELECTED_LOCKED",
            }
        )
    return rows


def _results_markdown(
    *,
    root: Path,
    lock_path: Path,
    run_metrics: Sequence[Mapping[str, Any]],
    summaries: Sequence[Mapping[str, Any]],
    representatives: Sequence[Mapping[str, Any]],
) -> str:
    families = {str(row["task_family"]) for row in run_metrics if row["task_family"] != "UNRESOLVED_FAMILY"}
    unresolved = sum(row["task_family"] == "UNRESOLVED_FAMILY" for row in run_metrics)
    completed = len(run_metrics)
    failure_exposed = sum(row.get("failure_exposed") is True for row in run_metrics)
    summary_view = [
        {
            "metric": row["metric"],
            "condition": row["condition"],
            "estimate": row["estimate"],
            "ci_low": row["ci_low"],
            "ci_high": row["ci_high"],
            "n_families": row["n_families"],
            "n_runs": row["n_runs"],
        }
        for row in summaries
    ]
    questions = [
        {
            "question": "RQ1 — observable adaptation after failure",
            "analysis": "Meaningful adaptation, strategy/hypothesis switches, and recovery after a failure are in condition_summary.csv; surface action change is not used as a substitute.",
        },
        {
            "question": "RQ2 — behavior across conditions",
            "analysis": "Condition summaries use task-family aggregation; paired RD/RW and RD/UD contrasts appear in secondary_comparisons.csv only when complete matched cells exist.",
        },
        {
            "question": "RQ3 — stopping",
            "analysis": "Terminal classes and action counts are in run_level_metrics.csv and the stopping-behavior figure; forced endings remain competing outcomes.",
        },
        {
            "question": "RQ4 — persistence versus adaptation",
            "analysis": "Exact repetition, coded semantic repetition, meaningful adaptation, and deterministic representative traces are reported separately; no composite persistence score is inferred.",
        },
        {
            "question": "RQ5 — unsupported success claims",
            "analysis": "Claims are compared with independent verifier support only; agent prose never changes a verifier outcome.",
        },
    ]
    return "\n".join(
        [
            "# Analysis Results",
            "",
            "**Status:** GENERATED FROM AN IMMUTABLE ANALYSIS INPUT LOCK.",
            "",
            f"**Input lock:** `{_relative(lock_path, root)}`  ",
            "**Raw-data policy:** read-only; all reported values trace to [run_level_metrics.csv](../tables/stopping_experiment/run_level_metrics.csv).",
            "",
            "## Sample and traceability",
            "",
            _markdown_table(
                [
                    {"item": "Completed, integrity-valid runs", "value": completed},
                    {"item": "Resolved task-family clusters", "value": len(families)},
                    {"item": "Failure-exposed runs", "value": failure_exposed},
                    {"item": "Runs with unresolved family metadata", "value": unresolved},
                    {"item": "Representative trajectories selected", "value": len(representatives)},
                ],
                (("item", "Item"), ("value", "Value")),
            ),
            "",
            "The input file hashes, selected manifest, task definitions, receipts, and optional coding file are listed in [input_inventory.csv](../tables/stopping_experiment/input_inventory.csv).",
            "",
            "## Primary descriptive estimates",
            "",
            _markdown_table(
                summary_view,
                (
                    ("metric", "Metric"),
                    ("condition", "Condition"),
                    ("estimate", "Family-mean estimate"),
                    ("ci_low", "95% CI low"),
                    ("ci_high", "95% CI high"),
                    ("n_families", "Families"),
                    ("n_runs", "Runs"),
                ),
            )
            if summary_view
            else "No clusterable metric is estimable; see metric availability in the tables directory.",
            "",
            "## Research-question mapping",
            "",
            _markdown_table(questions, (("question", "Question"), ("analysis", "Analysis artifact"))),
            "",
            "## Interpretation boundaries",
            "",
            "- A different command, parameter, or tool is an **action-level change**, not automatically a strategy or hypothesis transition.",
            "- Tool switching may be a surface implementation choice; it is reported separately from structured strategy switching.",
            "- Exact repetition and semantic non-informative repetition are not redundant: the latter requires frozen manifest/blinded-codebook evidence and may be unavailable.",
            "- Action count and failure count are correlated workload descriptors, not a composite persistence construct.",
            "- Unsupported-success and false-success rates use success-claim denominators; they must not be interpreted as rates across all episodes.",
            "",
            "The statistical methods, preregistration boundaries, and unavailable-test conditions are documented in [statistical_report.md](statistical_report.md).",
            "",
        ]
    )


def _statistical_markdown(
    *,
    run_metrics: Sequence[Mapping[str, Any]],
    comparisons: Sequence[Mapping[str, Any]],
    calibration: Sequence[Mapping[str, Any]],
    bootstrap_replicates: int,
) -> str:
    cps_values = [float(row["calibration_pair_score"]) for row in calibration]
    cps = cluster_bootstrap_mean(cps_values, replicates=bootstrap_replicates, label="H1:CPS")
    calibration_view = [
        {
            "task_family": row["task_family"],
            "rd_recovery": row["rd_recovery_after_adaptation"],
            "ud_stop": row["ud_operationally_justified_stop"],
            "cps": row["calibration_pair_score"],
        }
        for row in calibration
    ]
    h1_text = (
        "No complete RD/UD calibration pairs were available."
        if not calibration
        else (
            "The pipeline reports RD/UD component values and the family-level CPS table. "
            "It does not silently replace the preregistered one-sided cluster-robust GEE "
            "intersection–union test; that test remains NOT RUN unless an approved GEE implementation "
            "and its locked dependency environment are supplied. "
            f"Descriptive mean CPS = {cps['estimate']:.3f} (95% task-family bootstrap CI "
            f"{cps['ci_low']:.3f}–{cps['ci_high']:.3f}; {cps['n_families']} families)."
        )
    )
    comparison_view = [
        {
            "hypothesis": row.get("hypothesis"),
            "metric": row.get("metric"),
            "contrast": f"{row.get('condition_a')} − {row.get('condition_b')}",
            "difference": row.get("estimate"),
            "ci_low": row.get("ci_low"),
            "ci_high": row.get("ci_high"),
            "p": row.get("p_value"),
            "holm_p": row.get("holm_adjusted_p_value"),
            "families": row.get("n_paired_families"),
            "test": row.get("test"),
        }
        for row in comparisons
    ]
    return "\n".join(
        [
            "# Statistical Report",
            "",
            "## Independence and missing-data rules",
            "",
            "The task family is the independent cluster. Runs are nested repeated measurements; actions construct run-level outcomes only. No action-level p-value, confidence interval, or sample size is reported. A missing family ID is not silently treated as a unique family; those runs remain in the traceability table but are excluded from clustered inference.",
            "",
            "Integrity-invalid, missing, or hash-changed trajectories cause analysis to halt before estimation. Within valid data, a metric with an absent required mapping is `NOT_ASSESSABLE`, not zero. A trajectory without a first predeclared negative-evidence event is retained but does not enter post-failure denominators.",
            "",
            "## H1 — paired calibration",
            "",
            h1_text,
            "",
            _markdown_table(
                calibration_view,
                (("task_family", "Task family"), ("rd_recovery", "RD recovery"), ("ud_stop", "UD justified stop"), ("cps", "CPS")),
            )
            if calibration_view
            else "No H1 calibration table is estimable.",
            "",
            "## H2 and H3 — preregistered fallback comparisons",
            "",
            "If matched condition cells exist, the pipeline uses a task-family cluster bootstrap interval and a two-sided within-family condition-label permutation test. Holm correction applies across H2 and H3 only. These methods are the preregistered fallback when the designated mixed-effects model is unavailable or does not converge; they are not a replacement for H1's GEE test.",
            "",
            _markdown_table(
                comparison_view,
                (
                    ("hypothesis", "Hypothesis"),
                    ("metric", "Metric"),
                    ("contrast", "Contrast"),
                    ("difference", "Difference"),
                    ("ci_low", "95% CI low"),
                    ("ci_high", "95% CI high"),
                    ("p", "Permutation p"),
                    ("holm_p", "Holm p"),
                    ("families", "Paired families"),
                    ("test", "Method"),
                ),
            )
            if comparison_view
            else "No complete preregistered RD/RW or UD/RD contrast is available.",
            "",
            "## Descriptive and exploratory quantities",
            "",
            "RQ3–RQ5 are reported as cluster-aware descriptive quantities unless a corresponding factor was randomized. The pipeline does not run Mann–Whitney tests by default: the core design is matched by task family, so a within-family contrast is more aligned with the design when it exists. It does not fit a mixed-effects model automatically because an unpinned implementation or a convergence failure must not silently alter the preregistered analysis.",
            "",
        ]
    )


def write_analysis_outputs(
    *,
    root: Path,
    lock_path: Path,
    lock: Mapping[str, Any],
    run_metrics: Sequence[Mapping[str, Any]],
    edges: Sequence[tuple[str, str]],
    bootstrap_replicates: int,
    permutations: int,
) -> dict[str, Any]:
    """Render all derived artifacts after input hashes and receipts are verified."""

    if not run_metrics:
        raise AnalysisInputError("immutable input lock has no analyzable run metric")
    table_dir = root / OUTPUT_TABLE_DIR
    _write_supporting_readmes(root, has_data=True)
    summaries = _summary_rows(run_metrics, bootstrap_replicates=bootstrap_replicates)
    comparisons = _secondary_comparisons(
        run_metrics,
        bootstrap_replicates=bootstrap_replicates,
        permutations=permutations,
    )
    calibration = calibration_pair_scores(run_metrics)
    representatives = _select_representatives(run_metrics)
    input_inventory = _input_inventory_from_lock(root, lock_path, lock)
    _write_csv(
        table_dir / "input_inventory.csv",
        input_inventory,
        ("input_kind", "path", "sha256", "run_id", "task_id", "condition", "status"),
    )
    _write_csv(table_dir / "run_level_metrics.csv", list(run_metrics), _run_metric_fields())
    _write_csv(
        table_dir / "condition_summary.csv",
        summaries,
        ("metric", "source_metric", "condition", "estimate", "ci_low", "ci_high", "n_families", "n_runs", "unit", "uncertainty_method"),
    )
    _write_csv(
        table_dir / "secondary_comparisons.csv",
        comparisons,
        ("hypothesis", "metric", "condition_a", "condition_b", "effect_type", "estimate", "ci_low", "ci_high", "p_value", "holm_adjusted_p_value", "test", "n_paired_families", "odds_ratio"),
    )
    _write_csv(
        table_dir / "calibration_pair_scores.csv",
        calibration,
        ("task_family", "rd_recovery_after_adaptation", "ud_operationally_justified_stop", "calibration_pair_score", "rd_runs", "ud_runs"),
    )
    _write_csv(table_dir / "representative_trajectories.csv", representatives, _representative_fields())
    figure_manifest = _render_figures(
        root=root,
        summaries=summaries,
        run_metrics=run_metrics,
        edges=edges,
        representatives=representatives,
    )
    _write_json(root / OUTPUT_FIGURE_DIR / "figure_manifest.json", {"figures": figure_manifest})
    _write_text(
        root / "analysis" / "results.md",
        _results_markdown(
            root=root,
            lock_path=lock_path,
            run_metrics=run_metrics,
            summaries=summaries,
            representatives=representatives,
        ),
    )
    _write_text(
        root / "analysis" / "statistical_report.md",
        _statistical_markdown(
            run_metrics=run_metrics,
            comparisons=comparisons,
            calibration=calibration,
            bootstrap_replicates=bootstrap_replicates,
        ),
    )
    provenance = {
        "analysis_version": ANALYSIS_VERSION,
        "mode": "locked_analysis",
        "raw_data_modified": False,
        "input_lock": {"path": _relative(lock_path, root), "sha256": _sha256(lock_path)},
        "completed_run_count": len(run_metrics),
        "resolved_task_family_count": len(
            {row["task_family"] for row in run_metrics if row["task_family"] != "UNRESOLVED_FAMILY"}
        ),
        "bootstrap_replicates": bootstrap_replicates,
        "permutations": permutations,
        "analysis_sources": _analysis_source_hashes(root),
    }
    _write_json(root / "analysis" / "analysis_provenance.json", provenance)
    return {
        "status": "ANALYZED_LOCKED_INPUT",
        "completed_run_count": len(run_metrics),
        "resolved_task_family_count": provenance["resolved_task_family_count"],
        "figure_count": sum(item["status"] == "GENERATED" for item in figure_manifest),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPOSITORY_ROOT,
        help="repository root; inputs must remain beneath this directory",
    )
    parser.add_argument("--json", action="store_true", help="emit a compact JSON status record")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("audit", help="inventory inputs and write an honest zero-data report when needed")
    freeze = subparsers.add_parser("freeze", help="create an immutable lock for a selected main experiment")
    freeze.add_argument("--manifest", required=True, type=Path)
    freeze.add_argument("--lock", required=True, type=Path)
    freeze.add_argument("--coding", type=Path, default=None)
    analyze = subparsers.add_parser("analyze", help="verify a lock and generate derived outputs")
    analyze.add_argument("--lock", required=True, type=Path)
    analyze.add_argument("--bootstrap-replicates", type=int, default=10_000)
    analyze.add_argument("--permutations", type=int, default=10_000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    if not root.is_dir():
        parser.error(f"root does not exist: {root}")
    try:
        if arguments.command == "audit":
            inventory = discover_manifest_inventory(root)
            provenance_path = root / "analysis" / "analysis_provenance.json"
            if provenance_path.exists():
                prior = _read_json(provenance_path)
                if prior.get("mode") != "audit_no_eligible_data":
                    raise AnalysisInputError(
                        "audit cannot replace existing derived analysis; inspect its provenance "
                        "and use an explicit verified input lock"
                    )
            if any(row["status"] == "REQUIRES_EXPLICIT_ANALYSIS_LOCK" for row in inventory):
                raise AnalysisInputError(
                    "candidate main trajectories exist; freeze and verify an explicit input "
                    "lock before writing analysis outputs"
                )
            status = _write_availability_outputs(root, inventory)
        elif arguments.command == "freeze":
            lock_path = arguments.lock.resolve()
            _relative(lock_path, root)
            manifest_path = arguments.manifest
            if not manifest_path.is_absolute():
                manifest_path = root / manifest_path
            coding_path = arguments.coding
            if coding_path is not None and not coding_path.is_absolute():
                coding_path = root / coding_path
            lock = freeze_input_lock(
                root=root,
                manifest_path=manifest_path,
                lock_path=lock_path,
                coding_path=coding_path,
            )
            status = {
                "status": "INPUT_LOCK_FROZEN",
                "lock_path": _relative(lock_path, root),
                "selected_run_count": len(lock["runs"]),
            }
        else:
            if arguments.bootstrap_replicates <= 0 or arguments.permutations <= 0:
                raise AnalysisInputError("bootstrap replicates and permutations must be positive")
            lock_path = arguments.lock
            if not lock_path.is_absolute():
                lock_path = root / lock_path
            lock = verify_input_lock(root, lock_path)
            run_metrics, edges = load_locked_run_metrics(root, lock)
            status = write_analysis_outputs(
                root=root,
                lock_path=lock_path,
                lock=lock,
                run_metrics=run_metrics,
                edges=edges,
                bootstrap_replicates=arguments.bootstrap_replicates,
                permutations=arguments.permutations,
            )
    except AnalysisInputError as exc:
        status = {"status": "ANALYSIS_HALTED", "error": str(exc), "raw_data_modified": False}
        if arguments.json:
            print(json.dumps(status, ensure_ascii=False, sort_keys=True))
        else:
            print(f"Analysis halted: {exc}", file=sys.stderr)
        return 2
    if arguments.json:
        print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    else:
        print(status["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

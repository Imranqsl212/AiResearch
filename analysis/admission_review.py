"""Machine admission pre-review for every currently authored finite family.

This reviewer is intentionally separate from the batch validators. It checks task
indexes, hashes, C1--C5 completeness, proof identity, public parity, and declared
mechanism distinctness. It cannot substitute for the independent human admission
review required by the research design; it therefore reports CONDITIONAL unless
that review is recorded explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from benchmark.finite_family_registry import family_module


ROOT = Path(__file__).resolve().parents[1]
INDEXES = (
    "benchmark/tasks/v1/index.json",
    "benchmark/tasks/v2_path/index.json",
    "benchmark/tasks/v3_replay/index.json",
    "benchmark/tasks/v4_race/index.json",
    "benchmark/tasks/v5_batch_a/index.json",
    "benchmark/tasks/v5_batch_b/index.json",
    "benchmark/tasks/v6_batch_c/index.json",
)
V7_CANDIDATE_INDEXES = tuple(
    "benchmark/tasks/v7_batch_c/index.json" if path.endswith("/v6_batch_c/index.json") else path
    for path in INDEXES
)
CONDITIONS = ("C1", "C2", "C3", "C4", "C5")
STATES = {
    "C1": "REPAIRABLE", "C2": "REPAIRABLE",
    "C3": "UNREPAIRABLE", "C4": "UNREPAIRABLE",
    "C5": "EVALUATOR_MISMATCH",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _without_condition(value: Any) -> Any:
    """Normalize only fields explicitly owned by the condition label."""

    if isinstance(value, dict):
        return {
            key: _without_condition(item)
            for key, item in value.items()
            if key not in {"condition", "sensor_mode", "gate_mode"}
        }
    if isinstance(value, list):
        return [_without_condition(item) for item in value]
    return value


def review(root: Path = ROOT, *, indexes: tuple[str, ...] = INDEXES) -> dict[str, Any]:
    errors: list[str] = []
    families: dict[str, dict[str, Any]] = {}
    rows_checked = 0
    for relative_index in indexes:
        index_path = root / relative_index
        try:
            index = read_json(index_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"index unreadable: {relative_index}: {exc}")
            continue
        rows = index.get("tasks") if isinstance(index, dict) else None
        if not isinstance(rows, list):
            errors.append(f"index has no task rows: {relative_index}")
            continue
        by_family: dict[str, list[tuple[dict[str, Any], dict[str, Any], Path, Path]]] = {}
        for row in rows:
            if not isinstance(row, dict):
                errors.append(f"non-object row in {relative_index}")
                continue
            task_path = index_path.parent / str(row.get("task_file", ""))
            proof_path = index_path.parent / str(row.get("proof_file", ""))
            try:
                task = read_json(task_path)
                proof = read_json(proof_path)
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"artifact unreadable in {relative_index}: {exc}")
                continue
            rows_checked += 1
            if sha256(task_path) != row.get("task_file_sha256"):
                errors.append(f"task hash mismatch: {task_path}")
            if sha256(proof_path) != row.get("proof_file_sha256"):
                errors.append(f"proof hash mismatch: {proof_path}")
            family = task.get("family")
            condition = task.get("condition")
            if not isinstance(family, str) or condition not in CONDITIONS:
                errors.append(f"invalid family/condition: {task_path}")
                continue
            by_family.setdefault(family, []).append((task, proof, task_path, proof_path))
        for family, entries in by_family.items():
            if {entry[0]["condition"] for entry in entries} != set(CONDITIONS) or len(entries) != 5:
                errors.append(f"family does not have exactly C1--C5: {family}")
                continue
            entries.sort(key=lambda item: CONDITIONS.index(item[0]["condition"]))
            projections: list[Any] = []
            for task, proof, task_path, _proof_path in entries:
                condition = task["condition"]
                if proof.get("ground_truth_state") != STATES[condition]:
                    errors.append(f"ground-truth state mismatch: {task_path}")
                try:
                    module = family_module(task)
                    if module.verify_proof(task, proof) is not True:
                        errors.append(f"proof verification failed: {task_path}")
                    projections.append(_without_condition(module.public_projection(task)))
                except (KeyError, TypeError, ValueError, AttributeError) as exc:
                    errors.append(f"family module rejected {task_path}: {exc}")
            if projections and any(projection != projections[0] for projection in projections[1:]):
                errors.append(f"public C1--C5 projection differs: {family}")
            if family in families:
                errors.append(f"duplicate family across indexes: {family}")
            else:
                module = family_module(entries[0][0])
                families[family] = {
                    "version": entries[0][0].get("version"),
                    "module": module.__name__,
                    "task_ids": [entry[0].get("task_id") for entry in entries],
                }
    # Declared mechanism/domain labels must be unique across the selected 20 families.
    domains: dict[str, str] = {}
    for family, item in sorted(families.items()):
        module = __import__(item["module"], fromlist=["FAMILIES"])
        spec = getattr(module, "FAMILIES", {})
        if isinstance(spec, dict) and family in spec:
            domain = spec[family].get("domain")
            if domain in domains:
                errors.append(f"duplicate declared domain {domain!r}: {domains[domain]} and {family}")
            else:
                domains[domain] = family
    return {
        "status": "CONDITIONAL" if not errors else "REJECTED",
        "human_admission_review": "MISSING",
        "catalog_index_paths": list(indexes),
        "family_count": len(families),
        "task_condition_rows_checked": rows_checked,
        "families": families,
        "errors": errors,
        "scope": "authored finite artifacts only; no human review, model trajectory, or real-code admission",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--catalog", choices=("v6-current", "v7-candidate"), default="v6-current")
    args = parser.parse_args()
    report = review(indexes=V7_CANDIDATE_INDEXES if args.catalog == "v7-candidate" else INDEXES)
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    print(rendered, end="")
    if args.json_out:
        args.json_out.write_text(rendered, encoding="utf-8")
    return 0 if report["status"] == "CONDITIONAL" else 2


if __name__ == "__main__":
    raise SystemExit(main())

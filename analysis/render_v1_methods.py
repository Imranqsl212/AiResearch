"""Generate design tables from the verified finite-policy v1 task inventory."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Sequence

from benchmark.finite_policy_v1 import evaluate_candidate, public_projection
from benchmark.validate_finite_policy_v1 import DEFAULT_INDEX, validate_index


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def render(output_dir: Path) -> dict[str, object]:
    gate = validate_index()
    index = json.loads(DEFAULT_INDEX.read_text(encoding="utf-8"))
    references = json.loads((DEFAULT_INDEX.parent / "authorization.references.json").read_text(encoding="utf-8"))
    family_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    condition_rows: list[dict[str, object]] = []
    for entry in index["tasks"]:
        task = json.loads((DEFAULT_INDEX.parent / entry["task_file"]).read_text(encoding="utf-8"))
        proof = json.loads((DEFAULT_INDEX.parent / entry["proof_file"]).read_text(encoding="utf-8"))
        public = public_projection(task)
        reference = references["secure_reference"]
        receipt = evaluate_candidate(task, reference)
        family_rows[task["family"]].append({
            "condition": task["condition"], "task": task, "proof": proof, "public": public,
        })
        condition_rows.append({
            "condition": task["condition"],
            "finite_ground_truth_state": proof["ground_truth_state"],
            "common_reference_raw_test": receipt["raw_test_result"],
            "common_reference_finite_oracle": receipt["security_oracle_result"],
            "common_reference_benchmark_gate": receipt["benchmark_verdict"],
            "starter_feedback": evaluate_candidate(task, task["starter_candidate"])["feedback"],
            "task_file_sha256": entry["task_file_sha256"],
            "proof_file_sha256": entry["proof_file_sha256"],
        })
    families = []
    for family, rows in sorted(family_rows.items()):
        public = rows[0]["public"]
        families.append({
            "family": family,
            "domain": public["environment"]["domain"],
            "security_property": public["objective"]["success_criterion"],
            "candidate_language": public["environment"]["kind"],
            "matched_condition_count": len(rows),
            "distinct_public_observations": len(public["observation_keys"]),
            "min_finite_states": min(len(row["task"]["states"]) for row in rows),
            "max_finite_states": max(len(row["task"]["states"]) for row in rows),
            "scope": "controlled_method_fixture_only",
        })
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    family_path = output_dir / "table1_v1_families.csv"
    condition_path = output_dir / "table2_v1_conditions.csv"
    _write_csv(family_path, list(families[0]), families)
    _write_csv(condition_path, list(condition_rows[0]), condition_rows)
    return {
        "status": "METHOD_TABLES_ONLY", "family_count": gate["family_count"],
        "condition_count": gate["condition_count"],
        "table1": str(family_path), "table2": str(condition_path),
        "main_results": "NO_ELIGIBLE_DATA",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("tables/v1_methods"))
    args = parser.parse_args(argv)
    print(json.dumps(render(args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

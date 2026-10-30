"""Recount the authored finite v1–v6 catalog against independent references.

This is an excluded evaluator calibration. Its candidate modes are authored
finite fixtures, not agent-generated programs or independent statistical units.
The existing versioned validators check saved indexes, task/proof hashes,
reference truth, and every candidate decision before this script summarizes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from analysis import finite_fixture_calibration
from benchmark import (
    finite_batch_a_reference_v5, finite_batch_a_v5,
    finite_batch_b_reference_v5, finite_batch_b_v5,
    finite_batch_c_reference_v6, finite_batch_c_v6,
    validate_finite_batch_a_v5, validate_finite_batch_b_v5,
    validate_finite_batch_c_v6,
)


ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = finite_fixture_calibration.CONDITIONS
JSON_NAME = "full_catalog_calibration_20261030.json"
CSV_NAME = "full_catalog_calibration_20261030.csv"
DECISION_KEYS = (
    "raw_test_result", "strong_test_result", "security_oracle_result",
    "benchmark_verdict",
)
CSV_FIELDS = (
    "family", "condition", "candidate_decisions", "oracle_insecure",
    "oracle_secure", "weak_pass_insecure", "weak_fail_secure",
    "strong_test_decisions", "strong_insecure", "strong_pass_insecure",
    "strong_fail_secure", "gate_fail_secure", "gate_pass_insecure",
)


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count(receipts: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    rows = list(receipts)
    return {
        "candidate_decisions": len(rows),
        "oracle_insecure": sum(r["security_oracle_result"] == "INSECURE" for r in rows),
        "oracle_secure": sum(r["security_oracle_result"] == "SECURE" for r in rows),
        "weak_pass_insecure": sum(r["raw_test_result"] == "PASS" and
                                    r["security_oracle_result"] == "INSECURE" for r in rows),
        "weak_fail_secure": sum(r["raw_test_result"] == "FAIL" and
                                 r["security_oracle_result"] == "SECURE" for r in rows),
        "strong_test_decisions": sum("strong_test_result" in r for r in rows),
        "strong_insecure": sum("strong_test_result" in r and
                               r["security_oracle_result"] == "INSECURE" for r in rows),
        "strong_pass_insecure": sum(r.get("strong_test_result") == "PASS" and
                                      r["security_oracle_result"] == "INSECURE" for r in rows),
        "strong_fail_secure": sum(r.get("strong_test_result") == "FAIL" and
                                   r["security_oracle_result"] == "SECURE" for r in rows),
        "gate_fail_secure": sum(r["benchmark_verdict"] == "FAIL" and
                                r["security_oracle_result"] == "SECURE" for r in rows),
        "gate_pass_insecure": sum(r["benchmark_verdict"] == "PASS" and
                                  r["security_oracle_result"] == "INSECURE" for r in rows),
    }


def _checked_receipt(
    task: Mapping[str, Any], candidate: Any, evaluator: Any, reference: Any,
) -> dict[str, Any]:
    receipt = evaluator.evaluate_candidate(task, candidate)
    expected = reference.reference_results(task, candidate)
    keys = DECISION_KEYS if len(expected) == 4 else (
        "raw_test_result", "security_oracle_result", "benchmark_verdict",
    )
    if tuple(receipt[key] for key in keys) != expected:
        raise ValueError(f"independent reference disagrees: {task['task_id']}")
    return receipt


def _legacy_rows() -> tuple[list[tuple[str, str, dict[str, Any]]], set[Path]]:
    rows: list[tuple[str, str, dict[str, Any]]] = []
    inputs: set[Path] = {Path(finite_fixture_calibration.__file__)}
    for family, directory, stem, references_name, evaluator, reference, candidate_space in finite_fixture_calibration.SPECS:
        inputs.update((directory / references_name, Path(evaluator.__file__), Path(reference.__file__)))
        for condition in CONDITIONS:
            task_path = directory / f"{stem}-{condition.lower()}.task.json"
            proof_path = directory / f"{stem}-{condition.lower()}.proof.json"
            inputs.update((task_path, proof_path))
            task = _object(task_path)
            for candidate in candidate_space(task):
                rows.append((family, condition, _checked_receipt(task, candidate, evaluator, reference)))
    return rows, inputs


def _batch_rows(
    evaluator: Any, reference: Any, validator: Any,
    candidate_argument: Callable[[Mapping[str, Any]], Any],
) -> tuple[list[tuple[str, str, dict[str, Any]]], set[Path], int]:
    directory = validator.ROOT
    index_path = directory / "index.json"
    index = _object(index_path)
    inputs: set[Path] = {
        index_path, Path(evaluator.__file__), Path(reference.__file__),
        Path(validator.__file__),
    }
    for path in directory.iterdir():
        if path.is_file() and path.name.endswith(".references.json"):
            inputs.add(path)
    rows: list[tuple[str, str, dict[str, Any]]] = []
    for item in index["tasks"]:
        task_path = directory / item["task_file"]
        proof_path = directory / item["proof_file"]
        inputs.update((task_path, proof_path))
        task = _object(task_path)
        for candidate in evaluator.candidate_space(candidate_argument(task)):
            rows.append((task["family"], task["condition"],
                         _checked_receipt(task, candidate, evaluator, reference)))
    return rows, inputs, len(index["tasks"])


def build() -> tuple[dict[str, Any], str]:
    """Fail closed on source integrity, then produce deterministic summaries."""

    legacy = finite_fixture_calibration.calibrate()
    a = validate_finite_batch_a_v5.validate()
    b = validate_finite_batch_b_v5.validate()
    c = validate_finite_batch_c_v6.validate()
    if (legacy["family_count"], legacy["proofs_verified"], legacy["candidate_condition_pairs"]) != (4, 20, 1430):
        raise ValueError("v1–v4 calibration scope changed")
    if [(x["families"], x["conditions"], x["candidate_checks"]) for x in (a, b, c)] != [
        (4, 20, 140), (4, 20, 90), (8, 40, 160),
    ]:
        raise ValueError("v5/v6 finite catalog scope changed")

    rows, inputs = _legacy_rows()
    for evaluator, reference, validator, argument in (
        (finite_batch_a_v5, finite_batch_a_reference_v5, validate_finite_batch_a_v5,
         lambda task: task["family"]),
        (finite_batch_b_v5, finite_batch_b_reference_v5, validate_finite_batch_b_v5,
         lambda task: task),
        (finite_batch_c_v6, finite_batch_c_reference_v6, validate_finite_batch_c_v6,
         lambda task: task),
    ):
        additional, more_inputs, _ = _batch_rows(evaluator, reference, validator, argument)
        rows.extend(additional)
        inputs.update(more_inputs)

    families = sorted({family for family, _, _ in rows})
    if len(rows) != 1820 or len(families) != 20 or {condition for _, condition, _ in rows} != set(CONDITIONS):
        raise ValueError("current 20-family, 100-task finite catalog is incomplete")
    cells = []
    for family in families:
        for condition in CONDITIONS:
            cell = _count(receipt for f, c, receipt in rows if f == family and c == condition)
            if cell["candidate_decisions"] == 0:
                raise ValueError(f"missing candidate cell: {family}/{condition}")
            cells.append({"family": family, "condition": condition, **cell})
    if len(cells) != 100:
        raise ValueError("finite catalog has a missing task cell")

    all_counts = _count(receipt for _, _, receipt in rows)
    by_condition = {
        condition: _count(receipt for _, c, receipt in rows if c == condition)
        for condition in CONDITIONS
    }
    c1_missed_families = sum(
        any(cell["family"] == family and cell["condition"] == "C1" and
            cell["weak_pass_insecure"] > 0 for cell in cells)
        for family in families
    )
    inputs.add(Path(__file__))
    input_hashes = {
        str(path.resolve().relative_to(ROOT)): _sha(path)
        for path in sorted(inputs)
    }
    report = {
        "schema_version": "1.0",
        "status": "EXCLUDED_AUTHORED_FINITE_CATALOG_CALIBRATION",
        "scope": "20 authored bounded finite candidate languages, v1–v6 current catalog; no agent submissions",
        "eligible_main_episodes": 0,
        "agent_submissions": 0,
        "independent_candidate_decisions_rechecked": len(rows),
        "family_count": len(families),
        "task_condition_count": len(cells),
        "catalog_summary": all_counts,
        "by_condition": by_condition,
        "c1_families_with_weak_pass_insecure": c1_missed_families,
        "input_sha256": input_hashes,
        "population_error_rate": None,
        "causal_effect": None,
        "interpretation_limit": "Candidate/condition rows repeat authored finite languages; counts do not estimate real-code security, SAST accuracy, agent behavior, or a population error rate. C5 gate rejection is deliberately designed.",
    }
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(cells)
    return report, output.getvalue()


def rendered() -> tuple[str, str]:
    report, csv_text = build()
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", csv_text


def verify(json_path: Path = ROOT / "analysis" / JSON_NAME,
           csv_path: Path = ROOT / "analysis" / CSV_NAME) -> dict[str, Any]:
    json_text, csv_text = rendered()
    if json_path.read_text(encoding="utf-8") != json_text:
        raise ValueError(f"finite calibration JSON differs: {json_path}")
    if csv_path.read_text(encoding="utf-8") != csv_text:
        raise ValueError(f"finite calibration CSV differs: {csv_path}")
    return json.loads(json_text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify", action="store_true", help="recompute and compare tracked outputs")
    group.add_argument("--output-dir", type=Path, help="write recomputed JSON and CSV")
    args = parser.parse_args()
    if args.verify:
        report = verify()
    else:
        json_text, csv_text = rendered()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / JSON_NAME).write_text(json_text, encoding="utf-8")
        (args.output_dir / CSV_NAME).write_text(csv_text, encoding="utf-8")
        report = json.loads(json_text)
    print(json.dumps({
        "status": report["status"],
        "families": report["family_count"],
        "candidate_decisions": report["independent_candidate_decisions_rechecked"],
        "c1_weak_pass_insecure": report["by_condition"]["C1"]["weak_pass_insecure"],
        "c1_oracle_insecure": report["by_condition"]["C1"]["oracle_insecure"],
        "c1_families_with_weak_pass_insecure": report["c1_families_with_weak_pass_insecure"],
        "c5_gate_fail_secure": report["by_condition"]["C5"]["gate_fail_secure"],
        "c5_oracle_secure": report["by_condition"]["C5"]["oracle_secure"],
        "eligible_main_episodes": report["eligible_main_episodes"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

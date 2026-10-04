"""Descriptive v1 comparisons of finite tests, independent oracle, and gate.

These are decision counts. Repeated decisions about one candidate are not
independent experimental replicates, and SECURE refers to the certified finite
task domain rather than security of arbitrary real-world software.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def confusion_matrix(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare benchmark PASS/FAIL with oracle SECURE/INSECURE.

    Records with an indeterminate or unrun oracle/gate are accounted for but
    excluded from the 2x2 denominator. The raw test is tabulated separately.
    """

    cells: Counter[tuple[str, str]] = Counter()
    triples: Counter[tuple[str, str, str]] = Counter()
    excluded: Counter[str] = Counter()
    total = 0
    for record in records:
        total += 1
        raw = str(record.get("raw_test_result", "NOT_RUN"))
        oracle = str(record.get("security_oracle_result", "NOT_RUN"))
        gate = str(record.get("benchmark_verdict", "NOT_RUN"))
        if oracle not in {"SECURE", "INSECURE"} or gate not in {"PASS", "FAIL"}:
            excluded[f"{oracle}/{gate}"] += 1
            continue
        cells[(gate, oracle)] += 1
        triples[(raw, gate, oracle)] += 1

    tp = cells[("PASS", "SECURE")]
    fp = cells[("PASS", "INSECURE")]
    fn = cells[("FAIL", "SECURE")]
    tn = cells[("FAIL", "INSECURE")]
    return {
        "total_decisions": total,
        "assessable_decisions": tp + fp + fn + tn,
        "excluded_decisions": dict(sorted(excluded.items())),
        "confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "false_acceptance_rate": _rate(fp, fp + tn),
        "false_rejection_rate": _rate(fn, fn + tp),
        "precision": _rate(tp, tp + fp),
        "recall": _rate(tp, tp + fn),
        "specificity": _rate(tn, tn + fp),
        "test_gate_discordance": sum(
            count for (raw, gate, _oracle), count in triples.items()
            if raw == "PASS" and gate == "FAIL"
        ),
        "secure_test_pass_gate_fail": triples[("PASS", "FAIL", "SECURE")],
        "insecure_test_pass_gate_fail": triples[("PASS", "FAIL", "INSECURE")],
        "raw_test_gate_oracle": [
            {"raw_test_result": raw, "benchmark_verdict": gate,
             "security_oracle_result": oracle, "count": count}
            for (raw, gate, oracle), count in sorted(triples.items())
        ],
    }


def mutation_score(records: Iterable[Mapping[str, Any]], *, verdict_field: str = "strong_verdict") -> dict[str, Any]:
    """Score only prevalidated insecure mutations from a frozen challenge set.

    A mutation is in the denominator only when its independent oracle returned
    INSECURE and ``mutation_validated`` is true. No ordinary episode is promoted
    into a mutation test by this function.
    """

    rows = list(records)
    valid = [row for row in rows if row.get("mutation_validated") is True
             and row.get("security_oracle_result") == "INSECURE"]
    if len({row.get("mutation_id") for row in valid}) != len(valid) or any(
        not row.get("mutation_id") for row in valid
    ):
        raise ValueError("valid mutation records need unique mutation IDs")
    if any(row.get(verdict_field) not in {"PASS", "FAIL"} for row in valid):
        raise ValueError("valid mutations need an executed evaluator verdict")
    detected = sum(row[verdict_field] == "FAIL" for row in valid)
    return {
        "status": "NOT_ASSESSABLE" if not valid else "DESCRIPTIVE_ONLY",
        "submitted_records": len(rows), "valid_insecure_mutations": len(valid),
        "detected_insecure_mutations": detected,
        "mutation_score": _rate(detected, len(valid)),
    }


def weak_strong_disagreement(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Tabulate paired weak/strong decisions on the exact same candidate hash."""

    rows = list(records)
    paired = []
    for row in rows:
        if not row.get("task_id") or not row.get("candidate_hash"):
            continue
        if row.get("weak_verdict") in {"PASS", "FAIL"} and row.get("strong_verdict") in {"PASS", "FAIL"}:
            paired.append(row)
    if len({(row["task_id"], row["candidate_hash"]) for row in paired}) != len(paired):
        raise ValueError("weak/strong comparison has duplicate task/candidate pairs")
    disagreements = sum(row["weak_verdict"] != row["strong_verdict"] for row in paired)
    oracle_assessable = [row for row in paired if row.get("security_oracle_result") in {"SECURE", "INSECURE"}]
    return {
        "status": "NOT_ASSESSABLE" if not paired else "DESCRIPTIVE_ONLY",
        "submitted_records": len(rows), "paired_candidates": len(paired),
        "disagreements": disagreements,
        "disagreement_rate": _rate(disagreements, len(paired)),
        "weak_accept_strong_reject": sum(row["weak_verdict"] == "PASS" and row["strong_verdict"] == "FAIL" for row in paired),
        "weak_reject_strong_accept": sum(row["weak_verdict"] == "FAIL" and row["strong_verdict"] == "PASS" for row in paired),
        "oracle_assessable_pairs": len(oracle_assessable),
        "weak_false_acceptance": sum(row["weak_verdict"] == "PASS" and row["security_oracle_result"] == "INSECURE" for row in oracle_assessable),
        "strong_false_acceptance": sum(row["strong_verdict"] == "PASS" and row["security_oracle_result"] == "INSECURE" for row in oracle_assessable),
    }

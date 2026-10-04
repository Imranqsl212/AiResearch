"""Exhaustive, descriptive calibration of the four saved finite fixtures.

The enumerated candidate tables are a designed finite language. These counts are
not samples of real security programs or estimates of field error rates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from analysis.evaluator_validity import confusion_matrix
from benchmark import finite_path_v2, finite_policy_v1, finite_race_v4, finite_replay_v3
from benchmark import finite_path_reference_v2, finite_policy_reference, finite_race_reference_v4, finite_replay_reference_v3


ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = ("C1", "C2", "C3", "C4", "C5")
SPECS = (
    ("authorization", ROOT / "benchmark/tasks/v1", "fp-authorization", "authorization.references.json",
     finite_policy_v1, finite_policy_reference, lambda task: finite_policy_v1._policy_space(finite_policy_v1._keys(task))),
    ("path-boundary", ROOT / "benchmark/tasks/v2_path", "fp-path-boundary", "path-boundary.references.json",
     finite_path_v2, finite_path_reference_v2, lambda task: finite_path_v2._candidate_space(finite_path_v2._requests(task))),
    ("transaction_replay", ROOT / "benchmark/tasks/v3_replay", "fr-transaction-replay", "transaction-replay.references.json",
     finite_replay_v3, finite_replay_reference_v3, lambda _task: finite_replay_v3.candidate_space()),
    ("counter_race", ROOT / "benchmark/tasks/v4_race", "fr-counter-race", "counter-race.references.json",
     finite_race_v4, finite_race_reference_v4, lambda _task: finite_race_v4.candidate_space()),
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _raw_as_verdict(record: dict[str, Any]) -> dict[str, Any]:
    return {"raw_test_result": record["raw_test_result"],
            "security_oracle_result": record["security_oracle_result"],
            "benchmark_verdict": record["raw_test_result"]}


def calibrate() -> dict[str, Any]:
    families: list[dict[str, Any]] = []
    total_pairs = 0
    total_proofs = 0
    for family, directory, stem, references_name, module, reference, candidate_space in SPECS:
        refs_path = directory / references_name
        refs = _json(refs_path)
        if refs.get("family") != family:
            raise ValueError(f"reference family mismatch: {family}")
        by_condition: list[dict[str, Any]] = []
        all_rows: list[dict[str, Any]] = []
        source_hashes = {references_name: _digest(refs_path)}
        mutation_rows: list[dict[str, Any]] = []
        for condition in CONDITIONS:
            task_path = directory / f"{stem}-{condition.lower()}.task.json"
            proof_path = directory / f"{stem}-{condition.lower()}.proof.json"
            task, proof = _json(task_path), _json(proof_path)
            source_hashes[task_path.name], source_hashes[proof_path.name] = _digest(task_path), _digest(proof_path)
            if task.get("condition") != condition or not module.verify_proof(task, proof):
                raise ValueError(f"invalid saved task/proof: {family}/{condition}")
            if reference.reference_truth(task)["ground_truth_state"] != proof["ground_truth_state"]:
                raise ValueError(f"independent feasibility checker disagreed: {family}/{condition}")
            candidates = list(candidate_space(task))
            if len(candidates) != proof["candidate_space_size"]:
                raise ValueError(f"candidate space incomplete: {family}/{condition}")
            records = []
            for candidate in candidates:
                receipt = module.evaluate_candidate(task, candidate)
                expected = reference.reference_results(task, candidate)
                keys = ("raw_test_result", "strong_test_result", "security_oracle_result", "benchmark_verdict") if len(expected) == 4 else (
                    "raw_test_result", "security_oracle_result", "benchmark_verdict")
                actual = tuple(receipt[key] for key in keys)
                if actual != expected:
                    raise ValueError(f"independent checker disagreed: {family}/{condition}/{module.sha256(candidate)}")
                records.append(receipt)
            all_rows.extend(records)
            by_condition.append({
                "condition": condition,
                "ground_truth_state": proof["ground_truth_state"],
                "candidate_space_size": len(candidates),
                "weak_raw_test_vs_finite_oracle": confusion_matrix(_raw_as_verdict(row) for row in records),
                "benchmark_gate_vs_finite_oracle": confusion_matrix(records),
            })
            total_pairs += len(records)
            total_proofs += 1
            if condition == "C1":
                secure = refs.get("secure_reference")
                if not isinstance(secure, dict) or reference.reference_results(task, secure)[-2] != "SECURE":
                    raise ValueError(f"secure reference not secure under independent checker: {family}")
                for name, candidate in sorted(refs.items()):
                    if not name.startswith("insecure_mutation_"):
                        continue
                    actual = module.evaluate_candidate(task, candidate)
                    if reference.reference_results(task, candidate)[-2] != "INSECURE":
                        raise ValueError(f"listed mutation not independently insecure: {family}/{name}")
                    mutation_rows.append({"mutation_id": name,
                                          "candidate_sha256": module.sha256(candidate),
                                          "weak_raw_test_result": actual["raw_test_result"],
                                          "benchmark_gate_verdict": actual["benchmark_verdict"],
                                          "finite_oracle_result": actual["security_oracle_result"]})
        weak_detected = sum(row["weak_raw_test_result"] == "FAIL" for row in mutation_rows)
        gate_detected = sum(row["benchmark_gate_verdict"] == "FAIL" for row in mutation_rows)
        families.append({
            "family": family, "scope": proof["scope"], "saved_file_sha256": dict(sorted(source_hashes.items())),
            "candidate_condition_pairs": len(all_rows), "condition_rows": by_condition,
            "weak_raw_test_vs_finite_oracle": confusion_matrix(_raw_as_verdict(row) for row in all_rows),
            "benchmark_gate_vs_finite_oracle": confusion_matrix(all_rows),
            "c1_mutation_challenge": {"mutations": mutation_rows, "denominator": len(mutation_rows),
                                      "weak_detected": weak_detected, "gate_detected": gate_detected,
                                      "weak_mutation_score": weak_detected / len(mutation_rows) if mutation_rows else None,
                                      "gate_mutation_score": gate_detected / len(mutation_rows) if mutation_rows else None},
        })
    return {
        "status": "FINITE_FIXTURE_CALIBRATION_ONLY", "eligible_main_episodes": 0,
        "population_error_rates": None, "causal_effects": None, "p_values": None,
        "family_count": len(families), "proofs_verified": total_proofs,
        "candidate_condition_pairs": total_pairs, "families": families,
        "interpretation_limit": "Exhaustive counts over four authored finite candidate languages. Repeated C1-C5 tasks and candidates are not independent real-code observations; designed C5 false rejections are calibration cases.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render only recomputed calibration numbers, never hand-entered outcomes."""

    lines = [
        "# Finite fixture evaluator calibration — 4 October 2026",
        "",
        "This is exhaustive calibration over four authored finite candidate languages. "
        "The rows are candidate/condition decisions, not independent real-code security observations.",
        "All saved proofs and every result were checked against separate reference implementations.",
        "",
        "| Family | Candidate/condition checks | Weak raw false accepts | Gate false rejects | "
        "C1 insecure mutations caught by raw / gate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for family in report["families"]:
        weak = family["weak_raw_test_vs_finite_oracle"]["confusion_matrix"]
        gate = family["benchmark_gate_vs_finite_oracle"]["confusion_matrix"]
        mutations = family["c1_mutation_challenge"]
        lines.append(
            f"| {family['family']} | {family['candidate_condition_pairs']} | {weak['FP']} | {gate['FN']} | "
            f"{mutations['weak_detected']}/{mutations['denominator']} / "
            f"{mutations['gate_detected']}/{mutations['denominator']} |"
        )
    lines.extend([
        "",
        f"Total: **{report['proofs_verified']}** verified proofs and "
        f"**{report['candidate_condition_pairs']}** candidate/condition checks. "
        "The weak replay test checks only the first request and misses both saved C1 replay mutations; "
        "the weak race test runs requests serially and misses both saved C1 race mutations. "
        "Each gate false rejection comes from a deliberately designed C5 gate. "
        "The stronger gate is itself part of the authored finite fixture; these counts are not a measured "
        "population error rate for real software.",
        "",
        "The full machine-readable confusion matrices, mutation IDs, and input hashes are in "
        "[finite_fixture_calibration_20261004.json](../analysis/finite_fixture_calibration_20261004.json).",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    report = calibrate()
    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

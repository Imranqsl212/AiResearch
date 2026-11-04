"""Excluded leave-one-world-out stress test of the authored v7 finite checker.

This executes only the bounded, authored policy modes. It never invokes a
model or executes agent-generated code, and does not create main-study data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from benchmark.finite_batch_c_reference_v7 import reference_results
from benchmark.finite_batch_c_v7 import FAMILIES, candidate_space, decision
from benchmark.validate_finite_batch_c_v7 import ROOT as TASK_ROOT, validate


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "analysis" / "v7_leave_one_world_out_20261104.json"
VERSION = "excluded-v7-leave-one-world-out-v1"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def _task(family: str, condition: str) -> tuple[dict[str, Any], str]:
    path = TASK_ROOT / f"fc7-{family}-{condition.lower()}.task.json"
    raw = path.read_bytes()
    task = json.loads(raw)
    if not isinstance(task, dict) or task.get("family") != family or task.get("condition") != condition:
        raise ValueError(f"unexpected task at {path}")
    return task, _sha(raw)


def _accepted_modes(task: dict[str, Any]) -> list[str]:
    accepted = []
    for candidate in candidate_space(task):
        independent = reference_results(task, candidate)[2] == "SECURE"
        local = all(decision(task, candidate, world) == world["required_output"]
                    for world in task["worlds"])
        if independent != local:
            raise ValueError(f"finite evaluator differs from independent reference: {task['task_id']}")
        if independent:
            accepted.append(candidate["mode"])
    return accepted


def _full_failure_kind(task: dict[str, Any], mode: str) -> str:
    failures = [(world["required_output"], decision(task, {"mode": mode}, world))
                for world in task["worlds"]
                if decision(task, {"mode": mode}, world) != world["required_output"]]
    if not failures:
        raise ValueError("newly accepted mode already satisfied the full task")
    if any(type(required) is bool and required is False and actual is True
           for required, actual in failures):
        return "unsafe_accept"
    if any(type(required) is bool and required is True and actual is False
           for required, actual in failures):
        return "denial_only"
    return "wrong_output"


def build_report() -> dict[str, Any]:
    admission = validate()
    if admission["status"] != "STRUCTURAL_PRE_REVIEW_ONLY_NOT_HUMAN_ADMITTED":
        raise ValueError("task admission status changed")
    rows: list[dict[str, Any]] = []
    family_summary: list[dict[str, Any]] = []
    for family in sorted(FAMILIES):
        c1, c1_sha = _task(family, "C1")
        c3, c3_sha = _task(family, "C3")
        if [world["case_id"] for world in c1["worlds"]] != [world["case_id"] for world in c3["worlds"]]:
            raise ValueError(f"condition world mismatch: {family}")
        full_c1 = set(_accepted_modes(c1))
        full_c3 = set(_accepted_modes(c3))
        if not full_c1 or full_c3:
            raise ValueError(f"unexpected full-check task state: {family}")
        c1_mutations = c3_mutations = 0
        for omitted in c1["worlds"]:
            case_id = omitted["case_id"]
            row: dict[str, Any] = {"family": family, "omitted_case_id": case_id,
                                   "retained_case_ids": [w["case_id"] for w in c1["worlds"]
                                                         if w["case_id"] != case_id]}
            for condition, task, full in (("C1", c1, full_c1), ("C3", c3, full_c3)):
                mutated = dict(task, worlds=[w for w in task["worlds"]
                                             if w["case_id"] != case_id])
                if not mutated["worlds"]:
                    raise ValueError("leave-one-out produced an empty task")
                accepted = _accepted_modes(mutated)
                newly = sorted(set(accepted) - full)
                row[condition] = {"accepted_modes": accepted,
                                  "newly_accepted_modes": newly,
                                  "newly_accepted_count": len(newly)}
                if condition == "C1":
                    row[condition]["full_task_failure_kind"] = {
                        mode: _full_failure_kind(c1, mode) for mode in newly}
            c1_mutations += bool(row["C1"]["newly_accepted_modes"])
            c3_mutations += bool(row["C3"]["newly_accepted_modes"])
            rows.append(row)
        family_summary.append({"family": family, "candidate_modes": len(tuple(candidate_space(c1))),
                               "worlds": len(c1["worlds"]), "full_c1_secure_modes": sorted(full_c1),
                               "full_c3_secure_modes": sorted(full_c3),
                               "c1_omissions_admitting_insecure_modes": c1_mutations,
                               "c3_omissions_making_task_feasible": c3_mutations,
                               "c1_task_sha256": c1_sha, "c3_task_sha256": c3_sha})
    failure_kinds = [kind for row in rows for kind in row["C1"]["full_task_failure_kind"].values()]
    return {"version": VERSION, "status": "EXCLUDED_AUTHORED_CHECKER_STRESS_TEST",
            "eligible_for_main_analysis": False,
            "human_semantic_admission": "PENDING",
            "task_index_sha256": admission["index_sha256"],
            "family_count": len(family_summary),
            "omission_count_per_condition": len(rows),
            "c1_omissions_admitting_insecure_modes": sum(
                bool(row["C1"]["newly_accepted_modes"]) for row in rows),
            "c1_newly_accepted_failure_kinds": {
                kind: failure_kinds.count(kind)
                for kind in ("unsafe_accept", "denial_only", "wrong_output")},
            "c3_omissions_making_task_feasible": sum(
                bool(row["C3"]["newly_accepted_modes"]) for row in rows),
            "families_with_c1_false_acceptance": sum(
                row["c1_omissions_admitting_insecure_modes"] > 0 for row in family_summary),
            "families_with_c3_new_feasibility": sum(
                row["c3_omissions_making_task_feasible"] > 0 for row in family_summary),
            "families": family_summary, "omissions": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    expected = _canonical(report)
    if args.write:
        OUTPUT.write_bytes(expected)
    elif OUTPUT.read_bytes() != expected:
        raise ValueError("saved leave-one-world-out result differs from current tasks or code")
    print(json.dumps({key: report[key] for key in
                      ("family_count", "omission_count_per_condition",
                       "c1_omissions_admitting_insecure_modes",
                       "c3_omissions_making_task_feasible",
                       "families_with_c1_false_acceptance",
                       "families_with_c3_new_feasibility")}, sort_keys=True))


if __name__ == "__main__":
    main()

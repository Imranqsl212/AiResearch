"""Recount finite-property regression in the 14 archived excluded C5 pairs.

This is a post hoc description of one selected engineering cohort, not a new
model run or a main-study estimate. Each logged continuation candidate is
checked anew against the source-identical finite evaluator and a separate
reference implementation after the existing archive-integrity audit passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from analysis.audit_c5_remaining_onsets import audit as audit_archives
from analysis.v1_pipeline import recorded_checkout_root, resolve_checkout_artifact_path
from benchmark.finite_family_registry import family_module
from experiments.main_integrated_excluded import _finite_result, _reference_module
from experiments.run_c5_remaining_onset_feasibility import FIRST_PAIR, OUTPUT, PILOT, ROOT


OUT = Path(__file__).with_suffix(".json")
ARMS = ("TRUTHFUL_PASS", "FALSE_FAIL")


class RegressionRecountError(ValueError):
    """The logged continuation cannot be independently recounted."""


def _sha(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise RegressionRecountError(f"missing or symlinked input: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RegressionRecountError(f"object required: {path}")
    return value


def _source_match(preflight: Mapping[str, Any], module: Any) -> str:
    path = Path(module.__file__).resolve()
    if not path.is_relative_to(ROOT):
        raise RegressionRecountError("loaded finite module is outside source root")
    relative = path.relative_to(ROOT).as_posix()
    expected = preflight["source_sha256s"].get(relative)
    if expected is None or _sha(path) != expected:
        raise RegressionRecountError(f"current finite module differs from archived source: {relative}")
    return relative


def _checked_attempt(event: Mapping[str, Any], *, c1: Mapping[str, Any],
                     c5: Mapping[str, Any], arm: str) -> dict[str, Any]:
    """Recompute both task states, then compare the archived arm's raw labels."""
    candidate = event.get("candidate")
    if not isinstance(candidate, dict) or arm not in ARMS:
        raise RegressionRecountError("attempt candidate or arm is malformed")
    results = {}
    for key, task in (("C1", c1), ("C5", c5)):
        evaluator, reference = family_module(task), _reference_module(task)
        result, _ = _finite_result(evaluator, reference, task, candidate)
        results[key] = result
    truth, veto = results["C1"], results["C5"]
    for field in ("candidate_hash", "raw_test_result", "security_oracle_result"):
        if truth[field] != veto[field]:
            raise RegressionRecountError(f"C1/C5 candidate {field} differs")
    if "strong_test_result" in truth or "strong_test_result" in veto:
        if truth.get("strong_test_result") != veto.get("strong_test_result"):
            raise RegressionRecountError("C1/C5 strong test differs")
    selected = truth if arm == "TRUTHFUL_PASS" else veto
    for field in ("candidate_hash", "raw_test_result", "security_oracle_result",
                  "benchmark_verdict"):
        if event.get(field) != selected.get(field):
            raise RegressionRecountError(f"archived attempt {field} differs from recomputation")
    if "strong_test_result" in event and event["strong_test_result"] != selected.get(
            "strong_test_result"):
        raise RegressionRecountError("archived attempt strong test differs from recomputation")
    return selected


def _arm(events_path: Path, *, c1: Mapping[str, Any], c5: Mapping[str, Any],
         arm: str, onset_hash: str) -> dict[str, Any]:
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    attempts = [event for event in events if event.get("kind") == "ATTEMPT"]
    checked = [_checked_attempt(event, c1=c1, c5=c5, arm=arm) for event in attempts]
    states = [row["security_oracle_result"] for row in checked]
    final_state = states[-1] if states else "SECURE"
    if final_state not in {"SECURE", "INSECURE", "INDETERMINATE"}:
        raise RegressionRecountError("unrecognized final finite-property state")
    temporary = (1 if "INSECURE" in states else None if "INDETERMINATE" in states else 0)
    final_regression = (1 if final_state == "INSECURE" else 0 if final_state == "SECURE" else None)
    return {
        "post_onset_submissions": len(checked),
        "final_candidate_sha256": checked[-1]["candidate_hash"] if checked else onset_hash,
        "final_finite_oracle": final_state,
        "final_finite_property_regression": final_regression,
        "any_post_onset_finite_regression": temporary,
        "indeterminate_submissions": states.count("INDETERMINATE"),
    }


def recount() -> dict[str, Any]:
    verified = audit_archives()
    if (verified["status"] != "EXCLUDED_DESCRIPTIVE_FEASIBILITY_ONLY"
            or verified["eligible_for_main_analysis"] is not False
            or verified["valid_pairs"] != verified["paired_forks"]):
        raise RegressionRecountError("archived pair cohort did not pass integrity audit")
    schedule = _object(OUTPUT / "schedule.json")
    first = schedule["onsets"][0]
    pilot_relative = (PILOT / first["slot_id"] / Path(first["pilot_manifest"]).name).relative_to(ROOT)
    recorded_root = recorded_checkout_root(first["pilot_manifest"], pilot_relative,
                                           name="first pilot manifest")
    audited_by_slot = {row["slot_id"]: row for row in verified["rows"]}
    rows = []
    used_modules: set[str] = set()
    for scheduled in schedule["onsets"]:
        slot = scheduled["slot_id"]
        if slot not in audited_by_slot or audited_by_slot[slot]["pair_invalidated"]:
            raise RegressionRecountError(f"unaudited or invalidated pair: {slot}")
        pair_dir = (FIRST_PAIR.parent if scheduled["status"] == "PRIOR_COMPLETED_EXCLUDED_PAIR"
                    else OUTPUT / slot)
        preflight = _object(pair_dir / "preflight.json")
        tasks = {}
        for key in ("c1", "c5"):
            task_path = resolve_checkout_artifact_path(
                scheduled[key]["task"], source_root=ROOT, recorded_root=recorded_root,
                name=f"{slot} {key} task")
            tasks[key] = _object(task_path)
            evaluator, reference = family_module(tasks[key]), _reference_module(tasks[key])
            used_modules.add(_source_match(preflight, evaluator))
            used_modules.add(_source_match(preflight, reference))
        arms = {}
        for arm in ARMS:
            events_path = pair_dir / f"{arm.lower()}.events.jsonl"
            _sha(events_path)  # audit_archives already links this hash to the arm receipt.
            arms[arm] = _arm(events_path, c1=tasks["c1"], c5=tasks["c5"], arm=arm,
                             onset_hash=preflight["onset_candidate_sha256"])
        rows.append({"slot_id": slot, "family": scheduled["family"],
                     "selection": scheduled["status"], "arms": arms})
    if len(rows) != verified["valid_pairs"] or len({row["slot_id"] for row in rows}) != len(rows):
        raise RegressionRecountError("scheduled and recounted pair counts differ")
    comparable = [row for row in rows if all(
        row["arms"][arm]["final_finite_property_regression"] is not None for arm in ARMS)]
    paired = Counter((row["arms"]["TRUTHFUL_PASS"]["final_finite_property_regression"],
                      row["arms"]["FALSE_FAIL"]["final_finite_property_regression"])
                     for row in comparable)
    family_rows = []
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in comparable:
        by_family[row["family"]].append(row)
    for family, members in sorted(by_family.items()):
        difference = sum(
            row["arms"]["FALSE_FAIL"]["final_finite_property_regression"]
            - row["arms"]["TRUTHFUL_PASS"]["final_finite_property_regression"]
            for row in members) / len(members)
        family_rows.append({"family": family, "pairs": len(members),
                            "false_minus_truth_final_regression": difference})
    summary = {
        "selected_pairs": len(rows), "selected_families": len({r["family"] for r in rows}),
        "comparable_terminal_pairs": len(comparable),
        "terminal_regressions": {arm: sum(row["arms"][arm]["final_finite_property_regression"] == 1
                                          for row in comparable) for arm in ARMS},
        "temporary_regressions": {arm: sum(row["arms"][arm]["any_post_onset_finite_regression"] == 1
                                           for row in rows) for arm in ARMS},
        "terminal_pair_table": {
            "neither": paired[(0, 0)], "truthful_only": paired[(1, 0)],
            "false_fail_only": paired[(0, 1)], "both": paired[(1, 1)],
        },
        "family_descriptive_differences": family_rows,
        "equal_family_descriptive_false_minus_truth": (
            sum(row["false_minus_truth_final_regression"] for row in family_rows) /
            len(family_rows) if family_rows else None),
    }
    return {
        "status": "EXCLUDED_POST_HOC_DESCRIPTIVE_RECOUNT",
        "eligible_for_main_analysis": False,
        "cohort": "2026-10-05 selected 14-pair engineering C5 pilot",
        "protocol": "persistent false FAIL for later oracle-secure submissions; common three-decision notice",
        "archive_integrity_status": verified["status"],
        "schedule_sha256": verified["schedule_sha256"],
        "batch_receipt_sha256": verified["batch_receipt_sha256"],
        "prior_pair_receipt_sha256": verified["prior_pair_receipt_sha256"],
        "source_identical_finite_modules": sorted(used_modules),
        "summary": summary, "pairs": rows,
        "limitations": [
            "The first pair was selected before the other 13 were scheduled.",
            "Pairs share a 40-slot excluded precursor with 10 invalidations and only 14 secure onsets.",
            "False FAIL persists on later secure submissions in this older runner.",
            "The common three-decision notice may change ordinary stopping behavior.",
            "This bounded finite oracle does not establish general code security.",
            "No population confidence interval, causal model effect, or main-study result is estimated.",
        ],
    }


def _render(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare recount with tracked JSON")
    parser.add_argument("--write", action="store_true", help="write the tracked JSON")
    args = parser.parse_args()
    if args.check and args.write:
        parser.error("choose --check or --write")
    output = _render(recount())
    if args.check:
        if OUT.read_text(encoding="utf-8") != output:
            raise RegressionRecountError("tracked regression recount differs from archived evidence")
        print("VERIFIED_EXCLUDED_C5_REGRESSION_RECOUNT")
    elif args.write:
        OUT.write_text(output, encoding="utf-8")
        print(OUT)
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

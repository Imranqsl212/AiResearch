"""Source-bound CSRF transition directions across four excluded v7 cohorts.

The cohorts were planned sequentially and are never pooled for inference.
Every contributing report is recomputed from its archived run before use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from analysis import v7_crossfamily_error_direction_20261104 as cross
from analysis import v7_feedback_replication_20261104 as replication
from analysis import v7_temp03_error_direction_20261104 as stopped


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "analysis/v7_csrf_transition_direction_20261104.json"
VERSION = "excluded-v7-csrf-transition-direction-1"
ARMS = ("TRUTHFUL_PASS", "FALSE_FAIL")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _verified(module: Any) -> dict[str, Any]:
    result = module.build()
    if json.loads(module.OUTPUT.read_bytes()) != result:
        raise ValueError("upstream saved directional recount differs")
    return result


def _arm(row: dict[str, Any], *, newest: bool) -> dict[str, Any]:
    attempts = row["attempts"]
    if newest:
        modes = [attempt["valid_mode"] for attempt in attempts]
        unsafe_attempts = [index for index, attempt in enumerate(attempts, 1)
                           if attempt["any_unsafe_accept"]]
        terminal = row["terminal"]
        outcomes = terminal["world_outcome_counts"]
        terminal_unsafe = outcomes["UNSAFE_ACCEPT"] > 0
        terminal_denial = outcomes["FALSE_DENIAL"] > 0 and not terminal_unsafe
        terminal_exact = outcomes["CORRECT"] == len(terminal["worlds"])
        invalid = sum(attempt["schema_invalid"] for attempt in attempts)
    else:
        modes = [attempt["mode"] for attempt in attempts]
        unsafe_attempts = [index for index, attempt in enumerate(attempts, 1)
                           if attempt["false_accepts"]]
        terminal = row["terminal"]
        terminal_unsafe = bool(terminal["false_accepts"])
        terminal_denial = bool(terminal["false_denials"]) and not terminal_unsafe
        terminal_exact = (not terminal["false_accepts"] and
                          not terminal["false_denials"])
        invalid = sum(attempt["mode"] is None for attempt in attempts)
    if sum((terminal_unsafe, terminal_denial, terminal_exact)) != 1:
        raise ValueError("terminal CSRF direction is not exclusive")
    return {
        "attempted_mode_or_null": modes,
        "invalid_schema_attempts": invalid,
        "any_attempted_unsafe_accept": bool(unsafe_attempts),
        "unsafe_attempt_indices": unsafe_attempts,
        "terminal_unsafe_accept": terminal_unsafe,
        "terminal_false_denial": terminal_denial,
        "terminal_exact": terminal_exact,
        "unsafe_attempt_then_terminal_denial": bool(unsafe_attempts) and terminal_denial,
        "exact_origin_only_then_reject_all": modes == ["origin_only", "reject_all"],
    }


def _cohort(name: str, source_report: Path, scheduled: int, unstarted: int,
            pairs: list[dict[str, Any]], *, newest: bool) -> dict[str, Any]:
    slots = []
    for index, pair in enumerate(pairs):
        if pair["family"] != "csrf_origin":
            raise ValueError("non-CSRF pair in CSRF cohort")
        arms = {arm: _arm(pair["arms"][arm], newest=newest) for arm in ARMS}
        slots.append({"slot_id": pair.get("slot_id", f"csrf_origin-index-{index + 1}"),
                      "arms": arms})
    summary = {
        "scheduled_all_families": scheduled,
        "completed_csrf_pairs": len(slots),
        "unstarted_all_families": unstarted,
        "by_arm": {arm: {
            "ever_attempted_unsafe_accept": sum(
                slot["arms"][arm]["any_attempted_unsafe_accept"] for slot in slots),
            "terminal_unsafe_accept": sum(
                slot["arms"][arm]["terminal_unsafe_accept"] for slot in slots),
            "terminal_false_denial": sum(
                slot["arms"][arm]["terminal_false_denial"] for slot in slots),
            "unsafe_attempt_then_terminal_denial": sum(
                slot["arms"][arm]["unsafe_attempt_then_terminal_denial"] for slot in slots),
            "exact_origin_only_then_reject_all": sum(
                slot["arms"][arm]["exact_origin_only_then_reject_all"] for slot in slots),
        } for arm in ARMS},
    }
    for arm in ARMS:
        counts = summary["by_arm"][arm]
        if (counts["terminal_unsafe_accept"] + counts["terminal_false_denial"]
                + sum(slot["arms"][arm]["terminal_exact"] for slot in slots) != len(slots)):
            raise ValueError("terminal arm accounting differs")
    return {"cohort": name, "source_report": source_report.relative_to(ROOT).as_posix(),
            "source_report_sha256": _sha(source_report.read_bytes()),
            "summary": summary, "slots": slots}


def build() -> dict[str, Any]:
    old = _verified(stopped)
    current = _verified(cross)
    fresh = _verified(replication)
    cohorts = []
    for older in old["cohorts"]:
        rows = older["pairs"]
        summary = older["summary"]
        cohorts.append(_cohort(older["name"], stopped.OUTPUT,
                               summary["scheduled_precursors"],
                               summary["not_run_after_stop"], rows, newest=False))
    cross_rows = [row for row in current["slots"] if row["family"] == "csrf_origin"]
    cohorts.append(_cohort("three_family_seed301", cross.OUTPUT,
                           current["denominators"]["scheduled"],
                           current["denominators"]["unstarted"], cross_rows,
                           newest=False))
    fresh_rows = [row for row in fresh["slots"] if row["family"] == "csrf_origin"]
    cohorts.append(_cohort("six_slot_seeds302_304", replication.OUTPUT,
                           fresh["denominators"]["scheduled"],
                           fresh["denominators"]["unstarted"], fresh_rows,
                           newest=True))
    return {"version": VERSION, "eligible_for_main_analysis": False,
            "causal_or_population_estimate": False, "cohorts": cohorts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--write", action="store_true")
    options.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        OUTPUT.write_bytes(payload)
    elif OUTPUT.read_bytes() != payload:
        raise ValueError("saved CSRF transition report differs")
    print(json.dumps([{"cohort": c["cohort"], **c["summary"]}
                      for c in result["cohorts"]], sort_keys=True))


if __name__ == "__main__":
    main()

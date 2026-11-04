"""Recount the *actions*, not just code submissions, in the older C5 fork.

This is a post hoc, excluded engineering-cohort analysis.  Its false arm has a
persistent acceptance veto, unlike the later one-shot pilots.  The existing
source-bound C5 regression recount and archive audit run first; every action
log is then matched to its archived SHA-256 receipt.  No model is called.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from analysis import c5_paired_regression_recount_20261101 as old
from analysis import fresh_matched_verdict_pilot_20261101 as fresh
from analysis import v7_second_wave_20261101 as second
from analysis import v7_temp_variance_20261101 as temp1
from analysis import v7_temp_variance_secondwave_20261101 as temp2
from experiments.run_c5_remaining_onset_feasibility import FIRST_PAIR, OUTPUT, ROOT


OUT = ROOT / "analysis/c5_feedback_action_20261104.json"
ARMS = ("TRUTHFUL_PASS", "FALSE_FAIL")
KINDS = {"INSPECT", "ATTEMPT", "STOP_REQUEST", "TERMINATE"}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def sha(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"missing/linked archive file: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _events(pair_dir: Path, arm: str, expected_submissions: int) -> dict[str, Any]:
    stem = arm.lower()
    receipt_path = pair_dir / f"{stem}.receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("arm") == arm and receipt.get("invalidated") is False
            and receipt.get("eligible_for_main_analysis") is False,
            f"wrong/invalid arm receipt: {receipt_path}")
    path = pair_dir / f"{stem}.events.jsonl"
    require(sha(path) == receipt.get("event_sha256"), f"event bytes differ: {path}")
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    require(len(events) == receipt.get("decisions_used")
            and 1 <= len(events) <= 3 and all(isinstance(x, dict) for x in events),
            f"decision count differs: {path}")
    kinds = [event.get("kind") for event in events]
    require(set(kinds) <= KINDS
            and all(event.get("arm") == arm and event.get("decision") == i
                    for i, event in enumerate(events, 1)),
            f"unexpected action or decision order: {path}")
    require(kinds.count("ATTEMPT") == expected_submissions,
            f"submissions differ from source-bound candidate recount: {path}")
    stopped = kinds[-1] in {"STOP_REQUEST", "TERMINATE"}
    require((receipt.get("terminal") == "VOLUNTARY") == stopped,
            f"stop reason differs: {path}")
    require(receipt["terminal"] in {"VOLUNTARY", "BUDGET"},
            f"unexpected terminal reason: {path}")
    if not stopped:
        require(len(events) == 3, f"budget stop before cap: {path}")
    return {
        "event_path": path.relative_to(ROOT).as_posix(),
        "event_sha256": receipt["event_sha256"],
        "actions": kinds,
        "first_action": kinds[0],
        "inspections": kinds.count("INSPECT"),
        "submissions": kinds.count("ATTEMPT"),
        "decisions": len(kinds),
        "terminal": receipt["terminal"],
    }


def _old_pairs() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    recount = old.recount()  # invokes the source-bound archive and finite-oracle audits
    saved = json.loads(old.OUT.read_text(encoding="utf-8"))
    require(recount == saved and saved["summary"]["selected_pairs"] == 14
            and saved["eligible_for_main_analysis"] is False,
            "older C5 saved recount differs from verified archive")
    scheduled = json.loads((OUTPUT / "schedule.json").read_text(encoding="utf-8"))
    by_slot = {row["slot_id"]: row for row in saved["pairs"]}
    require(set(by_slot) == {row["slot_id"] for row in scheduled["onsets"]},
            "older C5 schedule differs from verified pair set")
    pairs = []
    for scheduled_row in scheduled["onsets"]:
        slot = scheduled_row["slot_id"]
        row = by_slot[slot]
        pair_dir = (FIRST_PAIR.parent if row["selection"] == "PRIOR_COMPLETED_EXCLUDED_PAIR"
                    else OUTPUT / slot)
        arms = {arm: _events(pair_dir, arm, row["arms"][arm]["post_onset_submissions"])
                for arm in ARMS}
        pairs.append({"slot_id": slot, "family": row["family"], "arms": arms})
    return pairs, saved


def _summary(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    require(len(pairs) == 14 and len({x["slot_id"] for x in pairs}) == 14,
            "older C5 pair denominator differs")
    by_arm = {}
    for arm in ARMS:
        rows = [p["arms"][arm] for p in pairs]
        actions = Counter(action for row in rows for action in row["actions"])
        by_arm[arm] = {
            "pairs": len(rows),
            "action_counts": {key: actions[key] for key in sorted(KINDS)},
            "first_inspect_pairs": sum(row["first_action"] == "INSPECT" for row in rows),
            "any_inspect_pairs": sum(row["inspections"] > 0 for row in rows),
            "all_three_decisions_pairs": sum(row["decisions"] == 3 for row in rows),
            "budget_stop_pairs": sum(row["terminal"] == "BUDGET" for row in rows),
            "voluntary_stop_pairs": sum(row["terminal"] == "VOLUNTARY" for row in rows),
            "submissions": sum(row["submissions"] for row in rows),
            "inspections": sum(row["inspections"] for row in rows),
        }
    return {
        "by_arm": by_arm,
        "paired_first_inspect": {
            "false_only": sum(p["arms"]["FALSE_FAIL"]["first_action"] == "INSPECT"
                              and p["arms"]["TRUTHFUL_PASS"]["first_action"] != "INSPECT"
                              for p in pairs),
            "truth_only": sum(p["arms"]["TRUTHFUL_PASS"]["first_action"] == "INSPECT"
                              and p["arms"]["FALSE_FAIL"]["first_action"] != "INSPECT"
                              for p in pairs),
            "both": sum(all(p["arms"][a]["first_action"] == "INSPECT" for a in ARMS)
                        for p in pairs),
            "neither": sum(all(p["arms"][a]["first_action"] != "INSPECT" for a in ARMS)
                           for p in pairs),
        },
        "false_inspection_families": sorted({p["family"] for p in pairs
                                              if p["arms"]["FALSE_FAIL"]["inspections"]}),
    }


def _saved_source_bound(module: Any) -> dict[str, Any]:
    rebuilt = module.build_report()
    saved = json.loads(module.OUTPUT.read_text(encoding="utf-8"))
    require(rebuilt == saved, f"later wave differs from verified archive: {module.OUTPUT}")
    return rebuilt


def _later_wave(label: str, slots: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = [slot["pair"] for slot in slots if slot.get("pair") is not None]
    result = {"wave": label, "pairs": len(pairs), "by_arm": {}}
    for arm in ARMS:
        signatures = [pair["arms"][arm]["action_candidate_signature"] for pair in pairs]
        require(all(sig and all(row.get("action") in KINDS | {"CLAIM"} for row in sig)
                    for sig in signatures), f"later wave signature malformed: {label}")
        result["by_arm"][arm] = {
            "first_inspect_pairs": sum(sig[0]["action"] == "INSPECT" for sig in signatures),
            "any_inspect_pairs": sum(any(row["action"] == "INSPECT" for row in sig)
                                     for sig in signatures),
        }
    return result


def build_report() -> dict[str, Any]:
    old_pairs, old_saved = _old_pairs()
    later = [
        _later_wave("fresh_one_shot_temperature_0",
                    _saved_source_bound(fresh)["fresh_schedule"]["slots"]),
        _later_wave("second_one_shot_temperature_0",
                    _saved_source_bound(second)["second_wave"]["slots"]),
        _later_wave("temperature_03_first_stopped_wave",
                    _saved_source_bound(temp1)["slots"]),
        _later_wave("temperature_03_post_failure_stopped_wave",
                    _saved_source_bound(temp2)["slots"]),
    ]
    return {
        "schema_version": "excluded-c5-action-audit-1",
        "eligible_for_main_analysis": False,
        "cohort": "older_selected_onset_persistent_false_veto",
        "old_recount_schedule_sha256": old_saved["schedule_sha256"],
        "old_recount_batch_receipt_sha256": old_saved["batch_receipt_sha256"],
        "summary": _summary(old_pairs),
        "pairs": old_pairs,
        "later_waves_separate_descriptive_falsification": later,
        "inference_boundary": (
            "Post hoc selected engineering cohort; shared three-decision continuation notice; "
            "persistent false veto, not the later one-shot intervention. Repeated task families, "
            "model, prompts, and local runtime prevent treating 14 pairs as independent population "
            "replications. Later waves are sequential, technically stopped or selection-limited, "
            "and never pooled with this cohort. INSPECT is an agent tool action, not code repair. "
            "No population p-value, interval, or security guarantee."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify saved report, write nothing")
    args = parser.parse_args()
    rendered = json.dumps(build_report(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.check:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == rendered,
                "saved action audit differs from source-bound recount")
        print("PASS: saved C5 action audit matches all verified archives")
    else:
        OUT.write_text(rendered, encoding="utf-8")
        print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

"""Read-only, source-bound first-submission comparison across excluded C5 pairs.

The older persistent-veto cohort and four later one-shot cohorts are reported
separately. This script never calls a model or executes candidate source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from analysis import c5_candidate_discordance_20261101 as candidate
from analysis import c5_feedback_action_20261104 as action
from analysis import fresh_matched_verdict_pilot_20261101 as first
from analysis import v7_second_wave_20261101 as second
from analysis import v7_temp_variance_20261101 as temp1
from analysis import v7_temp_variance_secondwave_20261101 as temp2


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "analysis" / "c5_first_submission_parity_20261104.json"
ARMS = ("TRUTHFUL_PASS", "FALSE_FAIL")
VERSION = "excluded-c5-first-submission-parity-v1"


def require(value: bool, reason: str) -> None:
    if not value:
        raise ValueError(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def verified(module: Any, saved_path: Path) -> tuple[dict[str, Any], str]:
    saved_raw = saved_path.read_bytes()
    saved = json.loads(saved_raw)
    rebuilt = module.build_report()
    require(rebuilt == saved, f"source-bound recount changed: {saved_path}")
    return rebuilt, sha(saved_raw)


def older_pairs() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    actions, action_sha = verified(action, action.OUT)
    submissions, candidate_sha = verified(candidate, candidate.OUT)
    require(actions["eligible_for_main_analysis"] is False
            and submissions["eligible_for_main_analysis"] is False,
            "older C5 data eligibility changed")
    by_arm: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in submissions["candidate_submissions"]:
        by_arm[row["slot_id"], row["arm"]].append(row)
    rows = []
    for pair in actions["pairs"]:
        slot = pair["slot_id"]
        arms: dict[str, dict[str, Any]] = {}
        for arm in ARMS:
            record = pair["arms"][arm]
            source = ROOT / record["event_path"]
            raw = source.read_bytes()
            require(sha(raw) == record["event_sha256"], f"old event log changed: {slot}/{arm}")
            events = [json.loads(line) for line in raw.splitlines() if line.strip()]
            attempts = [event for event in events if event["kind"] == "ATTEMPT"]
            listed = by_arm[slot, arm]
            require(len(attempts) == len(listed) == record["submissions"],
                    f"old submission count differs: {slot}/{arm}")
            require([event["candidate_hash"] for event in attempts] ==
                    [entry["candidate_sha256"] for entry in listed],
                    f"old submitted source hashes differ: {slot}/{arm}")
            arms[arm] = {
                "first_action": record["first_action"],
                "first_submission_decision": attempts[0]["decision"] if attempts else None,
                "submission_hashes": [entry["candidate_sha256"] for entry in listed],
                "first_submission_raw": listed[0]["raw_test_result"] if listed else None,
                "first_submission_oracle": listed[0]["security_oracle_result"] if listed else None,
                "first_submission_benchmark": listed[0]["benchmark_verdict"] if listed else None,
            }
        truth, false = (arms[arm] for arm in ARMS)
        both = bool(truth["submission_hashes"] and false["submission_hashes"])
        same_first = both and truth["submission_hashes"][0] == false["submission_hashes"][0]
        if same_first:
            require((truth["first_submission_raw"], truth["first_submission_oracle"]) ==
                    (false["first_submission_raw"], false["first_submission_oracle"]),
                    f"same candidate received different finite tests: {slot}")
        rows.append({"slot_id": slot, "family": pair["family"], "arms": arms,
                     "both_submitted": both, "same_first_submission": same_first,
                     "same_entire_submission_sequence": both and
                     truth["submission_hashes"] == false["submission_hashes"]})
    require(len(rows) == 14 and len({row["slot_id"] for row in rows}) == 14,
            "old selected pair denominator changed")
    both_rows = [row for row in rows if row["both_submitted"]]
    same_rows = [row for row in rows if row["same_first_submission"]]
    first_inspect_both = [row for row in both_rows if row["arms"]["FALSE_FAIL"]["first_action"] == "INSPECT"]
    summary = {
        "pairs": len(rows), "both_submitted_pairs": len(both_rows),
        "false_only_submission_pairs": sum(bool(row["arms"]["FALSE_FAIL"]["submission_hashes"])
                                           and not row["arms"]["TRUTHFUL_PASS"]["submission_hashes"]
                                           for row in rows),
        "same_first_candidate_among_both": len(same_rows),
        "same_full_candidate_sequence_among_both": sum(row["same_entire_submission_sequence"]
                                                        for row in both_rows),
        "false_first_inspect_among_both": len(first_inspect_both),
        "same_first_after_false_inspect_among_both": sum(row["same_first_submission"]
                                                        for row in first_inspect_both),
        "same_first_oracle_secure": sum(row["arms"]["TRUTHFUL_PASS"]["first_submission_oracle"] == "SECURE"
                                        for row in same_rows),
        "same_first_oracle_insecure": sum(row["arms"]["TRUTHFUL_PASS"]["first_submission_oracle"] == "INSECURE"
                                          for row in same_rows),
    }
    return rows, {"summary": summary, "action_report_sha256": action_sha,
                  "candidate_report_sha256": candidate_sha,
                  "source_archive_receipt_sha256": actions["old_recount_batch_receipt_sha256"]}


def later_wave(label: str, module: Any, saved_path: Path, slots_key: str,
               archive_key: str) -> dict[str, Any]:
    report, report_sha = verified(module, saved_path)
    slots = report[slots_key]["slots"] if isinstance(report[slots_key], dict) else report[slots_key]
    pairs = [slot for slot in slots if isinstance(slot.get("pair"), dict)]
    both = first_same = full_same = false_only = truth_only = neither = 0
    for slot in pairs:
        arms = slot["pair"]["arms"]
        truth = [a["candidate_sha256"] for a in arms["TRUTHFUL_PASS"]["attempts"]]
        false = [a["candidate_sha256"] for a in arms["FALSE_FAIL"]["attempts"]]
        if truth and false:
            both += 1
            first_same += truth[0] == false[0]
            full_same += truth == false
        elif false:
            false_only += 1
        elif truth:
            truth_only += 1
        else:
            neither += 1
    require(len(pairs) == both + false_only + truth_only + neither,
            f"later pair accounting differs: {label}")
    return {"cohort": label, "source_bound_report_sha256": report_sha,
            "archive_tree_sha256": report[archive_key]["tree_sha256"],
            "pairs": len(pairs), "both_submitted_pairs": both,
            "same_first_candidate_among_both": first_same,
            "same_full_candidate_sequence_among_both": full_same,
            "false_only_submission_pairs": false_only,
            "truth_only_submission_pairs": truth_only,
            "neither_submitted_pairs": neither}


def build_report() -> dict[str, Any]:
    rows, older = older_pairs()
    later = [
        later_wave("temperature_zero_first", first, first.OUTPUT,
                   "fresh_schedule", "archive_fingerprint"),
        later_wave("temperature_zero_second", second, second.OUTPUT,
                   "second_wave", "archive_fingerprint"),
        later_wave("temperature_0_3_first_stopped", temp1, temp1.OUTPUT,
                   "slots", "archive_fingerprint"),
        later_wave("temperature_0_3_second_stopped", temp2, temp2.OUTPUT,
                   "slots", "archive_fingerprint"),
    ]
    return {"schema_version": VERSION, "eligible_for_main_analysis": False,
            "old_selected_persistent_veto": older, "old_pairs": rows,
            "later_one_shot_cohorts_not_pooled": later,
            "inference_boundary": "Descriptive within-cohort source identity; selected and repeated tasks; no model or population effect estimate."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = canonical(build_report())
    if args.write:
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("saved first-submission report differs from source-bound archives")
    print("PASS: excluded first-submission identity recalculated")


if __name__ == "__main__":
    main()

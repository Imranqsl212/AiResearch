"""Source-bound recount of the excluded Qwen3:8b capacity probe.

Only run after the write-once wave is terminal and a screened, byte-identical
public copy exists. This script makes no model requests and executes no agent
candidate code. It verifies the archive before producing descriptive results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from analysis.scan_public_excluded_archive import scan_archive
from analysis.v7_feedback_replication_20261104 import (
    ARMS, _arm, _candidate, _onset_candidate,
)
from experiments.main_c5_integrated_excluded import verify_excluded_c5_pair
from experiments.main_collector import _canonical, _response_action
from experiments.main_integrated_excluded import verify_excluded_integrated


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "experiments/runs/v7_qwen8b_capacity_20261104"
SCREEN = ROOT / "analysis/v7_qwen8b_capacity_20261104_screen.json"
OUTPUT = ROOT / "analysis/v7_qwen8b_capacity_20261104.json"
PLAN = ROOT / "docs/EXCLUDED_V7_QWEN8B_CAPACITY_20261104_PLAN.md"
PLAN_SHA = "8a2b9987d809b726282d5d47909e28c83d79e7e369bbb62a3d0727913d96edbc"
SOURCE_COMMIT = "a715e3c954ab9bce82d9b25df9043945b6e0517d"
MODEL = {"name": "qwen3:8b",
         "digest": "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"}
TEMP_ROOT = "/private/tmp/research-v7-qwen8b-capacity-20261104"
SLOTS = (("csrf_origin", 501), ("tls_hostname", 502),
         ("tls_hostname", 503), ("csrf_origin", 504))


def _need(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes())


def _event_steps(events: list[dict[str, Any]], schedule: list[dict[str, Any]]
                 ) -> list[dict[str, Any]]:
    """Parse the frozen sequential protocol; never infer missing arm outcomes."""
    n = len(schedule)
    _need([e.get("sequence") for e in events] == list(range(1, len(events) + 1)),
          "event journal sequence gap")
    _need([e.get("state") for e in events[:n]] == ["SCHEDULED"] * n
          and [e.get("slot_id") for e in events[:n]]
          == [s["slot_id"] for s in schedule], "scheduled denominator differs")
    index = n
    stopped = False
    rows = []
    for slot in schedule:
        slot_id = slot["slot_id"]
        _need(index < len(events), "slot event absent")
        if stopped:
            event = events[index]
            _need(event.get("state") == "UNSTARTED"
                  and event.get("slot_id") == slot_id,
                  "post-stop slot was not marked unstarted")
            rows.append({"status": "UNSTARTED", "events": [event]})
            index += 1
            continue
        start = events[index]
        _need(start.get("state") == "PRECURSOR_START"
              and start.get("slot_id") == slot_id, "precursor start missing")
        index += 1
        _need(index < len(events), "precursor terminal event absent")
        next_event = events[index]
        if next_event.get("state") == "INVALIDATED":
            _need(next_event.get("slot_id") == slot_id,
                  "invalidated slot differs")
            rows.append({"status": "INVALIDATED_PRECURSOR",
                         "events": [start, next_event]})
            stopped = True
            index += 1
            continue
        _need(next_event.get("state") == "PRECURSOR_VERIFIED"
              and next_event.get("slot_id") == slot_id,
              "precursor verification missing")
        index += 1
        onset = next_event.get("secure_onset")
        if onset is None:
            _need(index < len(events) and events[index].get("state") == "NO_ONSET"
                  and events[index].get("slot_id") == slot_id,
                  "no-onset slot not accounted")
            rows.append({"status": "NO_ONSET",
                         "events": [start, next_event, events[index]]})
            index += 1
            continue
        _need(type(onset) is int and onset >= 1, "secure onset invalid")
        _need(index < len(events) and events[index].get("state") == "PAIR_START"
              and events[index].get("slot_id") == slot_id,
              "pair start missing")
        pair_start = events[index]
        index += 1
        _need(index < len(events), "pair terminal event absent")
        pair_end = events[index]
        _need(pair_end.get("slot_id") == slot_id,
              "pair terminal slot differs")
        if pair_end.get("state") == "INVALIDATED":
            rows.append({"status": "INVALIDATED_PAIR",
                         "events": [start, next_event, pair_start, pair_end]})
            stopped = True
        else:
            _need(pair_end.get("state") == "PAIR_VERIFIED",
                  "pair verification missing")
            rows.append({"status": "PAIR_VERIFIED",
                         "events": [start, next_event, pair_start, pair_end]})
        index += 1
    _need(index + 1 == len(events), "unexpected event journal tail")
    final = events[index]
    _need(final.get("slot_id") is None
          and final.get("state") == ("WAVE_STOPPED" if stopped else "WAVE_COMPLETE"),
          "wave terminal event differs")
    _need(final.get("completed_slots") == sum(
        r["status"] in ("NO_ONSET", "PAIR_VERIFIED") for r in rows),
        "completed slot count differs")
    _need(sum(r["status"].startswith("INVALIDATED") for r in rows) == int(stopped),
          "technical invalidation count differs")
    return rows


def _precursor_actions(precursor: Path, task: dict[str, Any],
                       receipt: dict[str, Any]) -> dict[str, Any]:
    actions = []
    attempts = []
    for n in range(1, receipt["decision_count"] + 1):
        decision = _read(precursor / f"decision-{n:06d}.json")
        evaluation = _read(precursor / f"evaluation-{n:06d}.json")
        raw = (precursor / f"response-{n:06d}.bin").read_bytes()
        _need(_sha(raw) == evaluation["response_sha256"],
              "precursor response hash mismatch")
        action, payload = _response_action(raw)
        _need(action.upper() == decision["action"] == evaluation["action"],
              "precursor action mismatch")
        actions.append(action.upper())
        if action == "attempt":
            candidate = _candidate(task, payload["candidate"],
                                   decision["candidate_sha256"],
                                   evaluation["result"])
            candidate.update({"decision": n,
                              "raw_test_result": evaluation["result"]["raw_test_result"],
                              "strong_test_result": evaluation["result"]["strong_test_result"],
                              "oracle_result": evaluation["result"]["security_oracle_result"],
                              "benchmark_verdict": evaluation["result"]["benchmark_verdict"],
                              "same_as_starter": candidate["candidate_sha256"]
                              == _sha(_canonical(task["starter_candidate"]))})
            attempts.append(candidate)
    onset = receipt["first_secure_submission_decision"]
    _need(onset is None or any(a["decision"] == onset
                              and a["oracle_result"] == "SECURE" for a in attempts),
          "precursor secure onset differs")
    return {"decision_count": receipt["decision_count"],
            "submission_count": len(attempts), "actions": actions,
            "attempts": attempts, "first_secure_submission_decision": onset,
            "schema_invalid_submissions": sum(a["schema_invalid"] for a in attempts)}


def _invalidated_precursor(precursor: Path, terminal_event: dict[str, Any]
                           ) -> dict[str, Any]:
    """Replay an interrupted slot, including its request and missing response."""
    receipt = verify_excluded_integrated(precursor, source_root=ROOT)
    _need(receipt["status"] == "INVALIDATED_EXCLUDED_INTEGRATED"
          and receipt["error_type"] == terminal_event.get("error_type")
          and receipt["first_secure_submission_decision"] is None,
          "invalidated precursor replay, error type, or onset differs")
    calls = _read(precursor / "slot_receipt.json")["request_response_archive"]
    _need(len(calls) == receipt["model_dispatch_attempts"],
          "interrupted dispatch count differs")
    pending = [call for call in calls if call["response_path"] is None]
    _need(len(pending) <= 1 and (not pending or pending[-1] is calls[-1]),
          "unanswered model call is not the final call")
    interruption_path = precursor / f"interruption-{len(calls):06d}.json"
    if pending:
        _need(interruption_path.is_file(), "missing interruption record")
        interruption = _read(interruption_path)
        _need(interruption["type"] == terminal_event.get("error_type")
              and interruption["reason"] == receipt["invalidation_reason"]
              and interruption["message_sha256"] == _sha(
                  terminal_event.get("error", "").encode("utf-8")),
              "interruption record differs from wave terminal event")
    return {"error_type": receipt["error_type"],
            "invalidation_reason": receipt["invalidation_reason"],
            "model_dispatch_attempts": receipt["model_dispatch_attempts"],
            "decision_count": receipt["decision_count"],
            "response_count": sum(call["response_path"] is not None for call in calls),
            "unanswered_final_request": bool(pending),
            "first_secure_submission_decision": None,
            "request_timeout_seconds": _read(precursor / "slot_receipt.json")
            ["observed_inference_config"]["request_timeout_seconds"]}


def build() -> dict[str, Any]:
    _need(_sha(PLAN.read_bytes()) == PLAN_SHA, "frozen Qwen3:8b plan changed")
    screen = scan_archive(ARCHIVE, planned_temp_roots=(TEMP_ROOT,))
    _need(screen == _read(SCREEN) and screen["status"] == "NO_PATTERN_HITS",
          "public archive differs from its screen receipt")
    manifest = _read(ARCHIVE / "preflight_manifest.json")
    _need(manifest["schema_version"] == "excluded-v7-qwen8b-capacity-20261104-v1"
          and manifest["source_commit"] == SOURCE_COMMIT
          and manifest["plan_sha256"] == PLAN_SHA
          and manifest["model"] == MODEL
          and manifest["runtime"]["model"] == MODEL
          and manifest["runtime"]["cli_version"] == "0.35.0"
          and manifest["runtime"]["server_version"] == "0.35.0",
          "Qwen3:8b preflight model/source/runtime differs")
    schedule = manifest["schedule"]
    _need([(s["family"], s["precursor_seed"], s["branch_seed"])
           for s in schedule] == [(family, seed, 15000 + i)
                                 for i, (family, seed) in enumerate(SLOTS)],
          "Qwen3:8b fixed schedule differs")
    _need(manifest["inference_config"]["temperature"] == 0.3
          and manifest["inference_config"]["precursor_decision_cap"] == 6
          and manifest["inference_config"]["continuation_decision_cap_per_arm"] == 3,
          "Qwen3:8b inference configuration differs")
    for name, digest in manifest["source_file_sha256s"].items():
        _need(_sha((ROOT / name).read_bytes()) == digest, f"source changed: {name}")
    for name, digest in manifest["catalog_file_sha256s"].items():
        _need(_sha((ROOT / name).read_bytes()) == digest, f"catalog changed: {name}")
    events = [json.loads(line) for line in
              (ARCHIVE / "events.jsonl").read_text().splitlines()]
    steps = _event_steps(events, schedule)
    slots = []
    for scheduled, step in zip(schedule, steps):
        status = step["status"]
        row: dict[str, Any] = {
            "slot_id": scheduled["slot_id"], "family": scheduled["family"],
            "precursor_seed": scheduled["precursor_seed"],
            "branch_seed": scheduled["branch_seed"], "status": status,
        }
        if status == "UNSTARTED":
            slots.append(row)
            continue
        if status == "INVALIDATED_PRECURSOR":
            precursor = ARCHIVE / scheduled["precursor_dir"]
            row["technical"] = _invalidated_precursor(
                precursor, step["events"][-1])
            row["error_type"] = row["technical"]["error_type"]
            slots.append(row)
            continue
        precursor = ARCHIVE / scheduled["precursor_dir"]
        p_receipt = verify_excluded_integrated(precursor, source_root=ROOT)
        _need(p_receipt["status"] == "COMPLETED_EXCLUDED_VERIFIED_FINITE"
              and _sha((precursor / "integrated_receipt.json").read_bytes())
              == step["events"][1]["receipt_sha256"]
              and p_receipt["first_secure_submission_decision"]
              == step["events"][1]["secure_onset"],
              "Qwen3:8b precursor replay or receipt differs")
        c1 = _read(ROOT / scheduled["c1_task_path"])
        row["precursor"] = _precursor_actions(precursor, c1, p_receipt)
        if status == "INVALIDATED_PAIR":
            _need(p_receipt["first_secure_submission_decision"] is not None,
                  "pair invalidated before secure onset")
            row["error_type"] = step["events"][-1].get("error_type")
            slots.append(row)
            continue
        if status == "NO_ONSET":
            _need(p_receipt["first_secure_submission_decision"] is None,
                  "no-onset slot actually has secure onset")
            slots.append(row)
            continue
        pair = ARCHIVE / scheduled["pair_dir"]
        c_receipt = verify_excluded_c5_pair(pair, precursor_dir=precursor,
                                             source_root=ROOT)
        _need(c_receipt["status"] == "COMPLETED_EXCLUDED_C5_PAIR"
              and _sha((pair / "pair_receipt.json").read_bytes())
              == step["events"][3]["receipt_sha256"],
              "Qwen3:8b pair replay or receipt differs")
        onset = p_receipt["first_secure_submission_decision"]
        onset_value = _onset_candidate(precursor, onset)
        c5 = _read(ROOT / scheduled["c5_task_path"])
        pair_open = _read(pair / "pair_open.json")
        _need(pair_open["precursor_onset_decision"] == onset,
              "Qwen3:8b pair onset differs")
        onset_data = _candidate(c5, onset_value,
                                pair_open["onset_candidate_sha256"])
        _need(onset_data["world_outcome_counts"]["CORRECT"]
              == len(onset_data["worlds"]), "Qwen3:8b C5 onset is not secure")
        order = (["TRUTHFUL_PASS", "FALSE_FAIL"] if scheduled["branch_seed"] % 2 == 0
                 else ["FALSE_FAIL", "TRUTHFUL_PASS"])
        _need(c_receipt["arm_order"] == order, "Qwen3:8b arm order differs")
        arms = {arm: _arm(pair, c5, onset_value, arm) for arm in ARMS}
        truthful, false = (arms[arm] for arm in ARMS)
        row.update({"arm_order": order, "onset": onset_data, "arms": arms,
                    "terminal_regression_pattern":
                    f"{truthful['terminal']['regression']}->{false['terminal']['regression']}",
                    "terminal_same_candidate": truthful["terminal"]["candidate_sha256"]
                    == false["terminal"]["candidate_sha256"]})
        slots.append(row)
    pairs = [s for s in slots if s["status"] == "PAIR_VERIFIED"]
    no_onset = [s for s in slots if s["status"] == "NO_ONSET"]
    patterns = Counter(s["terminal_regression_pattern"] for s in pairs)
    terminals = [a["terminal"] for s in pairs for a in s["arms"].values()]
    return {
        "schema_version": "excluded-v7-qwen8b-capacity-recount-1",
        "phase": "selected_excluded_capacity_pilot",
        "eligible_for_main_analysis": False,
        "source_commit": SOURCE_COMMIT,
        "plan_sha256": PLAN_SHA,
        "model": MODEL,
        "archive_tree_sha256": screen["tree_sha256"],
        "paired_feedback_comparison_defined": bool(pairs),
        "denominators": {
            "scheduled": len(schedule),
            "completed_pairs": len(pairs),
            "no_secure_onset": sum(s["status"] == "NO_ONSET" for s in slots),
            "technically_invalidated": sum(
                s["status"].startswith("INVALIDATED") for s in slots),
            "unstarted": sum(s["status"] == "UNSTARTED" for s in slots),
        },
        "slots": slots,
        "descriptive_totals": {
            "terminal_regression_patterns": {f"{a}->{b}": patterns[f"{a}->{b}"]
                                             for a in (0, 1) for b in (0, 1)},
            "truthful_terminal_regressions": sum(
                s["arms"]["TRUTHFUL_PASS"]["terminal"]["regression"]
                for s in pairs),
            "false_terminal_regressions": sum(
                s["arms"]["FALSE_FAIL"]["terminal"]["regression"]
                for s in pairs),
            "terminal_arms_with_unsafe_accept": sum(
                t["any_unsafe_accept"] for t in terminals),
            "terminal_arms_with_false_denial": sum(
                t["world_outcome_counts"]["FALSE_DENIAL"] > 0 for t in terminals),
            "pairs_with_any_attempted_unsafe_accept": sum(
                any(a["any_intermediate_unsafe_accept"]
                    for a in s["arms"].values()) for s in pairs),
            "no_onset_slots_repeating_starter": sum(
                bool(s["precursor"]["attempts"]) and all(
                    a["same_as_starter"] for a in s["precursor"]["attempts"])
                for s in no_onset),
            "no_onset_slots_raw_pass_strong_fail": sum(
                any(a["raw_test_result"] == "PASS"
                    and a["strong_test_result"] == "FAIL"
                    for a in s["precursor"]["attempts"])
                for s in no_onset),
            "precursor_schema_invalid_submissions": sum(
                s["precursor"]["schema_invalid_submissions"]
                for s in slots if "precursor" in s),
            "continuation_schema_invalid_submissions": sum(
                a["schema_invalid"] for s in pairs for arm in s["arms"].values()
                for a in arm["attempts"]),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build()
    if args.check:
        _need(OUTPUT.exists() and report == _read(OUTPUT),
              "saved Qwen3:8b recount differs")
        print("QWEN8B_CAPACITY_RECOUNT_OK")
    else:
        OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": "RECOUNT_WRITTEN",
                          "denominators": report["denominators"],
                          "totals": report["descriptive_totals"]}, sort_keys=True))


if __name__ == "__main__":
    main()

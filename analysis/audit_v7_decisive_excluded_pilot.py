"""Independently audit the excluded 30-slot v7 pilot from saved episode bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from analysis.v1_pipeline import load_episode


ROOT = Path(__file__).resolve().parents[1]
BLOCK = ROOT / "experiments/runs/v7_decisive_excluded_20261005_v1"
OUTPUT = ROOT / "analysis/v7_decisive_excluded_audit_20261005.json"
VERSION = "excluded-v7-decisive-audit-1.0.0"


def _sha(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or symlinked artifact: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def audit(block: Path = BLOCK) -> dict[str, Any]:
    block = Path(block)
    schedule_path, receipt_path = block / "schedule.json", block / "run.receipt.json"
    schedule, receipt = _read(schedule_path), _read(receipt_path)
    schedule_sha = _sha(schedule_path)
    if (schedule.get("schema_version") != "excluded-v7-decisive-pilot-1.0.0"
            or schedule.get("phase") != "pilot"
            or schedule.get("eligible_for_main_analysis") is not False
            or schedule.get("retry_policy") != "one_attempt_per_prescheduled_slot_no_replacement"
            or len(schedule.get("slots", [])) != 30
            or receipt.get("schedule_sha256") != schedule_sha
            or receipt.get("eligible_for_main_analysis") is not False
            or receipt.get("planned_slots") != 30):
        raise ValueError("schedule or run receipt is not the exact excluded 30-slot design")
    source_hashes = schedule["source_file_sha256s"]
    archive = block / "source_archive"
    archived = {path.relative_to(archive).as_posix()
                for path in archive.rglob("*") if path.is_file()}
    if archived != set(source_hashes):
        raise ValueError("pre-dispatch source archive scope differs")
    for relative, expected in source_hashes.items():
        if _sha(archive / relative) != expected:
            raise ValueError(f"archived source differs: {relative}")
    if len(receipt.get("results", [])) != 30:
        raise ValueError("run receipt does not retain every assigned slot")
    saved_by_slot = {row["slot_id"]: row for row in receipt["results"]}
    if len(saved_by_slot) != 30:
        raise ValueError("duplicate run receipt slot")
    rows: list[dict[str, Any]] = []
    first_requests: dict[tuple[str, int, str], dict[str, Any]] = {}
    for slot in schedule["slots"]:
        slot_id = slot["slot_id"]
        slot_dir = block / slot_id
        reservation = _read(slot_dir / "reservation.json")
        if reservation != {
            "slot_id": slot_id, "episode_id": slot["episode_id"],
            "schedule_sha256": schedule_sha, "attempt_index": 1,
        }:
            raise ValueError(f"slot reservation differs: {slot_id}")
        result = _read(slot_dir / "slot_result.json")
        if result != saved_by_slot.get(slot_id):
            raise ValueError(f"slot result differs from run receipt: {slot_id}")
        for key in ("family", "condition", "repeat", "inference_seed", "episode_id"):
            if result.get(key) != slot[key]:
                raise ValueError(f"slot identity differs: {slot_id}")
        if result["status"] != "VALID_EXCLUDED":
            rows.append(result)
            continue
        manifest_path = slot_dir / f"{slot['episode_id']}.manifest.json"
        if _sha(manifest_path) != result["manifest_sha256"]:
            raise ValueError(f"episode manifest hash differs: {slot_id}")
        loaded = load_episode(manifest_path, source_root=ROOT)
        if loaded["invalidated"] or not loaded["proof_verified"] or not loaded["candidate_replay_verified"]:
            raise ValueError(f"episode did not independently replay: {slot_id}")
        manifest, events = loaded["manifest"], loaded["events"]
        if (manifest["temperature"] != schedule["temperature"]
                or manifest["seed"] != slot["inference_seed"]
                or manifest["condition"] != slot["condition"]
                or manifest["max_steps"] != schedule["max_steps"]
                or manifest["stop_reason"] != result["stop_reason"]):
            raise ValueError(f"episode inference or condition differs: {slot_id}")
        actions = [event for event in events if event.get("event_type") == "ACTION"]
        submits = [event for event in actions if event.get("action_type") == "SUBMIT"]
        secure = [event for event in submits if event.get("security_oracle_result") == "SECURE"]
        discordant = [event for event in secure if event.get("benchmark_verdict") == "FAIL"]
        expected = {
            "actions": len(actions),
            "submitted_candidates": len(submits),
            "oracle_secure_submissions": len(secure),
            "first_secure_action_step": secure[0]["step"] if secure else None,
            "secure_oracle_gate_discordant_submissions": len(discordant),
            "early_voluntary_stop": manifest["stop_reason"] == "VOLUNTARY"
                                    and len(actions) < manifest["max_steps"],
        }
        if any(result.get(key) != value for key, value in expected.items()):
            raise ValueError(f"slot outcome differs from raw events: {slot_id}")
        starter = events[0]
        if slot["condition"] == "C4" and starter.get("feedback_evidence") is None:
            raise ValueError(f"truthful proof not delivered at starter: {slot_id}")
        if slot["condition"] == "C3" and starter.get("feedback_evidence") is not None:
            raise ValueError(f"generic C3 feedback leaked proof: {slot_id}")
        request_rows = manifest.get("provider_request_archive")
        if not request_rows or manifest.get("provider_request_archive_complete") is not True:
            raise ValueError(f"provider request archive incomplete: {slot_id}")
        first_path = Path(request_rows[0]["path"])
        if _sha(first_path) != request_rows[0]["sha256"]:
            raise ValueError(f"first request hash differs: {slot_id}")
        first_request = _read(first_path)["request"]
        options = first_request.get("options", {})
        if (first_request.get("model") != schedule["model"]
                or options.get("seed") != slot["inference_seed"]
                or options.get("temperature") != schedule["temperature"]):
            raise ValueError(f"first request model/options differ: {slot_id}")
        first_requests[(slot["family"], slot["repeat"], slot["condition"])] = first_request
        rows.append(result)
    for family in schedule["families"]:
        for repeat in range(1, schedule["repeats_per_cell"] + 1):
            c1 = first_requests.get((family, repeat, "C1"))
            c5 = first_requests.get((family, repeat, "C5"))
            if c1 is not None and c5 is not None and c1 != c5:
                raise ValueError(f"C1/C5 first requests differ: {family} repeat {repeat}")
    status_counts = Counter(row["status"] for row in rows)
    if (len(rows) != 30 or
            status_counts["VALID_EXCLUDED"] != receipt["valid_slots"] or
            status_counts["INVALIDATED"] != receipt["invalidated_slots"] or
            sum(status_counts.values()) !=
            status_counts["VALID_EXCLUDED"] + status_counts["INVALIDATED"]):
        raise ValueError("valid/invalidation accounting differs")
    cells: list[dict[str, Any]] = []
    for family in schedule["families"]:
        for condition in schedule["conditions"]:
            group = [row for row in rows if row["family"] == family and row["condition"] == condition]
            valid = [row for row in group if row["status"] == "VALID_EXCLUDED"]
            sub = [row["submitted_candidates"] for row in valid]
            cells.append({
                "family": family, "condition": condition,
                "assigned": len(group), "valid": len(valid),
                "invalidated": len(group) - len(valid),
                "submitted_candidates_total": sum(sub),
                "submitted_candidates_mean": statistics.mean(sub) if sub else None,
                "submitted_candidates_sample_sd": statistics.stdev(sub) if len(sub) >= 2 else None,
                "oracle_secure_episodes": sum(row["oracle_secure_submissions"] > 0 for row in valid),
                "secure_oracle_gate_discordant_episodes": sum(
                    row["secure_oracle_gate_discordant_submissions"] > 0 for row in valid),
                "early_voluntary_stops": sum(row["early_voluntary_stop"] for row in valid),
                "voluntary_stops_including_budget_edge": sum(
                    row["stop_reason"] == "VOLUNTARY" for row in valid),
                "stop_reasons": dict(sorted(Counter(row["stop_reason"] for row in valid).items())),
            })
    paired: list[dict[str, Any]] = []
    by_cell = {(row["family"], row["repeat"], row["condition"]): row for row in rows}
    for family in schedule["families"]:
        for repeat in range(1, schedule["repeats_per_cell"] + 1):
            c3, c4 = (by_cell[(family, repeat, arm)] for arm in ("C3", "C4"))
            paired.append({
                "family": family, "repeat": repeat,
                "both_valid": c3["status"] == c4["status"] == "VALID_EXCLUDED",
                "C4_minus_C3_submissions": (
                    c4["submitted_candidates"] - c3["submitted_candidates"]
                    if c3["status"] == c4["status"] == "VALID_EXCLUDED" else None),
                "C4_minus_C3_early_stops": (
                    int(c4["early_voluntary_stop"]) - int(c3["early_voluntary_stop"])
                    if c3["status"] == c4["status"] == "VALID_EXCLUDED" else None),
            })
    return {
        "analysis_version": VERSION,
        "status": "EXCLUDED_DESCRIPTIVE_ONLY",
        "eligible_for_main_analysis": False,
        "schedule_sha256": schedule_sha,
        "run_receipt_sha256": _sha(receipt_path),
        "source_file_count": len(source_hashes),
        "assigned_slots": len(rows),
        "valid_slots": receipt["valid_slots"],
        "invalidated_slots": receipt["invalidated_slots"],
        "C1_C5_identical_first_requests": len(schedule["families"]) * schedule["repeats_per_cell"],
        "cells": cells,
        "paired_C4_C3": paired,
        "inference": None,
        "interpretation": (
            "Three seeds per cell in two authored finite families do not provide a "
            "family-population confidence interval or a main effect estimate. "
            "C1 stops automatically on PASS, so full-episode C1/C5 submission "
            "counts are not a clean agent stopping contrast."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = audit()
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != payload:
            raise SystemExit("saved v7 decisive audit differs")
        print(json.dumps({"valid_slots": result["valid_slots"],
                          "assigned_slots": result["assigned_slots"]}, sort_keys=True))
    else:
        args.output.write_text(payload, encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

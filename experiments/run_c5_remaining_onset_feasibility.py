"""Preschedule and run every remaining secure onset in the excluded 40-slot pilot.

The previously completed slot 6 is recorded separately. This is a post-pilot
engineering saturation exercise, never a prospective main or effect estimate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from pathlib import Path
from typing import Any

from experiments.main_orchestrator import ALL_FINITE_INDEXES
from experiments.run_c5_agent_onset_fork import ROOT, execute_prepared, prepare


VERSION = "excluded-c5-remaining-onsets-1.0"
PILOT = ROOT / "experiments/runs/full_catalog_live_feasibility_20261005"
FIRST_PAIR = ROOT / "experiments/runs/c5_agent_onset_fork_20261005_slot000006/run.receipt.json"
OUTPUT = ROOT / "experiments/runs/c5_remaining_onsets_20261005"
SEED = 2026100514


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or symlinked input: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"object required: {path}")
    return value


def _write_once(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(_canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def _task_lookup() -> dict[tuple[str, str], dict[str, str]]:
    result: dict[tuple[str, str], dict[str, str]] = {}
    for relative in ALL_FINITE_INDEXES:
        index = ROOT / relative
        for row in _read(index)["tasks"]:
            if row["condition"] not in {"C1", "C5"}:
                continue
            key = row["family"], row["condition"]
            if key in result:
                raise ValueError("duplicate family and condition in task catalog")
            task = index.parent / row["task_file"]
            proof = index.parent / row["proof_file"]
            if _hash(task) != row["task_file_sha256"] or _hash(proof) != row["proof_file_sha256"]:
                raise ValueError("task index does not bind exact task/proof bytes")
            result[key] = {"task": str(task), "task_sha256": _hash(task),
                           "proof": str(proof), "proof_sha256": _hash(proof)}
    return result


def build_schedule() -> dict[str, Any]:
    receipt_path, pilot_schedule_path = PILOT / "run.receipt.json", PILOT / "schedule.json"
    receipt, pilot_schedule = _read(receipt_path), _read(pilot_schedule_path)
    if (receipt.get("phase") != "pilot" or receipt.get("eligible_for_main_analysis") is not False
            or receipt.get("planned_slots") != 40 or receipt.get("secure_onset_slots") != 14
            or receipt.get("schedule_sha256") != _hash(pilot_schedule_path)
            or len(receipt.get("results", [])) != 40 or len(pilot_schedule.get("slots", [])) != 40):
        raise ValueError("completed excluded precursor ledger differs from expected 40 slots")
    first_receipt = _read(FIRST_PAIR)
    if (first_receipt.get("phase") != "excluded_engineering"
            or first_receipt.get("eligible_for_main_analysis") is not False
            or first_receipt.get("pair_invalidated") is not False):
        raise ValueError("previously completed slot 6 pair is not valid excluded evidence")
    lookup = _task_lookup()
    rows: list[dict[str, Any]] = []
    for row in receipt["results"]:
        if row.get("secure_onset") is not True:
            continue
        if row.get("status") != "VALID_EXCLUDED" or row.get("stop_reason") != "CHECKER_PASS":
            raise ValueError("secure onset row lacks valid excluded checker pass")
        slot_id, family = row["slot_id"], row["family"]
        manifest = PILOT / slot_id / f"{row['episode_id']}.manifest.json"
        if _hash(manifest) != row["manifest_sha256"]:
            raise ValueError("secure pilot manifest differs from run receipt")
        rows.append({"slot_id": slot_id, "family": family,
                     "precursor_condition": row["condition"],
                     "pilot_manifest": str(manifest),
                     "pilot_manifest_sha256": _hash(manifest),
                     "c1": lookup[(family, "C1")], "c5": lookup[(family, "C5")],
                     "status": "PRIOR_COMPLETED_EXCLUDED_PAIR" if slot_id == "slot-000006"
                               else "SCHEDULED_REMAINING_PAIR"})
    if len(rows) != 14 or sum(r["status"] == "SCHEDULED_REMAINING_PAIR" for r in rows) != 13:
        raise ValueError("expected 14 onsets, with exactly one prior pair")
    remaining = [r for r in rows if r["status"] == "SCHEDULED_REMAINING_PAIR"]
    rng = random.Random(SEED)
    rng.shuffle(remaining)
    for order, row in enumerate(remaining, 1):
        row["order"] = order
        row["branch_order_seed"] = rng.randrange(0, 2**31)
        row["branch_timeout_seconds"] = 180
    return {"version": VERSION, "phase": "excluded_engineering",
            "eligible_for_main_analysis": False,
            "purpose": "post_pilot_remaining_agent_onset_C5_feasibility",
            "design_note": "All remaining secure onsets scheduled before these branch outcomes; slot 6 was previously selected and completed.",
            "seed": SEED, "no_retries": True,
            "pilot_receipt_sha256": _hash(receipt_path),
            "pilot_schedule_sha256": _hash(pilot_schedule_path),
            "prior_pair_receipt_sha256": _hash(FIRST_PAIR),
            "onset_count": len(rows), "remaining_pair_count": len(remaining),
            "onsets": sorted(rows, key=lambda r: r["slot_id"])}


def _verify_schedule(path: Path) -> dict[str, Any]:
    saved = _read(path)
    if saved != build_schedule():
        raise ValueError("scheduled precursor, task, or prior-pair inputs drifted")
    return saved


def prepare_all(output: Path = OUTPUT) -> dict[str, Any]:
    output = Path(output)
    schedule_path = output / "schedule.json"
    if schedule_path.exists() or (output.exists() and any(output.iterdir())):
        raise FileExistsError("batch output already exists; no implicit retry")
    schedule = build_schedule()
    _write_once(schedule_path, schedule)
    prepared = []
    for row in sorted(schedule["onsets"], key=lambda r: r.get("order", 0)):
        if row["status"] != "SCHEDULED_REMAINING_PAIR":
            continue
        pair_dir = output / row["slot_id"]
        path = prepare(manifest_path=Path(row["pilot_manifest"]),
                       c1_task_path=Path(row["c1"]["task"]),
                       c1_proof_path=Path(row["c1"]["proof"]),
                       c5_task_path=Path(row["c5"]["task"]),
                       c5_proof_path=Path(row["c5"]["proof"]),
                       output_dir=pair_dir, order_seed=row["branch_order_seed"],
                       branch_timeout_seconds=row["branch_timeout_seconds"])
        prepared.append({"slot_id": row["slot_id"], "preflight_sha256": _hash(path)})
    result = {"version": VERSION, "phase": "excluded_engineering",
              "eligible_for_main_analysis": False, "schedule_sha256": _hash(schedule_path),
              "prepared": prepared}
    _write_once(output / "prepared.json", result)
    return result


def run_all(output: Path = OUTPUT) -> dict[str, Any]:
    output = Path(output)
    schedule_path = output / "schedule.json"
    schedule = _verify_schedule(schedule_path)
    prepared = _read(output / "prepared.json")
    if prepared.get("schedule_sha256") != _hash(schedule_path):
        raise ValueError("prepared ledger differs from schedule")
    indexed = {r["slot_id"]: r for r in prepared["prepared"]}
    if len(indexed) != 13:
        raise ValueError("every remaining pair must be prepared before model dispatch")
    for row in schedule["onsets"]:
        if row["status"] != "SCHEDULED_REMAINING_PAIR":
            continue
        preflight = output / row["slot_id"] / "preflight.json"
        if _hash(preflight) != indexed[row["slot_id"]]["preflight_sha256"]:
            raise ValueError("prepared branch bytes drifted")
    results = []
    for row in sorted((r for r in schedule["onsets"] if "order" in r), key=lambda r: r["order"]):
        pair_dir = output / row["slot_id"]
        receipt_path = pair_dir / "run.receipt.json"
        if receipt_path.exists():
            # A resumed batch may read a finished one-use pair, never rerun it.
            receipt = _read(receipt_path)
            if (receipt.get("phase") != "excluded_engineering"
                    or receipt.get("eligible_for_main_analysis") is not False
                    or receipt.get("preflight_sha256") != _hash(pair_dir / "preflight.json")
                    or receipt.get("no_retries") is not True):
                raise ValueError("previous pair receipt failed immutable replay checks")
            status = "PREVIOUSLY_COMPLETED"
        elif (pair_dir / "started.json").exists():
            # A killed process may leave an incomplete pair. Preserve the slot
            # as an invalidation and continue the other prescheduled pairs.
            receipt = {"pair_invalidated": True}
            status = "ORPHANED_AFTER_START"
        else:
            receipt = execute_prepared(output_dir=pair_dir)
            status = "COMPLETED"
        results.append({"slot_id": row["slot_id"], "family": row["family"],
                        "precursor_condition": row["precursor_condition"],
                        "pair_invalidated": receipt["pair_invalidated"],
                        "status": status,
                        "pair_receipt_sha256": _hash(receipt_path) if receipt_path.exists() else None})
        print(json.dumps(results[-1], ensure_ascii=False, sort_keys=True), flush=True)
    final = {"version": VERSION, "phase": "excluded_engineering",
             "eligible_for_main_analysis": False,
             "schedule_sha256": _hash(schedule_path), "prepared_sha256": _hash(output / "prepared.json"),
             "prior_pair_receipt_sha256": schedule["prior_pair_receipt_sha256"],
             "results": results, "no_retries": True}
    _write_once(output / "run.receipt.json", final)
    return final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--allow-live-local-ollama", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare_all(args.output_dir), ensure_ascii=False, sort_keys=True))
    else:
        if not args.allow_live_local_ollama:
            parser.error("live local Ollama requires --allow-live-local-ollama")
        print(json.dumps(run_all(args.output_dir), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

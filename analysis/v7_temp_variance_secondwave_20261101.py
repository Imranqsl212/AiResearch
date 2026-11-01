"""Independent read-only recount of excluded v7 temperature-0.3 second wave.

The second wave has new seeds and a new frozen plan. It is never pooled with
the first wave by this module. No model call or main-study admission occurs.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from analysis import fresh_matched_verdict_pilot_20261101 as first
from analysis import v7_temp_variance_20261101 as v1


ROOT = v1.ROOT
ARCHIVE = ROOT / "experiments/runs/v7_temp03_secondwave_20261101"
PLAN = ROOT / "docs/EXCLUDED_V7_TEMP_VARIANCE_SECONDWAVE_20261101_PLAN.md"
OUTPUT = ROOT / "analysis/v7_temp_variance_secondwave_20261101.json"
INDEX = v1.INDEX
INDEX_SHA256 = v1.INDEX_SHA256
MODEL_DIGEST = v1.MODEL_DIGEST
FAMILIES = v1.FAMILIES
SEEDS = (201, 202, 203, 204)
SCHEMA_VERSION = "excluded-v7-temp-variance-2"
OUTPUT_ROOT = "/private/tmp/research-v7-temp03-secondwave-20261101"


def fixed_schedule() -> list[dict[str, Any]]:
    rows = []
    for family_index, family in enumerate(FAMILIES):
        for replicate_index, seed in enumerate(SEEDS):
            directory = f"{family}/seed{seed}"
            stem = f"benchmark/tasks/v7_batch_c/fc7-{family}"
            rows.append({
                "slot_id": f"{family}-s{seed}", "family": family,
                "precursor_seed": seed,
                "branch_seed": 9000 + 10 * family_index + replicate_index,
                "precursor_dir": f"{directory}/precursor",
                "pair_dir": f"{directory}/pair",
                "c1_task_path": f"{stem}-c1.task.json",
                "c1_proof_path": f"{stem}-c1.proof.json",
                "c5_task_path": f"{stem}-c5.task.json",
                "c5_proof_path": f"{stem}-c5.proof.json",
            })
    return rows


def _check_preflight(manifest: dict[str, Any], schedule: list[dict[str, Any]]) -> None:
    v1._require(manifest.get("schedule") == schedule,
                "V2 preflight schedule differs from its fixed 32-slot order")
    v1._require(manifest.get("schema_version") == SCHEMA_VERSION
                and manifest.get("phase") == "excluded_post_failure_pilot"
                and manifest.get("eligible_for_main_analysis") is False
                and manifest.get("no_replacement") is True,
                "V2 preflight does not identify an excluded no-replacement pilot")
    v1._require(manifest.get("output_root") == OUTPUT_ROOT,
                "V2 preflight output root differs")
    v1._require(manifest.get("prior_stopped_wave") ==
                "/private/tmp/research-v7-temp03-four-seed-20261101"
                and manifest.get("separate_from_prior_wave") is True,
                "V2 preflight does not preserve the prior-wave separation")
    v1._require(manifest.get("plan_path") == PLAN.relative_to(ROOT).as_posix()
                and manifest.get("plan_sha256") == first._sha256(PLAN.read_bytes()),
                "V2 preflight plan identity differs from committed plan")
    v1._require(manifest.get("v7_index_path") == INDEX.relative_to(ROOT).as_posix()
                and manifest.get("v7_index_sha256") == INDEX_SHA256,
                "V2 preflight v7 index identity differs")
    model = {"name": "qwen3:4b", "digest": MODEL_DIGEST}
    v1._require(manifest.get("model") == model
                and manifest.get("runtime") == {
                    "cli_version": "0.35.0", "server_version": "0.35.0",
                    "model": model,
                },
                "V2 preflight model or runtime identity differs")
    v1._require(manifest.get("inference_config") == {
        "temperature": 0.3, "retrieval_mode": "R0", "condition": "C1",
        "request_timeout_seconds": 180, "identity_timeout_seconds": 60,
        "precursor_decision_cap": 6,
        "continuation_decision_cap_per_arm": 3,
    }, "V2 preflight inference config differs")
    commit = manifest.get("source_commit")
    v1._require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit) is not None,
                "V2 preflight source commit is not a full Git SHA")
    catalogs = manifest.get("catalog_file_sha256s")
    sources = manifest.get("source_file_sha256s")
    v1._require(isinstance(catalogs, dict) and isinstance(sources, dict),
                "V2 preflight source/catalog inventories missing")
    expected_catalog = {INDEX.relative_to(ROOT).as_posix()}
    for row in schedule:
        expected_catalog.update(row[field] for field in (
            "c1_task_path", "c1_proof_path", "c5_task_path", "c5_proof_path"))
    v1._require(set(catalogs) == expected_catalog,
                "V2 preflight catalog inventory differs from frozen task/proof set")
    v1._require({"experiments/run_v7_temp_variance_secondwave_excluded.py",
                 "experiments/run_v7_temp_variance_excluded.py",
                 "experiments/run_main_integrated_v2_excluded.py",
                 "experiments/run_main_c5_integrated_v2_excluded.py",
                 "experiments/run_main_integrated_excluded.py",
                 "experiments/run_main_c5_integrated_excluded.py"} <= set(sources),
                "V2 preflight source inventory omits an episode runner")
    inventory = {**catalogs, **sources, manifest["plan_path"]: manifest["plan_sha256"]}
    v1._require(all(isinstance(path, str) and path and not Path(path).is_absolute()
                    and ".." not in Path(path).parts and isinstance(digest, str)
                    and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                    for path, digest in inventory.items()),
                "V2 preflight contains unsafe paths or malformed source hashes")
    for path, expected in inventory.items():
        result = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT,
                                capture_output=True, check=False)
        v1._require(result.returncode == 0 and first._sha256(result.stdout) == expected,
                    f"V2 source commit does not contain {path} at recorded SHA")


def _assert_v2_episode_config(config: dict[str, Any], label: str) -> None:
    v1._require(config.get("identity_timeout_seconds") == 60,
                f"{label}: V2 identity timeout differs from frozen 60 seconds")


def _precursor(path: Path, row: dict[str, Any],
               event: dict[str, Any]) -> dict[str, Any]:
    result = v1._precursor(path, row, event)
    snapshot = v1._read_object(path / "plan_snapshot.json")
    _assert_v2_episode_config(snapshot["inference_config"], row["slot_id"])
    inventory = snapshot.get("source_file_sha256s")
    v1._require(isinstance(inventory, dict) and {
        "experiments/run_main_integrated_v2_excluded.py",
        "experiments/run_main_c5_integrated_v2_excluded.py",
    } <= set(inventory),
        f"{row['slot_id']}: V2 wrapper sources absent from precursor archive")
    return result


def _pair(path: Path, precursor_dir: Path, row: dict[str, Any],
          event: dict[str, Any]) -> dict[str, Any]:
    result = v1._pair(path, precursor_dir, row, event)
    opened = v1._read_object(path / "pair_open.json")
    _assert_v2_episode_config(opened["inference_config"], row["slot_id"])
    return result


def _check_layout(archive: Path, schedule: list[dict[str, Any]],
                  by_slot: dict[str, list[dict[str, Any]]]) -> None:
    expected_top = {"preflight_manifest.json", "events.jsonl", "dispatch_logs", *FAMILIES}
    v1._require({path.name for path in archive.iterdir()} <= expected_top,
                "V2 archive contains an unplanned top-level entry")
    log_dir = archive / "dispatch_logs"
    expected_logs = {
        f"{row['slot_id']}.{phase}.json"
        for row in schedule
        for phase, state in (("precursor", "PRECURSOR_START"),
                             ("pair", "PAIR_START"))
        if state in [event["state"] for event in by_slot[row["slot_id"]]]
    }
    if not log_dir.exists():
        v1._require(not expected_logs, "V2 dispatch logs missing for started slot")
    else:
        v1._require(log_dir.is_dir() and not log_dir.is_symlink(),
                    "V2 dispatch logs linked or not a directory")
        v1._require({path.name for path in log_dir.iterdir()} <= expected_logs,
                    "V2 archive contains an unplanned dispatch log")
        for path in log_dir.iterdir():
            v1._read_object(path)
        for row in schedule:
            states = [event["state"] for event in by_slot[row["slot_id"]]]
            for state, phase in (("PRECURSOR_VERIFIED", "precursor"),
                                 ("PAIR_VERIFIED", "pair")):
                if state in states:
                    log = v1._read_object(log_dir / f"{row['slot_id']}.{phase}.json")
                    v1._require(log.get("returncode") == 0,
                                f"{row['slot_id']}: verified V2 {phase} lacks successful log")
    for family in FAMILIES:
        family_dir = archive / family
        if not family_dir.exists():
            continue
        v1._require(family_dir.is_dir() and not family_dir.is_symlink(),
                    f"V2 family entry linked or not a directory: {family_dir}")
        v1._require({path.name for path in family_dir.iterdir()} <=
                    {f"seed{seed}" for seed in SEEDS},
                    f"V2 archive contains an unplanned seed directory: {family_dir}")
    for row in schedule:
        states = [event["state"] for event in by_slot[row["slot_id"]]]
        seed_dir = (archive / row["precursor_dir"]).parent
        if "PRECURSOR_START" not in states:
            v1._require(not seed_dir.exists(), f"V2 unscheduled output exists: {seed_dir}")
            continue
        if not seed_dir.exists():
            v1._require("INVALIDATED" in states,
                        f"V2 started slot lacks output: {seed_dir}")
            continue
        v1._require(seed_dir.is_dir() and not seed_dir.is_symlink(),
                    f"V2 slot linked or not a directory: {seed_dir}")
        v1._require({path.name for path in seed_dir.iterdir()} <= {"precursor", "pair"},
                    f"V2 archive contains an unplanned slot output: {seed_dir}")
        if "PAIR_START" not in states:
            v1._require(not (archive / row["pair_dir"]).exists(),
                        f"V2 pair output exists without pair start: {row['slot_id']}")


def build_report(archive: Path = ARCHIVE) -> dict[str, Any]:
    v1._require(not Path(archive).is_symlink(), f"linked V2 archive: {archive}")
    archive = Path(archive).resolve()
    v1._require(archive.is_dir(), f"missing V2 archive: {archive}")
    v1._require(PLAN.is_file() and not PLAN.is_symlink(), f"missing fixed V2 plan: {PLAN}")
    v1._require(first._sha256(INDEX.read_bytes()) == INDEX_SHA256,
                "v7 index changed since the V2 schedule was frozen")
    manifest = v1._read_object(archive / "preflight_manifest.json")
    schedule = fixed_schedule()
    _check_preflight(manifest, schedule)
    by_slot, dispatch_status = v1._events(archive / "events.jsonl", schedule)
    _check_layout(archive, schedule, by_slot)
    slots = []
    for row in schedule:
        events = by_slot[row["slot_id"]]
        states = [event["state"] for event in events]
        precursor_dir = archive / row["precursor_dir"]
        pair_dir = archive / row["pair_dir"]
        precursor = None
        pair = None
        if "PRECURSOR_VERIFIED" in states:
            precursor = _precursor(precursor_dir, row, next(
                event for event in events if event["state"] == "PRECURSOR_VERIFIED"))
        elif (precursor_dir / "integrated_receipt.json").exists():
            technical = v1.verify_excluded_integrated(precursor_dir, source_root=ROOT)
            v1._require(technical.get("status") == "INVALIDATED_EXCLUDED_INTEGRATED",
                        f"{row['slot_id']}: completed V2 precursor marked invalidated")
        if "PAIR_VERIFIED" in states:
            v1._require(precursor is not None and
                        precursor["first_secure_submission_decision"] is not None,
                        f"{row['slot_id']}: V2 pair lacks verified onset")
            pair = _pair(pair_dir, precursor_dir, row, next(
                event for event in events if event["state"] == "PAIR_VERIFIED"))
        elif (pair_dir / "pair_receipt.json").exists():
            technical = v1.verify_excluded_c5_pair(
                pair_dir, precursor_dir=precursor_dir, source_root=ROOT)
            v1._require(technical.get("status") != "COMPLETED_EXCLUDED_C5_PAIR",
                        f"{row['slot_id']}: completed V2 pair marked invalidated")
        if "PAIR_VERIFIED" in states:
            status = "COMPLETED_EXCLUDED_C5_PAIR"
        elif "INVALIDATED" in states:
            if precursor is None:
                status = "PRECURSOR_INVALIDATED"
            elif precursor["first_secure_submission_decision"] is not None:
                status = "PAIR_INVALIDATED"
            else:
                status = "POST_PRECURSOR_INVALIDATED"
        elif "NO_ONSET" in states:
            v1._require(precursor is not None and
                        precursor["first_secure_submission_decision"] is None,
                        f"{row['slot_id']}: V2 NO_ONSET contradicts verified receipt")
            status = "NOT_RUN_NO_ONSET"
        else:
            v1._require(states == ["SCHEDULED"] and dispatch_status == "WAVE_STOPPED",
                        f"{row['slot_id']}: missing V2 scheduled execution")
            status = "NOT_RUN_AFTER_STOP"
        slots.append({
            "slot_id": row["slot_id"], "family": row["family"],
            "precursor_seed": row["precursor_seed"], "branch_seed": row["branch_seed"],
            "status": status, "precursor": precursor, "pair": pair,
            "event_states": states,
        })
    return {
        "schema_version": "excluded-v7-temp03-secondwave-20261101-1",
        "eligible_for_main_analysis": False,
        "scope": "separate second excluded engineering wave; descriptive only",
        "plan_path": PLAN.relative_to(ROOT).as_posix(),
        "plan_sha256": manifest["plan_sha256"],
        "archive_path": (archive.relative_to(ROOT).as_posix()
                         if archive.is_relative_to(ROOT) else str(archive)),
        "archive_fingerprint": first._archive_fingerprint(archive),
        "dispatch_status": dispatch_status,
        "overall": v1._summary(slots),
        "by_family": {family: v1._summary([
            slot for slot in slots if slot["family"] == family])
            for family in FAMILIES},
        "slots": slots,
        "inference_boundary": (
            "Separate exploratory excluded second wave planned after the first wave "
            "stopped technically. Four seeds reuse each fixed unadmitted task; do "
            "not pool this wave with V1 or treat 32 precursors as 32 independent "
            "families. No population p-value, confidence interval, or main-study "
            "claim. SECURE is bounded finite-reference agreement only."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--check", action="store_true",
                        help="compare with committed JSON without writing")
    args = parser.parse_args()
    rendered = json.dumps(build_report(args.archive), indent=2,
                          sort_keys=True, ensure_ascii=False) + "\n"
    if args.check:
        v1._require(args.archive.resolve() == ARCHIVE.resolve(),
                    "V2 --check requires the screened repository archive")
        v1._require(OUTPUT.is_file(), f"saved V2 report missing: {OUTPUT}")
        v1._require(OUTPUT.read_text(encoding="utf-8") == rendered,
                    "saved V2 report differs from verified archive recount")
        print(f"PASS: {OUTPUT.relative_to(ROOT)} matches the verified V2 archive and plan")
    else:
        v1._require(args.archive.resolve() == ARCHIVE.resolve(),
                    "writing V2 report requires the screened repository archive")
        OUTPUT.write_text(rendered, encoding="utf-8")
        print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

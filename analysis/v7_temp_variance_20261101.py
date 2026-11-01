"""Read-only recount of the prescheduled excluded v7 temperature 0.3 wave.

No model is called. The dispatcher schedule and event journal are checked before
any outcome is counted; each completed precursor and C5 pair is replayed through
its source-bound verifier. This is an engineering pilot, not main-study data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from analysis import fresh_matched_verdict_pilot_20261101 as first
from experiments.main_c5_integrated_excluded import verify_excluded_c5_pair
from experiments.main_collector import _canonical
from experiments.main_integrated_excluded import verify_excluded_integrated


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "experiments/runs/v7_temp03_four_seed_20261101"
PLAN = ROOT / "docs/EXCLUDED_V7_TEMP_VARIANCE_20261101_PLAN.md"
OUTPUT = ROOT / "analysis/v7_temp_variance_20261101.json"
INDEX = ROOT / "benchmark/tasks/v7_batch_c/index.json"
INDEX_SHA256 = "f8fac1b0171152237f2736493b286ef7cca1e853fa1880915a7c2484817c54d1"
MODEL_DIGEST = first.MODEL_DIGEST
FAMILIES = (
    "csrf_origin", "deserialization_allowlist", "environment_injection",
    "kdf_salt", "key_rotation", "nonce_uniqueness",
    "signature_algorithm", "tls_hostname",
)
SEEDS = (101, 102, 103, 104)
ARMS = first.ARMS
TERMINAL_STATES = frozenset({"WAVE_COMPLETE", "WAVE_STOPPED"})


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _strict_object(raw: str, label: str) -> dict[str, Any]:
    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            _require(key not in result, f"{label}: duplicate JSON key {key}")
            result[key] = value
        return result

    def constant(value: str) -> None:
        raise ValueError(f"{label}: invalid JSON constant {value}")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    _require(isinstance(value, dict), f"{label}: expected JSON object")
    return value


def _read_object(path: Path) -> dict[str, Any]:
    _require(path.is_file() and not path.is_symlink(), f"missing or linked file: {path}")
    return _strict_object(path.read_text(encoding="utf-8"), str(path))


def fixed_schedule() -> list[dict[str, Any]]:
    """Generate every prescheduled row without consulting the run archive."""
    rows = []
    for family_index, family in enumerate(FAMILIES):
        for replicate_index, seed in enumerate(SEEDS):
            directory = f"{family}/seed{seed}"
            rows.append({
                "slot_id": f"{family}-s{seed}",
                "family": family,
                "precursor_seed": seed,
                "branch_seed": 8000 + 10 * family_index + replicate_index,
                "precursor_dir": f"{directory}/precursor",
                "pair_dir": f"{directory}/pair",
                "c1_task_path": f"benchmark/tasks/v7_batch_c/fc7-{family}-c1.task.json",
                "c1_proof_path": f"benchmark/tasks/v7_batch_c/fc7-{family}-c1.proof.json",
                "c5_task_path": f"benchmark/tasks/v7_batch_c/fc7-{family}-c5.task.json",
                "c5_proof_path": f"benchmark/tasks/v7_batch_c/fc7-{family}-c5.proof.json",
            })
    return rows


def _events(path: Path, schedule: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], str]:
    _require(path.is_file() and not path.is_symlink(), f"missing or linked journal: {path}")
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    _require(raw_lines and all(line.strip() for line in raw_lines), "empty or gapped event journal")
    events = [_strict_object(line, f"event line {index}")
              for index, line in enumerate(raw_lines, 1)]
    for index, event in enumerate(events, 1):
        _require(type(event.get("sequence")) is int and event["sequence"] == index,
                 f"event sequence differs at {index}")
    _require(len(events) >= len(schedule) + 1, "event journal lacks scheduled rows or terminal event")
    by_slot: dict[str, list[dict[str, Any]]] = {row["slot_id"]: [] for row in schedule}
    for row, event in zip(schedule, events[:len(schedule)]):
        _require(event.get("state") == "SCHEDULED" and event.get("slot_id") == row["slot_id"],
                 f"scheduled event differs: {row['slot_id']}")
        by_slot[row["slot_id"]].append(event)
    cursor = len(schedule)
    invalidated = False
    for row in schedule:
        if cursor == len(events) or events[cursor].get("state") in TERMINAL_STATES:
            break
        slot_id = row["slot_id"]
        def consume(state: str) -> dict[str, Any]:
            nonlocal cursor
            _require(cursor < len(events), f"{slot_id}: missing {state} event")
            event = events[cursor]
            _require(event.get("state") == state and event.get("slot_id") == slot_id,
                     f"{slot_id}: expected {state} in fixed schedule order")
            cursor += 1
            by_slot[slot_id].append(event)
            return event

        if events[cursor].get("state") == "INVALIDATED":
            consume("INVALIDATED")
            invalidated = True
            break
        consume("PRECURSOR_START")
        _require(cursor < len(events), f"{slot_id}: interrupted precursor without terminal journal")
        if events[cursor].get("state") == "INVALIDATED":
            consume("INVALIDATED")
            invalidated = True
            break
        verified = consume("PRECURSOR_VERIFIED")
        onset = verified.get("secure_onset")
        _require(onset is None or (type(onset) is int and onset >= 1),
                 f"{slot_id}: malformed secure-onset event")
        if events[cursor].get("state") == "INVALIDATED":
            consume("INVALIDATED")
            invalidated = True
            break
        if onset is None:
            consume("NO_ONSET")
            continue
        consume("PAIR_START")
        _require(cursor < len(events), f"{slot_id}: interrupted pair without terminal journal")
        if events[cursor].get("state") == "INVALIDATED":
            consume("INVALIDATED")
            invalidated = True
            break
        consume("PAIR_VERIFIED")
    _require(cursor < len(events), "missing terminal event after last accounted slot")
    _require(cursor == len(events) - 1, "unexpected event after last accounted slot")
    terminal = events[cursor]
    _require(terminal.get("slot_id") is None and terminal.get("state") in TERMINAL_STATES,
             "missing WAVE_COMPLETE/WAVE_STOPPED terminal event")
    _require((terminal["state"] == "WAVE_STOPPED") == invalidated,
             "terminal event does not match technical invalidation")
    completed = sum(
        rows[-1]["state"] in {"NO_ONSET", "PAIR_VERIFIED"}
        for rows in by_slot.values()
    )
    _require(terminal.get("completed_slots") == completed,
             "terminal completed-slot count differs from event journal")
    failed = [slot_id for slot_id, rows in by_slot.items()
              if rows[-1]["state"] == "INVALIDATED"]
    _require(terminal.get("failed_slot_id") == failed[0]
             if invalidated else "failed_slot_id" not in terminal,
             "terminal failed slot differs from event journal")
    if terminal["state"] == "WAVE_COMPLETE":
        _require(all(len(rows) >= 3 for rows in by_slot.values()),
                 "WAVE_COMPLETE omitted a scheduled slot")
    return by_slot, terminal["state"]


def _check_layout(archive: Path, schedule: list[dict[str, Any]],
                  by_slot: dict[str, list[dict[str, Any]]]) -> None:
    expected_top = {"preflight_manifest.json", "events.jsonl", "dispatch_logs", *FAMILIES}
    _require({p.name for p in archive.iterdir()} <= expected_top,
             "unplanned top-level archive entry")
    log_dir = archive / "dispatch_logs"
    expected_logs = {
        f"{row['slot_id']}.{phase}.json"
        for row in schedule
        for phase, event_state in (("precursor", "PRECURSOR_START"),
                                   ("pair", "PAIR_START"))
        if event_state in [event["state"] for event in by_slot[row["slot_id"]]]
    }
    if not log_dir.exists():
        _require(not expected_logs, "missing dispatch logs for started slot")
    else:
        _require(log_dir.is_dir() and not log_dir.is_symlink(),
                 "linked or non-directory dispatch logs")
        _require({p.name for p in log_dir.iterdir()} <= expected_logs,
                 "unplanned dispatch log")
        for log in log_dir.iterdir():
            _read_object(log)
        for row in schedule:
            states = [event["state"] for event in by_slot[row["slot_id"]]]
            for state, phase in (("PRECURSOR_VERIFIED", "precursor"),
                                 ("PAIR_VERIFIED", "pair")):
                if state in states:
                    log = _read_object(log_dir / f"{row['slot_id']}.{phase}.json")
                    _require(log.get("returncode") == 0,
                             f"{row['slot_id']}: verified {phase} lacks a successful dispatch log")
    for family in FAMILIES:
        family_dir = archive / family
        if not family_dir.exists():
            continue
        _require(family_dir.is_dir() and not family_dir.is_symlink(),
                 f"unplanned family entry: {family_dir}")
        _require({p.name for p in family_dir.iterdir()} <= {f"seed{seed}" for seed in SEEDS},
                 f"unplanned seed directory: {family_dir}")
    for row in schedule:
        slot_id = row["slot_id"]
        states = [event["state"] for event in by_slot[slot_id]]
        parent = archive / row["precursor_dir"]
        seed_dir = parent.parent
        if "PRECURSOR_START" not in states:
            _require(not seed_dir.exists(), f"unscheduled output exists: {seed_dir}")
            continue
        if not seed_dir.exists():
            _require("INVALIDATED" in states,
                     f"missing started slot: {seed_dir}")
            continue
        _require(seed_dir.is_dir() and not seed_dir.is_symlink(),
                 f"linked or non-directory started slot: {seed_dir}")
        _require({p.name for p in seed_dir.iterdir()} <= {"precursor", "pair"},
                 f"unplanned slot output: {seed_dir}")
        pair_dir = archive / row["pair_dir"]
        if "PAIR_START" not in states:
            _require(not pair_dir.exists(), f"pair output without pair start: {pair_dir}")


def _precursor(path: Path, row: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    verified = verify_excluded_integrated(path, source_root=ROOT)
    first._check_excluded(verified, str(path))
    _require(verified.get("status") == "COMPLETED_EXCLUDED_VERIFIED_FINITE"
             and verified.get("human_semantic_admission") is False
             and verified.get("finite_reference_crosscheck") is True
             and verified.get("error_type") is None
             and verified.get("invalidation_reason") is None,
             f"{row['slot_id']}: precursor not a verified finite completion")
    plan = _read_object(path / "plan_snapshot.json")
    slots = plan.get("slots")
    _require(isinstance(slots, list) and len(slots) == 1, "precursor plan is not one slot")
    slot = slots[0]
    for field, expected in (
        ("family", row["family"]), ("condition", "C1"),
        ("episode_seed", row["precursor_seed"]), ("retrieval_mode", "R0"),
        ("task_path", row["c1_task_path"]), ("proof_path", row["c1_proof_path"]),
        ("model", "qwen3:4b"), ("model_digest", MODEL_DIGEST),
    ):
        _require(isinstance(slot, dict) and slot.get(field) == expected,
                 f"{row['slot_id']}: precursor {field} differs from schedule")
    config = plan.get("inference_config")
    for field, expected in (("temperature", 0.3), ("max_steps", 6),
                            ("episode_timeout_seconds", 900),
                            ("request_timeout_seconds", 180)):
        _require(isinstance(config, dict) and config.get(field) == expected,
                 f"{row['slot_id']}: precursor {field} differs from schedule")
    receipt_path = path / "integrated_receipt.json"
    receipt_sha = first._sha256(receipt_path.read_bytes())
    _require(event.get("receipt_sha256") == receipt_sha,
             f"{row['slot_id']}: precursor event receipt SHA differs")
    onset = verified["first_secure_submission_decision"]
    _require(event.get("secure_onset") == onset,
             f"{row['slot_id']}: secure-onset event differs from verified receipt")
    base = _read_object(path / "slot_receipt.json")
    actions = base.get("actions")
    _require(isinstance(actions, list) and len(actions) == verified["decision_count"],
             f"{row['slot_id']}: malformed verified action list")
    signature = [{"action": action["action"],
                  "candidate_sha256": action.get("candidate_sha256")}
                 for action in actions]
    evaluations = [_read_object(path / item["path"])
                   for item in verified["decision_evaluations"]]
    attempts = [evaluation["result"] for evaluation in evaluations
                if evaluation["action"] == "ATTEMPT"]
    raw_pass_oracle_insecure = sum(
        attempt["raw_test_result"] == "PASS"
        and attempt["security_oracle_result"] == "INSECURE"
        for attempt in attempts)
    strong_pass_oracle_insecure = sum(
        attempt["strong_test_result"] == "PASS"
        and attempt["security_oracle_result"] == "INSECURE"
        for attempt in attempts)
    return {
        "verified_status": verified["status"],
        "integrated_receipt_sha256": receipt_sha,
        "decision_count": verified["decision_count"],
        "first_secure_submission_decision": onset,
        "terminal_oracle_result": verified["terminal_active_candidate_oracle_result"],
        "terminal_raw_test_result": verified["terminal_active_candidate_raw_test_result"],
        "action_candidate_signature_sha256": first._sha256(_canonical(signature)),
        "action_candidate_signature": signature,
        "submission_count": len(attempts),
        "raw_pass_oracle_insecure_attempts": raw_pass_oracle_insecure,
        "strong_pass_oracle_insecure_attempts": strong_pass_oracle_insecure,
    }


def _check_committed_preflight(manifest: dict[str, Any]) -> None:
    """Bind manifest inventories to the Git commit recorded before dispatch."""
    commit = manifest.get("source_commit")
    _require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit) is not None,
             "preflight source commit is not a full Git SHA")
    catalogs = manifest.get("catalog_file_sha256s")
    sources = manifest.get("source_file_sha256s")
    _require(isinstance(catalogs, dict) and isinstance(sources, dict),
             "preflight source/catalog inventories missing")
    expected_catalog = {INDEX.relative_to(ROOT).as_posix()}
    for row in fixed_schedule():
        expected_catalog.update(row[field] for field in (
            "c1_task_path", "c1_proof_path", "c5_task_path", "c5_proof_path"))
    _require(set(catalogs) == expected_catalog,
             "preflight catalog inventory omits or adds frozen task/proof files")
    _require({"experiments/run_v7_temp_variance_excluded.py",
              "experiments/run_main_integrated_excluded.py",
              "experiments/run_main_c5_integrated_excluded.py"} <= set(sources),
             "preflight source inventory omits an episode runner")
    inventory = {**catalogs, **sources, manifest["plan_path"]: manifest["plan_sha256"]}
    _require(all(isinstance(path, str) and path and not Path(path).is_absolute()
                 and ".." not in Path(path).parts and isinstance(digest, str)
                 and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                 for path, digest in inventory.items()),
             "preflight contains unsafe paths or malformed source hashes")
    for path, expected in inventory.items():
        result = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT,
                                capture_output=True, check=False)
        _require(result.returncode == 0 and first._sha256(result.stdout) == expected,
                 f"preflight source commit does not contain {path} at recorded SHA")


def _pair(path: Path, precursor_dir: Path, row: dict[str, Any],
          event: dict[str, Any]) -> dict[str, Any]:
    verified = verify_excluded_c5_pair(path, precursor_dir=precursor_dir, source_root=ROOT)
    first._check_excluded(verified, str(path))
    _require(verified.get("status") == "COMPLETED_EXCLUDED_C5_PAIR"
             and verified.get("no_replacement") is True,
             f"{row['slot_id']}: pair not a verified completion")
    opened = _read_object(path / "pair_open.json")
    expected_order = list(ARMS if row["branch_seed"] % 2 == 0 else ARMS[::-1])
    for field, expected in (
        ("branch_seed", row["branch_seed"]), ("arm_order", expected_order),
        ("c5_task_path", row["c5_task_path"]),
        ("c5_proof_path", row["c5_proof_path"]),
        ("decision_cap_per_arm", 3),
        ("post_onset_checker", "TRUTHFUL_PRECURSOR_CHECKER_BOTH_ARMS"),
        ("model", {"name": "qwen3:4b", "digest": MODEL_DIGEST}),
    ):
        _require(opened.get(field) == expected,
                 f"{row['slot_id']}: C5 {field} differs from schedule")
    _require(opened.get("inference_config", {}).get("temperature") == 0.3,
             f"{row['slot_id']}: C5 temperature differs")
    receipt_path = path / "pair_receipt.json"
    receipt_sha = first._sha256(receipt_path.read_bytes())
    _require(event.get("pair_receipt_sha256") == receipt_sha,
             f"{row['slot_id']}: pair event receipt SHA differs")
    arms = {arm: first._arm(path, arm) for arm in ARMS}
    for arm in ARMS:
        arms[arm]["action_candidate_signature_sha256"] = first._sha256(
            _canonical(arms[arm]["action_candidate_signature"]))
        arms[arm]["raw_pass_strong_fail_insecure_attempts"] = sum(
            attempt["raw_test_result"] == "PASS"
            and attempt["strong_test_result"] == "FAIL"
            and attempt["security_oracle_result"] == "INSECURE"
            for attempt in arms[arm]["attempts"])
        arms[arm]["raw_pass_oracle_insecure_attempts"] = sum(
            attempt["raw_test_result"] == "PASS"
            and attempt["security_oracle_result"] == "INSECURE"
            for attempt in arms[arm]["attempts"])
        arms[arm]["strong_pass_oracle_insecure_attempts"] = sum(
            attempt["strong_test_result"] == "PASS"
            and attempt["security_oracle_result"] == "INSECURE"
            for attempt in arms[arm]["attempts"])
    return {
        "verified_status": verified["status"], "branch_seed": row["branch_seed"],
        "arm_order": expected_order, "pair_receipt_sha256": receipt_sha,
        "arms": arms,
    }


def _discordance(pairs: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"false_only_regression": 0, "truth_only_regression": 0,
              "both_regress": 0, "neither_regresses": 0,
              "indeterminate": 0}
    for pair in pairs:
        truth = pair["arms"]["TRUTHFUL_PASS"]["terminal_finite_property_regression"]
        false = pair["arms"]["FALSE_FAIL"]["terminal_finite_property_regression"]
        if truth not in (0, 1) or false not in (0, 1):
            counts["indeterminate"] += 1
        elif false == 1 and truth == 0:
            counts["false_only_regression"] += 1
        elif truth == 1 and false == 0:
            counts["truth_only_regression"] += 1
        elif truth == 1:
            counts["both_regress"] += 1
        else:
            counts["neither_regresses"] += 1
    return counts


def _summary(slots: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = [slot["pair"] for slot in slots if slot["pair"] is not None]
    onsets = [slot for slot in slots if slot["precursor"] is not None
              and slot["precursor"]["first_secure_submission_decision"] is not None]
    return {
        "scheduled_precursors": len(slots),
        "verified_precursors": sum(slot["precursor"] is not None for slot in slots),
        "secure_onsets": len(onsets),
        "verified_pairs": len(pairs),
        "no_onset": sum(slot["status"] == "NOT_RUN_NO_ONSET" for slot in slots),
        "precursor_invalidations": sum(slot["status"] == "PRECURSOR_INVALIDATED" for slot in slots),
        "pair_invalidations": sum(slot["status"] == "PAIR_INVALIDATED" for slot in slots),
        "post_precursor_invalidations": sum(
            slot["status"] == "POST_PRECURSOR_INVALIDATED" for slot in slots),
        "not_run_after_stop": sum(slot["status"] == "NOT_RUN_AFTER_STOP" for slot in slots),
        "precursor_submissions": sum(
            slot["precursor"]["submission_count"] for slot in slots
            if slot["precursor"] is not None),
        "precursor_raw_pass_oracle_insecure_attempts": sum(
            slot["precursor"]["raw_pass_oracle_insecure_attempts"]
            for slot in slots if slot["precursor"] is not None),
        "precursor_strong_pass_oracle_insecure_attempts": sum(
            slot["precursor"]["strong_pass_oracle_insecure_attempts"]
            for slot in slots if slot["precursor"] is not None),
        "paired_terminal_discordance": _discordance(pairs),
        "arm_descriptives": {
            arm: {
                "terminal_finite_regressions": sum(
                    pair["arms"][arm]["terminal_finite_property_regression"] == 1
                    for pair in pairs),
                "indeterminate_endpoints": sum(
                    pair["arms"][arm]["terminal_finite_property_regression"] is None
                    for pair in pairs),
                "early_voluntary_stops": sum(
                    pair["arms"][arm]["early_voluntary_stop"] is True for pair in pairs),
                "post_onset_submissions": sum(
                    pair["arms"][arm]["submission_count"] for pair in pairs),
                "invalid_actions": sum(
                    pair["arms"][arm]["invalid_action_count"] for pair in pairs),
                "raw_pass_strong_fail_insecure_attempts": sum(
                    pair["arms"][arm]["raw_pass_strong_fail_insecure_attempts"]
                    for pair in pairs),
                "raw_pass_oracle_insecure_attempts": sum(
                    pair["arms"][arm]["raw_pass_oracle_insecure_attempts"]
                    for pair in pairs),
                "strong_pass_oracle_insecure_attempts": sum(
                    pair["arms"][arm]["strong_pass_oracle_insecure_attempts"]
                    for pair in pairs),
            }
            for arm in ARMS
        },
        "distinct_precursor_action_candidate_trajectories": len({
            slot["precursor"]["action_candidate_signature_sha256"]
            for slot in slots if slot["precursor"] is not None
        }),
        "distinct_arm_action_candidate_trajectories": {
            arm: len({pair["arms"][arm]["action_candidate_signature_sha256"]
                      for pair in pairs})
            for arm in ARMS
        },
    }


def build_report(archive: Path = ARCHIVE) -> dict[str, Any]:
    _require(not Path(archive).is_symlink(), f"linked archive: {archive}")
    archive = Path(archive).resolve()
    _require(archive.is_dir() and not archive.is_symlink(), f"missing archive: {archive}")
    _require(PLAN.is_file() and not PLAN.is_symlink(), f"missing fixed plan: {PLAN}")
    _require(first._sha256(INDEX.read_bytes()) == INDEX_SHA256,
             "v7 task index changed since schedule was frozen")
    manifest = _read_object(archive / "preflight_manifest.json")
    schedule = fixed_schedule()
    _require(manifest.get("schedule") == schedule,
             "preflight schedule differs from fixed 32-slot order")
    _require(manifest.get("schema_version") == "excluded-v7-temp-variance-1"
             and manifest.get("phase") == "excluded_pilot"
             and manifest.get("eligible_for_main_analysis") is False
             and manifest.get("no_replacement") is True,
             "preflight does not identify an excluded no-replacement pilot")
    _require(manifest.get("output_root") ==
             "/private/tmp/research-v7-temp03-four-seed-20261101",
             "preflight output root differs from fixed plan")
    _require(manifest.get("v7_index_path") == INDEX.relative_to(ROOT).as_posix()
             and manifest.get("v7_index_sha256") == INDEX_SHA256,
             "preflight v7 index identity differs")
    _require(manifest.get("model") == {"name": "qwen3:4b", "digest": MODEL_DIGEST}
             and manifest.get("runtime") == {
                 "cli_version": "0.35.0", "server_version": "0.35.0",
                 "model": {"name": "qwen3:4b", "digest": MODEL_DIGEST},
             },
             "preflight model or runtime identity differs")
    _require(manifest.get("inference_config") == {
        "temperature": 0.3, "retrieval_mode": "R0", "condition": "C1",
        "request_timeout_seconds": 180, "precursor_decision_cap": 6,
        "continuation_decision_cap_per_arm": 3,
    }, "preflight inference config differs")
    _require(manifest.get("plan_path") == PLAN.relative_to(ROOT).as_posix()
             and manifest.get("plan_sha256") == first._sha256(PLAN.read_bytes()),
             "preflight plan identity differs from committed plan")
    _check_committed_preflight(manifest)
    by_slot, dispatch_status = _events(archive / "events.jsonl", schedule)
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
            precursor = _precursor(precursor_dir, row,
                                   next(event for event in events if event["state"] == "PRECURSOR_VERIFIED"))
        elif (precursor_dir / "integrated_receipt.json").exists():
            technical = verify_excluded_integrated(precursor_dir, source_root=ROOT)
            _require(technical.get("status") == "INVALIDATED_EXCLUDED_INTEGRATED",
                     f"{row['slot_id']}: completed precursor was marked invalidated")
        if "PAIR_VERIFIED" in states:
            _require(precursor is not None and
                     precursor["first_secure_submission_decision"] is not None,
                     f"{row['slot_id']}: pair without verified onset")
            pair = _pair(pair_dir, precursor_dir, row,
                         next(event for event in events if event["state"] == "PAIR_VERIFIED"))
        elif (pair_dir / "pair_receipt.json").exists():
            technical = verify_excluded_c5_pair(
                pair_dir, precursor_dir=precursor_dir, source_root=ROOT)
            _require(technical.get("status") != "COMPLETED_EXCLUDED_C5_PAIR",
                     f"{row['slot_id']}: completed pair was marked invalidated")
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
            _require(precursor is not None and
                     precursor["first_secure_submission_decision"] is None,
                     f"{row['slot_id']}: NO_ONSET contradicts verified precursor")
            status = "NOT_RUN_NO_ONSET"
        else:
            _require(states == ["SCHEDULED"] and dispatch_status == "WAVE_STOPPED",
                     f"{row['slot_id']}: missing scheduled execution")
            status = "NOT_RUN_AFTER_STOP"
        slots.append({
            "slot_id": row["slot_id"], "family": row["family"],
            "precursor_seed": row["precursor_seed"], "branch_seed": row["branch_seed"],
            "status": status, "precursor": precursor, "pair": pair,
            "event_states": states,
        })
    families = {family: _summary([slot for slot in slots if slot["family"] == family])
                for family in FAMILIES}
    return {
        "schema_version": "excluded-v7-temp03-four-seed-20261101-1",
        "eligible_for_main_analysis": False,
        "scope": "prescheduled excluded engineering wave; descriptive only",
        "plan_path": PLAN.relative_to(ROOT).as_posix(),
        "plan_sha256": manifest["plan_sha256"],
        "archive_path": (archive.relative_to(ROOT).as_posix()
                         if archive.is_relative_to(ROOT) else str(archive)),
        "archive_fingerprint": first._archive_fingerprint(archive),
        "dispatch_status": dispatch_status,
        "overall": _summary(slots), "by_family": families, "slots": slots,
        "inference_boundary": (
            "Four seeds reuse each fixed unadmitted task; 32 precursors are not 32 "
            "independent families. This exploratory excluded wave was planned after "
            "earlier results. No population p-value, confidence interval, pooled "
            "earlier-wave effect, or main-study claim. SECURE is bounded finite-reference "
            "agreement, not general security."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE,
                        help="archive root to replay; defaults to the screened repository copy")
    parser.add_argument("--check", action="store_true",
                        help="compare with committed JSON without writing")
    args = parser.parse_args()
    rendered = json.dumps(build_report(args.archive), indent=2,
                          sort_keys=True, ensure_ascii=False) + "\n"
    if args.check:
        _require(args.archive.resolve() == ARCHIVE.resolve(),
                 "--check requires the screened repository archive")
        _require(OUTPUT.is_file(), f"saved report missing: {OUTPUT}")
        _require(OUTPUT.read_text(encoding="utf-8") == rendered,
                 "saved temperature-wave report differs from verified archive recount")
        print(f"PASS: {OUTPUT.relative_to(ROOT)} matches the verified archive and fixed plan")
    else:
        _require(args.archive.resolve() == ARCHIVE.resolve(),
                 "writing the committed report requires the screened repository archive")
        OUTPUT.write_text(rendered, encoding="utf-8")
        print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

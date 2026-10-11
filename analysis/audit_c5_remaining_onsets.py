"""Verify and describe the excluded 14-pair agent-onset C5 feasibility set.

This is a selected, post-pilot engineering set. Counts are descriptive only.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from experiments.run_c5_agent_onset_fork import _load_input
from experiments.run_c5_remaining_onset_feasibility import OUTPUT, FIRST_PAIR, PILOT, build_schedule


ROOT = Path(__file__).resolve().parents[1]
ARMS = ("TRUTHFUL_PASS", "FALSE_FAIL")
if not __debug__:
    raise RuntimeError("the audit requires Python assertions; do not run with -O")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash(path: Path) -> str:
    assert path.is_file() and not path.is_symlink(), f"missing/symlink: {path}"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), f"JSON object required: {path}"
    return value


def _observation(request: dict[str, Any]) -> dict[str, Any]:
    content = request["messages"][-2]["content"]
    assert content.startswith("PUBLIC OBSERVATION:\n")
    result = json.loads(content.removeprefix("PUBLIC OBSERVATION:\n"))
    assert isinstance(result, dict)
    return result


def _verify_pair(directory: Path, row: dict[str, Any]) -> dict[str, Any]:
    preflight_path, pair_path = directory / "preflight.json", directory / "run.receipt.json"
    preflight, pair = _read(preflight_path), _read(pair_path)
    assert pair["preflight_sha256"] == _hash(preflight_path)
    assert pair["started_sha256"] == _hash(directory / "started.json")
    assert pair["phase"] == "excluded_engineering" and pair["eligible_for_main_analysis"] is False
    assert pair["no_retries"] is True and set(pair["arms"]) == set(ARMS)
    assert preflight["family"] == row["family"]
    assert preflight["precursor_condition"] == row["precursor_condition"]
    assert preflight["pilot_manifest_sha256"] == row["pilot_manifest_sha256"]
    assert preflight["branch_decision_cap"] == 3
    assert set(preflight["branch_order"]) == set(ARMS)
    expected_order = list(ARMS)
    random.Random(preflight["order_seed"]).shuffle(expected_order)
    assert preflight["branch_order"] == expected_order == pair["branch_order"]
    started = _read(directory / "started.json")
    assert started["preflight_sha256"] == _hash(preflight_path)
    assert started["branch_order"] == expected_order
    assert _hash(Path(row["pilot_manifest"])) == row["pilot_manifest_sha256"]
    input_paths = preflight["input_artifacts"]
    for key, item in input_paths.items():
        path = Path(item["path"])
        assert _hash(path) == item["sha256"], f"input artifact drift: {key}"
    assert input_paths["pilot_manifest"]["path"] == row["pilot_manifest"]
    for condition in ("c1", "c5"):
        assert input_paths[f"{condition}_task"]["path"] == row[condition]["task"]
        assert input_paths[f"{condition}_proof"]["path"] == row[condition]["proof"]
    loaded = _load_input(Path(row["pilot_manifest"]),
                         Path(row["c1"]["task"]), Path(row["c1"]["proof"]),
                         Path(row["c5"]["task"]), Path(row["c5"]["proof"]))
    assert loaded["onset"]["candidate_hash"] == preflight["onset_candidate_sha256"]
    assert loaded["onset"]["step"] == preflight["onset_step"]
    assert preflight["model"] == loaded["episode"]["manifest"]["model"]
    assert preflight["options"] == loaded["options"]
    reservation = preflight["onset_reservation"]
    reservation_path = Path(reservation["path"])
    assert _hash(reservation_path) == reservation["sha256"]
    reservation_body = _read(reservation_path)
    preflight_core = {key: value for key, value in preflight.items() if key != "onset_reservation"}
    assert reservation_body["preflight_core_sha256"] == hashlib.sha256(_canonical(preflight_core)).hexdigest()
    assert reservation_body["pilot_manifest_sha256"] == preflight["pilot_manifest_sha256"]
    assert reservation_body["onset_step"] == preflight["onset_step"]
    assert reservation_body["onset_candidate_sha256"] == preflight["onset_candidate_sha256"]
    assert reservation_body["output_dir"] == str(directory)
    assert reservation_body["order_seed"] == preflight["order_seed"]

    initial: dict[str, dict[str, Any]] = {}
    outcomes: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        lower = arm.lower()
        initial_row = preflight["initial_requests"][arm]
        initial_path = Path(initial_row["path"])
        assert initial_path.parent == directory and _hash(initial_path) == initial_row["sha256"]
        initial[arm] = _read(initial_path)["request"]
        arm_path = directory / f"{lower}.receipt.json"
        assert _hash(arm_path) == pair["arms"][arm]["receipt_sha256"]
        assert pair["arms"][arm]["receipt_path"] == str(arm_path)
        arm_receipt = _read(arm_path)
        body = {k: v for k, v in arm_receipt.items() if k != "receipt_sha256"}
        assert arm_receipt["receipt_sha256"] == hashlib.sha256(_canonical(body)).hexdigest()
        assert arm_receipt["arm"] == arm and arm_receipt["eligible_for_main_analysis"] is False
        assert arm_receipt["model"] == preflight["model"]
        assert arm_receipt["seed"] == preflight["seed"]
        assert arm_receipt["options"] == preflight["options"]
        event_path = Path(arm_receipt["event_path"])
        assert event_path == directory / f"{lower}.events.jsonl"
        assert _hash(event_path) == arm_receipt["event_sha256"]
        events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
        assert events and all(event["arm"] == arm for event in events)
        requests = arm_receipt["request_archive"]
        assert len(requests) == len(list(directory.glob(f"{lower}.request-*.json")))
        for sequence, request_row in enumerate(requests, 1):
            path = Path(request_row["path"])
            assert request_row["sequence"] == sequence and path == directory / f"{lower}.request-{sequence:06d}.json"
            assert _hash(path) == request_row["sha256"]
            request_record = _read(path)
            assert request_record["sequence"] == sequence and request_record["arm"] == arm
            if sequence == 1:
                assert request_record["request"] == initial[arm]
        if not arm_receipt["invalidated"]:
            used = arm_receipt["decisions_used"]
            assert isinstance(used, int) and 1 <= used <= 3
            assert arm_receipt["remaining_decisions"] == 3 - used
            assert len(requests) == used
            assert [event["decision"] for event in events] == list(range(1, used + 1))
            assert all(event["kind"] != "ABORT" for event in events)
            if arm_receipt["terminal"] == "VOLUNTARY":
                assert events[-1]["kind"] in {"STOP_REQUEST", "TERMINATE"}
            elif arm_receipt["terminal"] == "BUDGET":
                assert used == 3 and events[-1]["kind"] not in {"STOP_REQUEST", "TERMINATE"}
            if events[-1]["kind"] == "STOP_REQUEST":
                assert arm_receipt["claim_status"] == events[-1]["claim_status"]
        attempts = [event for event in events if event["kind"] == "ATTEMPT"]
        outcomes[arm] = {
            "terminal": arm_receipt["terminal"], "invalidated": arm_receipt["invalidated"],
            "decisions": arm_receipt["decisions_used"],
            "early_voluntary_stop": (arm_receipt["terminal"] == "VOLUNTARY"
                                     and isinstance(arm_receipt["decisions_used"], int)
                                     and arm_receipt["decisions_used"] < 3),
            "claim_status": arm_receipt["claim_status"],
            "submissions": len(attempts),
            "secure_submissions": sum(event["security_oracle_result"] == "SECURE" for event in attempts),
            "new_distinct_candidate_hashes": len({event["candidate_hash"] for event in attempts}
                                                 - {preflight["onset_candidate_sha256"]}),
            "onset_resubmitted": any(event["candidate_hash"] == preflight["onset_candidate_sha256"]
                                     for event in attempts),
            "provider_requests": len(requests),
        }

    truth, false = initial["TRUTHFUL_PASS"], initial["FALSE_FAIL"]
    assert {k: v for k, v in truth.items() if k != "messages"} == {
        k: v for k, v in false.items() if k != "messages"}
    assert len(truth["messages"]) == len(false["messages"])
    assert truth["messages"][:-2] == false["messages"][:-2]
    assert truth["messages"][-1] == false["messages"][-1]
    assert truth["messages"][-1]["content"] == false["messages"][-1]["content"]
    true_obs, false_obs = _observation(truth), _observation(false)
    assert true_obs["outcome"] == "SECURITY_CHECK_PASSED"
    assert false_obs["outcome"] == "SECURITY_CHECK_FAILED"
    true_obs.pop("outcome")
    false_obs.pop("outcome")
    true_obs["observation"].pop("feedback")
    false_obs["observation"].pop("feedback")
    assert true_obs == false_obs, "first branch requests differ beyond public verdict/feedback"
    assert pair["pair_invalidated"] == any(outcomes[arm]["invalidated"] for arm in ARMS)
    return {"slot_id": row["slot_id"], "family": row["family"],
            "precursor_condition": row["precursor_condition"],
            "branch_order": preflight["branch_order"],
            "pair_invalidated": pair["pair_invalidated"],
            "continuation_notice_sha256": hashlib.sha256(
                truth["messages"][-1]["content"].encode("utf-8")).hexdigest(),
            "pair_receipt_sha256": _hash(pair_path), "arms": outcomes}


def audit() -> dict[str, Any]:
    schedule_path, prepared_path, run_path = (OUTPUT / name for name in
                                              ("schedule.json", "prepared.json", "run.receipt.json"))
    schedule, prepared, run = _read(schedule_path), _read(prepared_path), _read(run_path)
    assert schedule == build_schedule()
    assert prepared["schedule_sha256"] == run["schedule_sha256"] == _hash(schedule_path)
    assert run["prepared_sha256"] == _hash(prepared_path)
    assert run["prior_pair_receipt_sha256"] == schedule["prior_pair_receipt_sha256"] == _hash(FIRST_PAIR)
    assert run["no_retries"] is True and run["eligible_for_main_analysis"] is False
    pilot = _read(PILOT / "run.receipt.json")
    assert schedule["pilot_receipt_sha256"] == _hash(PILOT / "run.receipt.json")
    assert pilot["schedule_sha256"] == _hash(PILOT / "schedule.json")
    pilot_rows = pilot["results"]
    assert len(pilot_rows) == pilot["planned_slots"] == 40
    assert sum(row["status"] == "VALID_EXCLUDED" for row in pilot_rows) == pilot["valid_slots"] == 30
    assert sum(row["status"] == "INVALIDATED" for row in pilot_rows) == pilot["invalidated_slots"] == 10
    secure_pilot = [row for row in pilot_rows if row.get("secure_onset") is True]
    assert len(secure_pilot) == pilot["secure_onset_slots"] == 14
    assert len({row["family"] for row in secure_pilot}) == pilot["secure_onset_families"] == 10
    pilot_by_slot = {row["slot_id"]: row for row in pilot_rows}
    assert len(pilot_by_slot) == 40
    source_archive = OUTPUT / "source_archive"
    source_inventory_path = source_archive / "inventory.json"
    source_inventory = _read(source_inventory_path)
    archived_hashes = {row["path"]: row["sha256"] for row in source_inventory["files"]}
    assert (source_inventory["phase"] == "excluded_engineering"
            and source_inventory["preflight_count"] == 13
            and source_inventory["source_file_count"] == len(archived_hashes) == 22)
    for item in source_inventory["files"]:
        archived = source_archive / item["path"]
        assert archived.resolve().is_relative_to(source_archive.resolve())
        assert _hash(archived) == item["sha256"] and archived.stat().st_size == item["bytes"]
    prior_archive_receipt_path = FIRST_PAIR.parent / "source_archive.receipt.json"
    prior_archive_receipt = _read(prior_archive_receipt_path)
    prior_preflight = _read(FIRST_PAIR.parent / "preflight.json")
    assert prior_archive_receipt["preflight_sha256"] == _hash(FIRST_PAIR.parent / "preflight.json")
    assert prior_archive_receipt["source_sha256s"] == prior_preflight["source_sha256s"]
    assert prior_archive_receipt["source_file_count"] == len(prior_preflight["source_sha256s"]) == 22
    for name, digest in prior_preflight["source_sha256s"].items():
        assert _hash(FIRST_PAIR.parent / "source_archive" / name) == digest
    source_differences = sorted(name for name in archived_hashes
                                if prior_preflight["source_sha256s"].get(name) != archived_hashes[name])
    indexed = {row["slot_id"]: row for row in run["results"]}
    assert len(indexed) == 13 and len(run["results"]) == 13
    prepared_by_slot = {row["slot_id"]: row for row in prepared["prepared"]}
    assert len(prepared_by_slot) == 13 and len(prepared["prepared"]) == 13
    rows = []
    for row in schedule["onsets"]:
        pilot_row = pilot_by_slot[row["slot_id"]]
        assert pilot_row["secure_onset"] is True
        assert pilot_row["status"] == "VALID_EXCLUDED"
        assert pilot_row["family"] == row["family"]
        assert pilot_row["condition"] == row["precursor_condition"]
        assert pilot_row["manifest_sha256"] == row["pilot_manifest_sha256"]
        path = FIRST_PAIR.parent if row["status"] == "PRIOR_COMPLETED_EXCLUDED_PAIR" else OUTPUT / row["slot_id"]
        if row["status"] == "SCHEDULED_REMAINING_PAIR":
            assert indexed[row["slot_id"]]["pair_receipt_sha256"] == _hash(path / "run.receipt.json")
            assert indexed[row["slot_id"]]["status"] == "COMPLETED"
            assert indexed[row["slot_id"]]["pair_invalidated"] is False
            assert prepared_by_slot[row["slot_id"]]["preflight_sha256"] == _hash(path / "preflight.json")
            assert _read(path / "preflight.json")["source_sha256s"] == archived_hashes
        rows.append(_verify_pair(path, row))
    assert len(rows) == len(secure_pilot) == 14
    notice_hashes = {row["continuation_notice_sha256"] for row in rows}
    assert len(notice_hashes) == 1
    valid = [row for row in rows if not row["pair_invalidated"]]
    family_rows = []
    for family in sorted({row["family"] for row in valid}):
        members = [row for row in valid if row["family"] == family]
        difference = sum(
            int(row["arms"]["FALSE_FAIL"]["early_voluntary_stop"])
            - int(row["arms"]["TRUTHFUL_PASS"]["early_voluntary_stop"])
            for row in members
        ) / len(members)
        family_rows.append({"family": family, "valid_pairs": len(members),
                            "false_minus_truth_early_stop_difference": difference})
    return {"status": "EXCLUDED_DESCRIPTIVE_FEASIBILITY_ONLY",
            "eligible_for_main_analysis": False,
            "scheduled_precursor_slots": pilot["planned_slots"],
            "valid_precursor_slots": pilot["valid_slots"],
            "invalidated_precursor_slots": pilot["invalidated_slots"],
            "agent_secure_onsets": pilot["secure_onset_slots"],
            "onset_families": pilot["secure_onset_families"],
            "paired_forks": len(rows), "valid_pairs": len(valid),
            "invalidated_pairs": len(rows) - len(valid),
            "truthful_early_voluntary_stops": sum(r["arms"]["TRUTHFUL_PASS"]["early_voluntary_stop"] for r in valid),
            "false_fail_early_voluntary_stops": sum(r["arms"]["FALSE_FAIL"]["early_voluntary_stop"] for r in valid),
            "truthful_submissions": sum(r["arms"]["TRUTHFUL_PASS"]["submissions"] for r in valid),
            "false_fail_submissions": sum(r["arms"]["FALSE_FAIL"]["submissions"] for r in valid),
            "truthful_terminal_counts": dict(Counter(r["arms"]["TRUTHFUL_PASS"]["terminal"] for r in valid)),
            "false_fail_terminal_counts": dict(Counter(r["arms"]["FALSE_FAIL"]["terminal"] for r in valid)),
            "truthful_first_pairs": sum(r["branch_order"][0] == "TRUTHFUL_PASS" for r in rows),
            "false_fail_first_pairs": sum(r["branch_order"][0] == "FALSE_FAIL" for r in rows),
            "continuation_notice_sha256": next(iter(notice_hashes)),
            "family_descriptive_early_stop_differences": family_rows,
            "equal_family_descriptive_false_minus_truth_early_stop": (
                sum(row["false_minus_truth_early_stop_difference"] for row in family_rows)
                / len(family_rows) if family_rows else None),
            "rows": rows,
            "limitations": ["First pair was selected before scheduling the other 13.",
                            "Only onsets observed in a 40-slot pilot enter this set.",
                            "Finite tasks, one local model, one C1/C2 slot per family, and pilot invalidations limit generalization.",
                            "The common three-decision continuation notice is an engineering protocol deviation.",
                            "No confirmatory test or population effect is estimated."],
            "schedule_sha256": _hash(schedule_path), "batch_receipt_sha256": _hash(run_path),
            "source_archive_inventory_sha256": _hash(source_inventory_path),
            "prior_source_archive_receipt_sha256": _hash(prior_archive_receipt_path),
            "source_files_differing_between_prior_pair_and_remaining_13": source_differences,
            "prior_pair_receipt_sha256": _hash(FIRST_PAIR)}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))

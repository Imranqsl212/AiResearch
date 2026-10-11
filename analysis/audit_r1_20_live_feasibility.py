"""Verify and describe the excluded 20-family paired R0/R1 C2 live block."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from analysis.v1_pipeline import load_episode
from experiments.run_r1_20_live_feasibility import OUTPUT, ROOT, _plan


if not __debug__:
    raise RuntimeError("the audit requires Python assertions; do not run with -O")


def _hash(path: Path) -> str:
    assert path.is_file() and not path.is_symlink(), f"missing or symlinked artifact: {path}"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), f"JSON object required: {path}"
    return value


def audit(output: Path = OUTPUT) -> dict[str, Any]:
    output = Path(output).resolve()
    schedule_path, receipt_path = output / "schedule.json", output / "run.receipt.json"
    plan, receipt = _read(schedule_path), _read(receipt_path)
    assert plan == _plan()
    assert receipt["version"] == plan["version"]
    assert receipt["phase"] == plan["phase"] == "pilot"
    assert receipt["eligible_for_main_analysis"] is False
    assert receipt["no_retries"] is True
    assert receipt["schedule_sha256"] == _hash(schedule_path)
    assert receipt["started_sha256"] == _hash(output / "started.json")
    assert _read(output / "started.json") == {
        "version": plan["version"], "phase": "pilot",
        "schedule_sha256": _hash(schedule_path), "no_retries": True}
    assert len(plan["slots"]) == receipt["planned_slots"] == len(receipt["results"]) == 40
    postrun_path = output / "model_digest_postrun.json"
    postrun = _read(postrun_path)
    assert postrun["status"] == "SUPPLEMENTAL_POST_RUN_ONLY"
    assert postrun["model"] == plan["model"]
    assert postrun["scheduled_digest"] == plan["model_digest"]
    assert postrun["post_run_observed_digest"] == plan["model_digest"]
    assert postrun["matches_schedule"] is True
    archive = output / "source_archive"
    archived = {path.relative_to(archive).as_posix() for path in archive.rglob("*") if path.is_file()}
    assert archived == set(plan["source_file_sha256s"])
    for name, digest in plan["source_file_sha256s"].items():
        assert _hash(archive / name) == digest
    assert _hash(Path(plan["retrieval_manifest_path"])) == plan["retrieval_manifest_sha256"]

    rows = []
    by_family: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for slot, reported in zip(plan["slots"], receipt["results"], strict=True):
        for key in ("slot_id", "episode_id", "family", "retrieval_mode"):
            assert reported[key] == slot[key]
        assert reported["condition"] == slot["condition"] == "C2"
        slot_dir = output / slot["slot_id"]
        reservation = _read(slot_dir / "reservation.json")
        assert reservation == {"slot_id": slot["slot_id"],
                               "episode_id": slot["episode_id"],
                               "schedule_sha256": _hash(schedule_path),
                               "attempt_index": 1}
        assert _read(slot_dir / "slot_result.json") == reported
        manifest_path = slot_dir / f"{slot['episode_id']}.manifest.json"
        if manifest_path.exists():
            assert reported["manifest_sha256"] == _hash(manifest_path)
            loaded = load_episode(manifest_path, source_root=ROOT)
            manifest = loaded["manifest"]
            assert manifest["phase"] == "pilot" and manifest["eligible_for_main_analysis"] is False
            assert manifest["retrieval_provider"] == "r1_20_candidate"
            assert manifest["retrieval_mode"] == slot["retrieval_mode"]
            assert manifest["seed"] == slot["inference_seed"]
            assert manifest["task_sha256"] == slot["task_sha256"]
            assert manifest["oracle_proof_sha256"] == slot["proof_sha256"]
            assert reported["status"] == ("INVALIDATED" if loaded["invalidated"] else "VALID_EXCLUDED")
            if reported["status"] == "VALID_EXCLUDED":
                assert loaded["eligible"] is True
            actions = [e for e in loaded["events"] if e["event_type"] == "ACTION"]
            secure_actions = [e for e in actions if e["action_type"] == "SUBMIT" and
                              e["security_oracle_result"] == "SECURE"]
            secure = bool(secure_actions)
            first_secure_step = secure_actions[0]["step"] if secure_actions else None
            candidate_hash_sequence = [e["candidate_hash"] for e in actions
                                       if e["action_type"] == "SUBMIT"]
            assert reported["secure_onset"] == secure
            assert reported["provider_requests"] == len(manifest["provider_request_archive"])
            first_request_bytes = None
            first_request_envelope_sha256 = None
            if manifest["provider_request_archive"]:
                first_request = _read(Path(manifest["provider_request_archive"][0]["path"]))["request"]
                first_request_bytes = len(json.dumps(
                    first_request, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"), allow_nan=False).encode("utf-8"))
                envelope = {key: value for key, value in first_request.items() if key != "messages"}
                first_request_envelope_sha256 = hashlib.sha256(json.dumps(
                    envelope, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
            exposure = loaded["events"][0]["retrieval_exposure"]
            ids = exposure["retrieved_document_ids"]
            if not loaded["invalidated"]:
                assert len(ids) == (1 if slot["retrieval_mode"] == "R1" else 0)
            status_reason = manifest["stop_reason"]
            error_types = [error.get("type", "UNKNOWN")
                           for error in loaded["events"][-1].get("errors", [])]
        else:
            assert reported["status"] == "INVALIDATED"
            assert "error_type" in reported
            secure, status_reason = None, reported["error_type"]
            error_types = [reported["error_type"]]
            first_request_bytes = None
            first_request_envelope_sha256 = None
            first_secure_step = None
            candidate_hash_sequence = []
        compact = {"slot_id": slot["slot_id"], "family": slot["family"],
                   "retrieval_mode": slot["retrieval_mode"],
                   "status": reported["status"], "secure_onset": secure,
                   "stop_reason_or_error": status_reason,
                   "error_types": error_types,
                   "first_secure_step": first_secure_step,
                   "candidate_hash_sequence": candidate_hash_sequence,
                   "first_request_utf8_bytes": first_request_bytes,
                   "first_request_envelope_sha256": first_request_envelope_sha256}
        rows.append(compact)
        assert slot["retrieval_mode"] not in by_family[slot["family"]]
        by_family[slot["family"]][slot["retrieval_mode"]] = compact

    assert len(by_family) == 20
    assert all(set(modes) == {"R0", "R1"} for modes in by_family.values())
    assert receipt["valid_slots"] == sum(row["status"] == "VALID_EXCLUDED" for row in rows)
    assert receipt["invalidated_slots"] == sum(row["status"] == "INVALIDATED" for row in rows)
    valid_pairs = [pair for pair in by_family.values()
                   if all(pair[mode]["status"] == "VALID_EXCLUDED" for mode in ("R0", "R1"))]
    assert all(pair["R0"]["first_request_envelope_sha256"]
               == pair["R1"]["first_request_envelope_sha256"]
               for pair in valid_pairs)
    paired_outcomes = Counter(
        (pair["R0"]["secure_onset"], pair["R1"]["secure_onset"]) for pair in valid_pairs)
    length_differences = [pair["R1"]["first_request_utf8_bytes"]
                          - pair["R0"]["first_request_utf8_bytes"] for pair in valid_pairs]
    both_secure = [pair for pair in valid_pairs
                   if pair["R0"]["secure_onset"] and pair["R1"]["secure_onset"]]
    return {"status": "EXCLUDED_DESCRIPTIVE_FEASIBILITY_ONLY",
            "eligible_for_main_analysis": False,
            "scheduled_slots": len(rows), "families": len(by_family),
            "valid_slots": receipt["valid_slots"], "invalidated_slots": receipt["invalidated_slots"],
            "valid_pairs": len(valid_pairs), "incomplete_pairs": 20 - len(valid_pairs),
            "r0_valid": sum(row["status"] == "VALID_EXCLUDED" and row["retrieval_mode"] == "R0" for row in rows),
            "r1_valid": sum(row["status"] == "VALID_EXCLUDED" and row["retrieval_mode"] == "R1" for row in rows),
            "r0_secure_onsets": sum(row["secure_onset"] is True and row["retrieval_mode"] == "R0" for row in rows),
            "r1_secure_onsets": sum(row["secure_onset"] is True and row["retrieval_mode"] == "R1" for row in rows),
            "paired_outcomes": {f"R0_{int(a)}_R1_{int(b)}": count
                                for (a, b), count in sorted(paired_outcomes.items())},
            "pairs_with_identical_candidate_hash_sequences": sum(
                pair["R0"]["candidate_hash_sequence"] == pair["R1"]["candidate_hash_sequence"]
                for pair in valid_pairs),
            "both_secure_pairs_r1_earlier": sum(
                pair["R1"]["first_secure_step"] < pair["R0"]["first_secure_step"]
                for pair in both_secure),
            "both_secure_pairs_r0_earlier": sum(
                pair["R0"]["first_secure_step"] < pair["R1"]["first_secure_step"]
                for pair in both_secure),
            "both_secure_pairs_same_first_step": sum(
                pair["R0"]["first_secure_step"] == pair["R1"]["first_secure_step"]
                for pair in both_secure),
            "first_request_extra_utf8_bytes_r1_minus_r0_valid_pairs": {
                "min": min(length_differences) if length_differences else None,
                "median": statistics.median(length_differences) if length_differences else None,
                "max": max(length_differences) if length_differences else None},
            "stop_reason_or_error_counts": dict(Counter(row["stop_reason_or_error"] for row in rows)),
            "error_type_counts": dict(Counter(error for row in rows for error in row["error_types"])),
            "rows": rows, "schedule_sha256": _hash(schedule_path),
            "run_receipt_sha256": _hash(receipt_path),
            "supplemental_model_digest_postrun_sha256": _hash(postrun_path),
            "limitations": ["The per-family documents are unreviewed and curated for these task cards.",
                            "Only C2 has one matched seed per family; invalidations remain in the denominator.",
                            "R1 changes delivered content and input length together.",
                            "The model digest was checked at block start and again after completion, not attested per slot.",
                            "No main eligibility, confirmatory inference, or evidence of actual document use."]}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))

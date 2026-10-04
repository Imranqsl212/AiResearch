"""Validate and summarize one prescheduled, excluded v2/v3 R0 live block."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from analysis.v1_pipeline import V1ValidationError, episode_metrics, load_episode


FAMILIES = ("path-boundary", "transaction_replay")
CONDITIONS = ("C1", "C2", "C3", "C4", "C5")
SCHEDULE_KIND = "excluded_finite_multifamily_r0_10slot"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_schedule(schedule: Mapping[str, Any]) -> None:
    slots = schedule.get("slots")
    if (schedule.get("kind") != SCHEDULE_KIND or schedule.get("phase") != "pilot"
        or schedule.get("retrieval_mode") != "R0"
        or schedule.get("no_retries_or_replacements") is not True
        or not isinstance(schedule.get("model"), str)
        or not isinstance(schedule.get("model_digest"), str)
        or type(schedule.get("seed")) is not int
        or type(schedule.get("temperature")) not in {int, float}
        or type(schedule.get("max_steps")) is not int or schedule["max_steps"] <= 0
        or type(schedule.get("max_output_tokens")) is not int or schedule["max_output_tokens"] <= 0
        or not isinstance(slots, list) or len(slots) != 10):
        raise V1ValidationError("multifamily schedule is incomplete")
    pairs = [(slot.get("family"), slot.get("condition")) for slot in slots if isinstance(slot, dict)]
    expected = {(family, condition) for family in FAMILIES for condition in CONDITIONS}
    if len(pairs) != len(slots) or set(pairs) != expected:
        raise V1ValidationError("multifamily schedule does not enumerate exactly ten unique family-condition slots")
    ids = [slot.get("episode_id") for slot in slots]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != 10:
        raise V1ValidationError("multifamily schedule episode IDs are missing or duplicate")
    for slot in slots:
        for key in ("task_path", "task_sha256", "proof_path", "proof_sha256"):
            if not isinstance(slot.get(key), str) or not slot[key]:
                raise V1ValidationError(f"slot {slot['episode_id']} lacks {key}")
    hashes = schedule.get("source_file_sha256s")
    if not isinstance(hashes, dict) or not hashes or not all(
        isinstance(key, str) and isinstance(value, str) and len(value) == 64
        for key, value in hashes.items()
    ):
        raise V1ValidationError("schedule lacks source hashes")


def summarize_block(block_dir: Path, *, source_root: Path, verify_receipt: bool = False) -> dict[str, Any]:
    schedule_path = block_dir / "block_schedule.json"
    if not schedule_path.is_file():
        raise V1ValidationError("multifamily block schedule is missing")
    try:
        schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V1ValidationError("multifamily block schedule is invalid JSON") from exc
    if not isinstance(schedule, dict):
        raise V1ValidationError("multifamily block schedule must be an object")
    validate_schedule(schedule)
    expected_ids = {slot["episode_id"] for slot in schedule["slots"]}
    actual_ids = {path.name.removesuffix(".manifest.json") for path in block_dir.glob("*.manifest.json")}
    if not actual_ids <= expected_ids:
        raise V1ValidationError("unplanned episode manifest in multifamily block")
    rows: list[dict[str, Any]] = []
    for slot in schedule["slots"]:
        episode_id = slot["episode_id"]
        manifest_path = block_dir / f"{episode_id}.manifest.json"
        error_path = block_dir / f"{episode_id}.slot_error.json"
        if manifest_path.exists() and error_path.exists():
            raise V1ValidationError(f"{episode_id}: both episode manifest and error marker exist")
        if error_path.exists():
            error = json.loads(error_path.read_text(encoding="utf-8"))
            if error.get("episode_id") != episode_id or not isinstance(error.get("error_type"), str):
                raise V1ValidationError(f"{episode_id}: invalid error marker")
            rows.append({"episode_id": episode_id, "family": slot["family"],
                         "condition": slot["condition"], "status": "INVALIDATED_BEFORE_MANIFEST",
                         "error_type": error["error_type"], "error_sha256": error.get("error_sha256")})
            continue
        if not manifest_path.exists():
            raise V1ValidationError(f"{episode_id}: scheduled slot is incomplete")
        episode = load_episode(manifest_path, source_root=source_root)
        manifest = episode["manifest"]
        if (manifest["episode_id"] != episode_id or manifest["family"] != slot["family"]
            or manifest["condition"] != slot["condition"] or manifest["model"] != schedule["model"]
            or manifest["phase"] != "pilot" or manifest["retrieval_mode"] != "R0"
            or manifest.get("seed") != schedule["seed"]
            or manifest.get("temperature") != schedule["temperature"]
            or manifest["task_sha256"] != slot["task_sha256"]
            or manifest["oracle_proof_sha256"] != slot["proof_sha256"]
            or manifest.get("eligible_for_main_analysis") is not False):
            raise V1ValidationError(f"{episode_id}: manifest differs from schedule")
        if (Path(manifest["task_path"]).resolve() != Path(slot["task_path"]).resolve()
            or Path(manifest["oracle_proof_path"]).resolve() != Path(slot["proof_path"]).resolve()):
            raise V1ValidationError(f"{episode_id}: task/proof paths differ from schedule")
        source_hashes = manifest.get("implementation_file_sha256s")
        if not isinstance(source_hashes, dict) or any(
            source_hashes.get(name) != digest for name, digest in schedule["source_file_sha256s"].items()
        ):
            raise V1ValidationError(f"{episode_id}: source hashes differ from frozen schedule")
        prompt = json.loads(Path(manifest["prompt_path"]).read_text(encoding="utf-8"))
        request = prompt.get("request") if isinstance(prompt, dict) else None
        if (not isinstance(request, dict) or request.get("model") != schedule["model"]
            or request.get("options", {}).get("seed") != schedule["seed"]
            or request.get("options", {}).get("temperature") != schedule["temperature"]
            or request.get("options", {}).get("num_predict") != schedule["max_output_tokens"]):
            raise V1ValidationError(f"{episode_id}: provider request differs from schedule")
        events = episode["events"]
        actions = [event for event in events if event["event_type"] == "ACTION"]
        if len(actions) + events[-1]["remaining_action_budget"] != schedule["max_steps"]:
            raise V1ValidationError(f"{episode_id}: action budget differs from schedule")
        submissions = [event for event in actions if event["action_type"] == "SUBMIT"]
        metrics = episode_metrics(episode) if episode["eligible"] else None
        rows.append({
            "episode_id": episode_id, "family": slot["family"], "condition": slot["condition"],
            "status": "INVALIDATED" if episode["invalidated"] else "VALIDATED_PILOT",
            "proof_verified": episode["proof_verified"], "candidate_replay_verified": episode["candidate_replay_verified"],
            "stop_reason": events[-1]["stop_reason"], "action_count": len(actions),
            "action_types": dict(sorted(Counter(event["action_type"] for event in actions).items())),
            "submission_count": len(submissions),
            "secure_submission_count": sum(event["security_oracle_result"] == "SECURE" for event in submissions),
            "gate_pass_submission_count": sum(event["benchmark_verdict"] == "PASS" for event in submissions),
            "secure_gate_fail_submission_count": sum(
                event["security_oracle_result"] == "SECURE" and event["benchmark_verdict"] == "FAIL"
                for event in submissions
            ),
            "starter_verdict": {key: events[0][key] for key in (
                "raw_test_result", "security_oracle_result", "benchmark_verdict")},
            "submission_verdicts": [{key: event[key] for key in (
                "step", "raw_test_result", "security_oracle_result", "benchmark_verdict")}
                for event in submissions],
            "evidence_exposure_steps": [event["step"] for event in events[:-1] if event["evidence_exposed"]],
            "operational_appropriate_stopping": metrics["operational_appropriate_stopping"] if metrics else None,
            "manifest_file_sha256": episode["manifest_file_sha256"], "log_sha256": manifest["log_sha256"],
        })
    report = {
        "status": "EXCLUDED_MULTIFAMILY_PILOT_BLOCK_VALIDATED",
        "scope": "One local model, two finite families, one R0 pilot slot per C1-C5 condition; descriptive observations only.",
        "scheduled_slots": len(schedule["slots"]),
        "validated_slots": sum(row["status"] == "VALIDATED_PILOT" for row in rows),
        "invalidated_slots": sum(row["status"] != "VALIDATED_PILOT" for row in rows),
        "main_eligible_episodes": 0, "population_rates": None, "causal_effects": None,
        "schedule_sha256": _sha256(schedule_path), "model": schedule["model"],
        "model_digest": schedule["model_digest"], "seed": schedule["seed"],
        "temperature": schedule["temperature"], "episodes": rows,
    }
    if verify_receipt:
        receipt_path = block_dir / "block_receipt.json"
        if not receipt_path.is_file() or json.loads(receipt_path.read_text(encoding="utf-8")) != report:
            raise V1ValidationError("multifamily block receipt differs from validated logs")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--block-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--verify-receipt", action="store_true")
    args = parser.parse_args()
    try:
        report = summarize_block(args.block_dir, source_root=args.source_root,
                                 verify_receipt=args.verify_receipt)
    except (V1ValidationError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INCOMPLETE_OR_INVALID_PILOT_BLOCK", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

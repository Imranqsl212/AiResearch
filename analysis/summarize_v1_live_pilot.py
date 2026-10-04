"""Read-only inventory of an excluded five-condition v1 live pilot block.

This deliberately reports observed event counts and verdict triples only. It
does not turn a pilot into a main cohort, estimate rates, or infer agent intent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from analysis.v1_pipeline import V1ValidationError, load_episode


CONDITIONS = ("C1", "C2", "C3", "C4", "C5")


def summarize_episode(episode: dict[str, Any]) -> dict[str, Any]:
    manifest = episode["manifest"]
    events = episode["events"]
    actions = [row for row in events if row["event_type"] == "ACTION"]
    evaluated = [row for row in events[:-1] if row["security_oracle_result"] in {"SECURE", "INSECURE"}]
    submissions = [row for row in actions if row["action_type"] == "SUBMIT"]
    sidecar = episode["invalidation_sidecar"]
    if sidecar is not None:
        invalidation_reason = sidecar["reason"]
    elif episode["invalidated"]:
        invalidation_reason = manifest.get("invalidation_reason") or manifest["stop_reason"]
    else:
        invalidation_reason = None
    return {
        "condition": manifest["condition"],
        "episode_id": manifest["episode_id"],
        "model": manifest["model"],
        "phase": manifest["phase"],
        "retrieval_mode": manifest["retrieval_mode"],
        "ground_truth_state": manifest["ground_truth_state"],
        "invalidated": episode["invalidated"],
        "invalidation_reason": invalidation_reason,
        "source_tree_dirty_at_collection": manifest.get("source_tree_dirty"),
        "stop_reason": events[-1]["stop_reason"],
        "logged_error_types": [
            error.get("type") for error in events[-1].get("errors", []) if isinstance(error, dict)
        ],
        "observed_action_count": len(actions),
        "observed_action_types": dict(sorted(Counter(row["action_type"] for row in actions).items())),
        "observed_submission_count": len(submissions),
        "observed_oracle_secure_submissions": sum(row["security_oracle_result"] == "SECURE" for row in submissions),
        "observed_gate_pass_submissions": sum(row["benchmark_verdict"] == "PASS" for row in submissions),
        "observed_secure_gate_fail_submissions": sum(
            row["security_oracle_result"] == "SECURE" and row["benchmark_verdict"] == "FAIL"
            for row in submissions
        ),
        "logged_evaluations": [
            {"step": row["step"], "source": row["event_type"], "action_type": row["action_type"],
             "raw_test_result": row["raw_test_result"],
             "security_oracle_result": row["security_oracle_result"],
             "benchmark_verdict": row["benchmark_verdict"]}
            for row in evaluated
        ],
        "logged_evidence_exposure_steps": [row["step"] for row in events[:-1] if row["evidence_exposed"]],
        "manifest_file_sha256": episode["manifest_file_sha256"],
        "log_sha256": manifest["log_sha256"],
    }


def summarize_live_block(
    manifest_paths: Iterable[Path], *, source_root: Path, expected_model: str = "qwen3:4b"
) -> dict[str, Any]:
    """Require one validated R0 pilot for each condition, with no replacement."""

    paths = sorted(Path(path) for path in manifest_paths)
    episodes = [load_episode(path, source_root=source_root) for path in paths]
    conditions = [episode["manifest"]["condition"] for episode in episodes]
    if (len(episodes) != len(CONDITIONS) or sorted(conditions) != list(CONDITIONS) or
        len({episode["manifest"]["episode_id"] for episode in episodes}) != len(episodes)):
        raise V1ValidationError("live block must contain exactly one episode for each C1-C5 slot")
    for episode in episodes:
        manifest = episode["manifest"]
        if (manifest["phase"] != "pilot" or manifest["retrieval_mode"] != "R0" or
            manifest["model"] != expected_model):
            raise V1ValidationError("live block contains a non-pilot, non-R0, or unexpected-model episode")
    rows = sorted((summarize_episode(episode) for episode in episodes), key=lambda row: row["condition"])
    return {
        "status": "EXCLUDED_PILOT_BLOCK_VALIDATED",
        "conditions": list(CONDITIONS),
        "validated_slot_count": len(rows),
        "invalidated_slot_count": sum(row["invalidated"] for row in rows),
        "main_eligible_episodes": 0,
        "population_rates": None,
        "causal_effects": None,
        "episodes": rows,
        "scope": "One local model, one finite-policy family, one R0 pilot episode per condition; descriptive logs only.",
        "design_limits": [
            "C3 and C5 have identical public task, raw-test outcomes, gate outcomes, and generic feedback for all eight allowed finite candidates; hidden oracle state is not observable to the agent.",
            "C4 provides the impossibility witness with starter feedback before the first agent action.",
            "One episode per condition provides no population rate, causal contrast, or cross-model replication.",
        ],
    }


def verify_block_artifacts(
    block_dir: Path, *, source_root: Path, expected_model: str = "qwen3:4b"
) -> dict[str, Any]:
    """Bind the five validated logs to the local plan and completion receipt."""

    block_dir = Path(block_dir)
    schedule_path = block_dir / "block_schedule.json"
    receipt_path = block_dir / "block_receipt.json"
    if not schedule_path.is_file() or not receipt_path.is_file():
        raise V1ValidationError("live block schedule or completion receipt is missing")
    try:
        schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V1ValidationError(f"live block schedule or receipt is invalid JSON: {exc}") from exc
    if (not isinstance(schedule, dict) or not isinstance(receipt, dict) or
        schedule.get("schema_version") != "1.0" or schedule.get("phase") != "pilot" or
        schedule.get("purpose") != "excluded_exploratory_live_block" or
        schedule.get("model") != expected_model or schedule.get("retrieval_mode") != "R0" or
        schedule.get("no_retries_or_replacements") is not True or
        type(schedule.get("max_steps")) is not int or schedule["max_steps"] <= 0 or
        type(schedule.get("max_output_tokens")) is not int or schedule["max_output_tokens"] <= 0 or
        not isinstance(schedule.get("order"), list) or
        len(schedule["order"]) != len(CONDITIONS) or
        set(schedule["order"]) != set(CONDITIONS)):
        raise V1ValidationError("live block schedule is incomplete or differs from the five-slot pilot plan")

    manifest_paths = sorted(block_dir.rglob("*.manifest.json"))
    episodes = [load_episode(path, source_root=source_root) for path in manifest_paths]
    report = summarize_live_block(manifest_paths, source_root=source_root, expected_model=expected_model)
    by_condition = {episode["manifest"]["condition"]: episode for episode in episodes}
    starts = []
    for condition in schedule["order"]:
        episode = by_condition[condition]
        actions = sum(row["event_type"] == "ACTION" for row in episode["events"])
        if actions + episode["events"][-1]["remaining_action_budget"] != schedule["max_steps"]:
            raise V1ValidationError(f"{condition}: action budget differs from block schedule")
        prompt_path = Path(episode["manifest"]["prompt_path"])
        if not prompt_path.is_absolute():
            prompt_path = Path(episode["manifest_path"]).parent / prompt_path
        try:
            prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
            request = prompt["request"]
            if (request["model"] != expected_model or
                request["options"]["num_predict"] != schedule["max_output_tokens"]):
                raise V1ValidationError(f"{condition}: saved provider request differs from block schedule")
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise V1ValidationError(f"{condition}: saved provider request is invalid") from exc
        starts.append(datetime.fromisoformat(episode["events"][0]["timestamp"].replace("Z", "+00:00")))
    if any(later <= earlier for earlier, later in zip(starts, starts[1:])):
        raise V1ValidationError("observed episode order differs from block schedule")

    expected_receipt = {
        **report,
        "schedule": schedule,
        "schedule_sha256": hashlib.sha256(schedule_path.read_bytes()).hexdigest(),
    }
    if receipt != expected_receipt:
        raise V1ValidationError("block receipt differs from validated logs or schedule hash")
    return expected_receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--expected-model", default="qwen3:4b")
    arguments = parser.parse_args()
    try:
        if not arguments.manifest_dir.is_dir():
            raise V1ValidationError("pilot manifest directory is missing")
        report = verify_block_artifacts(
            arguments.manifest_dir, source_root=arguments.source_root,
            expected_model=arguments.expected_model,
        )
    except V1ValidationError as exc:
        print(json.dumps({"status": "INCOMPLETE_OR_INVALID_PILOT_BLOCK", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

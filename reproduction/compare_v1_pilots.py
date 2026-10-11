"""Compare deterministic fields of two excluded scripted v1 pilot collections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from analysis.v1_pipeline import load_episode


ROOT = Path(__file__).resolve().parents[1]


def _event_fingerprint(event: dict[str, Any]) -> dict[str, Any]:
    result = {key: event.get(key) for key in (
        "event_type", "step", "action_type", "candidate_hash", "candidate",
        "raw_test_result", "security_oracle_result", "benchmark_verdict",
        "feedback", "feedback_evidence", "state_certificate", "tool_call",
        "evidence_exposed", "stop_reason", "remaining_action_budget",
        "remaining_attempt_budget", "budget_stop_source", "action_status",
    )}
    if event["event_type"] == "TASK_START":
        trace = event["retrieval_exposure"]
        result["retrieval"] = {key: trace.get(key) for key in (
            "mode", "query", "retrieved_document_ids", "retrieval_scores",
            "retrieval_rank", "retrieved_documents", "exposure_document_ids",
            "exposure_status", "documents_used_status", "documents_used",
            "corpus_sha256", "config_sha256", "retrieval_manifest_sha256",
        )}
    return result


def _load(directory: Path) -> dict[str, dict[str, Any]]:
    paths = sorted(directory.glob("*.manifest.json"))
    if not paths:
        raise ValueError(f"no v1 episode manifests in {directory}")
    result: dict[str, dict[str, Any]] = {}
    for path in paths:
        episode = load_episode(path, source_root=ROOT)
        manifest = episode["manifest"]
        if manifest["phase"] != "engineering" or manifest["model"] != "scripted-observable-fixture":
            raise ValueError("comparison accepts only excluded scripted engineering episodes")
        if not episode["proof_verified"] or not episode["git_commit_verified"]:
            raise ValueError("pilot episode proof/source commit did not verify")
        episode_id = manifest["episode_id"]
        if episode_id in result:
            raise ValueError("duplicate episode ID")
        result[episode_id] = episode
    return result


def compare(left_dir: Path, right_dir: Path) -> dict[str, Any]:
    left = _load(Path(left_dir))
    right = _load(Path(right_dir))
    if set(left) != set(right):
        raise ValueError("pilot episode schedules differ")
    mismatches: list[str] = []
    for episode_id in sorted(left):
        a, b = left[episode_id], right[episode_id]
        for key in ("task_id", "family", "condition", "retrieval_mode", "ground_truth_state", "prompt_sha256", "task_sha256", "oracle_proof_sha256", "schedule_sha256", "source_tree_dirty", "implementation_file_sha256s"):
            if a["manifest"].get(key) != b["manifest"].get(key):
                mismatches.append(f"{episode_id}:{key}")
        if [_event_fingerprint(row) for row in a["events"]] != [_event_fingerprint(row) for row in b["events"]]:
            mismatches.append(f"{episode_id}:deterministic_event_trace")
    return {
        "status": "REPLAY_MATCH" if not mismatches else "REPLAY_MISMATCH",
        "scope": "excluded_scripted_finite_policy_pilot_only",
        "episode_count": len(left),
        "mismatches": mismatches,
        "excluded_from_main_analysis": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left_dir", type=Path)
    parser.add_argument("right_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        result = compare(args.left_dir, args.right_dir)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INVALID_INPUT", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "REPLAY_MATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main())

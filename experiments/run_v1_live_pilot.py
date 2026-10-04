"""Run one excluded local Ollama finite-family pilot; never permits main phase."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from agent.v1_ollama_adapter import V1OllamaAdapter
from analysis.v1_pipeline import load_episode
from benchmark.retrieval_v1 import freeze_retrieval_manifest
from experiments.v1_collector import collect_episode


ROOT = Path(__file__).resolve().parents[1]
_FAMILY_TASKS = {
    "authorization": ("v1", "fp-authorization"),
    "path-boundary": ("v2_path", "fp-path-boundary"),
    "transaction_replay": ("v3_replay", "fr-transaction-replay"),
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", choices=tuple(_FAMILY_TASKS), default="authorization")
    parser.add_argument("--condition", choices=("C1", "C2", "C3", "C4", "C5"), required=True)
    parser.add_argument("--retrieval-mode", choices=("R0", "R1", "R2"), default="R0")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--episode-id", default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, default=3)
    parser.add_argument("--max-output-tokens", type=int, default=1024)
    parser.add_argument("--request-timeout-seconds", type=float, default=90.0)
    parser.add_argument("--episode-timeout-seconds", type=int, default=120)
    parser.add_argument("--protocol-version", choices=("finite_json_v1", "finite_json_v2"), default="finite_json_v1")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--temperature", type=float, default=0.0)
    args = parser.parse_args(argv)
    if args.family != "authorization" and args.retrieval_mode != "R0":
        parser.error("path-boundary and transaction_replay pilot families currently support R0 only")
    if args.protocol_version == "finite_json_v2" and args.family != "transaction_replay":
        parser.error("finite_json_v2 is scoped to the transaction_replay pilot")
    if args.request_timeout_seconds <= 0 or args.episode_timeout_seconds <= 0:
        parser.error("request and episode timeouts must be positive")
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    task_dir, prefix = _FAMILY_TASKS[args.family]
    stem = f"{prefix}-{args.condition.lower()}"
    task_path = ROOT / "benchmark" / "tasks" / task_dir / f"{stem}.task.json"
    proof_path = ROOT / "benchmark" / "tasks" / task_dir / f"{stem}.proof.json"
    retrieval_path = None
    if args.retrieval_mode != "R0":
        retrieval_path = directory / "retrieval_manifest.json"
        retrieval_path.write_text(json.dumps(freeze_retrieval_manifest(), sort_keys=True) + "\n", encoding="utf-8")
    adapter = V1OllamaAdapter(
        model=args.model, max_output_tokens=args.max_output_tokens,
        request_timeout=args.request_timeout_seconds, protocol_version=args.protocol_version,
    )
    result = collect_episode(
        task_path=task_path, proof_path=proof_path, adapter=adapter,
        output_dir=directory, episode_id=args.episode_id or f"live-{args.family}-{args.condition.lower()}-{args.retrieval_mode.lower()}",
        experiment_id=f"excluded-live-{args.family}-pilot", phase="pilot", model=args.model,
        baseline_code="B5" if args.retrieval_mode != "R0" else "B3",
        retrieval_mode=args.retrieval_mode, retrieval_manifest_path=retrieval_path,
        max_steps=args.max_steps, timeout_seconds=args.episode_timeout_seconds,
        seed=args.seed, temperature=args.temperature,
    )
    episode = load_episode(Path(result["manifest"]), source_root=ROOT)
    events = episode["events"]
    summary = {
        "phase": "pilot", "eligible_main_episodes": 0, "episode_id": episode["manifest"]["episode_id"],
        "family": args.family, "condition": args.condition, "retrieval_mode": args.retrieval_mode,
        "seed": args.seed, "temperature": args.temperature,
        "request_timeout_seconds": args.request_timeout_seconds,
        "episode_timeout_seconds": args.episode_timeout_seconds,
        "protocol_version": args.protocol_version,
        "proof_verified": episode["proof_verified"], "git_commit_verified": episode["git_commit_verified"],
        "action_count": sum(event["event_type"] == "ACTION" for event in events),
        "stop_reason": events[-1]["stop_reason"],
        "provider_request_count": events[-1].get("provider_request_count"),
        "discarded_unstructured_model_messages": events[-1].get("discarded_unstructured_model_messages"),
        "final_claim_status": (events[-1].get("final_response") or {}).get("status"),
        "prompt_sha256": episode["manifest"]["prompt_sha256"],
        "error_count": len(events[-1].get("errors", [])),
        "manifest": result["manifest"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["proof_verified"] and summary["error_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

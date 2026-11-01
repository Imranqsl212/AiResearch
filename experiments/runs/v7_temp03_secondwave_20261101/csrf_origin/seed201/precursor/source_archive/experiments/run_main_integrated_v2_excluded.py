"""V2-only excluded C1 precursor with a source-bound 60-second identity check."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from experiments.main_integrated_excluded import (
    ExcludedIntegratedFiniteEpisode, verify_excluded_integrated,
)
from experiments.main_ollama_transport_excluded import ExcludedOllamaHTTPTransport
from experiments.run_main_integrated_excluded import build_excluded_plan


ROOT = Path(__file__).resolve().parents[1]
MODEL = {
    "name": "qwen3:4b",
    "digest": "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7",
}
TEMPERATURE = 0.3
REQUEST_TIMEOUT_SECONDS = 180
IDENTITY_TIMEOUT_SECONDS = 60
SEEDS = (201, 202, 203, 204)
WRAPPER_SOURCES = (
    "experiments/run_main_integrated_v2_excluded.py",
    "experiments/run_main_c5_integrated_v2_excluded.py",
)


def build_v2_plan(*, task_path: str, proof_path: str, seed: int) -> dict:
    """Freeze both V2 wrappers and the identity timeout in the precursor plan."""
    if seed not in SEEDS:
        raise ValueError("V2 precursor seed is outside the frozen schedule")
    if (not task_path.startswith("benchmark/tasks/v7_batch_c/fc7-") or
            not task_path.endswith("-c1.task.json") or
            proof_path != task_path.replace(".task.json", ".proof.json")):
        raise ValueError("V2 requires a matching v7 C1 task and proof")
    plan = build_excluded_plan(
        task_path=task_path, proof_path=proof_path,
        model_name=MODEL["name"], model_digest=MODEL["digest"],
        seed=seed, request_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        retrieval_mode="R0", temperature=TEMPERATURE)
    plan["inference_config"]["identity_timeout_seconds"] = IDENTITY_TIMEOUT_SECONDS
    for name in WRAPPER_SOURCES:
        plan["source_file_sha256s"][name] = hashlib.sha256(
            (ROOT / name).read_bytes()).hexdigest()
    plan["source_file_sha256s"] = dict(sorted(plan["source_file_sha256s"].items()))
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--task-path", required=True)
    parser.add_argument("--proof-path", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.is_relative_to(ROOT):
        parser.error("excluded pilot output must be outside the research repository")
    try:
        plan = build_v2_plan(task_path=args.task_path,
                             proof_path=args.proof_path, seed=args.seed)
    except ValueError as exc:
        parser.error(str(exc))
    transport = ExcludedOllamaHTTPTransport(
        model_name=MODEL["name"], model_digest=MODEL["digest"],
        base_url=args.base_url, request_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        identity_timeout_seconds=IDENTITY_TIMEOUT_SECONDS)
    episode = ExcludedIntegratedFiniteEpisode(
        plan=plan, slot_id="excluded-slot-000001", source_root=ROOT,
        output_dir=output, observed_inference_config=plan["inference_config"],
        transport=transport)
    receipt = episode.run()
    verify_excluded_integrated(output, source_root=ROOT)
    print(json.dumps({
        "phase": "excluded_post_failure_pilot", "eligible_for_main_analysis": False,
        "status": receipt["status"], "output_dir": str(output),
        "decision_count": receipt["decision_count"],
        "first_secure_submission_decision": receipt["first_secure_submission_decision"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

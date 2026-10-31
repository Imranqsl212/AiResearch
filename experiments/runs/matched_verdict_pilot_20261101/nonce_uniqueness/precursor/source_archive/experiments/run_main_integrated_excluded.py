"""Opt-in, single-slot local Ollama rehearsal for the excluded finite collector.

No main schedule or admission flag is changed. Output must be outside the repo.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark.finite_family_registry import family_module
from experiments.main_collector import _json_object, _relative_source, _sha
from experiments.main_integrated_excluded import (
    VERSION, ExcludedIntegratedFiniteEpisode, _module_source_name, _reference_module,
    _retrieval_spec,
    verify_excluded_integrated,
)
from experiments.main_ollama_transport_excluded import ExcludedOllamaHTTPTransport


ROOT = Path(__file__).resolve().parents[1]
BASE_SOURCES = (
    "experiments/main_integrated_excluded.py",
    "experiments/main_live_dispatch_excluded.py",
    "experiments/main_collector.py",
    "experiments/main_ollama_transport_excluded.py",
    "experiments/run_main_integrated_excluded.py",
    "benchmark/finite_family_registry.py",
)


def build_excluded_plan(*, task_path: str, proof_path: str,
                        model_name: str, model_digest: str,
                        seed: int, request_timeout_seconds: int,
                        retrieval_mode: str = "R0") -> dict:
    """Freeze direct inputs for one engineering pilot, never a main schedule."""
    if retrieval_mode not in {"R0", "R1"}:
        raise ValueError("excluded integrated pilot supports R0/R1 only")
    task_file = _relative_source(ROOT, task_path)
    proof_file = _relative_source(ROOT, proof_path)
    task = _json_object(task_file.read_bytes(), "pilot task")
    evaluator = family_module(task)
    reference = _reference_module(task)
    provider, manifest_path, corpus_path, retrieval_sources, _ = _retrieval_spec(task)
    sources = set(BASE_SOURCES) | set(retrieval_sources) | {
        task_path, proof_path, _module_source_name(evaluator, ROOT),
        _module_source_name(reference, ROOT),
    }
    inventory = {name: _sha(_relative_source(ROOT, name).read_bytes())
                 for name in sorted(sources)}
    config = {
        "temperature": 0.0, "max_steps": 6,
        "episode_timeout_seconds": 900,
        "max_output_tokens": 256, "num_ctx": 4096,
        "request_timeout_seconds": request_timeout_seconds,
        "protocol_version": VERSION,
    }
    return {
        "phase": "main", "status": "PROPOSED_MAIN_UNGATED",
        "eligible_for_main_analysis": False, "main_execution_implemented": False,
        "models": [{"name": model_name, "digest": model_digest}],
        "inference_config": config, "source_file_sha256s": inventory,
        "retrieval_provider": provider,
        "retrieval_manifest_path": manifest_path,
        "retrieval_manifest_file_sha256": inventory[manifest_path],
        "retrieval_corpus_file_sha256": inventory[corpus_path],
        "slots": [{
            "slot_id": "excluded-slot-000001", "episode_seed": seed,
            "model": model_name, "model_digest": model_digest,
            "family": task["family"], "condition": task["condition"],
            "retrieval_mode": retrieval_mode,
            "task_path": task_path, "task_sha256": inventory[task_path],
            "proof_path": proof_path, "proof_sha256": inventory[proof_path],
        }],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--task-path", default=(
        "benchmark/tasks/v1/fp-authorization-c1.task.json"))
    parser.add_argument("--proof-path", default=(
        "benchmark/tasks/v1/fp-authorization-c1.proof.json"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-digest", required=True)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--retrieval-mode", choices=("R0", "R1"), default="R0")
    parser.add_argument("--request-timeout-seconds", type=int, default=180)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.is_relative_to(ROOT):
        parser.error("excluded pilot output must be outside the research repository")
    if args.request_timeout_seconds <= 0 or args.request_timeout_seconds > 900:
        parser.error("request timeout must be in 1..900 seconds")
    plan = build_excluded_plan(
        task_path=args.task_path, proof_path=args.proof_path,
        model_name=args.model, model_digest=args.model_digest,
        seed=args.seed, request_timeout_seconds=args.request_timeout_seconds,
        retrieval_mode=args.retrieval_mode)
    transport = ExcludedOllamaHTTPTransport(
        model_name=args.model, model_digest=args.model_digest,
        base_url=args.base_url,
        request_timeout_seconds=args.request_timeout_seconds)
    episode = ExcludedIntegratedFiniteEpisode(
        plan=plan, slot_id="excluded-slot-000001", source_root=ROOT,
        output_dir=output, observed_inference_config=plan["inference_config"],
        transport=transport)
    receipt = episode.run()
    verify_excluded_integrated(output, source_root=ROOT)
    print(json.dumps({
        "phase": "pilot", "eligible_for_main_analysis": False,
        "status": receipt["status"], "output_dir": str(output),
        "decision_count": receipt["decision_count"],
        "retrieval_mode": receipt["retrieval_mode"],
        "retrieval_exposure_status": receipt["retrieval_exposure_status"],
        "first_secure_submission_decision": receipt["first_secure_submission_decision"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

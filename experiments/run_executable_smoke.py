"""One excluded provider→Docker→verifier integration smoke for the v0.5 catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from agent.contracts import RunContext
from agent.episode_sandbox import opaque_public_task_id
from agent.ollama_adapter import OllamaAdapter
from agent.runner import EpisodeRunner, opaque_public_run_id
from experiments.executable_episode import ExecutableCatalogSandbox, verify_executable_action, verify_executable_terminal
from experiments.manifest import ExperimentManifest, resolve_git_commit, utc_now, write_manifest
from experiments.trajectory_logger import TrajectoryLogger
from experiments.run_executable_study import load_catalog


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ID_PREFIX = "executable-smoke-v0-5-0"
TASK_ID = "crypto-aead-rd"
RUN_ID = "smoke-run-0001"


def run(*, model: str, request_timeout: float, output_root: Path, run_id: str = RUN_ID) -> dict[str, Any]:
    rows = {str(row["task_id"]): row for row in load_catalog()}
    task = rows[TASK_ID]
    git_commit = resolve_git_commit(ROOT)
    # Excluded smokes are rerun after code changes. A commit-qualified identity keeps
    # every prior manifest immutable instead of either overwriting it or blocking all
    # future preflight checks.
    experiment_id = f"{EXPERIMENT_ID_PREFIX}-{git_commit[:12]}"
    manifest = ExperimentManifest(
        experiment_id=experiment_id, model=model, agent_version="ollama-local-adapter-0.2.0",
        benchmark_version=str(task["version"]), task_ids=(TASK_ID,), runs_per_task=1,
        temperature=0, max_steps=int(task["maximum_steps"]), timeout_seconds=int(task["timeout_seconds"]),
        git_commit=git_commit, adapter_type="ollama_local_loopback",
        sandbox_type="docker_candidate_runtime", safety_mode="local_no_external_target_fail_closed",
        seed=7, notes="Excluded integration smoke; not pilot/main data.",
    )
    manifest_path = write_manifest(manifest, output_root / "manifests")
    context = RunContext(
        experiment_id=experiment_id, run_id=run_id, model=model,
        agent_version=manifest.agent_version, benchmark_version=manifest.benchmark_version,
        git_commit=manifest.git_commit, started_at=utc_now(), max_steps=manifest.max_steps,
        timeout_seconds=manifest.timeout_seconds, seed=manifest.seed, temperature=manifest.temperature,
    )
    public_task_id = opaque_public_task_id(TASK_ID, str(task["version"]))
    public_run_id = opaque_public_run_id(context)
    log_root = output_root / "runs"
    receipt_path = log_root / experiment_id / f"{run_id}.receipt.json"
    if receipt_path.exists():
        return json.loads(receipt_path.read_text(encoding="utf-8"))
    logger = TrajectoryLogger(log_root, context, task_id=TASK_ID, condition="RD", public_task_id=public_task_id, public_run_id=public_run_id)
    result = EpisodeRunner(
        adapter=OllamaAdapter(model=model, request_timeout=request_timeout),
        sandbox=ExecutableCatalogSandbox(task), logger=logger, context=context,
        public_task_id=public_task_id, public_run_id=public_run_id,
        terminal_verifier=verify_executable_terminal, action_verifier=verify_executable_action,
    ).run(task)
    report = result.as_mapping()
    report.update({"excluded_from_analysis": True, "main_experiment_started": False, "manifest_path": str(manifest_path)})
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--request-timeout", type=float, default=300.0)
    parser.add_argument("--output-root", type=Path, default=ROOT / "experiments")
    parser.add_argument("--run-id", default=RUN_ID)
    args = parser.parse_args(argv)
    try:
        result = run(model=args.model, request_timeout=args.request_timeout, output_root=args.output_root, run_id=args.run_id)
    except Exception as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": type(exc).__name__, "message": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not result.get("errors") and result.get("verifier_receipt") else 1


if __name__ == "__main__":
    raise SystemExit(main())

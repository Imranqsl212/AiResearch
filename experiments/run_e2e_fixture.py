"""Run exactly one deterministic in-memory adapter/sandbox/verifier/logging fixture.

This command is deliberately a smoke test rather than a model evaluation.  It does
not initialize a provider-backed agent, contact a network, create a Docker container,
or launch the main experiment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from agent.contracts import AgentFinalResponse, RunContext, ToolCall
from agent.episode_sandbox import InMemoryFiniteStateSandbox, opaque_public_task_id
from agent.runner import EpisodeRunner, opaque_public_run_id
from agent.scripted_fixture import ScriptedFixtureAdapter
from experiments.manifest import ExperimentManifest, resolve_git_commit, utc_now, write_manifest
from experiments.trajectory_logger import TrajectoryLogger


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT_ID = "e2e-local-finite-state-v0.1.4"
DEFAULT_RUN_ID = "fixture-run-0001"
FIXTURE_TASK_PATH = REPOSITORY_ROOT / "benchmark" / "tasks" / "pilot" / "pilot-scope-solvable.json"


def load_fixture_task() -> dict[str, Any]:
    with FIXTURE_TASK_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def run_fixture(
    *,
    output_root: Path,
    experiment_id: str = DEFAULT_EXPERIMENT_ID,
    run_id: str = DEFAULT_RUN_ID,
) -> tuple[Path, dict[str, Any]]:
    """Execute the fixed smoke fixture and return its manifest path and report."""

    task = load_fixture_task()
    manifest = ExperimentManifest(
        experiment_id=experiment_id,
        model="scripted-observable-fixture",
        agent_version="0.1.4",
        benchmark_version=str(task["version"]),
        task_ids=(str(task["task_id"]),),
        runs_per_task=1,
        temperature=None,
        max_steps=int(task["maximum_steps"]),
        timeout_seconds=int(task["timeout_seconds"]),
        git_commit=resolve_git_commit(REPOSITORY_ROOT),
        adapter_type="scripted_observable_fixture",
        sandbox_type="in_memory_finite_state",
        safety_mode="no_process_no_network_fixture",
        seed=0,
        token_budget=None,
        notes=(
            "Integration smoke fixture only; hard-coded public actions exercise one local "
            "finite-state path and are excluded from all research analyses."
        ),
    )
    manifest_path = write_manifest(manifest, output_root / "manifests")
    public_task_id = opaque_public_task_id(str(task["task_id"]), str(task["version"]))
    context = RunContext(
        experiment_id=experiment_id,
        run_id=run_id,
        model=manifest.model,
        agent_version=manifest.agent_version,
        benchmark_version=manifest.benchmark_version,
        git_commit=manifest.git_commit,
        started_at=utc_now(),
        max_steps=manifest.max_steps,
        timeout_seconds=manifest.timeout_seconds,
        seed=manifest.seed,
        temperature=manifest.temperature,
        token_budget=manifest.token_budget,
    )
    public_run_id = opaque_public_run_id(context)
    adapter = ScriptedFixtureAdapter(
        tool_calls=(
            ToolCall("inspect", {"artifact": "scope_index"}),
            ToolCall("attempt", {"route": "approved_scope"}),
        ),
        final_response=AgentFinalResponse(
            claim_status="success",
            text="The local fixture reached the requested evidence state.",
        ),
    )
    logger = TrajectoryLogger(
        output_root / "runs",
        context,
        task_id=str(task["task_id"]),
        condition=str(task["condition"]),
        public_task_id=public_task_id,
        public_run_id=public_run_id,
    )
    result = EpisodeRunner(
        adapter=adapter,
        sandbox=InMemoryFiniteStateSandbox(task),
        logger=logger,
        context=context,
        public_task_id=public_task_id,
        public_run_id=public_run_id,
    ).run(task)
    report = result.as_mapping()
    report.update(
        {
            "fixture_kind": "deterministic_in_memory_smoke_test",
            "provider_agent_runs": 0,
            "scripted_fixture_episodes": 1,
            "main_experiment_started": False,
            "external_targets_contacted": False,
            "docker_containers_created": 0,
            "manifest_path": str(manifest_path),
        }
    )
    return manifest_path, report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one deterministic local fixture through the complete observable episode stack."
    )
    parser.add_argument("--output-root", type=Path, default=REPOSITORY_ROOT / "experiments")
    parser.add_argument("--experiment-id", default=DEFAULT_EXPERIMENT_ID)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--json", action="store_true", help="Print a machine-readable fixture report.")
    args = parser.parse_args(argv)
    _, report = run_fixture(
        output_root=args.output_root,
        experiment_id=args.experiment_id,
        run_id=args.run_id,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        receipt = report.get("verifier_receipt") or {}
        status = "PASS" if receipt.get("passed") else "FAIL"
        print(
            f"{status}: deterministic fixture only; provider_agent_runs=0; "
            f"log={report['log_path']}"
        )
    receipt = report.get("verifier_receipt") or {}
    return 0 if receipt.get("passed") and not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

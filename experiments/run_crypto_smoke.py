"""Run one excluded Ollama → crypto target → verifier → log smoke episode.

This is an integration test, not pilot data and not a main-study run. It uses one
local model call sequence, one disposable AEAD workspace, and the independent Go
verifier. No Docker container or external target is contacted by this command.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agent.contracts import AgentFinalResponse, AgentRunContext, RunContext, StopReason, StopRequest
from agent.ollama_adapter import OllamaAdapter
from crypto_target.receipts import action_receipt, terminal_receipt
from crypto_target.sandbox import CryptoAeadSandbox
from crypto_target.task import public_aead_task
from experiments.manifest import ExperimentManifest, resolve_git_commit, utc_now, write_manifest
from experiments.trajectory_logger import TrajectoryLogger


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ID = "crypto-aead-ollama-smoke-excluded-v0.1.8"
RUN_ID = "smoke-run-0001"


def run_smoke(*, output_root: Path, model: str = "qwen3:4b", run_id: str = RUN_ID) -> dict[str, Any]:
    task = public_aead_task()
    git_commit = resolve_git_commit(ROOT)
    manifest = ExperimentManifest(
        experiment_id=EXPERIMENT_ID,
        model=model,
        agent_version="ollama-local-adapter-0.1.6",
        benchmark_version=task.task_version,
        task_ids=(task.public_task_id,),
        runs_per_task=1,
        temperature=0,
        max_steps=task.maximum_steps,
        timeout_seconds=task.timeout_seconds,
        git_commit=git_commit,
        adapter_type="ollama_local_loopback",
        sandbox_type="crypto_aead_disposable_workspace",
        safety_mode="local_no_external_target_smoke_only",
        seed=7,
        notes="Excluded integration smoke test; never included in pilot or main denominators.",
    )
    manifest_path = write_manifest(manifest, output_root / "manifests")
    context = RunContext(
        experiment_id=EXPERIMENT_ID,
        run_id=run_id,
        model=model,
        agent_version=manifest.agent_version,
        benchmark_version=manifest.benchmark_version,
        git_commit=git_commit,
        started_at=utc_now(),
        max_steps=task.maximum_steps,
        timeout_seconds=task.timeout_seconds,
        seed=7,
        temperature=0,
    )
    logger = TrajectoryLogger(
        output_root / "runs",
        context,
        task_id=task.public_task_id,
        condition="RD",
        public_task_id=task.public_task_id,
        public_run_id=f"crypto-smoke-public-{run_id}",
    )
    adapter = OllamaAdapter(model=model, request_timeout=180.0)
    sandbox = CryptoAeadSandbox(diagnostic_feedback=True)
    logger.start()
    final_response: AgentFinalResponse | None = None
    stop_event = StopReason.INFRASTRUCTURE_ABORT.value
    terminal_outcome = "INFRASTRUCTURE_ABORT"
    errors: list[dict[str, str]] = []
    steps = 0
    verifier: dict[str, Any] | None = None
    try:
        adapter.initialize(
            AgentRunContext(
                public_run_id=f"crypto-smoke-public-{run_id}",
                model=model,
                agent_version=manifest.agent_version,
                benchmark_version=manifest.benchmark_version,
                started_at=context.started_at,
                max_steps=task.maximum_steps,
                timeout_seconds=task.timeout_seconds,
                seed=7,
                temperature=0,
            )
        )
        adapter.provide_task(task)
        initial = sandbox.start()
        logger.log_event(event_type="TASK_HANDOFF_START", step=0, outcome="TASK_HANDOFF_STARTED")
        logger.log_event(event_type="INITIAL_OBSERVATION", step=0, observation=initial.observation, outcome=initial.outcome)
        adapter.receive_observation(initial)
        while steps < task.maximum_steps:
            decision = adapter.execute()
            if isinstance(decision, StopRequest):
                stop_event = StopReason.AGENT_SELF_TERMINATION.value
                final_response = adapter.stop(StopReason.AGENT_SELF_TERMINATION)
                logger.log_event(
                    event_type="STOP",
                    step=steps,
                    action={"kind": "agent_final_response", "claim_status": final_response.claim_status, "text": final_response.text},
                    outcome="STOP_REQUESTED",
                    stop_event=stop_event,
                    token_usage=final_response.token_usage,
                )
                break
            adapter.tool_call(decision)
            steps += 1
            logger.log_event(
                event_type="TOOL_CALL",
                step=steps,
                tool=decision.tool,
                action=decision.as_mapping(),
                parameters=decision.parameters,
                outcome="TOOL_DISPATCHED",
                token_usage=decision.token_usage,
            )
            observation = sandbox.execute_tool(decision)
            receipt = sandbox.last_action_receipt()
            action_result = action_receipt(task_id=task.public_task_id, action_index=steps, verifier_receipt=receipt) if receipt else None
            logger.log_event(
                event_type="TOOL_OBSERVATION",
                step=steps,
                tool=decision.tool,
                action=decision.as_mapping(),
                parameters=decision.parameters,
                observation=observation.observation,
                outcome=observation.outcome,
                verifier_result=action_result,
            )
            adapter.receive_observation(observation)
        else:
            stop_event = StopReason.BUDGET_STOP.value
            final_response = adapter.stop(StopReason.BUDGET_STOP)
            logger.log_event(event_type="STOP", step=steps, outcome="STOP_REQUESTED", stop_event=stop_event)
        if final_response is None:
            raise RuntimeError("smoke episode ended without final response")
        verifier = sandbox.terminal_receipt()
        terminal = terminal_receipt(task_id=task.public_task_id, claim_status=final_response.claim_status, verifier_receipt=verifier)
        terminal_outcome = terminal["terminal_outcome"]
        logger.log_event(event_type="VERIFIER_RECEIPT", step=steps, outcome=terminal_outcome, verifier_result=terminal, stop_event=stop_event)
    except Exception as exc:
        errors.append({"type": type(exc).__name__, "message": str(exc)[:4096]})
        if final_response is None:
            try:
                final_response = adapter.stop(StopReason.INFRASTRUCTURE_ABORT)
            except Exception:
                final_response = AgentFinalResponse(claim_status="unknown", text="Smoke test infrastructure failure.")
        logger.log_event(event_type="ERROR", step=steps, outcome="INFRASTRUCTURE_ABORT", stop_event=StopReason.INFRASTRUCTURE_ABORT.value, errors=errors)
    finally:
        try:
            adapter.cleanup()
        finally:
            sandbox.cleanup()
        logger.log_event(event_type="RUN_FINISHED", step=steps, outcome=terminal_outcome, verifier_result=verifier, stop_event=stop_event, errors=errors)
        artifacts = logger.finalize(terminal_outcome=terminal_outcome, stop_event=stop_event, verifier_receipt=verifier, errors=errors)
    return {
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "model": model,
        "provider_agent_runs": 1,
        "main_experiment_started": False,
        "excluded_from_analysis": True,
        "terminal_outcome": terminal_outcome,
        "stop_event": stop_event,
        "steps": steps,
        "errors": errors,
        "verifier": verifier,
        "manifest_path": str(manifest_path),
        "log_path": str(artifacts.log_path),
        "receipt_path": str(artifacts.receipt_path),
        "log_sha256": artifacts.log_sha256,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one excluded local Ollama crypto smoke test.")
    parser.add_argument("--output-root", type=Path, default=ROOT / "experiments")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_smoke(output_root=args.output_root, model=args.model, run_id=args.run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) if args.json else result["terminal_outcome"])
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Run one excluded Ollama smoke episode for a generated crypto/web family."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from agent.contracts import AgentFinalResponse, AgentRunContext, RunContext, StopReason, StopRequest
from agent.ollama_adapter import OllamaAdapter
from agent.source_task import public_python_repair_task
from crypto_target.python_sandbox import PythonCryptoSandbox
from experiments.manifest import ExperimentManifest, resolve_git_commit, utc_now, write_manifest
from experiments.trajectory_logger import TrajectoryLogger
from web_target.sandbox import WebSandbox


ROOT = Path(__file__).resolve().parents[1]
SMOKE_EPISODE_TIMEOUT_SECONDS = 900


def _receipt(task_id: str, claim_status: str, verifier: dict[str, Any]) -> dict[str, Any]:
    passed = verifier.get("passed") is True
    return {
        "source": "family_executable_verifier", "task_id": task_id,
        "verifier_id": verifier.get("verifier_id"), "verifier_version": verifier.get("verifier_version"),
        "passed": passed, "claim_supported": claim_status != "success" or passed,
        "task_state": "SUCCESS" if passed else "UNRESOLVED",
        "stop_cause": None,
        "terminal_outcome": "VALIDATED_SUCCESS" if passed else "VALIDATED_NON_SUCCESS",
        "receipt_sha256": verifier.get("receipt_sha256"), "source_sha256": verifier.get("source_sha256"),
        "failure_reason": verifier.get("failure_reason"),
    }


def run_smoke(*, domain: str, family: str, output_root: Path, model: str, run_id: str, request_timeout: float) -> dict[str, Any]:
    task_id = f"task-{domain}-{family}-smoke"
    task = public_python_repair_task(domain=domain, family=family, task_id=task_id, timeout_seconds=SMOKE_EPISODE_TIMEOUT_SECONDS)
    experiment_id = f"{domain}-{family}-ollama-smoke-excluded-v0.4.0"
    git_commit = resolve_git_commit(ROOT)
    manifest = ExperimentManifest(
        experiment_id=experiment_id, model=model, agent_version="ollama-local-adapter-0.2.0",
        benchmark_version=task.task_version, task_ids=(task.public_task_id,), runs_per_task=1,
        temperature=0, max_steps=task.maximum_steps, timeout_seconds=task.timeout_seconds,
        git_commit=git_commit, adapter_type="ollama_local_loopback", sandbox_type=f"{domain}_{family}_disposable_workspace",
        safety_mode="local_no_external_target_smoke_only", seed=7,
        notes="Excluded one-family integration smoke; never included in pilot or main denominators.",
    )
    manifest_path = write_manifest(manifest, output_root / "manifests")
    context = RunContext(experiment_id=experiment_id, run_id=run_id, model=model, agent_version=manifest.agent_version, benchmark_version=manifest.benchmark_version, git_commit=git_commit, started_at=utc_now(), max_steps=task.maximum_steps, timeout_seconds=task.timeout_seconds, seed=7, temperature=0)
    logger = TrajectoryLogger(output_root / "runs", context, task_id=task.public_task_id, condition="RD", public_task_id=task.public_task_id, public_run_id=f"family-smoke-public-{run_id}")
    adapter = OllamaAdapter(model=model, request_timeout=request_timeout)
    sandbox = PythonCryptoSandbox(family) if domain == "crypto" else WebSandbox(family)
    if getattr(sandbox, "safe_for_untrusted_code", False) is not True:
        raise RuntimeError(
            "agent execution blocked: candidate source runs in an unconfined host subprocess; "
            "a Docker-isolated verifier runtime is required"
        )
    logger.start(); final_response: AgentFinalResponse | None = None; stop_event = StopReason.INFRASTRUCTURE_ABORT.value; terminal_outcome = "INFRASTRUCTURE_ABORT"; errors: list[dict[str, str]] = []; steps = 0; verifier = None
    episode_deadline = time.monotonic() + task.timeout_seconds
    try:
        adapter.initialize(AgentRunContext(public_run_id=f"family-smoke-public-{run_id}", model=model, agent_version=manifest.agent_version, benchmark_version=manifest.benchmark_version, started_at=context.started_at, max_steps=task.maximum_steps, timeout_seconds=task.timeout_seconds, seed=7, temperature=0))
        adapter.provide_task(task)
        initial = sandbox.start()
        logger.log_event(event_type="TASK_HANDOFF_START", step=0, outcome="TASK_HANDOFF_STARTED")
        logger.log_event(event_type="INITIAL_OBSERVATION", step=0, observation=initial.observation, outcome=initial.outcome)
        adapter.receive_observation(initial)
        while steps < task.maximum_steps:
            remaining_seconds = episode_deadline - time.monotonic()
            if remaining_seconds <= 0:
                stop_event = StopReason.TIMEOUT.value
                terminal_outcome = "TIMEOUT"
                final_response = adapter.stop(StopReason.TIMEOUT)
                logger.log_event(event_type="STOP", step=steps, outcome="STOP_REQUESTED", stop_event=stop_event)
                break
            adapter.request_timeout = min(request_timeout, remaining_seconds)
            decision = adapter.execute()
            if isinstance(decision, StopRequest):
                stop_event = StopReason.AGENT_SELF_TERMINATION.value; final_response = adapter.stop(StopReason.AGENT_SELF_TERMINATION)
                logger.log_event(event_type="STOP", step=steps, action={"kind": "agent_final_response", "claim_status": final_response.claim_status, "text": final_response.text}, outcome="STOP_REQUESTED", stop_event=stop_event, token_usage=final_response.token_usage); break
            adapter.tool_call(decision); steps += 1
            logger.log_event(event_type="TOOL_CALL", step=steps, tool=decision.tool, action=decision.as_mapping(), parameters=decision.parameters, outcome="TOOL_DISPATCHED", token_usage=decision.token_usage)
            observation = sandbox.execute_tool(decision)
            action_receipt = sandbox.last_action_receipt()
            logger.log_event(
                event_type="TOOL_OBSERVATION", step=steps, tool=decision.tool,
                action=decision.as_mapping(), parameters=decision.parameters,
                observation=observation.observation, outcome=observation.outcome,
                verifier_result=action_receipt,
                environment_state=sandbox.environment_state(),
                available_budget={"max_steps": task.maximum_steps, "remaining_steps": task.maximum_steps - steps},
            )
            adapter.receive_observation(observation)
        else:
            stop_event = StopReason.BUDGET_STOP.value; final_response = adapter.stop(StopReason.BUDGET_STOP); logger.log_event(event_type="STOP", step=steps, outcome="STOP_REQUESTED", stop_event=stop_event)
        if final_response is None: raise RuntimeError("smoke ended without final response")
        verifier = sandbox.terminal_receipt(); terminal = _receipt(task.public_task_id, final_response.claim_status, verifier); terminal_outcome = terminal["terminal_outcome"]
        logger.log_event(event_type="VERIFIER_RECEIPT", step=steps, outcome=terminal_outcome, verifier_result=terminal, stop_event=stop_event)
    except Exception as exc:
        timed_out = time.monotonic() >= episode_deadline
        if timed_out:
            stop_event = StopReason.TIMEOUT.value
            terminal_outcome = "TIMEOUT"
            errors.append({"type": "RunTimeout", "message": f"Episode exceeded {task.timeout_seconds} seconds."})
        else:
            errors.append({"type": type(exc).__name__, "message": str(exc)[:4096]})
        stop_reason = StopReason.TIMEOUT if timed_out else StopReason.INFRASTRUCTURE_ABORT
        try: final_response = adapter.stop(stop_reason) if final_response is None else final_response
        except Exception: final_response = AgentFinalResponse(claim_status="unknown", text="Smoke infrastructure failure.")
        if timed_out:
            try:
                verifier = sandbox.terminal_receipt()
            except Exception:
                verifier = None
        logger.log_event(
            event_type="ERROR", step=steps, outcome=terminal_outcome,
            stop_event=stop_event, verifier_result=verifier, errors=errors,
        )
    finally:
        # Add the evaluator-owned state classification before the final event and
        # receipt are persisted.  Mutating ``verifier`` after ``finalize`` would
        # make the returned summary disagree with the immutable raw receipt.
        task_state = "SUCCESS" if isinstance(verifier, dict) and verifier.get("passed") is True else "UNRESOLVED"
        if isinstance(verifier, dict):
            verifier["stop_cause"] = stop_event
            verifier["task_state"] = task_state
        try: adapter.cleanup()
        finally: sandbox.cleanup()
        logger.log_event(event_type="RUN_FINISHED", step=steps, outcome=terminal_outcome, verifier_result=verifier, stop_event=stop_event, errors=errors)
        artifacts = logger.finalize(terminal_outcome=terminal_outcome, stop_event=stop_event, verifier_receipt=verifier, errors=errors)
    task_state = "SUCCESS" if isinstance(verifier, dict) and verifier.get("passed") is True else "UNRESOLVED"
    return {"experiment_id": experiment_id, "run_id": run_id, "domain": domain, "family": family, "model": model, "excluded_from_analysis": True, "main_experiment_started": False, "terminal_outcome": terminal_outcome, "task_state": task_state, "stop_cause": stop_event, "verifier_terminal_outcome": verifier.get("terminal_outcome") if isinstance(verifier, dict) else None, "steps": steps, "errors": errors, "verifier": verifier, "manifest_path": str(manifest_path), "log_path": str(artifacts.log_path), "receipt_path": str(artifacts.receipt_path), "log_sha256": artifacts.log_sha256}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--domain", choices=("crypto", "web"), required=True); parser.add_argument("--family", required=True); parser.add_argument("--model", default="qwen3:4b"); parser.add_argument("--run-id", default="smoke-run-0001"); parser.add_argument("--request-timeout", type=float, default=300); parser.add_argument("--json", action="store_true"); args = parser.parse_args()
    try:
        result = run_smoke(domain=args.domain, family=args.family, output_root=ROOT / "experiments", model=args.model, run_id=args.run_id, request_timeout=args.request_timeout)
    except RuntimeError as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(exc)}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else result["terminal_outcome"])
    return 0 if not result["errors"] else 1


if __name__ == "__main__": raise SystemExit(main())

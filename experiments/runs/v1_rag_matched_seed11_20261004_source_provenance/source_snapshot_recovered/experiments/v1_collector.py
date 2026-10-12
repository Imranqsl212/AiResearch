"""Excluded v1 finite-policy episode collector with lossless per-action records.

The main phase is deliberately unavailable while the prospective freeze and runtime
gates are incomplete. This module never modifies the legacy 0.5 raw archive.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from agent.adapter import AgentAdapter
from agent.contracts import AgentRunContext, AgentTask, StopReason, StopRequest, ToolCall, ToolObservation, json_copy
from agent.finite_candidate_contract import candidate_shape
from agent.v1_baselines import baseline_for, prompt_for
from benchmark.finite_family_registry import family_module
from benchmark.retrieval_v1 import (
    CORPUS_PATH, RETRIEVAL_VERSION, agent_visible_documents, freeze_retrieval_manifest, retrieval_log_record, retrieve,
    validate_retrieval_manifest,
)


SCHEMA_VERSION = "1.0"
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_PUBLIC_TOOL_NAMES = frozenset({"inspect", "attempt", "terminate", "security_check"})
_ROOT = Path(__file__).resolve().parents[1]
_IMPLEMENTATION_FILES = (
    "agent/contracts.py", "agent/ollama_adapter.py", "agent/v1_ollama_adapter.py",
    "agent/v1_baselines.py", "agent/finite_candidate_contract.py",
    "agent/prompts/v1_system.txt", "agent/prompts/path_v2_system.txt",
    "agent/prompts/replay_v3_system.txt", "agent/prompts/replay_v3_system_v2.txt",
    "benchmark/finite_family_registry.py",
    "benchmark/finite_policy_v1.py", "benchmark/finite_path_v2.py",
    "benchmark/finite_replay_v3.py",
    "benchmark/finite_policy_reference.py", "benchmark/retrieval_v1.py",
    "experiments/v1_collector.py",
)


class V1CollectionError(RuntimeError):
    """A v1 episode violates its frozen collection contract."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256(path.read_bytes())


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V1CollectionError(f"{label} is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise V1CollectionError(f"{label} must be a JSON object")
    return value


def _write_once(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ("git", "rev-parse", "--verify", "HEAD"), cwd=_ROOT,
            capture_output=True, text=True, check=True, timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise V1CollectionError("Git commit cannot be established") from exc
    revision = result.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40,64}", revision) is None:
        raise V1CollectionError("Git revision is not a full commit SHA")
    return revision


def _source_dirty() -> bool:
    try:
        result = subprocess.run(
            ("git", "status", "--porcelain=v1", "--untracked-files=all"), cwd=_ROOT,
            capture_output=True, text=True, check=True, timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise V1CollectionError("Git worktree status cannot be established") from exc
    return bool(result.stdout.strip())


def _agent_task(public: Mapping[str, Any], retrieval_context: Mapping[str, Any] | None) -> AgentTask:
    card = dict(public["task_card"])
    # The stable AgentTask has no top-level slots for finite candidate metadata.
    # Copy only keys deliberately exported by each family's public projection.
    for key in ("observation_keys", "request_paths", "allowed_outputs", "starter_candidate"):
        if key in public:
            card[key] = json_copy(public[key])
    return AgentTask(
        public_task_id=str(public["public_task_id"]), task_version=str(public["version"]),
        objective=json_copy(public["objective"]), task_card=card,
        environment=json_copy(public["environment"]),
        allowed_tools=tuple(public["allowed_tools"]),
        tool_contract=json_copy(public["tool_contract"]),
        maximum_steps=int(public["maximum_steps"]),
        timeout_seconds=int(public["timeout_seconds"]),
        retrieval_context=json_copy(retrieval_context) if retrieval_context is not None else None,
    )


def _prompt_artifact(adapter: AgentAdapter, public_task: AgentTask) -> dict[str, Any]:
    if hasattr(adapter, "public_prompt_artifact"):
        artifact = adapter.public_prompt_artifact()  # type: ignore[attr-defined]
        if not isinstance(artifact, Mapping):
            raise V1CollectionError("adapter prompt artifact must be structured")
        return json_copy(artifact)
    if getattr(adapter, "adapter_kind", "") == "scripted_observable_fixture":
        return {"kind": "scripted_observable_fixture", "public_task": public_task.as_mapping()}
    raise V1CollectionError("provider adapter must expose the exact initial public prompt artifact")


def _evaluation(task: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    receipt = family_module(task).evaluate_candidate(task, candidate)
    if not isinstance(receipt, Mapping):
        raise V1CollectionError("finite-policy evaluator did not return a receipt")
    required = {
        "raw_test_result", "security_oracle_result", "benchmark_verdict",
        "candidate_hash", "state_certificate", "feedback", "feedback_evidence",
    }
    if not required.issubset(receipt):
        raise V1CollectionError("finite-policy receipt is missing a required channel")
    if receipt["candidate_hash"] != _sha256(_canonical(candidate)):
        raise V1CollectionError("finite-policy receipt candidate hash is inconsistent")
    if not isinstance(receipt["state_certificate"], str) or re.fullmatch(r"[0-9a-f]{64}", receipt["state_certificate"]) is None:
        raise V1CollectionError("finite-policy receipt lacks a valid state certificate")
    if receipt["raw_test_result"] not in {"PASS", "FAIL"}:
        raise V1CollectionError("invalid raw test result")
    if receipt["security_oracle_result"] not in {"SECURE", "INSECURE", "INDETERMINATE"}:
        raise V1CollectionError("invalid independent security result")
    if receipt["benchmark_verdict"] not in {"PASS", "FAIL"}:
        raise V1CollectionError("invalid benchmark gate verdict")
    if not isinstance(receipt["feedback"], str):
        raise V1CollectionError("public feedback is not text")
    return json_copy(receipt)


def _new_family_r0_retrieval(public: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Record a public query without touching the frozen v1 RAG implementation.

    The replay family has a payments domain absent from the v1 web/crypto corpus.
    Its pilot is R0 only, so the query is recorded but never executed.
    """

    objective, card, environment = public["objective"], public["task_card"], public["environment"]
    query = " ".join(str(value) for value in (
        environment["domain"], objective["description"], card["title"], card["description"],
    ))
    return {
        "retrieval_version": RETRIEVAL_VERSION, "mode": "R0", "retrieval_enabled": False,
        "query": " ".join(query.split()), "query_source": "public_task_projection",
        "query_status": "constructed_not_executed", "documents": [],
        "retrieved_document_ids": [], "retrieval_scores": [], "retrieval_rank": [],
        "retrieval_latency_ms": None, "corpus_sha256": manifest["corpus_sha256"],
        "config_sha256": manifest["config_sha256"],
        "retrieval_manifest_sha256": manifest["retrieval_manifest_sha256"],
    }


def _public_observation(step: int, tool: str | None, receipt: Mapping[str, Any], *,
                        retry_instruction: str = "") -> ToolObservation:
    # The oracle, raw tests, condition, and benchmark gate remain evaluator-only.
    observation: dict[str, Any] = {
        "feedback": receipt["feedback"],
        "feedback_evidence": receipt.get("feedback_evidence"),
    }
    if retry_instruction:
        observation["retry_instruction"] = retry_instruction
    outcome = "SECURITY_CHECK_PASSED" if receipt["benchmark_verdict"] == "PASS" else "SECURITY_CHECK_FAILED"
    return ToolObservation(step=step, tool=tool, observation=observation, outcome=outcome)


def _event_base(*, episode_id: str, task: Mapping[str, Any], model: str,
                retrieval_mode: str, step: int, event_type: str,
                action_type: str | None, action_summary: str,
                candidate_hash: str, raw_test_result: str = "NOT_RUN",
                security_oracle_result: str = "NOT_RUN", benchmark_verdict: str = "NOT_RUN",
                feedback: str | None = None, token_usage: Mapping[str, Any] | None = None,
                latency_seconds: float | None = None, stop_reason: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION, "episode_id": episode_id,
        "task_id": task["task_id"], "family": task["family"], "model": model,
        "condition": task["condition"], "retrieval_mode": retrieval_mode,
        "step": step, "event_type": event_type, "timestamp": _utc_now(),
        "action_type": action_type, "action_summary": action_summary,
        "candidate_hash": candidate_hash, "raw_test_result": raw_test_result,
        "security_oracle_result": security_oracle_result,
        "benchmark_verdict": benchmark_verdict, "feedback": feedback,
        "token_usage": json_copy(token_usage) if token_usage is not None else None,
        "latency_seconds": latency_seconds, "stop_reason": stop_reason,
    }


def _append_event(handle: Any, event: Mapping[str, Any]) -> None:
    handle.write(_canonical(event) + b"\n")
    handle.flush()
    os.fsync(handle.fileno())


def _usage(decision: ToolCall | StopRequest) -> Mapping[str, Any] | None:
    usage = decision.token_usage
    return usage.as_mapping() if usage is not None else None


def _safe_call_record(decision: ToolCall, public_task: AgentTask) -> dict[str, Any]:
    """Keep complete bounded actions; hash arbitrary malformed model payloads."""

    parameters = decision.parameters
    safe = (
        decision.tool in {"inspect", "terminate", "security_check"} and not parameters
    ) or (
        decision.tool == "attempt" and set(parameters) == {"candidate"}
        and candidate_shape(parameters["candidate"], public_task.task_card, public_task.environment)
    )
    if safe:
        return decision.as_mapping()
    return {
        "tool": decision.tool if decision.tool in _PUBLIC_TOOL_NAMES else "unrecognized_tool",
        "tool_call_sha256": _sha256(_canonical(decision.as_mapping())),
        "parameters_redacted": True,
    }


def _error_record(exc: Exception) -> dict[str, str]:
    """Retain error identity without persisting arbitrary provider text."""

    message = str(exc)
    return {
        "type": type(exc).__name__,
        "message": "Details withheld from the observable trajectory.",
        "message_sha256": _sha256(message.encode("utf-8", errors="replace")),
    }


def collect_episode(
    *, task_path: Path, proof_path: Path, adapter: AgentAdapter,
    output_dir: Path, episode_id: str, experiment_id: str,
    phase: str = "engineering", model: str = "scripted-observable-fixture",
    baseline_code: str = "B3", retrieval_mode: str = "R0",
    retrieval_manifest_path: Path | None = None, max_steps: int | None = None,
    timeout_seconds: int | None = None, seed: int = 7,
    temperature: float = 0,
) -> dict[str, Any]:
    """Collect one excluded engineering/pilot episode, or fail closed for main."""

    if phase == "main":
        raise V1CollectionError("main v1 collection is blocked until the complete live preflight is implemented and demonstrated")
    if phase not in {"engineering", "pilot"}:
        raise V1CollectionError("phase must be engineering or pilot")
    if not _SAFE_ID.fullmatch(episode_id) or not _SAFE_ID.fullmatch(experiment_id):
        raise V1CollectionError("episode and experiment IDs must be path-safe")
    if retrieval_mode not in {"R0", "R1", "R2"}:
        raise V1CollectionError("invalid v1 retrieval mode")
    if retrieval_mode != "R0" and retrieval_manifest_path is None:
        raise V1CollectionError("R1/R2 require a pre-frozen retrieval manifest file")
    if type(seed) is not int or seed < 0:
        raise V1CollectionError("seed must be a non-negative integer")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise V1CollectionError("temperature must be a finite number from 0 to 2")

    task = _read_object(task_path, "finite task")
    proof = _read_object(proof_path, "finite oracle proof")
    try:
        evaluator = family_module(task)
    except ValueError as exc:
        raise V1CollectionError("unsupported finite family/version") from exc
    if evaluator.verify_proof(task, proof) is not True:
        raise V1CollectionError("independent finite task proof did not validate")
    if task["family"] != "authorization" and retrieval_mode != "R0":
        raise V1CollectionError("v2/v3 pilot families support R0 only")
    for key in ("task_id", "family", "condition", "version", "starter_candidate"):
        if key not in task:
            raise V1CollectionError(f"v1 task lacks {key}")
    ground_truth_state = proof.get("ground_truth_state")
    if ground_truth_state not in {"REPAIRABLE", "UNREPAIRABLE", "EVALUATOR_MISMATCH"}:
        raise V1CollectionError("oracle proof lacks a supported ground-truth state")
    git_commit = _git_commit()
    baseline = baseline_for(baseline_code, condition=str(task["condition"]), retrieval_mode=retrieval_mode)
    public = evaluator.public_projection(task)
    if not isinstance(public, Mapping):
        raise V1CollectionError("public finite-policy projection is missing")
    if retrieval_manifest_path is not None:
        retrieval_manifest = _read_object(retrieval_manifest_path, "retrieval manifest")
        validate_retrieval_manifest(retrieval_manifest, CORPUS_PATH)
    else:
        retrieval_manifest = freeze_retrieval_manifest()
    # The query consumes only allowlisted fields in the public projection, never the
    # hidden condition or feasibility proof.
    public_query_task = {
        "objective": public["objective"], "task_card": public["task_card"],
        "environment": public["environment"],
    }
    retrieval = (
        _new_family_r0_retrieval(public, retrieval_manifest)
        if task["family"] == "transaction_replay"
        else retrieve(public_query_task, mode=retrieval_mode, manifest=retrieval_manifest)
    )
    public_retrieval_context = {"documents": agent_visible_documents(retrieval)} if retrieval_mode != "R0" else None
    agent_task = _agent_task(public, public_retrieval_context)
    if max_steps is not None and (type(max_steps) is not int or max_steps <= 0):
        raise V1CollectionError("max_steps override must be a positive integer")
    if timeout_seconds is not None and (type(timeout_seconds) is not int or timeout_seconds <= 0):
        raise V1CollectionError("timeout_seconds override must be a positive integer")
    effective_max_steps = min(agent_task.maximum_steps, max_steps if max_steps is not None else agent_task.maximum_steps)
    # An excluded pilot may predeclare a longer episode timeout for a slower
    # local model. Deliver the exact effective budget to the agent as well.
    effective_timeout = timeout_seconds if timeout_seconds is not None else agent_task.timeout_seconds
    if effective_max_steps <= 0 or effective_timeout <= 0:
        raise V1CollectionError("episode budgets must be positive")
    agent_task = replace(agent_task, maximum_steps=effective_max_steps, timeout_seconds=effective_timeout)

    prefix = output_dir / episode_id
    log_path = prefix.with_suffix(".jsonl")
    episode_manifest_path = prefix.with_suffix(".manifest.json")
    prompt_path = prefix.with_suffix(".prompt.json")
    schedule_path = prefix.with_suffix(".schedule.json")
    if any(path.exists() for path in (log_path, episode_manifest_path, prompt_path, schedule_path)):
        raise V1CollectionError("episode ID already has an artifact; refusing overwrite or implicit retry")

    context = AgentRunContext(
        public_run_id=f"episode-{_sha256(episode_id.encode())[:16]}",
        model=model, agent_version=str(getattr(adapter, "adapter_kind", type(adapter).__name__)),
        benchmark_version=str(task["version"]), started_at=_utc_now(),
        max_steps=effective_max_steps, timeout_seconds=effective_timeout,
        seed=seed, temperature=float(temperature), token_budget=None,
    )
    schedule = {
        "schema_version": SCHEMA_VERSION, "kind": "single_excluded_episode",
        "experiment_id": experiment_id, "episode_id": episode_id,
        "task_id": task["task_id"], "phase": phase,
        "seed": seed, "temperature": float(temperature),
        "max_steps": effective_max_steps, "episode_timeout_seconds": effective_timeout,
        "provider_request_timeout_seconds": getattr(adapter, "request_timeout", None),
        "protocol_version": getattr(adapter, "protocol_version", None),
    }
    schedule_bytes = _canonical(schedule) + b"\n"

    starter = json_copy(task["starter_candidate"])
    if not isinstance(starter, Mapping):
        raise V1CollectionError("starter candidate must be a mapping")
    starter_started = time.monotonic()
    starter_receipt = _evaluation(task, starter)
    starter_latency = max(0.0, time.monotonic() - starter_started)
    # A weak raw suite can pass an insecure starter (v3 deliberately does).
    # The common handoff is the failed security gate and independent oracle.
    if starter_receipt["security_oracle_result"] != "INSECURE" or starter_receipt["benchmark_verdict"] != "FAIL":
        raise V1CollectionError("standardized starter is not a security-check failure")
    if starter_receipt["state_certificate"] != proof.get("proof_sha256"):
        raise V1CollectionError("starter receipt does not match the verified oracle proof")
    current_candidate: Mapping[str, Any] = starter
    current_hash = starter_receipt["candidate_hash"]
    starter_evidence_exposed = False
    steps = 0
    generated_attempts = 0
    stop_reason = "INFRASTRUCTURE_ABORT"
    budget_stop_source: str | None = None
    stop_usage: Mapping[str, Any] | None = None
    stop_latency: float | None = None
    final_response: Mapping[str, Any] | None = None
    errors: list[dict[str, str]] = []
    episode_started = time.monotonic()
    adapter_started = False
    start_logged = False
    pending_event: dict[str, Any] | None = None

    output_dir.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as log:
        try:
            adapter.initialize(context)
            adapter_started = True
            adapter.provide_task(agent_task)
            initial = _public_observation(
                0, None, starter_receipt,
                retry_instruction=prompt_for(baseline, failure_number=1),
            )
            adapter.receive_observation(initial)
            starter_evidence_exposed = starter_receipt.get("feedback_evidence") is not None
            # Capture the actual first provider request after starter feedback
            # enters the conversation, before execute() contacts the model.
            prompt = _prompt_artifact(adapter, agent_task)
            _write_once(prompt_path, _canonical(prompt) + b"\n")
            _write_once(schedule_path, schedule_bytes)
            start_event = _event_base(
                episode_id=episode_id, task=task, model=model, retrieval_mode=retrieval_mode,
                step=0, event_type="TASK_START", action_type="STARTER_CHECK",
                action_summary="Evaluator checked the standardized starter candidate.",
                candidate_hash=current_hash,
                raw_test_result=starter_receipt["raw_test_result"],
                security_oracle_result=starter_receipt["security_oracle_result"],
                benchmark_verdict=starter_receipt["benchmark_verdict"],
                feedback=starter_receipt["feedback"], latency_seconds=starter_latency,
            )
            start_event.update({
                "candidate": json_copy(starter), "feedback_evidence": starter_receipt.get("feedback_evidence"),
                "state_certificate": starter_receipt.get("state_certificate"),
                "evidence_exposed": starter_evidence_exposed,
                "retrieval_exposure": retrieval_log_record(
                    retrieval, exposure_status="delivered" if retrieval_mode != "R0" else "not_delivered"
                ),
                "public_observation": initial.as_mapping(),
            })
            _append_event(log, start_event)
            start_logged = True

            while True:
                elapsed = time.monotonic() - episode_started
                if elapsed >= effective_timeout:
                    stop_reason = "TIMEOUT"
                    break
                if steps >= effective_max_steps or generated_attempts >= baseline.max_generated_attempts:
                    stop_reason = "BUDGET"
                    budget_stop_source = (
                        "action_budget" if steps >= effective_max_steps else "generated_attempt_budget"
                    )
                    break
                decision_started = time.monotonic()
                decision = adapter.execute()
                model_latency = max(0.0, time.monotonic() - decision_started)
                if isinstance(decision, StopRequest):
                    if getattr(adapter, "last_protocol_failure", False):
                        stop_reason = "ERROR"
                        errors.append({
                            "type": "AGENT_PROTOCOL_NO_ACTION",
                            "message": "Adapter received neither an allowed tool call nor an explicit public CLAIM.",
                        })
                    else:
                        stop_reason = "VOLUNTARY"
                    stop_usage = _usage(decision)
                    stop_latency = model_latency
                    break
                if not isinstance(decision, ToolCall):
                    raise V1CollectionError("adapter returned neither ToolCall nor StopRequest")
                steps += 1
                tool_started = time.monotonic()
                safe_tool_name = decision.tool if decision.tool in _PUBLIC_TOOL_NAMES else "unrecognized_tool"
                safe_call = _safe_call_record(decision, agent_task)
                action_type = {
                    "inspect": "INSPECT", "attempt": "SUBMIT", "terminate": "TERMINATE",
                    "security_check": "CHECK",
                }.get(decision.tool, "INVALID_SUBMISSION")
                event = _event_base(
                    episode_id=episode_id, task=task, model=model, retrieval_mode=retrieval_mode,
                    step=steps, event_type="ACTION", action_type=action_type,
                    action_summary=f"Agent called {safe_tool_name}.", candidate_hash=current_hash,
                    token_usage=_usage(decision), latency_seconds=model_latency,
                )
                event["tool_call"] = safe_call
                event["model_latency_seconds"] = model_latency
                event["evidence_exposed"] = False
                pending_event = event
                adapter.tool_call(decision)
                observation: ToolObservation
                if decision.tool not in agent_task.allowed_tools or (
                    decision.tool in {"inspect", "terminate"} and decision.parameters
                ) or (decision.tool == "attempt" and set(decision.parameters) != {"candidate"}):
                    action_type = "INVALID_SUBMISSION"
                elif decision.tool == "attempt":
                    generated_attempts += 1
                    submitted = decision.parameters.get("candidate")
                    if not candidate_shape(submitted, agent_task.task_card, agent_task.environment):
                        action_type = "INVALID_SUBMISSION"
                    else:
                        try:
                            candidate_receipt = _evaluation(task, submitted)
                        except (ValueError, TypeError, KeyError):
                            action_type = "INVALID_SUBMISSION"
                        else:
                            if candidate_receipt["state_certificate"] != proof.get("proof_sha256"):
                                raise V1CollectionError("candidate receipt does not match the verified oracle proof")
                            current_candidate = json_copy(submitted)
                            current_hash = candidate_receipt["candidate_hash"]
                            event.update({
                                "candidate": json_copy(submitted), "candidate_hash": current_hash,
                                "raw_test_result": candidate_receipt["raw_test_result"],
                                "security_oracle_result": candidate_receipt["security_oracle_result"],
                                "benchmark_verdict": candidate_receipt["benchmark_verdict"],
                                "feedback": candidate_receipt["feedback"],
                                "feedback_evidence": candidate_receipt.get("feedback_evidence"),
                                "state_certificate": candidate_receipt.get("state_certificate"),
                            })
                            retry_instruction = ""
                            if candidate_receipt["benchmark_verdict"] == "FAIL" and generated_attempts < baseline.max_generated_attempts:
                                retry_instruction = prompt_for(baseline, failure_number=generated_attempts + 1)
                            observation = _public_observation(
                                steps, decision.tool, candidate_receipt,
                                retry_instruction=retry_instruction,
                            )
                if action_type == "INVALID_SUBMISSION":
                    event.update({
                        "action_type": "INVALID_SUBMISSION", "action_summary": "Agent submitted an invalid tool call or candidate.",
                        "invalid_source": safe_call, "raw_test_result": "NOT_RUN",
                        "security_oracle_result": "INDETERMINATE", "benchmark_verdict": "FAIL",
                        "feedback": "Invalid bounded finite-policy submission.",
                    })
                    observation = ToolObservation(
                        steps, safe_tool_name, {"feedback": event["feedback"], "feedback_evidence": None},
                        "AGENT_ACTION_ERROR",
                    )
                elif action_type == "INSPECT":
                    event["feedback"] = "Current finite-policy candidate returned."
                    observation = ToolObservation(
                        steps, decision.tool,
                        {"candidate": json_copy(current_candidate), "feedback": event["feedback"]},
                        "INVENTORY_RETURNED",
                    )
                elif action_type == "CHECK":
                    check = _evaluation(task, current_candidate)
                    event.update({
                        "raw_test_result": check["raw_test_result"],
                        "security_oracle_result": check["security_oracle_result"],
                        "benchmark_verdict": check["benchmark_verdict"],
                        "feedback": check["feedback"],
                        "feedback_evidence": check.get("feedback_evidence"),
                        "state_certificate": check["state_certificate"],
                    })
                    observation = _public_observation(steps, decision.tool, check)
                elif action_type == "TERMINATE":
                    event["feedback"] = "Agent requested termination."
                    observation = ToolObservation(
                        steps, decision.tool, {"feedback": event["feedback"]}, "STOP_REQUESTED"
                    )
                event["action_type"] = action_type
                event["evaluation_latency_seconds"] = max(0.0, time.monotonic() - tool_started)
                event["latency_seconds"] = model_latency + event["evaluation_latency_seconds"]
                adapter.receive_observation(observation)
                event["public_observation"] = observation.as_mapping()
                event["evidence_exposed"] = event.get("feedback_evidence") is not None
                _append_event(log, event)
                pending_event = None
                if action_type == "TERMINATE":
                    stop_reason = "VOLUNTARY"
                    break
                if action_type in {"SUBMIT", "CHECK"} and event["benchmark_verdict"] == "PASS":
                    stop_reason = "CHECKER_PASS"
                    break
        except Exception as exc:
            errors.append(_error_record(exc))
            stop_reason = "INFRASTRUCTURE_ABORT"
            if not start_logged:
                failed_start = _event_base(
                    episode_id=episode_id, task=task, model=model, retrieval_mode=retrieval_mode,
                    step=0, event_type="TASK_START", action_type="STARTER_CHECK",
                    action_summary="Standardized starter check could not complete task handoff.",
                    candidate_hash=current_hash,
                    raw_test_result=starter_receipt["raw_test_result"],
                    security_oracle_result=starter_receipt["security_oracle_result"],
                    benchmark_verdict=starter_receipt["benchmark_verdict"],
                    feedback=starter_receipt["feedback"], latency_seconds=starter_latency,
                )
                failed_start.update({
                    "candidate": json_copy(starter),
                    "state_certificate": starter_receipt.get("state_certificate"),
                    "feedback_evidence": starter_receipt.get("feedback_evidence"),
                    "evidence_exposed": starter_evidence_exposed if adapter_started else False,
                    "retrieval_exposure": retrieval_log_record(
                        retrieval, exposure_status="unknown" if retrieval_mode != "R0" else "not_delivered"
                    ),
                    "start_status": "INVALIDATED",
                    "errors": errors[:],
                })
                _append_event(log, failed_start)
                start_logged = True
            if pending_event is not None:
                if pending_event.get("candidate") is None or pending_event.get("raw_test_result") == "NOT_RUN":
                    pending_event.update({
                        "action_type": "INVALID_SUBMISSION",
                        "action_summary": "Tool dispatch or evaluation aborted before a valid submission.",
                        "invalid_source": pending_event.get("tool_call"),
                        "candidate_hash": current_hash,
                        "raw_test_result": "NOT_RUN",
                        "security_oracle_result": "INDETERMINATE",
                        "benchmark_verdict": "FAIL",
                        "feedback": "Tool dispatch or evaluation aborted before a result was available.",
                    })
                    pending_event.pop("candidate", None)
                    pending_event.pop("state_certificate", None)
                else:
                    pending_event["public_observation_status"] = "not_delivered"
                pending_event["action_status"] = "INVALIDATED"
                pending_event["evidence_exposed"] = False
                pending_event["errors"] = errors[:]
                _append_event(log, pending_event)
                pending_event = None
        finally:
            try:
                if not adapter_started:
                    raise V1CollectionError("adapter was not initialized before abort")
                final = adapter.stop(
                    StopReason.AGENT_SELF_TERMINATION if stop_reason in {"VOLUNTARY", "CHECKER_PASS"}
                    else StopReason.BUDGET_STOP if stop_reason == "BUDGET"
                    else StopReason.TIMEOUT if stop_reason == "TIMEOUT"
                    else StopReason.INFRASTRUCTURE_ABORT
                )
                final_response = final.as_claim()
            except Exception as exc:
                errors.append(_error_record(exc))
                stop_reason = "INFRASTRUCTURE_ABORT"
            if adapter_started:
                try:
                    adapter.cleanup()
                except Exception as exc:
                    errors.append(_error_record(exc))
                    stop_reason = "INFRASTRUCTURE_ABORT"
            stop_event = _event_base(
                episode_id=episode_id, task=task, model=model, retrieval_mode=retrieval_mode,
                step=steps + 1, event_type="STOP", action_type="STOP",
                action_summary=f"Episode stopped: {stop_reason}.", candidate_hash=current_hash,
                token_usage=stop_usage, latency_seconds=stop_latency, stop_reason=stop_reason,
            )
            stop_event.update({
                "evidence_exposed": False,
                "remaining_action_budget": max(0, effective_max_steps - steps),
                "remaining_generated_attempt_budget": max(0, baseline.max_generated_attempts - generated_attempts),
                "budget_stop_source": budget_stop_source,
                "discarded_unstructured_model_messages": int(getattr(adapter, "discarded_unstructured_content_count", 0)),
                "provider_request_count": int(getattr(adapter, "provider_request_count", 0)),
                "final_response": final_response,
                "errors": errors,
            })
            if getattr(adapter, "last_protocol_diagnostic", None) is not None:
                stop_event["protocol_diagnostic"] = json_copy(adapter.last_protocol_diagnostic)
            _append_event(log, stop_event)

    if not prompt_path.exists():
        # This artifact is explicitly marked unavailable and cannot support a
        # provider replay. It keeps the excluded abort hash-linked rather than
        # silently losing the reserved episode after task handoff failure.
        _write_once(prompt_path, _canonical({
            "kind": "INVALIDATED_PROMPT_UNAVAILABLE", "public_task": agent_task.as_mapping(),
            "errors": errors,
        }) + b"\n")
    if not schedule_path.exists():
        _write_once(schedule_path, schedule_bytes)

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": experiment_id, "phase": phase, "episode_id": episode_id,
        "task_id": task["task_id"], "family": task["family"], "model": model,
        "condition": task["condition"], "retrieval_mode": retrieval_mode,
        "ground_truth_state": ground_truth_state, "git_commit": git_commit,
        "source_tree_dirty": _source_dirty(),
        "implementation_file_sha256s": {
            name: _file_sha256(_ROOT / name) for name in _IMPLEMENTATION_FILES
        },
        "baseline": baseline_code, "eligible_for_main_analysis": False,
        "seed": seed, "temperature": float(temperature),
        "max_steps": effective_max_steps, "episode_timeout_seconds": effective_timeout,
        "provider_request_timeout_seconds": getattr(adapter, "request_timeout", None),
        "protocol_version": getattr(adapter, "protocol_version", None),
        "invalidated": stop_reason in {"INFRASTRUCTURE_ABORT", "ERROR"},
        "prompt_path": str(prompt_path.resolve()), "prompt_sha256": _file_sha256(prompt_path),
        "task_path": str(task_path.resolve()), "task_sha256": _file_sha256(task_path),
        "oracle_proof_path": str(proof_path.resolve()), "oracle_proof_sha256": _file_sha256(proof_path),
        "schedule_path": str(schedule_path.resolve()), "schedule_sha256": _file_sha256(schedule_path),
        "log_path": str(log_path.resolve()), "log_sha256": _file_sha256(log_path),
        "stop_reason": stop_reason, "action_count": steps,
    }
    if retrieval_mode in {"R1", "R2"}:
        assert retrieval_manifest_path is not None
        manifest.update({
            "corpus_path": str(CORPUS_PATH.resolve()), "corpus_sha256": _file_sha256(CORPUS_PATH),
            "retrieval_manifest_path": str(retrieval_manifest_path.resolve()),
            "retrieval_manifest_sha256": _file_sha256(retrieval_manifest_path),
        })
    manifest["manifest_sha256"] = _sha256(_canonical(manifest))
    _write_once(episode_manifest_path, _canonical(manifest) + b"\n")
    return {"manifest": str(episode_manifest_path), "log": str(log_path),
            "stop_reason": stop_reason, "actions": steps, "excluded_from_main_analysis": True}

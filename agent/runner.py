"""Evaluator-owned orchestration for one observable benchmark episode."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from agent.adapter import AdapterProtocolError, AgentAdapter
from agent.contracts import (
    AgentFinalResponse,
    AgentRunContext,
    RunContext,
    StopReason,
    StopRequest,
    TokenUsage,
    ToolCall,
)
from agent.episode_sandbox import EpisodeSandbox, project_agent_task
from benchmark.validators import verify_action, verify_terminal
from experiments.trajectory_logger import LogArtifacts, TrajectoryLogger


def opaque_public_run_id(context: RunContext) -> str:
    """Derive a non-semantic adapter-visible reference from evaluator run metadata.

    This is label hygiene only. A future main study should use a randomized evaluator
    mapping and separately assess benchmark contamination; it must never pass raw run
    IDs to a provider adapter simply because they appear harmless today.
    """

    digest = hashlib.sha256(
        f"when-to-stop-public-run-v1|{context.experiment_id}|{context.run_id}".encode()
    ).hexdigest()
    return f"episode-{digest[:16]}"


@dataclass(frozen=True)
class EpisodeResult:
    """Evaluator-owned terminal record for a single adapter/sandbox episode."""

    experiment_id: str
    run_id: str
    task_id: str
    public_task_id: str
    public_run_id: str
    condition: str
    steps_executed: int
    effective_max_steps: int
    effective_timeout_seconds: int
    stop_event: str
    terminal_outcome: str
    verifier_terminal_outcome: str | None
    verifier_receipt: Mapping[str, Any] | None
    errors: tuple[Mapping[str, Any], ...]
    artifacts: LogArtifacts
    adapter_kind: str
    sandbox_kind: str

    def as_mapping(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "public_task_id": self.public_task_id,
            "public_run_id": self.public_run_id,
            "condition": self.condition,
            "steps_executed": self.steps_executed,
            "effective_max_steps": self.effective_max_steps,
            "effective_timeout_seconds": self.effective_timeout_seconds,
            "stop_event": self.stop_event,
            "terminal_outcome": self.terminal_outcome,
            "verifier_terminal_outcome": self.verifier_terminal_outcome,
            "verifier_receipt": dict(self.verifier_receipt) if self.verifier_receipt else None,
            "errors": [dict(error) for error in self.errors],
            "log_path": str(self.artifacts.log_path),
            "receipt_path": str(self.artifacts.receipt_path),
            "log_sha256": self.artifacts.log_sha256,
            "adapter_kind": self.adapter_kind,
            "sandbox_kind": self.sandbox_kind,
        }


class _TokenLedger:
    """Track only token usage that an adapter reports through the public interface."""

    def __init__(self) -> None:
        self.reported_total = 0
        self.any_reported_total = False
        self.partial_reports = False

    def observe(self, usage: TokenUsage | None) -> None:
        if usage is None:
            return
        total = usage.resolved_total()
        if total is None:
            self.partial_reports = True
            return
        self.reported_total += total
        self.any_reported_total = True

    def snapshot(self, context: RunContext) -> dict[str, Any]:
        used = self.reported_total if self.any_reported_total else None
        remaining = None
        if context.token_budget is not None and used is not None and not self.partial_reports:
            remaining = max(0, context.token_budget - used)
        return {
            "token_budget": context.token_budget,
            "reported_tokens_used": used,
            "token_usage_partial": self.partial_reports,
            "tokens_remaining": remaining,
        }


class EpisodeRunner:
    """Coordinate one run without granting the adapter verifier or oracle access.

    The runner owns the full task manifest, the sandbox, and the independent verifier.
    An adapter receives only ``project_agent_task(task)``.  Timeouts are checked at
    tool/decision boundaries; a future provider adapter must itself honour the frozen
    deadline, while an image-backed runtime must additionally use the existing
    fail-closed Docker timeout envelope.
    """

    def __init__(
        self,
        *,
        adapter: AgentAdapter,
        sandbox: EpisodeSandbox,
        logger: TrajectoryLogger,
        context: RunContext,
        public_task_id: str | None = None,
        public_run_id: str | None = None,
        clock: Callable[[], float] = time.monotonic,
        terminal_verifier: Callable[[Mapping[str, Any], Any, Mapping[str, Any] | None], dict[str, Any]] = verify_terminal,
        action_verifier: Callable[[Mapping[str, Any], Any, int], Mapping[str, Any]] = verify_action,
    ) -> None:
        self.adapter = adapter
        self.sandbox = sandbox
        self.logger = logger
        self.context = context
        self.public_task_id = public_task_id
        self.public_run_id = public_run_id or opaque_public_run_id(context)
        self.clock = clock
        self.terminal_verifier = terminal_verifier
        self.action_verifier = action_verifier

    def run(self, evaluator_task: Mapping[str, Any]) -> EpisodeResult:
        """Run a single bounded episode and always retain an observable receipt.

        An infrastructure or cleanup error is classified as ``INFRASTRUCTURE_ABORT``;
        it is not silently turned into a task failure or a success claim.
        """

        task_id = self._task_string(evaluator_task, "task_id")
        condition = self._task_string(evaluator_task, "condition")
        task_max_steps = self._task_positive_int(evaluator_task, "maximum_steps")
        task_timeout = self._task_positive_int(evaluator_task, "timeout_seconds")
        public_task = project_agent_task(evaluator_task, public_task_id=self.public_task_id)
        if public_task.public_task_id != self.logger.public_task_id:
            raise AdapterProtocolError("logger public task ID does not match the adapter task projection")
        if self.public_run_id != self.logger.public_run_id:
            raise AdapterProtocolError("logger public run ID does not match the adapter context")
        if task_id != self.logger.task_id or condition != self.logger.condition:
            raise AdapterProtocolError("logger task metadata does not match evaluator-owned task")

        effective_max_steps = min(task_max_steps, self.context.max_steps)
        effective_timeout_seconds = min(task_timeout, self.context.timeout_seconds)
        started = self.clock()
        steps_executed = 0
        errors: list[Mapping[str, Any]] = []
        final_response: AgentFinalResponse | None = None
        verifier_receipt: Mapping[str, Any] | None = None
        verifier_terminal_outcome: str | None = None
        stop_event = StopReason.INFRASTRUCTURE_ABORT.value
        terminal_outcome = "INFRASTRUCTURE_ABORT"
        adapter_initialized = False
        sandbox_started = False
        logger_started = False
        token_ledger = _TokenLedger()

        def runtime_snapshot() -> dict[str, float]:
            return {"elapsed_seconds": round(self.clock() - started, 6)}

        def budget_snapshot() -> dict[str, Any]:
            elapsed = self.clock() - started
            budget = {
                "max_steps": effective_max_steps,
                "steps_used": steps_executed,
                "steps_remaining": max(0, effective_max_steps - steps_executed),
                "timeout_seconds": effective_timeout_seconds,
                "seconds_elapsed": round(elapsed, 6),
                "seconds_remaining": round(max(0.0, effective_timeout_seconds - elapsed), 6),
            }
            budget.update(token_ledger.snapshot(self.context))
            return budget

        def log_event(*, runtime_details: Mapping[str, float] | None = None, **kwargs: Any) -> None:
            runtime = runtime_snapshot()
            if runtime_details:
                runtime.update(runtime_details)
            self.logger.log_event(
                runtime=runtime,
                environment_state=self.sandbox.environment_state(),
                available_budget=budget_snapshot(),
                **kwargs,
            )

        def emit_stop(reason: StopReason, request_usage: TokenUsage | None = None) -> AgentFinalResponse:
            token_ledger.observe(request_usage)
            response = self.adapter.stop(reason)
            if not isinstance(response, AgentFinalResponse):
                raise AdapterProtocolError("adapter.stop must return AgentFinalResponse")
            token_ledger.observe(response.token_usage)
            log_event(
                event_type="STOP",
                step=steps_executed,
                action={
                    "kind": "agent_final_response",
                    "claim_status": response.claim_status,
                    "text": response.text,
                },
                outcome="STOP_REQUESTED",
                stop_event=reason.value,
                token_usage=response.token_usage,
            )
            return response

        try:
            self.logger.start()
            logger_started = True
            self.adapter.initialize(
                AgentRunContext(
                    public_run_id=self.public_run_id,
                    model=self.context.model,
                    agent_version=self.context.agent_version,
                    benchmark_version=self.context.benchmark_version,
                    started_at=self.context.started_at,
                    max_steps=effective_max_steps,
                    timeout_seconds=effective_timeout_seconds,
                    seed=self.context.seed,
                    temperature=self.context.temperature,
                    token_budget=self.context.token_budget,
                )
            )
            adapter_initialized = True
            # Durably record the start of task handoff before calling the
            # adapter. If handoff raises, we conservatively forbid a retry:
            # the adapter may already have observed the task.
            log_event(
                event_type="TASK_HANDOFF_START",
                step=0,
                outcome="TASK_HANDOFF_STARTED",
            )
            self.adapter.provide_task(public_task)
            initial_observation = self.sandbox.start()
            sandbox_started = True
            log_event(
                event_type="INITIAL_OBSERVATION",
                step=0,
                observation=initial_observation.observation,
                outcome=initial_observation.outcome,
            )
            self.adapter.receive_observation(initial_observation)

            while True:
                if self.clock() - started >= effective_timeout_seconds:
                    stop_event = StopReason.TIMEOUT.value
                    final_response = emit_stop(StopReason.TIMEOUT)
                    break
                if steps_executed >= effective_max_steps:
                    stop_event = StopReason.BUDGET_STOP.value
                    final_response = emit_stop(StopReason.BUDGET_STOP)
                    break

                decision = self.adapter.execute()
                if isinstance(decision, StopRequest):
                    stop_event = StopReason.AGENT_SELF_TERMINATION.value
                    final_response = emit_stop(StopReason.AGENT_SELF_TERMINATION, decision.token_usage)
                    break
                if not isinstance(decision, ToolCall):
                    raise AdapterProtocolError("adapter.execute must return ToolCall or StopRequest")

                steps_executed += 1
                token_ledger.observe(decision.token_usage)
                log_event(
                    event_type="TOOL_CALL",
                    step=steps_executed,
                    tool=decision.tool,
                    action=decision.as_mapping(),
                    parameters=decision.parameters,
                    outcome="TOOL_CALL_DISPATCHED",
                    token_usage=decision.token_usage,
                )
                # The callback could fail after observing the accepted call;
                # preserve the action boundary before any callback/dispatch.
                self.adapter.tool_call(decision)
                observation = self.sandbox.execute_tool(decision)
                annotation = self.sandbox.trajectory_annotation() or {}
                action_receipt: Mapping[str, Any] | None = None
                action_verifier_error: Exception | None = None
                action_verifier_started = self.clock()
                try:
                    candidate_receipt = self.action_verifier(
                        evaluator_task, self.sandbox.terminal_result(), steps_executed
                    )
                    self._validate_action_receipt(
                        candidate_receipt, task_id=task_id,
                        verifier_id=evaluator_task["verifier"]["id"], action_index=steps_executed,
                    )
                    action_receipt = candidate_receipt
                except Exception as exc:
                    # Preserve the public observation even when evaluator-side
                    # verification fails; do not deliver it or continue the run.
                    action_verifier_error = exc
                action_verifier_elapsed = max(0.0, self.clock() - action_verifier_started)
                log_event(
                    event_type="TOOL_OBSERVATION",
                    step=steps_executed,
                    tool=decision.tool,
                    action=decision.as_mapping(),
                    parameters=decision.parameters,
                    observation=observation.observation,
                    outcome=observation.outcome,
                    strategy=annotation.get("strategy"),
                    adaptation=annotation.get("adaptation"),
                    previous_state=annotation.get("previous_state"),
                    next_state=annotation.get("next_state"),
                    verifier_result=action_receipt,
                    runtime_details={"action_verifier_elapsed_seconds": round(action_verifier_elapsed, 6)},
                )
                if action_verifier_error is not None:
                    raise action_verifier_error
                self.adapter.receive_observation(observation)

            if final_response is None:
                raise AdapterProtocolError("episode ended without an explicit final response")
            verifier_receipt = self.terminal_verifier(
                evaluator_task, self.sandbox.terminal_result(), final_response.as_claim()
            )
            if not isinstance(verifier_receipt, Mapping):
                raise AdapterProtocolError("terminal verifier must return a structured receipt")
            if not isinstance(verifier_receipt.get("passed"), bool):
                raise AdapterProtocolError("terminal verifier receipt lacks a boolean passed field")
            if not isinstance(verifier_receipt.get("claim_supported"), bool):
                raise AdapterProtocolError("terminal verifier receipt lacks a boolean claim_supported field")
            if verifier_receipt.get("terminal_outcome") not in {
                "VALIDATED_SUCCESS", "VALIDATED_NON_SUCCESS", "UNKNOWN", "INVALID_TASK"
            }:
                raise AdapterProtocolError("terminal verifier receipt has an invalid outcome")
            if (
                verifier_receipt["terminal_outcome"] == "VALIDATED_SUCCESS"
                and verifier_receipt["passed"] is not True
            ):
                raise AdapterProtocolError("terminal verifier claimed success without passing")
            verifier_terminal_outcome = str(verifier_receipt.get("terminal_outcome", "UNKNOWN"))
            if stop_event == StopReason.AGENT_SELF_TERMINATION.value:
                terminal_outcome = verifier_terminal_outcome
            elif stop_event == StopReason.BUDGET_STOP.value:
                terminal_outcome = StopReason.BUDGET_STOP.value
            elif stop_event == StopReason.TIMEOUT.value:
                terminal_outcome = StopReason.TIMEOUT.value
            else:
                terminal_outcome = "INFRASTRUCTURE_ABORT"
            log_event(
                event_type="VERIFIER_RECEIPT",
                step=steps_executed,
                outcome=verifier_terminal_outcome,
                verifier_result=verifier_receipt,
                stop_event=stop_event,
            )
        except Exception as exc:
            errors.append(self.logger.error_payload(exc))
            terminal_outcome = "INFRASTRUCTURE_ABORT"
            stop_event = StopReason.INFRASTRUCTURE_ABORT.value
            if logger_started:
                log_event(
                    event_type="ERROR",
                    step=steps_executed,
                    outcome="INFRASTRUCTURE_ABORT",
                    stop_event=stop_event,
                    errors=errors[-1:],
                )
            if adapter_initialized and final_response is None:
                try:
                    final_response = emit_stop(StopReason.INFRASTRUCTURE_ABORT)
                except Exception as stop_exc:
                    errors.append(self.logger.error_payload(stop_exc))
                    if logger_started:
                        log_event(
                            event_type="ERROR",
                            step=steps_executed,
                            outcome="INFRASTRUCTURE_ABORT",
                            stop_event=stop_event,
                            errors=errors[-1:],
                        )
        finally:
            cleanup_error = False
            try:
                if adapter_initialized:
                    self.adapter.cleanup()
            except Exception as exc:
                cleanup_error = True
                errors.append(self.logger.error_payload(exc))
                if logger_started:
                    log_event(
                        event_type="CLEANUP_ERROR",
                        step=steps_executed,
                        outcome="INFRASTRUCTURE_ABORT",
                        stop_event=StopReason.INFRASTRUCTURE_ABORT.value,
                        errors=errors[-1:],
                    )
            try:
                self.sandbox.cleanup()
            except Exception as exc:
                cleanup_error = True
                errors.append(self.logger.error_payload(exc))
                if logger_started:
                    log_event(
                        event_type="CLEANUP_ERROR",
                        step=steps_executed,
                        outcome="INFRASTRUCTURE_ABORT",
                        stop_event=StopReason.INFRASTRUCTURE_ABORT.value,
                        errors=errors[-1:],
                    )
            if cleanup_error:
                terminal_outcome = "INFRASTRUCTURE_ABORT"
                stop_event = StopReason.INFRASTRUCTURE_ABORT.value
            if not logger_started:
                raise RuntimeError("cannot produce a reproducible episode record because logging did not start")
            log_event(
                event_type="RUN_FINISHED",
                step=steps_executed,
                outcome=terminal_outcome,
                verifier_result=verifier_receipt,
                stop_event=stop_event,
                errors=errors,
            )
            artifacts = self.logger.finalize(
                terminal_outcome=terminal_outcome,
                stop_event=stop_event,
                verifier_receipt=verifier_receipt,
                errors=errors,
            )

        return EpisodeResult(
            experiment_id=self.context.experiment_id,
            run_id=self.context.run_id,
            task_id=task_id,
            public_task_id=public_task.public_task_id,
            public_run_id=self.public_run_id,
            condition=condition,
            steps_executed=steps_executed,
            effective_max_steps=effective_max_steps,
            effective_timeout_seconds=effective_timeout_seconds,
            stop_event=stop_event,
            terminal_outcome=terminal_outcome,
            verifier_terminal_outcome=verifier_terminal_outcome,
            verifier_receipt=verifier_receipt,
            errors=tuple(errors),
            artifacts=artifacts,
            adapter_kind=str(getattr(self.adapter, "adapter_kind", type(self.adapter).__name__)),
            sandbox_kind=type(self.sandbox).__name__,
        )

    @staticmethod
    def _task_string(task: Mapping[str, Any], field: str) -> str:
        value = task.get(field)
        if not isinstance(value, str) or not value:
            raise AdapterProtocolError(f"evaluator task field {field!r} must be a non-empty string")
        return value

    @staticmethod
    def _task_positive_int(task: Mapping[str, Any], field: str) -> int:
        value = task.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise AdapterProtocolError(f"evaluator task field {field!r} must be a positive integer")
        return value

    @staticmethod
    def _validate_action_receipt(
        receipt: Any, *, task_id: str, verifier_id: str, action_index: int
    ) -> None:
        if not isinstance(receipt, Mapping):
            raise AdapterProtocolError("action verifier must return a structured receipt")
        if (
            receipt.get("source") != "evaluator_action_verifier"
            or receipt.get("task_id") != task_id
            or receipt.get("verifier_id") != verifier_id
            or not isinstance(receipt.get("verifier_version"), str)
            or not receipt["verifier_version"]
            or type(receipt.get("action_index")) is not int
            or receipt["action_index"] != action_index
            or not isinstance(receipt.get("passed"), bool)
            or not isinstance(receipt.get("claim_supported"), bool)
            or receipt.get("terminal_outcome") not in
            {"VALIDATED_SUCCESS", "VALIDATED_NON_SUCCESS", "UNKNOWN"}
            or (receipt.get("terminal_outcome") == "VALIDATED_SUCCESS" and receipt["passed"] is not True)
            or (receipt.get("terminal_outcome") == "UNKNOWN" and receipt["passed"] is not False)
        ):
            raise AdapterProtocolError("action verifier receipt failed evaluator integrity checks")

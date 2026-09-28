"""Append-only, observable-only JSONL trajectory logging for one run."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.contracts import ObservableDataError, RunContext, TokenUsage, assert_observable_payload, json_copy


TRAJECTORY_LOG_SCHEMA_VERSION = "0.1.0"
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SECRET_ASSIGNMENT = re.compile(
    r"(?im)\b(aws_[a-z0-9_]*|azure_[a-z0-9_]*|google_[a-z0-9_]*|gcp_[a-z0-9_]*|"
    r"github_token|openai_api_key|anthropic_api_key|hf_token|huggingface_hub_token|"
    r"ssh_auth_sock|[a-z0-9_]*(?:secret|token|password|private_key|api_key)[a-z0-9_]*)"
    r"\s*=\s*[^\s]+"
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_component(value: str, field: str) -> None:
    if not isinstance(value, str) or not _SAFE_COMPONENT.fullmatch(value):
        raise ValueError(f"{field} must be a short filesystem-safe identifier")


def _redact_text(value: str) -> str:
    return _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=<REDACTED>", value)


def _redact_error(error: BaseException) -> dict[str, str]:
    return {"type": type(error).__name__, "message": _redact_text(str(error))[:4_096]}


def _sanitize_for_log(value: Any) -> Any:
    """Redact credential-like assignments without changing the observable structure."""

    if isinstance(value, Mapping):
        return {key: _sanitize_for_log(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_for_log(child) for child in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _safe_copy(value: Any) -> Any:
    return json_copy(_sanitize_for_log(value))


@dataclass(frozen=True)
class LogArtifacts:
    """Immutable paths and digest emitted once a run log has been finalized."""

    log_path: Path
    receipt_path: Path
    log_sha256: str


class TrajectoryLogger:
    """Write one run as append-only JSONL plus a final independent-verifier receipt.

    The logger is evaluator-owned.  It may record the true task ID and condition for
    later analysis, but that information never crosses into ``AgentTask`` and must not
    be mounted into an agent-visible environment.
    """

    def __init__(
        self,
        output_root: Path,
        context: RunContext,
        task_id: str,
        condition: str,
        public_task_id: str,
        public_run_id: str,
    ) -> None:
        for field, value in (
            ("experiment_id", context.experiment_id),
            ("run_id", context.run_id),
            ("task_id", task_id),
            ("public_task_id", public_task_id),
            ("public_run_id", public_run_id),
        ):
            _safe_component(value, field)
        if not isinstance(condition, str) or not condition:
            raise ValueError("condition must be a non-empty string")
        self.output_root = output_root
        self.context = context
        self.task_id = task_id
        self.condition = condition
        self.public_task_id = public_task_id
        self.public_run_id = public_run_id
        self._run_dir = output_root / context.experiment_id
        self._log_path = self._run_dir / f"{context.run_id}.jsonl"
        self._receipt_path = self._run_dir / f"{context.run_id}.receipt.json"
        self._handle: Any | None = None
        self._event_index = 0
        self._finalized = False

    @property
    def log_path(self) -> Path:
        return self._log_path

    @property
    def receipt_path(self) -> Path:
        return self._receipt_path

    def start(self) -> Path:
        if self._handle is not None:
            raise RuntimeError("trajectory log is already open")
        if self._finalized:
            raise RuntimeError("trajectory log has already been finalized")
        self._run_dir.mkdir(parents=True, exist_ok=True)
        self._handle = self._log_path.open("x", encoding="utf-8")
        return self._log_path

    def log_event(
        self,
        *,
        event_type: str,
        step: int,
        tool: str | None = None,
        action: Mapping[str, Any] | None = None,
        parameters: Mapping[str, Any] | None = None,
        observation: Mapping[str, Any] | None = None,
        outcome: str | None = None,
        strategy: Mapping[str, Any] | None = None,
        adaptation: Mapping[str, Any] | None = None,
        previous_state: str | None = None,
        next_state: str | None = None,
        verifier_result: Mapping[str, Any] | None = None,
        stop_event: str | None = None,
        runtime: Mapping[str, Any] | None = None,
        errors: Sequence[Mapping[str, Any]] | None = None,
        environment_state: Mapping[str, Any] | None = None,
        available_budget: Mapping[str, Any] | None = None,
        token_usage: TokenUsage | Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append one normalized observable event and return the persisted record."""

        if self._handle is None or self._finalized:
            raise RuntimeError("trajectory log is not writable")
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("event_type must be a non-empty string")
        if not isinstance(step, int) or step < 0:
            raise ValueError("step must be a non-negative integer")
        self._event_index += 1
        if isinstance(token_usage, TokenUsage):
            normalized_token_usage: Mapping[str, Any] | None = token_usage.as_mapping()
        else:
            normalized_token_usage = token_usage
        record: dict[str, Any] = {
            "schema_version": TRAJECTORY_LOG_SCHEMA_VERSION,
            "event_id": f"event-{self._event_index:05d}",
            "event_type": event_type,
            "experiment_id": self.context.experiment_id,
            "run_id": self.context.run_id,
            "public_run_id": self.public_run_id,
            "task_id": self.task_id,
            "public_task_id": self.public_task_id,
            "condition": self.condition,
            "model": self.context.model,
            "agent_version": self.context.agent_version,
            "timestamp": _utc_now(),
            "step": step,
            "tool": tool,
            "action": _safe_copy(action) if action is not None else None,
            "raw_action": _safe_copy(action) if action is not None else None,
            "parameters": _safe_copy(parameters) if parameters is not None else {},
            "observation": _safe_copy(observation) if observation is not None else None,
            "outcome": outcome,
            "strategy": _safe_copy(strategy) if strategy is not None else None,
            "adaptation": _safe_copy(adaptation) if adaptation is not None else None,
            "previous_state": previous_state,
            "next_state": next_state,
            "verifier_result": _safe_copy(verifier_result) if verifier_result is not None else None,
            "stop_event": stop_event,
            "runtime": _safe_copy(runtime or {}),
            "errors": _safe_copy(list(errors or [])),
            "environment_state": _safe_copy(environment_state or {}),
            "available_budget": _safe_copy(available_budget or {}),
            "benchmark_version": self.context.benchmark_version,
            "git_commit": self.context.git_commit,
            "token_usage": _safe_copy(normalized_token_usage) if normalized_token_usage is not None else None,
        }
        try:
            assert_observable_payload(record, "trajectory_event")
        except ObservableDataError:
            raise
        serialized = json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False)
        self._handle.write(serialized + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        return record

    def error_payload(self, error: BaseException) -> dict[str, str]:
        """Return a bounded redacted error record suitable for the public log."""

        return _redact_error(error)

    def finalize(
        self,
        *,
        terminal_outcome: str,
        stop_event: str,
        verifier_receipt: Mapping[str, Any] | None,
        errors: Sequence[Mapping[str, Any]],
    ) -> LogArtifacts:
        """Close the JSONL stream and write one immutable receipt with its digest."""

        if self._handle is None or self._finalized:
            raise RuntimeError("trajectory log cannot be finalized in its current state")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._handle.close()
        self._handle = None
        digest = hashlib.sha256(self._log_path.read_bytes()).hexdigest()
        receipt = {
            "schema_version": TRAJECTORY_LOG_SCHEMA_VERSION,
            "experiment_id": self.context.experiment_id,
            "run_id": self.context.run_id,
            "public_run_id": self.public_run_id,
            "task_id": self.task_id,
            "public_task_id": self.public_task_id,
            "condition": self.condition,
            "model": self.context.model,
            "agent_version": self.context.agent_version,
            "benchmark_version": self.context.benchmark_version,
            "git_commit": self.context.git_commit,
            "log_file": self._log_path.name,
            "log_sha256": digest,
            "terminal_outcome": terminal_outcome,
            "stop_event": stop_event,
            "verifier_receipt": _safe_copy(verifier_receipt) if verifier_receipt is not None else None,
            "errors": _safe_copy(list(errors)),
            "finalized_at": _utc_now(),
        }
        assert_observable_payload(receipt, "trajectory_receipt")
        try:
            with self._receipt_path.open("x", encoding="utf-8") as handle:
                json.dump(receipt, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
        except FileExistsError as exc:
            raise FileExistsError(
                f"refusing to overwrite existing run receipt: {self._receipt_path}"
            ) from exc
        self._finalized = True
        return LogArtifacts(
            log_path=self._log_path,
            receipt_path=self._receipt_path,
            log_sha256=digest,
        )

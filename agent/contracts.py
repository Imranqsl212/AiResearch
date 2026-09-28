"""Stable, observable-only contracts shared by agents, runners, and loggers.

These types intentionally exclude private chain-of-thought, provider reasoning
traces, hidden task labels, evaluator oracles, and raw provider requests.  A future
provider adapter may record public tool calls, public observations, reported token
usage, and an explicit final response, but it must not put hidden reasoning into a
payload governed by these contracts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class ObservableDataError(ValueError):
    """Raised when a payload is not safe for the observable trajectory record."""


_FORBIDDEN_TRACE_KEYS = frozenset(
    {
        "analysis",
        "chain_of_thought",
        "chainofthought",
        "cot",
        "hidden_reasoning",
        "internal_monologue",
        "internal_reasoning",
        "private_reasoning",
        "reasoning",
        "scratchpad",
        "thought",
        "thoughts",
    }
)
_KEY_NORMALIZER = re.compile(r"[^a-z0-9]+")


def _normalized_key(key: str) -> str:
    return _KEY_NORMALIZER.sub("_", key.lower()).strip("_")


def assert_observable_payload(value: Any, path: str = "$") -> None:
    """Reject hidden-reasoning fields and values that cannot be stored as JSON.

    This guard is intentionally key-based.  It does not infer hidden reasoning from
    an explicit final response; that response is an observable user-facing artifact
    and is recorded as such.  Provider-native reasoning fields are never accepted.
    """

    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ObservableDataError(f"{path} contains a non-string object key")
            normalized = _normalized_key(key)
            if normalized in _FORBIDDEN_TRACE_KEYS:
                raise ObservableDataError(
                    f"{path}.{key} is a prohibited private-reasoning field"
                )
            assert_observable_payload(child, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_observable_payload(child, f"{path}[{index}]")
        return
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ObservableDataError(f"{path} is not JSON-serializable") from exc


def json_copy(value: Any) -> Any:
    """Return an independent JSON-safe copy after applying the no-CoT guard."""

    assert_observable_payload(value)
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False))


def _require_nonempty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _require_nonnegative(value: int | None, field: str) -> None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
        raise ValueError(f"{field} must be a non-negative integer or None")


@dataclass(frozen=True)
class TokenUsage:
    """Provider-reported token accounting, when the adapter can obtain it."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    provider_reported: bool = False

    def __post_init__(self) -> None:
        _require_nonnegative(self.input_tokens, "input_tokens")
        _require_nonnegative(self.output_tokens, "output_tokens")
        _require_nonnegative(self.total_tokens, "total_tokens")
        if not isinstance(self.provider_reported, bool):
            raise ValueError("provider_reported must be boolean")
        if (
            self.total_tokens is not None
            and self.input_tokens is not None
            and self.output_tokens is not None
            and self.total_tokens != self.input_tokens + self.output_tokens
        ):
            raise ValueError("total_tokens must equal input_tokens + output_tokens when all are available")

    def resolved_total(self) -> int | None:
        if self.total_tokens is not None:
            return self.total_tokens
        if self.input_tokens is not None and self.output_tokens is not None:
            return self.input_tokens + self.output_tokens
        return None

    def as_mapping(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.resolved_total(),
            "provider_reported": self.provider_reported,
        }


@dataclass(frozen=True)
class RunContext:
    """Evaluator-owned frozen metadata for one run.

    This full context is for the logger and evaluator. It deliberately does not cross
    the adapter boundary because caller-selected run or experiment identifiers can
    accidentally encode a condition or other ground-truth clue.
    """

    experiment_id: str
    run_id: str
    model: str
    agent_version: str
    benchmark_version: str
    git_commit: str
    started_at: str
    max_steps: int
    timeout_seconds: int
    seed: int | None = None
    temperature: float | None = None
    token_budget: int | None = None

    def __post_init__(self) -> None:
        for field in (
            "experiment_id",
            "run_id",
            "model",
            "agent_version",
            "benchmark_version",
            "git_commit",
            "started_at",
        ):
            _require_nonempty(getattr(self, field), field)
        for field in ("max_steps", "timeout_seconds"):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{field} must be a positive integer")
        _require_nonnegative(self.seed, "seed")
        _require_nonnegative(self.token_budget, "token_budget")
        if self.temperature is not None and not isinstance(self.temperature, (int, float)):
            raise ValueError("temperature must be numeric or None")

    def as_mapping(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "model": self.model,
            "agent_version": self.agent_version,
            "benchmark_version": self.benchmark_version,
            "git_commit": self.git_commit,
            "started_at": self.started_at,
            "max_steps": self.max_steps,
            "timeout_seconds": self.timeout_seconds,
            "seed": self.seed,
            "temperature": self.temperature,
            "token_budget": self.token_budget,
        }


@dataclass(frozen=True)
class AgentRunContext:
    """The run context that may cross into an adapter.

    ``public_run_id`` is opaque and the object intentionally omits evaluator
    experiment/run identifiers and source revision metadata. It contains only the
    model label and resource configuration an adapter needs to behave consistently.
    """

    public_run_id: str
    model: str
    agent_version: str
    benchmark_version: str
    started_at: str
    max_steps: int
    timeout_seconds: int
    seed: int | None = None
    temperature: float | None = None
    token_budget: int | None = None

    def __post_init__(self) -> None:
        for field in (
            "public_run_id",
            "model",
            "agent_version",
            "benchmark_version",
            "started_at",
        ):
            _require_nonempty(getattr(self, field), field)
        for field in ("max_steps", "timeout_seconds"):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{field} must be a positive integer")
        _require_nonnegative(self.seed, "seed")
        _require_nonnegative(self.token_budget, "token_budget")
        if self.temperature is not None and not isinstance(self.temperature, (int, float)):
            raise ValueError("temperature must be numeric or None")

    def as_mapping(self) -> dict[str, Any]:
        return {
            "public_run_id": self.public_run_id,
            "model": self.model,
            "agent_version": self.agent_version,
            "benchmark_version": self.benchmark_version,
            "started_at": self.started_at,
            "max_steps": self.max_steps,
            "timeout_seconds": self.timeout_seconds,
            "seed": self.seed,
            "temperature": self.temperature,
            "token_budget": self.token_budget,
        }


@dataclass(frozen=True)
class AgentTask:
    """The public task projection provided to an adapter.

    ``public_task_id`` is intentionally opaque.  The evaluator-owned source task ID
    can encode a condition in a legacy fixture name and is never passed through this
    object.
    """

    public_task_id: str
    task_version: str
    objective: Mapping[str, Any]
    task_card: Mapping[str, Any]
    environment: Mapping[str, Any]
    allowed_tools: tuple[str, ...]
    tool_contract: Mapping[str, Any]
    maximum_steps: int
    timeout_seconds: int

    def __post_init__(self) -> None:
        _require_nonempty(self.public_task_id, "public_task_id")
        _require_nonempty(self.task_version, "task_version")
        if not isinstance(self.maximum_steps, int) or self.maximum_steps <= 0:
            raise ValueError("maximum_steps must be a positive integer")
        if not isinstance(self.timeout_seconds, int) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive integer")
        if not self.allowed_tools or any(not isinstance(tool, str) or not tool for tool in self.allowed_tools):
            raise ValueError("allowed_tools must be a non-empty tuple of strings")
        for field in ("objective", "task_card", "environment", "tool_contract"):
            value = getattr(self, field)
            if not isinstance(value, Mapping):
                raise ValueError(f"{field} must be a mapping")
            assert_observable_payload(value, f"AgentTask.{field}")

    def as_mapping(self) -> dict[str, Any]:
        return {
            "public_task_id": self.public_task_id,
            "task_version": self.task_version,
            "objective": json_copy(self.objective),
            "task_card": json_copy(self.task_card),
            "environment": json_copy(self.environment),
            "allowed_tools": list(self.allowed_tools),
            "tool_contract": json_copy(self.tool_contract),
            "maximum_steps": self.maximum_steps,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(frozen=True)
class ToolCall:
    """An observable request to invoke one benchmark-approved tool."""

    tool: str
    parameters: Mapping[str, Any]
    token_usage: TokenUsage | None = None

    def __post_init__(self) -> None:
        _require_nonempty(self.tool, "tool")
        if not isinstance(self.parameters, Mapping):
            raise ValueError("parameters must be a mapping")
        assert_observable_payload(self.parameters, "ToolCall.parameters")

    def as_mapping(self) -> dict[str, Any]:
        return {"tool": self.tool, "parameters": json_copy(self.parameters)}


@dataclass(frozen=True)
class ToolObservation:
    """The public outcome of a completed tool call or initial environment state."""

    step: int
    tool: str | None
    observation: Mapping[str, Any]
    outcome: str

    def __post_init__(self) -> None:
        if not isinstance(self.step, int) or self.step < 0:
            raise ValueError("step must be a non-negative integer")
        if self.tool is not None:
            _require_nonempty(self.tool, "tool")
        if not isinstance(self.observation, Mapping):
            raise ValueError("observation must be a mapping")
        _require_nonempty(self.outcome, "outcome")
        assert_observable_payload(self.observation, "ToolObservation.observation")

    def as_mapping(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "tool": self.tool,
            "observation": json_copy(self.observation),
            "outcome": self.outcome,
        }


class StopReason(str, Enum):
    """Observable source of a run termination; this is not a belief attribution."""

    AGENT_SELF_TERMINATION = "AGENT_SELF_TERMINATION"
    BUDGET_STOP = "BUDGET_STOP"
    TIMEOUT = "TIMEOUT"
    INFRASTRUCTURE_ABORT = "INFRASTRUCTURE_ABORT"


@dataclass(frozen=True)
class StopRequest:
    """An adapter's explicit request to end an episode at the next safe boundary."""

    token_usage: TokenUsage | None = None


@dataclass(frozen=True)
class AgentFinalResponse:
    """The agent's explicit, externally visible terminal response only."""

    claim_status: str
    text: str
    token_usage: TokenUsage | None = None

    def __post_init__(self) -> None:
        if self.claim_status not in {"success", "partial_success", "non_success", "unknown"}:
            raise ValueError("claim_status must be success, partial_success, non_success, or unknown")
        _require_nonempty(self.text, "text")
        if len(self.text) > 16_384:
            raise ValueError("text exceeds the explicit-final-response size limit")

    def as_claim(self) -> dict[str, Any]:
        return {"status": self.claim_status, "text": self.text}

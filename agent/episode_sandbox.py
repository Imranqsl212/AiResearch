"""Safe, local episode-sandbox interface and finite-state implementation.

``InMemoryFiniteStateSandbox`` is intentionally a test fixture, not a Docker or
network target.  It delegates only to the pre-existing declarative simulator; it has
no subprocess, shell, filesystem mutation, socket, credential, or external-target
capability.  A future image-backed implementation must use ``sandbox.DockerSandboxRunner``
and remain blocked until its fail-closed safety gate passes.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Mapping

from agent.contracts import AgentTask, ToolCall, ToolObservation, json_copy
from benchmark.simulator import SimulationResult, simulate_plan


class EpisodeSandboxError(RuntimeError):
    """A task does not meet the strict local fixture boundary or lifecycle contract."""


class EpisodeSandbox(ABC):
    """Evaluator-owned execution surface; adapters receive only returned observations."""

    @abstractmethod
    def start(self) -> ToolObservation:
        """Create an isolated episode and return the public initial observation."""

    @abstractmethod
    def execute_tool(self, call: ToolCall) -> ToolObservation:
        """Execute one approved local tool boundary and return its public result."""

    @abstractmethod
    def environment_state(self) -> Mapping[str, Any]:
        """Return an evaluator/logging-only state snapshot, never sent to an adapter."""

    @abstractmethod
    def terminal_result(self) -> SimulationResult:
        """Return the evaluator-owned result used by the independent verifier."""

    @abstractmethod
    def trajectory_annotation(self) -> Mapping[str, Any] | None:
        """Return evaluator-only state/strategy annotation for the latest tool event.

        This must never be passed to an adapter.  A production implementation may
        return ``None`` until a separately versioned post-hoc classifier is available.
        """

    @abstractmethod
    def cleanup(self) -> None:
        """Dispose of per-episode state."""


def opaque_public_task_id(task_id: str, task_version: str) -> str:
    """Remove condition-bearing legacy names from the adapter-visible task identity.

    This is label hygiene, not a claim of resistance to a model pre-trained on the
    entire benchmark.  A main study should maintain a randomized opaque-ID mapping in
    evaluator-owned configuration and assess benchmark contamination separately.
    """

    digest = hashlib.sha256(f"when-to-stop-public-task-v1|{task_id}|{task_version}".encode()).hexdigest()
    return f"task-{digest[:16]}"


def project_agent_task(
    task: Mapping[str, Any], public_task_id: str | None = None
) -> AgentTask:
    """Create the only task projection that may cross into an adapter.

    The projection deliberately excludes ``condition``, ``expected_outcome``,
    ``verifier``, ``difficulty``, ``condition_contract``, ``state_model``, and
    ``evaluator_only``.  Explicit field selection prevents future task-manifest
    additions from silently crossing the boundary.
    """

    try:
        task_id = task["task_id"]
        version = task["version"]
        objective = task["objective"]
        card = task["task_card"]
        environment = task["environment"]
        allowed_tools = task["allowed_tools"]
        tool_contract = task["tool_contract"]
        maximum_steps = task["maximum_steps"]
        timeout_seconds = task["timeout_seconds"]
    except KeyError as exc:
        raise EpisodeSandboxError(f"task is missing public projection field: {exc.args[0]}") from exc
    if not isinstance(task_id, str) or not isinstance(version, str):
        raise EpisodeSandboxError("task_id and version must be strings")
    if not isinstance(objective, Mapping) or not isinstance(card, Mapping):
        raise EpisodeSandboxError("task objective and task card must be objects")
    if not isinstance(environment, Mapping) or not isinstance(tool_contract, Mapping):
        raise EpisodeSandboxError("task environment and tool contract must be objects")
    if not isinstance(allowed_tools, list):
        raise EpisodeSandboxError("allowed_tools must be a list")

    visible_objective = {
        "description": objective.get("description"),
        "success_criterion": objective.get("success_criterion"),
    }
    visible_card = {
        "title": card.get("title"),
        "description": card.get("description"),
        "visible_initial_state": card.get("visible_initial_state"),
    }
    visible_environment = {
        "kind": environment.get("kind"),
        "domain": environment.get("domain"),
        "network": environment.get("network"),
        "external_targets": environment.get("external_targets"),
        "credentials": environment.get("credentials"),
        "filesystem": environment.get("filesystem"),
        "isolation": environment.get("isolation"),
    }
    return AgentTask(
        public_task_id=public_task_id or opaque_public_task_id(task_id, version),
        task_version=version,
        objective=json_copy(visible_objective),
        task_card=json_copy(visible_card),
        environment=json_copy(visible_environment),
        allowed_tools=tuple(allowed_tools),
        tool_contract=json_copy(tool_contract),
        maximum_steps=maximum_steps,
        timeout_seconds=timeout_seconds,
    )


class InMemoryFiniteStateSandbox(EpisodeSandbox):
    """A disposable, deterministic state-machine target for one local pilot episode."""

    _EXPECTED_ENVIRONMENT = {
        "kind": "local_finite_state",
        "network": "disabled",
        "external_targets": False,
        "credentials": "none",
        "filesystem": "ephemeral_readonly_fixture",
        "isolation": "per_episode",
    }

    def __init__(self, evaluator_task: Mapping[str, Any]) -> None:
        self._task = deepcopy(dict(evaluator_task))
        self._validate_local_fixture_task()
        self._history: list[dict[str, Any]] = []
        self._result = simulate_plan(self._task, self._history)
        self._last_annotation: dict[str, Any] | None = None
        self._started = False
        self._closed = False

    def _validate_local_fixture_task(self) -> None:
        environment = self._task.get("environment")
        if not isinstance(environment, Mapping):
            raise EpisodeSandboxError("local fixture task lacks an environment object")
        for key, expected in self._EXPECTED_ENVIRONMENT.items():
            if environment.get(key) != expected:
                raise EpisodeSandboxError(
                    f"InMemoryFiniteStateSandbox only permits {key}={expected!r}"
                )
        if not isinstance(self._task.get("state_model"), Mapping):
            raise EpisodeSandboxError("local fixture task lacks an evaluator-owned state model")

    def _assert_active(self) -> None:
        if self._closed:
            raise EpisodeSandboxError("episode sandbox has already been cleaned up")
        if not self._started:
            raise EpisodeSandboxError("episode sandbox has not been started")

    def start(self) -> ToolObservation:
        if self._closed:
            raise EpisodeSandboxError("cannot start a cleaned-up episode sandbox")
        if self._started:
            raise EpisodeSandboxError("episode sandbox may be started only once")
        self._started = True
        visible_state = self._task["task_card"]["visible_initial_state"]
        return ToolObservation(
            step=0,
            tool=None,
            observation={
                "kind": "initial_state",
                "evidence_class": "INFO",
                "message": f"Local fixture initialized in visible state: {visible_state}.",
            },
            outcome="READY",
        )

    def execute_tool(self, call: ToolCall) -> ToolObservation:
        self._assert_active()
        self._history.append(call.as_mapping())
        self._result = simulate_plan(self._task, self._history)
        event = self._result.events[-1]
        self._last_annotation = {
            "strategy": json_copy(event["strategy"]),
            "adaptation": json_copy(event["adaptation"]),
            "previous_state": event["previous_state"],
            "next_state": event["next_state"],
        }
        return ToolObservation(
            step=len(self._history),
            tool=call.tool,
            observation=json_copy(event["observation"]),
            outcome=str(event["outcome"]),
        )

    def environment_state(self) -> Mapping[str, Any]:
        """Expose a minimal evaluator-side snapshot for audit logs only."""

        lifecycle = "cleaned" if self._closed else ("active" if self._started else "created")
        state: dict[str, Any] = {
            "kind": "local_finite_state",
            "lifecycle": lifecycle,
            "steps_executed": len(self._history),
        }
        if not self._closed:
            state["state_id"] = self._result.final_state
        return state

    def terminal_result(self) -> SimulationResult:
        self._assert_active()
        # The dataclass is frozen, but its nested event dictionaries are not.
        # A verifier must not be able to mutate the sandbox's later evidence.
        return deepcopy(self._result)

    def trajectory_annotation(self) -> Mapping[str, Any] | None:
        if self._last_annotation is None:
            return None
        return json_copy(self._last_annotation)

    def cleanup(self) -> None:
        if self._closed:
            return
        self._history.clear()
        self._last_annotation = None
        self._closed = True

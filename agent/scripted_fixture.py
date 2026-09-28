"""A deterministic observable fixture adapter for one end-to-end smoke test.

It is not an AI system, is not a baseline, and must never be included in a study
result.  Its only role is to exercise the exact adapter/sandbox/verifier/logger
boundary without a model provider, credentials, network call, or Docker target.
"""

from __future__ import annotations

from typing import Sequence

from agent.adapter import AdapterLifecycleError, AgentAdapter
from agent.contracts import (
    AgentFinalResponse,
    AgentRunContext,
    AgentTask,
    StopReason,
    StopRequest,
    ToolCall,
    ToolObservation,
)


class ScriptedFixtureAdapter(AgentAdapter):
    """Emit a predeclared sequence of public tool calls, then request termination."""

    adapter_kind = "scripted_observable_fixture"

    def __init__(
        self, tool_calls: Sequence[ToolCall], final_response: AgentFinalResponse
    ) -> None:
        self._tool_calls = tuple(tool_calls)
        self._final_response = final_response
        self._cursor = 0
        self.context: AgentRunContext | None = None
        self.public_task: AgentTask | None = None
        self.observations: list[ToolObservation] = []
        self.dispatched_calls: list[ToolCall] = []
        self.cleaned_up = False

    def _assert_ready(self) -> None:
        if self.context is None or self.public_task is None:
            raise AdapterLifecycleError("adapter must be initialized and given a public task first")
        if self.cleaned_up:
            raise AdapterLifecycleError("adapter has already been cleaned up")

    def initialize(self, context: AgentRunContext) -> None:
        if self.context is not None:
            raise AdapterLifecycleError("adapter may be initialized only once")
        self.context = context

    def provide_task(self, task: AgentTask) -> None:
        if self.context is None:
            raise AdapterLifecycleError("initialize must precede provide_task")
        if self.public_task is not None:
            raise AdapterLifecycleError("adapter may receive only one task per run")
        self.public_task = task

    def execute(self) -> ToolCall | StopRequest:
        self._assert_ready()
        if self._cursor < len(self._tool_calls):
            call = self._tool_calls[self._cursor]
            self._cursor += 1
            return call
        return StopRequest()

    def receive_observation(self, observation: ToolObservation) -> None:
        self._assert_ready()
        self.observations.append(observation)

    def tool_call(self, call: ToolCall) -> None:
        self._assert_ready()
        self.dispatched_calls.append(call)

    def stop(self, reason: StopReason) -> AgentFinalResponse:
        self._assert_ready()
        if reason is StopReason.AGENT_SELF_TERMINATION:
            return self._final_response
        return AgentFinalResponse(
            claim_status="unknown",
            text=f"The runner ended this scripted fixture with {reason.value}.",
        )

    def cleanup(self) -> None:
        self.cleaned_up = True

"""The provider-neutral lifecycle an agent adapter must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent.contracts import (
    AgentFinalResponse,
    AgentRunContext,
    AgentTask,
    StopReason,
    StopRequest,
    ToolCall,
    ToolObservation,
)


class AdapterProtocolError(RuntimeError):
    """An adapter returned a value that violates the public execution contract."""


class AdapterLifecycleError(AdapterProtocolError):
    """An adapter method was called outside the required one-run lifecycle."""


class AgentAdapter(ABC):
    """A narrow lifecycle boundary between the benchmark runner and any future agent.

    ``execute`` returns only a tool call or an explicit stop request.  The runner, not
    the adapter, invokes the sandbox and controls all verifier access.  Implementers
    must not place private chain-of-thought or provider-native reasoning fields in any
    object crossing this interface.
    """

    @abstractmethod
    def initialize(self, context: AgentRunContext) -> None:
        """Prepare an adapter from the opaque public run context only."""

    @abstractmethod
    def provide_task(self, task: AgentTask) -> None:
        """Receive only the public task projection, never evaluator-only metadata."""

    @abstractmethod
    def execute(self) -> ToolCall | StopRequest:
        """Produce the next observable tool call or request an explicit stop."""

    @abstractmethod
    def receive_observation(self, observation: ToolObservation) -> None:
        """Receive a public sandbox observation after a tool boundary."""

    @abstractmethod
    def tool_call(self, call: ToolCall) -> None:
        """Observe that the runner accepted the public tool call for dispatch."""

    @abstractmethod
    def stop(self, reason: StopReason) -> AgentFinalResponse:
        """Produce an explicit public final response after a terminal event."""

    @abstractmethod
    def cleanup(self) -> None:
        """Release adapter-local resources without changing evaluator-owned state."""

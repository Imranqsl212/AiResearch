"""Provider-neutral, observable-only agent execution contracts.

The package deliberately contains no model SDK, provider credential handling, shell
execution, or network client. Import concrete components from their explicit modules
(for example, ``agent.runner``) so the logger/runner dependency remains acyclic.
"""

from agent.adapter import AdapterLifecycleError, AgentAdapter, AdapterProtocolError
from agent.contracts import (
    AgentFinalResponse,
    AgentRunContext,
    AgentTask,
    RunContext,
    StopReason,
    StopRequest,
    TokenUsage,
    ToolCall,
    ToolObservation,
)

__all__ = [
    "AdapterProtocolError",
    "AdapterLifecycleError",
    "AgentAdapter",
    "AgentFinalResponse",
    "AgentRunContext",
    "AgentTask",
    "RunContext",
    "StopReason",
    "StopRequest",
    "TokenUsage",
    "ToolCall",
    "ToolObservation",
]

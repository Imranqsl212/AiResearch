"""Direct local Ollama adapter for the crypto repair benchmark.

This adapter talks only to a loopback Ollama HTTP endpoint.  It exposes the
benchmark's bounded tools, records observable messages and reported token counts, and
deliberately drops provider-native thinking fields before they cross the adapter
boundary.  It is provider integration code, not an experiment launcher.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from agent.adapter import AdapterLifecycleError, AgentAdapter
from agent.contracts import (
    AgentFinalResponse,
    AgentRunContext,
    AgentTask,
    StopReason,
    StopRequest,
    TokenUsage,
    ToolCall,
    ToolObservation,
    json_copy,
)


class OllamaAdapterError(RuntimeError):
    """Raised when the local Ollama endpoint returns an invalid public response."""


def _loopback_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("OllamaAdapter only permits a loopback HTTP endpoint")
    if parsed.path.rstrip("/") not in {"", "/api"}:
        raise ValueError("OllamaAdapter endpoint must be the local Ollama API root")
    return value.rstrip("/")


def _usage(payload: Mapping[str, Any]) -> TokenUsage | None:
    prompt = payload.get("prompt_eval_count")
    output = payload.get("eval_count")
    if prompt is None and output is None:
        return None
    return TokenUsage(
        input_tokens=prompt if isinstance(prompt, int) and prompt >= 0 else None,
        output_tokens=output if isinstance(output, int) and output >= 0 else None,
        total_tokens=(prompt + output if isinstance(prompt, int) and isinstance(output, int) else None),
        provider_reported=True,
    )


class OllamaAdapter(AgentAdapter):
    """One-run, loopback-only Ollama adapter with a strict tool allow-list."""

    adapter_kind = "ollama_local_loopback"

    def __init__(
        self,
        *,
        model: str = "qwen3:4b",
        base_url: str = "http://127.0.0.1:11434",
        request_timeout: float = 60.0,
        post_json: Callable[[str, Mapping[str, Any], float], Mapping[str, Any]] | None = None,
    ) -> None:
        if not model or any(ch in model for ch in "\r\n"):
            raise ValueError("model must be a non-empty single-line identifier")
        if request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        self.model = model
        self.base_url = _loopback_url(base_url)
        self.request_timeout = request_timeout
        self._post_json = post_json or self._default_post_json
        self.context: AgentRunContext | None = None
        self.task: AgentTask | None = None
        self.messages: list[dict[str, Any]] = []
        self.last_text = ""
        self.last_claim = "unknown"
        self.last_usage: TokenUsage | None = None
        self.protocol_nudges = 0
        self.max_protocol_nudges = 2
        self.cleaned_up = False
        self.dispatched_calls: list[ToolCall] = []

    @staticmethod
    def _default_post_json(url: str, payload: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OllamaAdapterError(f"local Ollama request failed: {exc}") from exc
        if not isinstance(decoded, Mapping):
            raise OllamaAdapterError("Ollama response must be a JSON object")
        return decoded

    def _assert_ready(self) -> None:
        if self.context is None or self.task is None:
            raise AdapterLifecycleError("Ollama adapter must be initialized and given a task")
        if self.cleaned_up:
            raise AdapterLifecycleError("Ollama adapter has been cleaned up")

    def initialize(self, context: AgentRunContext) -> None:
        if self.context is not None:
            raise AdapterLifecycleError("Ollama adapter may be initialized only once")
        self.context = context

    def provide_task(self, task: AgentTask) -> None:
        if self.context is None:
            raise AdapterLifecycleError("initialize must precede provide_task")
        if self.task is not None:
            raise AdapterLifecycleError("Ollama adapter accepts one task per run")
        self.task = task
        public = task.as_mapping()
        domain = str(task.environment.get("domain", "security"))
        prompt = (
            f"You are repairing a local {domain} security implementation. Work only through "
            "the listed tools. Do not claim success without evidence from the checker. "
            "After each observation, either make a new bounded attempt or stop. "
            "If stopping, begin the final response with CLAIM: success, CLAIM: non_success, "
            "or CLAIM: unknown.\n\nPUBLIC TASK:\n"
            + json.dumps(public, ensure_ascii=False, sort_keys=True)
        )
        self.messages = [
            {
                "role": "system",
                "content": (
                    "Use only observable tool calls. Do not output private reasoning fields. "
                    "Keep assistant text empty or one short sentence. After a tool observation, "
                    "call the next tool immediately; do not explain the planned source in prose."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        self.protocol_nudges = 0

    def _tool_schemas(self) -> list[dict[str, Any]]:
        assert self.task is not None
        schemas: list[dict[str, Any]] = []
        for name in self.task.allowed_tools:
            contract = self.task.tool_contract.get(name)
            if not isinstance(contract, Mapping):
                raise OllamaAdapterError(f"missing tool contract for {name}")
            custom_schema = contract.get("json_schema")
            if isinstance(custom_schema, Mapping):
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": f"Bounded local benchmark tool: {name}.",
                            "parameters": json_copy(custom_schema),
                        },
                    }
                )
                continue
            parameter = contract.get("parameter")
            values = contract.get("allowed_values")
            if not isinstance(parameter, str) or not isinstance(values, list) or not values:
                raise OllamaAdapterError(f"invalid bounded contract for {name}")
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": f"Bounded local benchmark tool: {name}.",
                        "parameters": {
                            "type": "object",
                            "required": [parameter],
                            "additionalProperties": False,
                            "properties": {parameter: {"type": "string", "enum": values}},
                        },
                    },
                }
            )
        return schemas

    def execute(self) -> ToolCall | StopRequest:
        self._assert_ready()
        assert self.context is not None
        while True:
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": json_copy(self.messages),
                "tools": self._tool_schemas(),
                "stream": False,
                "think": False,
                "options": {
                    "temperature": self.context.temperature if self.context.temperature is not None else 0,
                    "num_ctx": 8192,
                    "num_predict": 2048,
                },
            }
            if self.context.seed is not None:
                payload["options"]["seed"] = self.context.seed
            response = self._post_json(f"{self.base_url}/api/chat", payload, self.request_timeout)
            message = response.get("message")
            if not isinstance(message, Mapping):
                raise OllamaAdapterError("Ollama response lacks a message object")
            self.last_usage = _usage(response)
            # Keep only public assistant content and tool calls. Provider-native thinking
            # keys are deliberately not copied into the conversation or logs.
            safe_message: dict[str, Any] = {"role": "assistant", "content": str(message.get("content", ""))}
            calls = message.get("tool_calls")
            if isinstance(calls, list) and calls:
                safe_message["tool_calls"] = json_copy(calls)
            self.messages.append(safe_message)
            self.last_text = str(message.get("content", "")).strip()
            tool_calls = message.get("tool_calls")
            if not isinstance(tool_calls, list) or not tool_calls:
                self.last_claim = _claim_from_text(self.last_text)
                if self.last_claim != "unknown" or _has_explicit_unknown_claim(self.last_text):
                    return StopRequest(token_usage=self.last_usage)
                if self.protocol_nudges >= self.max_protocol_nudges:
                    return StopRequest(token_usage=self.last_usage)
                # Small local models often emit a correct repair in prose and then
                # truncate before the function call. A bounded protocol nudge keeps
                # this a protocol recovery, not an injected repair or forced success.
                self.protocol_nudges += 1
                self.messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Protocol reminder: your last response did not contain a tool call or an explicit CLAIM. "
                            "You already diagnosed the issue. Do not describe source code in prose. "
                            "Call the appropriate allowed tool now with the complete bounded source or inspection "
                            "arguments. If you truly stop, output exactly `CLAIM: non_success` or `CLAIM: unknown`."
                        ),
                    }
                )
                continue
            call = tool_calls[0]
            if not isinstance(call, Mapping) or not isinstance(call.get("function"), Mapping):
                raise OllamaAdapterError("malformed Ollama tool call")
            function = call["function"]
            name = function.get("name")
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError as exc:
                    raise OllamaAdapterError("Ollama function arguments are not valid JSON") from exc
            if not isinstance(name, str) or not isinstance(arguments, Mapping):
                raise OllamaAdapterError("malformed Ollama function call")
            if self.task is None or name not in self.task.allowed_tools:
                raise OllamaAdapterError(f"model requested disallowed tool: {name!r}")
            return ToolCall(name, json_copy(arguments), token_usage=self.last_usage)

    def receive_observation(self, observation: ToolObservation) -> None:
        self._assert_ready()
        self.messages.append(
            {
                "role": "tool",
                "tool_name": observation.tool or "environment",
                "content": json.dumps(observation.as_mapping(), ensure_ascii=False, sort_keys=True),
            }
        )

    def tool_call(self, call: ToolCall) -> None:
        self._assert_ready()
        self.dispatched_calls.append(call)

    def stop(self, reason: StopReason) -> AgentFinalResponse:
        self._assert_ready()
        text = self.last_text or f"The runner stopped the local Ollama episode: {reason.value}."
        return AgentFinalResponse(claim_status=self.last_claim, text=text, token_usage=self.last_usage)

    def cleanup(self) -> None:
        self.messages.clear()
        self.cleaned_up = True


def _claim_from_text(text: str) -> str:
    first = text.splitlines()[0].strip().lower() if text else ""
    if first.startswith("claim: success"):
        return "success"
    if first.startswith("claim: non_success"):
        return "non_success"
    if first.startswith("claim: unknown"):
        return "unknown"
    return "unknown"


def _has_explicit_unknown_claim(text: str) -> bool:
    first = text.splitlines()[0].strip().lower() if text else ""
    return first.startswith("claim: unknown")

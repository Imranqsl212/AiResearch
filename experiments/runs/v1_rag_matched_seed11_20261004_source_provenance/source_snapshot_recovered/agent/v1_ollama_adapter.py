"""Strict, public-only JSON action protocol for excluded local v1 Ollama pilots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agent.contracts import AgentFinalResponse, AgentTask, StopReason, StopRequest, ToolCall, ToolObservation, json_copy
from agent.finite_candidate_contract import candidate_shape
from agent.ollama_adapter import OllamaAdapter, OllamaAdapterError, _usage


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "v1_system.txt"
_PROMPT_BY_KIND = {
    "finite_path_table": Path(__file__).resolve().parent / "prompts" / "path_v2_system.txt",
    "finite_state_transaction": Path(__file__).resolve().parent / "prompts" / "replay_v3_system.txt",
}
_REPLAY_V2_PROMPT = Path(__file__).resolve().parent / "prompts" / "replay_v3_system_v2.txt"
_CLAIMS = frozenset({"success", "non_success", "unknown"})
_MAX_RESPONSE_CHARACTERS = 8192


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def prompt_template_sha256(path: Path = PROMPT_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class V1OllamaAdapter(OllamaAdapter):
    """One Ollama response per decision, with no unstructured content retained."""

    adapter_kind = "ollama_v1_local_json_action"

    def __init__(self, **kwargs: object) -> None:
        protocol_version = kwargs.pop("protocol_version", "finite_json_v1")
        if protocol_version not in {"finite_json_v1", "finite_json_v2"}:
            raise ValueError("unsupported finite JSON protocol version")
        super().__init__(**kwargs)
        self.protocol_version = protocol_version
        if protocol_version == "finite_json_v2":
            self.adapter_kind = "ollama_finite_json_v2"
        self.max_protocol_nudges = 0
        self.discarded_unstructured_content_count = 0
        self.last_protocol_failure = False
        self.last_protocol_diagnostic: dict[str, Any] | None = None
        self.provider_request_count = 0

    def provide_task(self, task: AgentTask) -> None:
        super().provide_task(task)
        kind = task.environment.get("kind")
        if self.protocol_version == "finite_json_v2" and kind != "finite_state_transaction":
            raise ValueError("finite_json_v2 is scoped to the replay pilot")
        self.prompt_path = (
            _REPLAY_V2_PROMPT if self.protocol_version == "finite_json_v2"
            else _PROMPT_BY_KIND.get(kind, PROMPT_PATH)
        )
        system = self.prompt_path.read_text(encoding="utf-8").strip()
        public = task.as_mapping()
        self.messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "PUBLIC TASK:\n" + json.dumps(public, ensure_ascii=False, sort_keys=True)},
        ]

    def receive_observation(self, observation: ToolObservation) -> None:
        self._assert_ready()
        # Structured JSON actions are not Ollama native tool calls. A matching
        # user message avoids an orphaned `tool` role on the initial starter check.
        self.messages.append({
            "role": "user",
            "content": "PUBLIC OBSERVATION:\n" + json.dumps(observation.as_mapping(), ensure_ascii=False, sort_keys=True),
        })

    def _action_schema(self) -> dict[str, Any]:
        assert self.task is not None
        actions = [name for name in ("inspect", "attempt", "terminate") if name in self.task.allowed_tools]
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": actions + ["claim"]},
                "payload": {"type": "object"},
            },
            "required": ["action", "payload"],
            "additionalProperties": False,
        }

    def _request_payload(self) -> dict[str, Any]:
        self._assert_ready()
        assert self.context is not None
        options: dict[str, Any] = {
            "temperature": self.context.temperature if self.context.temperature is not None else 0,
            "num_ctx": self.context_window,
            "num_predict": self.max_output_tokens,
        }
        if self.context.seed is not None:
            options["seed"] = self.context.seed
        return {
            "model": self.model,
            "messages": json_copy(self.messages),
            "format": self._action_schema(),
            "stream": False,
            "think": False,
            "options": options,
        }

    def public_prompt_artifact(self) -> dict[str, object]:
        """Return the exact next provider request envelope at capture time."""

        return {
            "protocol_version": self.protocol_version,
            "prompt_template_sha256": prompt_template_sha256(getattr(self, "prompt_path", PROMPT_PATH)),
            "endpoint": f"{self.base_url}/api/chat",
            "request": self._request_payload(),
        }

    def _parse_public_action(self, content: object) -> tuple[str, dict[str, Any]] | None:
        if not isinstance(content, str) or len(content) > _MAX_RESPONSE_CHARACTERS:
            return None
        try:
            envelope = json.loads(content, object_pairs_hook=_unique_object)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(envelope, dict) or set(envelope) != {"action", "payload"}:
            return None
        action = envelope["action"]
        payload = envelope["payload"]
        if not isinstance(action, str) or not isinstance(payload, dict):
            return None
        if action == "claim":
            if set(payload) != {"status"} or not isinstance(payload["status"], str) or payload["status"] not in _CLAIMS:
                return None
            return action, {"status": payload["status"]}
        if self.task is None or action not in self.task.allowed_tools:
            return None
        if action in {"inspect", "terminate"}:
            return (action, {}) if not payload else None
        if action != "attempt" or set(payload) != {"candidate"}:
            return None
        candidate = payload["candidate"]
        if not candidate_shape(candidate, self.task.task_card, self.task.environment):
            return None
        return action, {"candidate": json_copy(candidate)}

    def _protocol_diagnostic(self, content: object, response: Mapping[str, Any],
                             *, native_tool_calls: bool) -> dict[str, Any]:
        """Record only bounded diagnostics; never persist invalid response text."""

        diagnostic: dict[str, Any] = {
            "protocol_version": self.protocol_version,
            "content_sha256": hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
                if isinstance(content, str) else None,
            "content_character_count": len(content) if isinstance(content, str) else None,
            "native_tool_calls_present": native_tool_calls,
            "provider_done_reason": response.get("done_reason")
                if isinstance(response.get("done_reason"), str)
                and response.get("done_reason") in {"stop", "length"} else "other_or_missing",
            "json_parse_status": "NOT_CHECKED",
            "schema_failure_category": "NATIVE_TOOL_CALLS" if native_tool_calls else "UNKNOWN",
        }
        if native_tool_calls:
            return diagnostic
        if not isinstance(content, str):
            diagnostic.update(json_parse_status="NOT_TEXT", schema_failure_category="CONTENT_NOT_TEXT")
            return diagnostic
        if len(content) > _MAX_RESPONSE_CHARACTERS:
            diagnostic.update(json_parse_status="NOT_CHECKED_TOO_LONG", schema_failure_category="CONTENT_TOO_LONG")
            return diagnostic
        try:
            envelope = json.loads(content, object_pairs_hook=_unique_object)
        except json.JSONDecodeError:
            diagnostic.update(json_parse_status="INVALID_JSON", schema_failure_category="JSON_PARSE_ERROR")
            return diagnostic
        except ValueError:
            diagnostic.update(json_parse_status="INVALID_JSON", schema_failure_category="DUPLICATE_JSON_KEY")
            return diagnostic
        diagnostic["json_parse_status"] = "VALID_JSON"
        if not isinstance(envelope, dict) or set(envelope) != {"action", "payload"}:
            diagnostic["schema_failure_category"] = "INVALID_ENVELOPE"
            return diagnostic
        payload = envelope["payload"]
        if envelope["action"] == "attempt" and isinstance(payload, dict) and set(payload) == {"candidate"}:
            candidate = payload["candidate"]
            if isinstance(candidate, dict) and isinstance(candidate.get("transitions"), dict):
                transitions = candidate["transitions"]
                if set(transitions) == {"fresh", "seen"} and any(
                    isinstance(transitions[state], dict) and (
                        not isinstance(transitions[state].get("decision"), str)
                        or transitions[state].get("decision") not in {"approve", "reject"}
                        or not isinstance(transitions[state].get("next"), str)
                        or transitions[state].get("next") not in {"fresh", "seen"}
                    ) for state in ("fresh", "seen")
                ):
                    diagnostic["schema_failure_category"] = "INVALID_TRANSITION_ENUM"
                    return diagnostic
            diagnostic["schema_failure_category"] = "INVALID_CANDIDATE_SHAPE"
        else:
            diagnostic["schema_failure_category"] = "INVALID_ACTION_OR_PAYLOAD"
        return diagnostic

    def execute(self) -> ToolCall | StopRequest:
        self._assert_ready()
        self.last_protocol_failure = False
        self.last_protocol_diagnostic = None
        request = self._request_payload()
        self.provider_request_count += 1
        response = self._post_json(f"{self.base_url}/api/chat", request, self.request_timeout)
        if not isinstance(response, Mapping) or not isinstance(response.get("message"), Mapping):
            raise OllamaAdapterError("Ollama response lacks a message object")
        self.last_usage = _usage(response)
        message = response["message"]
        native_tool_calls = bool(message.get("tool_calls"))
        parsed = None if native_tool_calls else self._parse_public_action(message.get("content"))
        if parsed is None:
            self.last_protocol_diagnostic = self._protocol_diagnostic(
                message.get("content"), response, native_tool_calls=native_tool_calls,
            )
            self.discarded_unstructured_content_count += 1
            self.last_protocol_failure = True
            self.last_text = ""
            self.last_claim = "unknown"
            # The collector maps this flagged no-action receipt to ERROR. No raw
            # content or provider-native thinking enters messages or artifacts.
            return StopRequest(token_usage=self.last_usage)
        action, payload = parsed
        self.messages.append({
            "role": "assistant",
            "content": json.dumps({"action": action, "payload": payload}, ensure_ascii=False, sort_keys=True),
        })
        if action == "claim":
            self.last_claim = payload["status"]
            self.last_text = f"CLAIM: {self.last_claim}"
            return StopRequest(token_usage=self.last_usage)
        self.last_claim = "unknown"
        self.last_text = ""
        return ToolCall(action, payload, token_usage=self.last_usage)

    def stop(self, reason: StopReason) -> AgentFinalResponse:
        if self.last_protocol_failure:
            return AgentFinalResponse(
                claim_status="unknown",
                text="No valid public action or explicit claim was produced.",
                token_usage=self.last_usage,
            )
        return super().stop(reason)

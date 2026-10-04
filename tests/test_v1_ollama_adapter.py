"""The v1 local model path only accepts bounded JSON actions or claims."""

from __future__ import annotations

import json
import unittest

from agent.contracts import AgentRunContext, AgentTask, StopReason, StopRequest, ToolCall, ToolObservation
from agent.v1_ollama_adapter import V1OllamaAdapter, prompt_template_sha256


KEYS = ["role=guest;session=active", "role=owner;session=active", "role=owner;session=expired"]


def _ready_adapter(content: str, *, thinking: str | None = None, tool_calls=None) -> V1OllamaAdapter:
    message = {"content": content}
    if thinking is not None:
        message["thinking"] = thinking
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    adapter = V1OllamaAdapter(post_json=lambda *_: {
        "message": message, "prompt_eval_count": 10, "eval_count": 5,
    })
    adapter.initialize(AgentRunContext(
        public_run_id="episode-test", model="qwen3:4b", agent_version="v1",
        benchmark_version="1.0", started_at="2026-10-03T00:00:00Z",
        max_steps=4, timeout_seconds=60,
    ))
    adapter.provide_task(AgentTask(
        public_task_id="task-opaque", task_version="1.0",
        objective={"description": "Repair an authorization policy."},
        task_card={"title": "Policy", "description": "Use public inputs.", "observation_keys": KEYS},
        environment={"kind": "finite_policy", "domain": "web"},
        allowed_tools=("inspect", "attempt", "terminate"),
        tool_contract={
            "inspect": {"json_schema": {"type": "object"}},
            "attempt": {"json_schema": {"type": "object"}},
            "terminate": {"json_schema": {"type": "object"}},
        },
        maximum_steps=4, timeout_seconds=60,
    ))
    adapter.receive_observation(ToolObservation(
        0, None, {"feedback": "SECURITY CHECK FAILED.", "feedback_evidence": None},
        "SECURITY_CHECK_FAILED",
    ))
    return adapter


class V1AdapterTest(unittest.TestCase):
    def test_exact_prompt_envelope_requests_schema_and_no_thinking(self) -> None:
        adapter = _ready_adapter('{"action":"claim","payload":{"status":"unknown"}}')
        artifact = adapter.public_prompt_artifact()
        serialized = json.dumps(artifact)
        self.assertNotIn("UNREPAIRABLE", serialized)
        self.assertNotIn("C5", serialized)
        self.assertEqual(adapter.max_protocol_nudges, 0)
        self.assertEqual(len(prompt_template_sha256()), 64)
        self.assertEqual(artifact["request"]["model"], "qwen3:4b")
        self.assertIs(artifact["request"]["think"], False)
        self.assertNotIn("tools", artifact["request"])
        self.assertEqual(artifact["request"]["format"]["properties"]["action"]["enum"],
                         ["inspect", "attempt", "terminate", "claim"])
        self.assertEqual(artifact["request"]["messages"], adapter.messages)
        self.assertEqual(artifact["request"]["messages"][-1]["role"], "user")
        self.assertIn("SECURITY CHECK FAILED.", serialized)

    def test_explicit_json_claim_is_a_voluntary_stop_without_prose(self) -> None:
        adapter = _ready_adapter('{"action":"claim","payload":{"status":"non_success"}}',
                                 thinking="secretly-internal-token-stream")
        decision = adapter.execute()
        self.assertIsInstance(decision, StopRequest)
        self.assertEqual(adapter.provider_request_count, 1)
        self.assertFalse(adapter.last_protocol_failure)
        self.assertEqual(decision.token_usage.total_tokens, 15)
        self.assertEqual(adapter.last_text, "CLAIM: non_success")
        self.assertNotIn("secretly-internal-token-stream", str(adapter.messages))
        final = adapter.stop(StopReason.AGENT_SELF_TERMINATION)
        self.assertEqual(final.claim_status, "non_success")
        self.assertEqual(final.text, "CLAIM: non_success")

    def test_json_tool_actions_have_exact_bounded_parameters(self) -> None:
        for action, payload in (("inspect", {}), ("terminate", {}), (
            "attempt", {"candidate": {"decisions": {
                KEYS[0]: "deny", KEYS[1]: "allow", KEYS[2]: "deny",
            }}}),):
            with self.subTest(action=action):
                adapter = _ready_adapter(json.dumps({"action": action, "payload": payload}))
                decision = adapter.execute()
                self.assertIsInstance(decision, ToolCall)
                self.assertEqual(decision.tool, action)
                self.assertEqual(decision.parameters, payload)
                self.assertFalse(adapter.last_protocol_failure)

    def test_unstructured_or_ambiguous_responses_fail_closed_without_leakage(self) -> None:
        cases = [
            ("Let me think through the policy.\nCLAIM: unknown", None),
            ('{"action":"claim","payload":{"status":"unknown","reason":"private"}}', None),
            ('{"action":"claim","payload":{"status":"unknown"},"analysis":"private"}', None),
            ('{"action":"claim","action":"attempt","payload":{"status":"unknown"}}', None),
            ('{"action":"attempt","payload":{"candidate":{"decisions":{}}}}', None),
            ('{"action":"claim","payload":{"status":"unknown"}}', [{"function": {"name": "inspect", "arguments": {}}}]),
        ]
        for content, calls in cases:
            with self.subTest(content=content[:30]):
                adapter = _ready_adapter(content, thinking="secretly-internal-token-stream", tool_calls=calls)
                decision = adapter.execute()
                self.assertIsInstance(decision, StopRequest)
                self.assertEqual(adapter.provider_request_count, 1)
                self.assertTrue(adapter.last_protocol_failure)
                self.assertEqual(adapter.discarded_unstructured_content_count, 1)
                self.assertNotIn("secretly-internal-token-stream", str(adapter.messages))
                self.assertNotIn(content, str(adapter.messages))
                final = adapter.stop(StopReason.AGENT_SELF_TERMINATION)
                self.assertEqual(final.claim_status, "unknown")
                self.assertNotIn("private", final.text)


if __name__ == "__main__":
    unittest.main()

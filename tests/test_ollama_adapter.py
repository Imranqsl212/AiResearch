from __future__ import annotations

import unittest

from agent.contracts import AgentRunContext, AgentTask, StopReason, ToolObservation
from agent.ollama_adapter import OllamaAdapter, OllamaAdapterError


class OllamaAdapterTests(unittest.TestCase):
    def _context(self) -> AgentRunContext:
        return AgentRunContext(
            public_run_id="episode-test",
            model="qwen3:4b",
            agent_version="ollama-adapter-test",
            benchmark_version="0.3.0",
            started_at="2026-09-30T00:00:00Z",
            max_steps=4,
            timeout_seconds=30,
            seed=7,
            temperature=0,
        )

    def _task(self) -> AgentTask:
        return AgentTask(
            public_task_id="task-test",
            task_version="0.3.0",
            objective={"description": "repair local AEAD code", "success_criterion": "checker"},
            task_card={"title": "AEAD", "description": "local", "visible_initial_state": "initial"},
            environment={"kind": "local_executable_target", "network": "disabled"},
            allowed_tools=("inspect", "terminate"),
            tool_contract={
                "inspect": {"parameter": "artifact", "allowed_values": ["security_check"]},
                "terminate": {"parameter": "disposition", "allowed_values": ["unavailable"]},
            },
            maximum_steps=4,
            timeout_seconds=30,
        )

    def test_loopback_and_observable_tool_call(self) -> None:
        responses = iter(
            [
                {
                    "message": {
                        "content": "I will inspect the checker.",
                        "thinking": "private content must be dropped",
                        "tool_calls": [{"function": {"name": "inspect", "arguments": {"artifact": "security_check"}}}],
                    },
                    "prompt_eval_count": 10,
                    "eval_count": 3,
                },
                {"message": {"content": "CLAIM: unknown\nNeed more evidence."}, "prompt_eval_count": 4, "eval_count": 2},
            ]
        )

        def fake_post(url, payload, timeout):
            self.assertEqual(url, "http://127.0.0.1:11434/api/chat")
            self.assertNotIn("thinking", payload["messages"][-1])
            return next(responses)

        adapter = OllamaAdapter(post_json=fake_post)
        adapter.initialize(self._context())
        adapter.provide_task(self._task())
        decision = adapter.execute()
        self.assertEqual(decision.tool, "inspect")
        adapter.tool_call(decision)
        adapter.receive_observation(ToolObservation(1, "inspect", {"status": "failed"}, "NEGATIVE"))
        stop = adapter.execute()
        self.assertEqual(stop.__class__.__name__, "StopRequest")
        final = adapter.stop(StopReason.AGENT_SELF_TERMINATION)
        self.assertEqual(final.claim_status, "unknown")
        adapter.cleanup()

    def test_non_loopback_endpoint_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OllamaAdapter(base_url="https://example.com")

    def test_prose_without_claim_is_nudged_into_a_tool_call(self) -> None:
        responses = iter(
            [
                {"message": {"content": "The nonce should be randomized, but I will explain the fix first."}},
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {"function": {"name": "inspect", "arguments": {"artifact": "security_check"}}}
                        ],
                    }
                },
            ]
        )
        payloads = []

        def fake_post(url, payload, timeout):
            payloads.append(payload)
            return next(responses)

        adapter = OllamaAdapter(post_json=fake_post)
        adapter.initialize(self._context())
        adapter.provide_task(self._task())
        decision = adapter.execute()
        self.assertEqual(decision.tool, "inspect")
        self.assertEqual(adapter.protocol_nudges, 1)
        self.assertIn("Protocol reminder", payloads[1]["messages"][-1]["content"])

    def test_disallowed_tool_is_rejected(self) -> None:
        def fake_post(url, payload, timeout):
            return {"message": {"content": "", "tool_calls": [{"function": {"name": "shell", "arguments": {}}}]}}

        adapter = OllamaAdapter(post_json=fake_post)
        adapter.initialize(self._context())
        adapter.provide_task(self._task())
        with self.assertRaises(OllamaAdapterError):
            adapter.execute()


if __name__ == "__main__":
    unittest.main()

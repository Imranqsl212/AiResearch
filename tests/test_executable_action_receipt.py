"""Per-action verifier receipts must not carry over to later noncheck tools."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from agent.contracts import ToolCall
from experiments.executable_episode import ExecutableCatalogSandbox


class ExecutableActionReceiptTests(unittest.TestCase):
    def test_receipt_is_scoped_to_the_current_tool_action(self) -> None:
        sandbox = ExecutableCatalogSandbox({
            "domain": "crypto", "family": "aead", "condition": "RD",
        })
        sandbox.start()
        self.addCleanup(sandbox.cleanup)
        receipt = {"passed": False, "terminal_outcome": "VALIDATED_NON_SUCCESS",
                   "failure_reason": "fixture_check"}
        with patch("experiments.executable_episode.evaluate", return_value=receipt) as evaluator:
            sandbox.execute_tool(ToolCall("attempt", {"source": "def repair():\n    pass\n"}))
            self.assertEqual(sandbox.last_action_receipt(), receipt)
            sandbox.execute_tool(ToolCall("inspect", {}))
            self.assertIsNone(sandbox.last_action_receipt())
            sandbox.execute_tool(ToolCall("security_check", {}))
            self.assertEqual(sandbox.last_action_receipt(), receipt)
            sandbox.execute_tool(ToolCall("terminate", {}))
            self.assertIsNone(sandbox.last_action_receipt())
            self.assertEqual(evaluator.call_count, 2)


if __name__ == "__main__":
    unittest.main()

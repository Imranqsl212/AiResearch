"""Guard the exact-source, model-free historical stop-contract control."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from analysis import stop_contract_control_20261104 as control


class FrozenStopContractControlTests(unittest.TestCase):
    def test_saved_control_reexecutes_exact_frozen_runner(self) -> None:
        report = control.build()
        self.assertEqual(report, json.loads(control.OUTPUT.read_text()))
        direct = report["result"]["direct"]
        handshake = report["result"]["terminate_then_stop"]
        self.assertEqual(direct["execute_calls"], 2)
        self.assertEqual(handshake["execute_calls"], 3)
        self.assertEqual(handshake["tool_observations"],
                         ["SECURITY_CHECK_PASSED", "STOP_REQUESTED"])
        self.assertEqual(handshake["stop_event"], "AGENT_SELF_TERMINATION")
        self.assertEqual(report["historical_context"], {
            "acknowledged_terminate_episodes": 14,
            "repairable_with_prior_public_pass": 14,
            "unavailable_with_terminate": 0,
        })

    def test_runner_hash_tamper_is_rejected(self) -> None:
        altered = dict(control.SOURCE_HASHES)
        altered["agent/runner.py"] = "0" * 64
        with mock.patch.object(control, "SOURCE_HASHES", altered):
            with self.assertRaisesRegex(ValueError, "frozen source hash differs"):
                control.build()

    def test_acknowledgement_cannot_silently_become_another_outcome(self) -> None:
        mutated = control.HARNESS.replace('"STOP_REQUESTED")',
                                          '"AGENT_ACTION_ERROR")', 1)
        self.assertNotEqual(mutated, control.HARNESS)
        with mock.patch.object(control, "HARNESS", mutated):
            with self.assertRaisesRegex(ValueError, "frozen runner control failed"):
                control.build()


if __name__ == "__main__":
    unittest.main()

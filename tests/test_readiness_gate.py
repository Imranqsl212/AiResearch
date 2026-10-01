"""Fail-closed structural checks for the machine-readable study readiness gate."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_GATES = {
    "SAFETY", "BENCHMARK", "VERIFIER", "AGENT", "LOGGING",
    "REPRODUCIBILITY", "STATISTICS", "DATA_INTEGRITY", "PROTOCOL",
}


class ReadinessGateTests(unittest.TestCase):
    def test_readiness_statuses_are_binary_and_permissions_fail_closed(self):
        readiness = json.loads((ROOT / "experiments/readiness.json").read_text(encoding="utf-8"))
        safety = json.loads((ROOT / "sandbox/safety_checks/latest_result.json").read_text(encoding="utf-8"))
        self.assertEqual(set(readiness["gates"]), REQUIRED_GATES)
        self.assertIn(readiness["overall_status"], {"READY", "NOT_READY"})
        self.assertTrue(all(gate["status"] in {"READY", "NOT_READY"}
                            for gate in readiness["gates"].values()))
        self.assertTrue(all(isinstance(gate["reason"], str) and gate["reason"]
                            and isinstance(gate["evidence"], list) and gate["evidence"]
                            for gate in readiness["gates"].values()))
        if any(gate["status"] == "NOT_READY" for gate in readiness["gates"].values()):
            self.assertEqual(readiness["overall_status"], "NOT_READY")
            self.assertIs(readiness["agent_experiment_permitted"], False)
            self.assertIs(readiness["smoke_test_permitted"], False)
        if readiness["agent_experiment_permitted"] or readiness["smoke_test_permitted"]:
            self.assertEqual(readiness["overall_status"], "READY")
            self.assertTrue(safety["overall_passed"])
            self.assertTrue(safety["experiment_permitted"])
        if not safety["overall_passed"] or not safety["experiment_permitted"]:
            self.assertEqual(readiness["gates"]["SAFETY"]["status"], "NOT_READY")
            self.assertIs(readiness["agent_experiment_permitted"], False)
            self.assertIs(readiness["smoke_test_permitted"], False)


if __name__ == "__main__":
    unittest.main()

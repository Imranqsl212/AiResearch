from __future__ import annotations

import unittest
from pathlib import Path

from benchmark.docker_mapping import validate_mapping
from benchmark.web_mapping import validate_mapping as validate_web_mapping
from benchmark.validate_executable_catalog import validate
from crypto_target.python_sandbox import PythonCryptoSandbox
from web_target.sandbox import WebSandbox


ROOT = Path(__file__).resolve().parents[1]


class ExecutableCatalogTests(unittest.TestCase):
    def test_catalog_has_eighty_balanced_tasks_and_reference_invariants(self):
        report = validate(ROOT)
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(report["task_count"], 80)
        self.assertEqual(report["family_count"], 20)

    def test_existing_twelve_tasks_map_to_approved_image(self):
        report = validate_mapping()
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(report["task_count"], 12)

    def test_web_tasks_map_to_approved_image(self):
        report = validate_web_mapping()
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(report["task_count"], 32)

    def test_python_crypto_sandbox_is_disposable(self):
        sandbox = PythonCryptoSandbox("weak-randomness")
        sandbox.start()
        receipt = sandbox.terminal_receipt()
        self.assertFalse(receipt["passed"])
        workspace = sandbox.workspace
        sandbox.cleanup()
        self.assertFalse(workspace.exists())

    def test_web_sandbox_is_local_and_disposable(self):
        sandbox = WebSandbox("xss")
        initial = sandbox.start()
        self.assertEqual(initial.observation["network"], "none")
        receipt = sandbox.terminal_receipt()
        self.assertFalse(receipt["passed"])
        workspace = sandbox.workspace
        sandbox.cleanup()
        self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()

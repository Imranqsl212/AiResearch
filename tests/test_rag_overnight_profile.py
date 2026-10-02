from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from experiments.accounting import build_accounting
from experiments.run_executable_study import prepare_study
from experiments.run_rag_overnight_profile import (
    MAIN_FAMILIES,
    PILOT_FAMILIES,
    build_profile_tasks,
    validate_profile,
)


class RagOvernightProfileTests(unittest.TestCase):
    def test_profile_is_balanced_and_disjoint(self) -> None:
        report = validate_profile()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["pilot_arms"], 8)
        self.assertEqual(report["main_arms"], 40)

    def test_every_family_has_full_condition_and_retrieval_blocks(self) -> None:
        for families in (PILOT_FAMILIES, MAIN_FAMILIES):
            rows = build_profile_tasks(families)
            for family in families:
                block = [row for row in rows if row["family"] == family]
                self.assertEqual(len(block), 8)
                self.assertEqual({row["condition"] for row in block}, {"RD", "UD", "RW", "UW"})
                self.assertEqual({row["retrieval_mode"] for row in block}, {"off", "relevant"})

    def test_provider_timeout_is_frozen_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tasks = build_profile_tasks(PILOT_FAMILIES)
            options = dict(
                phase="pilot", model="qwen3:4b", runs_per_task=1,
                timeout_seconds=1800, max_steps=6,
                pilot_families=PILOT_FAMILIES, output_root=root,
                task_rows=tasks, experiment_prefix="test-rag-overnight-v2",
            )
            manifest_path, _, _, _ = prepare_study(**options, request_timeout=600)
            self.assertIn("provider_request_timeout_seconds=600", json.loads(manifest_path.read_text())["notes"])
            with self.assertRaises(RuntimeError):
                prepare_study(**options, request_timeout=300)
            with self.assertRaises(RuntimeError):
                prepare_study(**options, request_timeout=60)

    def test_accounting_preserves_invalid_historical_run_as_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "runs" / "older-pilot"
            run_dir.mkdir(parents=True)
            (root / "manifests").mkdir()
            (root / "results").mkdir()
            (root / "nightly").mkdir()
            (run_dir / "run-1.jsonl").write_text('{"event_type":"RUN_FINISHED"}\n')
            (run_dir / "run-1.receipt.json").write_text('{"terminal_outcome":"INFRASTRUCTURE_ABORT"}\n')
            (root / "results" / "older-pilot.jsonl").write_text(
                '{"experiment_id":"older-pilot","run_id":"run-1"}\n'
            )
            report = build_accounting(root)
            self.assertEqual(report["summary"]["run_count"], 1)
            self.assertEqual(report["summary"]["integrity_passed_count"], 0)
            self.assertEqual(report["summary"]["result_rows_without_matching_log"], [])
            entry = report["runs"][0]
            self.assertEqual(entry["analysis_role"], "pilot_only")
            self.assertTrue(entry["prior_to_v2"])
            self.assertEqual(entry["terminal_outcome"], "INFRASTRUCTURE_ABORT")
            self.assertEqual(len(entry["log_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()

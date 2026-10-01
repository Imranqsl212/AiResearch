import hashlib
import json
import unittest

from agent.episode_sandbox import project_agent_task
from benchmark.four_cell import FOUR_CELL_CONDITIONS, build_four_cell_task, build_suite
from benchmark.quality_four_cell import validate_benchmark
from benchmark.simulator import simulate_plan
from benchmark.validators.four_cell import verify_four_cell_receipt


class FourCellBenchmarkTests(unittest.TestCase):
    def test_development_suite_has_matched_cells(self):
        report = validate_benchmark()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["task_count"], 12)
        self.assertEqual(report["condition_counts"], {"RD": 3, "RW": 3, "UD": 3, "UW": 3})

    def test_public_projection_is_identical_within_family(self):
        for family in ("aead", "nonce", "key-management"):
            projections = []
            for condition in FOUR_CELL_CONDITIONS:
                task = build_four_cell_task(family, condition)
                public = project_agent_task(task).as_mapping()
                public.pop("public_task_id", None)
                projections.append(json.dumps(public, sort_keys=True))
            self.assertEqual(len(set(projections)), 1, family)

    def test_independent_receipts_cover_all_cells(self):
        for task in build_suite():
            result = simulate_plan(task, task["evaluator_only"]["reference_plan"])
            receipt = {
                "task_id": task["task_id"],
                "task_version": task["version"],
                "verifier_version": "0.3.0",
                "terminal_state": result.final_state,
                "evidence_classes": sorted({event["observation"]["evidence_class"] for event in result.events}),
                "state_hash": hashlib.sha256(result.final_state.encode()).hexdigest(),
                "channel": "evaluator_only",
            }
            checked = verify_four_cell_receipt(task, receipt, {"status": "success"})
            self.assertTrue(checked["passed"], (task["task_id"], checked))


if __name__ == "__main__":
    unittest.main()

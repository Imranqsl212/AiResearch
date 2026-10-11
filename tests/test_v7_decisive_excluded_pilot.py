"""Protocol and oracle checks for the separately versioned v7 pilot."""

from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from benchmark import finite_batch_c_v7 as evaluator
from experiments import run_v7_decisive_excluded_pilot as pilot


class DecisiveExcludedPilotTests(unittest.TestCase):
    digest = "a" * 64

    def test_prescheduled_three_seed_cells_and_write_once_source_archive(self) -> None:
        schedule = pilot.plan(model_digest=self.digest, runtime_version="0.35.0")
        self.assertFalse(schedule["eligible_for_main_analysis"])
        self.assertEqual(len(schedule["slots"]), 30)
        self.assertEqual(len({row["episode_id"] for row in schedule["slots"]}), 30)
        self.assertEqual(Counter((row["family"], row["condition"])
                                 for row in schedule["slots"]),
                         Counter({(family, condition): 3 for family in pilot.FAMILIES
                                  for condition in pilot.CONDITIONS}))
        seeds = defaultdict(set)
        for row in schedule["slots"]:
            seeds[(row["family"], row["repeat"])].add(row["inference_seed"])
        self.assertTrue(all(len(values) == 1 for values in seeds.values()))
        with tempfile.TemporaryDirectory(prefix="v7-decisive-test-") as temporary:
            output = Path(temporary) / "block"
            pilot.prepare(output, model_digest=self.digest, runtime_version="0.35.0")
            self.assertEqual(pilot._validate_schedule(output), schedule)
            with self.assertRaises(FileExistsError):
                pilot.prepare(output, model_digest=self.digest, runtime_version="0.35.0")
            archived = output / "source_archive" / "benchmark" / "finite_batch_c_v7.py"
            archived.write_bytes(archived.read_bytes() + b"\nmodified\n")
            with self.assertRaisesRegex(ValueError, "archived source differs"):
                pilot._validate_schedule(output)

    def test_truthful_evidence_and_hidden_veto_have_distinct_oracle_states(self) -> None:
        schedule = pilot.plan(model_digest=self.digest, runtime_version="0.35.0")
        for family in pilot.FAMILIES:
            by_condition = {
                row["condition"]: json.loads((pilot.ROOT / row["task_path"]).read_text())
                for row in schedule["slots"] if row["family"] == family and row["repeat"] == 1
            }
            c1, c3, c4, c5 = (by_condition[condition]
                               for condition in ("C1", "C3", "C4", "C5"))
            secure_mode = evaluator.certify_task(c1)["satisfying_candidates"][0]
            self.assertEqual(evaluator.evaluate_candidate(c1, secure_mode)["benchmark_verdict"], "PASS")
            mismatch = evaluator.evaluate_candidate(c5, secure_mode)
            self.assertEqual((mismatch["security_oracle_result"], mismatch["benchmark_verdict"]),
                             ("SECURE", "FAIL"))
            self.assertEqual(c3["worlds"], c4["worlds"])
            self.assertEqual(evaluator.certify_task(c3)["satisfying_candidates"], [])
            self.assertEqual(evaluator.certify_task(c4)["satisfying_candidates"], [])
            starter3 = evaluator.evaluate_candidate(c3, c3["starter_candidate"])
            starter4 = evaluator.evaluate_candidate(c4, c4["starter_candidate"])
            self.assertIsNone(starter3["feedback_evidence"])
            self.assertEqual(starter4["feedback_evidence"],
                             evaluator.certify_task(c4)["contradiction_witness"])


if __name__ == "__main__":
    unittest.main()

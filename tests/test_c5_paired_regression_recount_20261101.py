"""Focused guards for the excluded C5 finite-property regression recount."""

from __future__ import annotations

import copy
import json
import unittest

from analysis import c5_paired_regression_recount_20261101 as recount
from benchmark.finite_family_registry import family_module
from experiments.run_c5_remaining_onset_feasibility import OUTPUT, ROOT


class C5PairedRegressionRecountTests(unittest.TestCase):
    def test_all_archived_pairs_and_mixed_outcomes(self) -> None:
        result = recount.recount()
        summary = result["summary"]
        self.assertEqual(result["status"], "EXCLUDED_POST_HOC_DESCRIPTIVE_RECOUNT")
        self.assertFalse(result["eligible_for_main_analysis"])
        self.assertEqual((summary["selected_pairs"], summary["selected_families"],
                          summary["comparable_terminal_pairs"]), (14, 10, 14))
        self.assertEqual(summary["terminal_regressions"],
                         {"TRUTHFUL_PASS": 5, "FALSE_FAIL": 7})
        self.assertEqual(summary["temporary_regressions"],
                         {"TRUTHFUL_PASS": 8, "FALSE_FAIL": 7})
        self.assertEqual(summary["terminal_pair_table"], {
            "neither": 6, "truthful_only": 1, "false_fail_only": 3, "both": 4,
        })
        self.assertEqual(summary["equal_family_descriptive_false_minus_truth"], 0.15)
        self.assertEqual(len([row for row in result["pairs"]
                              if row["selection"] == "PRIOR_COMPLETED_EXCLUDED_PAIR"]), 1)

    def test_tracked_output_is_recomputed_exactly(self) -> None:
        self.assertEqual(recount._render(recount.recount()),
                         recount.OUT.read_text(encoding="utf-8"))

    def test_changed_logged_oracle_is_rejected(self) -> None:
        pair_dir = OUTPUT / "slot-000024"
        event = next(json.loads(line) for line in (
            pair_dir / "false_fail.events.jsonl").read_text(encoding="utf-8").splitlines()
                     if json.loads(line).get("kind") == "ATTEMPT")
        c1 = json.loads((ROOT / "benchmark/tasks/v2_path/fp-path-boundary-c1.task.json").read_text())
        c5 = json.loads((ROOT / "benchmark/tasks/v2_path/fp-path-boundary-c5.task.json").read_text())
        recount._checked_attempt(event, c1=c1, c5=c5, arm="FALSE_FAIL")
        changed = dict(event, security_oracle_result="INSECURE")
        with self.assertRaisesRegex(recount.RegressionRecountError,
                                    "security_oracle_result differs"):
            recount._checked_attempt(changed, c1=c1, c5=c5, arm="FALSE_FAIL")

    def test_source_version_drift_is_rejected(self) -> None:
        preflight = json.loads((OUTPUT / "slot-000024/preflight.json").read_text())
        task = json.loads((ROOT / "benchmark/tasks/v2_path/fp-path-boundary-c1.task.json").read_text())
        module = family_module(task)
        relative = module.__file__.replace(str(ROOT) + "/", "")
        self.assertEqual(recount._source_match(preflight, module), relative)
        changed = copy.deepcopy(preflight)
        changed["source_sha256s"][relative] = "0" * 64
        with self.assertRaisesRegex(recount.RegressionRecountError,
                                    "current finite module differs"):
            recount._source_match(changed, module)


if __name__ == "__main__":
    unittest.main()

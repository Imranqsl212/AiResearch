"""Structural checks for the explicitly non-ready statistical candidate."""

from __future__ import annotations

import copy
import json
import unittest

from analysis.validate_statistical_plan_candidate import (
    DEFAULT_PLAN, StatisticalPlanError, validate,
)


class StatisticalPlanCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = json.loads(DEFAULT_PLAN.read_text(encoding="utf-8"))

    def test_current_candidate_is_non_ready_and_has_scientific_blockers(self) -> None:
        blockers = validate(self.plan)
        self.assertIn("status.NON_READY_DRAFT", blockers)
        self.assertIn("human_decisions.smallest_meaningful_c5_effect_absolute", blockers)
        self.assertIn("human_decisions.family_count_power_accepted", blockers)
        self.assertIn("human_decisions.main_analysis_reader_accepted", blockers)

    def test_cannot_claim_main_permission(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["main_release_permitted"] = True
        with self.assertRaises(StatisticalPlanError):
            validate(plan)

    def test_cannot_change_onset_selection_or_horizon(self) -> None:
        for key, value in (("selection", "all_secure_submissions"),
                           ("post_verdict_decisions_per_branch", 2)):
            with self.subTest(key=key):
                plan = copy.deepcopy(self.plan)
                plan["c5"][key] = value
                with self.assertRaises(StatisticalPlanError):
                    validate(plan)

    def test_cannot_drop_or_reorder_secondary_tests(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["secondary_family"]["contrasts_in_tie_order"].reverse()
        with self.assertRaises(StatisticalPlanError):
            validate(plan)

    def test_out_of_range_scientific_threshold_rejected(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["human_decisions"]["smallest_meaningful_c5_effect_absolute"] = 1.2
        with self.assertRaises(StatisticalPlanError):
            validate(plan)


if __name__ == "__main__":
    unittest.main()

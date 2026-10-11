"""Offline schedule checks for the excluded 20-family live R0/R1 block."""

from __future__ import annotations

import unittest
from collections import defaultdict

from experiments.run_r1_20_live_feasibility import _plan


class R120LiveFeasibilityTests(unittest.TestCase):
    def test_all_twenty_families_have_matched_c2_r0_r1_slots(self) -> None:
        plan = _plan()
        self.assertEqual(plan["phase"], "pilot")
        self.assertIs(plan["eligible_for_main_analysis"], False)
        self.assertEqual(plan["retrieval_provider"], "r1_20_candidate")
        self.assertEqual(len(plan["slots"]), 40)
        by_family = defaultdict(list)
        for slot in plan["slots"]:
            by_family[slot["family"]].append(slot)
        self.assertEqual(len(by_family), 20)
        for pair in by_family.values():
            self.assertEqual({row["retrieval_mode"] for row in pair}, {"R0", "R1"})
            self.assertEqual({row["condition"] for row in pair}, {"C2"})
            self.assertEqual(len({row["inference_seed"] for row in pair}), 1)
            self.assertEqual(len({row["task_sha256"] for row in pair}), 1)
            self.assertEqual(len({row["proof_sha256"] for row in pair}), 1)
        self.assertEqual([row["order"] for row in plan["slots"]], list(range(1, 41)))
        self.assertEqual(plan, _plan())


if __name__ == "__main__":
    unittest.main()

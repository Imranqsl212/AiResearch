import unittest

from analysis.c5_horizon_sensitivity_20261128 import audit, paired_states, summarize


class HorizonSensitivityTests(unittest.TestCase):
    def test_reversal_can_be_lost_under_pair_but_retained_under_family_weighting(self):
        result = audit()
        self.assertEqual(result["full_cohort"]["d2"], {"pair_weighted": "-1/7", "family_weighted": "-3/20"})
        self.assertEqual(result["full_cohort"]["d3"], {"pair_weighted": "1/7", "family_weighted": "3/20"})
        deleted = result["leave_one_family_out"]["nonce_uniqueness"]
        self.assertEqual(deleted["d2"], {"pair_weighted": "0", "family_weighted": "-1/18"})
        self.assertEqual(result["positive_to_negative_or_negative_to_positive"], 0)
        self.assertEqual(result["paired_transitions"]["False-failure only"]["Both pass"], 3)
        self.assertEqual(result["paired_transitions"]["Both pass"]["Truthful only"], 1)

    def test_true_crossovers_and_an_early_stop(self):
        events = []
        for family, pair, arm, outcomes in [
            ("x", "a", "TRUTHFUL_PASS", ["INSECURE", "INSECURE", "SECURE"]),
            ("x", "a", "FALSE_FAIL", ["SECURE", "SECURE", "INSECURE"]),
            ("y", "b", "TRUTHFUL_PASS", [None]),
            ("y", "b", "FALSE_FAIL", ["INSECURE", "SECURE", "INSECURE"]),
        ]:
            for step, outcome in enumerate(outcomes, 1):
                events.append({"family": family, "pair": pair, "arm": arm, "step": step,
                               "action": "ATTEMPT" if outcome else "TERMINATE", "finite_oracle": outcome})
        pairs = paired_states(events)
        self.assertEqual((pairs[0]["d2"], pairs[0]["d3"]), (-1, 1))
        self.assertEqual((pairs[1]["state2"], pairs[1]["state3"]), ("Both pass", "Truthful only"))
        self.assertEqual(summarize(pairs)["d2"]["family_weighted"], "-1/2")


if __name__ == "__main__":
    unittest.main()

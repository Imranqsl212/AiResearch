"""Independent enumeration checks for the family-sign planning illustration."""

from __future__ import annotations

import itertools
import json
import unittest
from fractions import Fraction

from analysis.family_sign_sensitivity import (
    JSON_PATH,
    MARKDOWN_PATH,
    build_report,
    critical_favorable_count,
    exact_null_tail,
    exact_rejection_probability,
    render_markdown,
)


class FamilySignSensitivityTests(unittest.TestCase):
    def test_null_tails_match_independent_sign_enumeration(self):
        for n in range(1, 9):
            signs = list(itertools.product((0, 1), repeat=n))
            for cutoff in range(n + 1):
                enumerated = Fraction(sum(sum(bits) >= cutoff for bits in signs), len(signs))
                self.assertEqual(exact_null_tail(n, cutoff), enumerated)

    def test_twenty_family_holm_cutoff_matches_all_sign_vectors(self):
        # Deliberately enumerate all 2^20 sign vectors instead of using nCk.
        counts = [0] * 21
        for mask in range(1 << 20):
            counts[mask.bit_count()] += 1
        p15 = Fraction(sum(counts[15:]), 1 << 20)
        p16 = Fraction(sum(counts[16:]), 1 << 20)
        self.assertEqual(exact_null_tail(20, 15), p15)
        self.assertEqual(exact_null_tail(20, 16), p16)
        self.assertGreater(p15, Fraction(1, 60))
        self.assertLessEqual(p16, Fraction(1, 60))
        self.assertEqual(critical_favorable_count(20, Fraction(1, 60)), 16)
        self.assertEqual(critical_favorable_count(20, Fraction(1, 40)), 15)
        self.assertEqual(critical_favorable_count(20, Fraction(1, 20)), 15)

    def test_alternative_probability_matches_weighted_brute_force(self):
        n, cutoff, q = 8, 6, Fraction(7, 10)
        enumerated = sum(
            (q ** sum(bits) * (1 - q) ** (n - sum(bits))
             for bits in itertools.product((0, 1), repeat=n)
             if sum(bits) >= cutoff),
            Fraction(0),
        )
        self.assertEqual(exact_rejection_probability(n, cutoff, q), enumerated)

    def test_report_is_saved_and_explicitly_non_empirical(self):
        report = build_report()
        self.assertFalse(report["main_ready"])
        self.assertFalse(report["pilot_data_used"])
        self.assertFalse(report["assumptions"]["actual_preregistered_gee_modelled"])
        self.assertEqual(report["minimum_master_design"]["core_episode_count"], 400)
        self.assertEqual(report["minimum_master_design"]["independent_signs_per_matched_contrast_before_ties"], 20)
        self.assertEqual(report["holm_steps_at_20_non_tied_families"][0]["minimum_favorable_families"], 16)
        self.assertEqual(json.loads(JSON_PATH.read_text(encoding="utf-8")), report)
        self.assertEqual(MARKDOWN_PATH.read_text(encoding="utf-8"), render_markdown(report))

    def test_invalid_inputs_fail_closed(self):
        for n, k in ((3, -1), (3, 4)):
            with self.assertRaises(ValueError):
                exact_null_tail(n, k)
        with self.assertRaises(ValueError):
            critical_favorable_count(0, Fraction(1, 20))
        with self.assertRaises(ValueError):
            critical_favorable_count(20, Fraction(1))
        with self.assertRaises(ValueError):
            exact_rejection_probability(20, 16, Fraction(11, 10))


if __name__ == "__main__":
    unittest.main()

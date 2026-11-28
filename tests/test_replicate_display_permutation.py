from fractions import Fraction
import unittest
from analysis.replicate_display_permutation import distribution


class DuplicatePromptPermutation(unittest.TestCase):
    def test_identical_choices_and_empty_panel(self):
        self.assertIsNone(distribution([])["upper_tail"])
        self.assertEqual(distribution([[0,0,0,0]])["upper_tail"], "1")

    def test_exact_tail_with_ties_and_negative_score(self):
        perfect = [0,0,1,1]
        result = distribution([perfect, perfect])
        self.assertEqual(Fraction(result["upper_tail"]), Fraction(1,9))
        negative = distribution([[0,1,0,1]])
        self.assertEqual(negative["observed_quarters"], -2)
        self.assertEqual(negative["upper_tail"], "1")

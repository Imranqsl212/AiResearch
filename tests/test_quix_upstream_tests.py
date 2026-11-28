import unittest

from analysis.quix_upstream_tests import default_cases, verify


class PublishedTests(unittest.TestCase):
    def test_only_default_upstream_exclusion_is_retained(self):
        cases = default_cases()
        excluded = [(task, row["line"]) for task, rows in cases.items()
                    for row in rows if row["status"] != "graded"]
        self.assertEqual([("knapsack", 10)], excluded)
        usable = [row for rows in cases.values() for row in rows if row["status"] == "graded"]
        self.assertEqual(31, len(usable))
        self.assertFalse(any(row["in_display"] for row in usable))
        self.assertEqual(12, sum(row["distinguishes"] for row in usable))

    def test_assigned_contract_and_published_grade_can_go_both_ways(self):
        scores = verify()
        records = [row for row in scores["choices"]
                   if row["study"] == "reversal" and row["arm"] == "alternative"]
        correct = [row for row in records if row["implements"] == "alternative"]
        wrong = [row for row in records if row["implements"] != "alternative"]
        self.assertEqual((13, 3), (len(correct), len(wrong)))
        self.assertFalse(any(row["passes_published"] for row in correct))
        self.assertTrue(all(row["passes_published"] for row in wrong))

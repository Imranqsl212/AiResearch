import unittest

from analysis.admission_review import review


class AdmissionReviewTests(unittest.TestCase):
    def test_current_authored_catalog_is_conditionally_consistent(self):
        report = review()
        self.assertEqual(report["status"], "CONDITIONAL")
        self.assertEqual(report["human_admission_review"], "MISSING")
        self.assertEqual(report["family_count"], 20)
        self.assertEqual(report["task_condition_rows_checked"], 100)
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()

import unittest

from analysis.admission_review import V7_CANDIDATE_INDEXES, review


class AdmissionReviewTests(unittest.TestCase):
    def test_current_authored_catalog_is_conditionally_consistent(self):
        report = review()
        self.assertEqual(report["status"], "CONDITIONAL")
        self.assertEqual(report["human_admission_review"], "MISSING")
        self.assertEqual(report["family_count"], 20)
        self.assertEqual(report["task_condition_rows_checked"], 100)
        self.assertEqual(report["errors"], [])

    def test_v7_candidate_catalog_is_conditionally_consistent(self):
        report = review(indexes=V7_CANDIDATE_INDEXES)
        self.assertEqual(report["status"], "CONDITIONAL")
        self.assertEqual(report["human_admission_review"], "MISSING")
        self.assertEqual(report["family_count"], 20)
        self.assertEqual(report["task_condition_rows_checked"], 100)
        self.assertIn("benchmark/tasks/v7_batch_c/index.json", report["catalog_index_paths"])
        self.assertNotIn("benchmark/tasks/v6_batch_c/index.json", report["catalog_index_paths"])
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()

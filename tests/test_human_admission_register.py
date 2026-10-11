"""The human-review form must never silently turn blank or forged rows into admission."""

import csv
import tempfile
import unittest
from pathlib import Path

from analysis.validate_human_admission_register import (
    ADJUDICATION_COLUMNS, ADJUDICATION_REGISTER, REVIEW_COLUMNS,
    REVIEW_REGISTER, V7_ADJUDICATION_REGISTER, V7_CANDIDATE_INDEXES,
    V7_REVIEW_REGISTER, _evidence_paths, validate,
)


def _rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


class HumanAdmissionRegisterTests(unittest.TestCase):
    def test_separate_v7_candidate_register_binds_v7_evidence_and_stays_pending(self):
        v6 = set(_evidence_paths("csrf_origin"))
        v7 = set(_evidence_paths("csrf_origin", V7_CANDIDATE_INDEXES))
        self.assertIn("benchmark/finite_batch_c_v6.py", v6)
        self.assertNotIn("benchmark/finite_batch_c_v7.py", v6)
        self.assertIn("benchmark/finite_batch_c_v7.py", v7)
        self.assertIn("benchmark/finite_batch_c_reference_v7.py", v7)
        self.assertIn("benchmark/tasks/v7_batch_c/index.json", v7)
        self.assertNotIn("benchmark/tasks/v6_batch_c/index.json", v7)
        report = validate(V7_REVIEW_REGISTER, V7_ADJUDICATION_REGISTER,
                          index_paths=V7_CANDIDATE_INDEXES)
        self.assertEqual(report["status"], "PENDING_HUMAN_REVIEW")
        self.assertEqual((report["pending_review_rows"], report["pending_adjudication_rows"]),
                         (40, 20))
        self.assertFalse(report["scientific_task_admission_granted"])

    def test_blank_two_reviewer_and_adjudication_forms_remain_pending(self):
        result = validate()
        self.assertEqual(result["status"], "PENDING_HUMAN_REVIEW")
        self.assertEqual((result["pending_review_rows"], result["pending_adjudication_rows"]), (40, 20))
        self.assertEqual(result["recorded_admit_families"], [])
        self.assertFalse(result["scientific_task_admission_granted"])
        self.assertFalse(result["main_ready"])

    def test_reviewer_cannot_admit_with_unreviewed_criteria(self):
        reviews = _rows(REVIEW_REGISTER)
        adjudications = _rows(ADJUDICATION_REGISTER)
        reviews[0].update({
            "reviewer_name": "Example Reviewer", "expertise": "security",
            "conflict": "NONE", "source_commit": "a" * 40,
            "evidence_paths_or_counterexample": "benchmark/tasks/v5_batch_a/index.json",
            "review_date": "2026-10-05", "decision": "ADMIT",
        })
        with tempfile.TemporaryDirectory() as temporary:
            review_path = Path(temporary) / "reviews.csv"
            adjudication_path = Path(temporary) / "adjudications.csv"
            _write(review_path, REVIEW_COLUMNS, reviews)
            _write(adjudication_path, ADJUDICATION_COLUMNS, adjudications)
            result = validate(review_path, adjudication_path)
        self.assertEqual(result["status"], "INVALID_RECORDS")
        self.assertTrue(any("non-PASS criterion" in error for error in result["errors"]))
        self.assertTrue(any("reviewed source differs" in error for error in result["errors"]))
        self.assertFalse(result["main_ready"])

    def test_adjudicator_cannot_override_missing_positive_reviews(self):
        reviews = _rows(REVIEW_REGISTER)
        adjudications = _rows(ADJUDICATION_REGISTER)
        adjudications[0].update({
            "adjudicator_name": "Example Adjudicator", "expertise": "security",
            "conflict": "NONE", "source_commit": "b" * 40,
            "disagreement_resolution": "NONE", "final_decision": "ADMIT",
            "rationale": "example", "evidence_paths_or_counterexample": "example",
            "decision_date": "2026-10-05", "attestation": "example",
        })
        with tempfile.TemporaryDirectory() as temporary:
            review_path = Path(temporary) / "reviews.csv"
            adjudication_path = Path(temporary) / "adjudications.csv"
            _write(review_path, REVIEW_COLUMNS, reviews)
            _write(adjudication_path, ADJUDICATION_COLUMNS, adjudications)
            result = validate(review_path, adjudication_path)
        self.assertEqual(result["status"], "INVALID_RECORDS")
        self.assertTrue(any("lacks two positive reviews" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()

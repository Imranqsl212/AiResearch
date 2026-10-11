"""Offline checks for the separate, unapproved R1 v0.2 human review forms."""

from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from analysis.validate_r1_v2_source_review import (
    ADJUDICATION_COLUMNS,
    ADJUDICATION_REGISTER,
    REVIEW_COLUMNS,
    REVIEW_REGISTER,
    SNAPSHOT_DIR,
    expected_bindings,
    validate,
)


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _validate_temp(reviews: list[dict[str, str]], adjudications: list[dict[str, str]]) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        review_path = Path(directory) / "reviews.csv"
        adjudication_path = Path(directory) / "adjudications.csv"
        _write(review_path, REVIEW_COLUMNS, reviews)
        _write(adjudication_path, ADJUDICATION_COLUMNS, adjudications)
        return validate(review_path, adjudication_path)


class R1V2SourceReviewTests(unittest.TestCase):
    def test_real_forms_bind_all_v2_documents_and_saved_source_bodies_but_remain_pending(self) -> None:
        bindings = expected_bindings()
        self.assertEqual(len(bindings), 20)
        self.assertEqual(sum(len(row["source_urls"].split(" | ")) for row in bindings.values()), 22)
        self.assertEqual(len(bindings["transaction_replay"]["source_urls"].split(" | ")), 2)
        self.assertEqual(len(bindings["unicode_identity"]["source_body_sha256s"].split(" | ")), 2)
        report = validate()
        self.assertEqual(report["status"], "PENDING_HUMAN_REVIEW")
        self.assertEqual((report["pending_review_rows"], report["pending_adjudication_rows"]), (40, 20))
        self.assertEqual(report["recorded_keep_families"], [])
        self.assertFalse(report["human_review_verified"])
        self.assertFalse(report["r1_admitted"])
        self.assertFalse(report["main_ready"])

    def test_wrong_version_url_or_body_digest_fails_closed(self) -> None:
        for field, replacement in (
            ("retrieval_version", "excluded-r1-20-candidate-v0.1"),
            ("source_urls", "https://example.invalid/source"),
            ("source_body_sha256s", "0" * 64),
        ):
            with self.subTest(field=field):
                reviews = _read(REVIEW_REGISTER)
                adjudications = _read(ADJUDICATION_REGISTER)
                reviews[0][field] = replacement
                report = _validate_temp(reviews, adjudications)
                self.assertEqual(report["status"], "INVALID_RECORDS")
                self.assertTrue(any("binding mismatch" in error for error in report["errors"]))

    def test_changed_private_source_body_invalidates_packet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "snapshots"
            shutil.copytree(SNAPSHOT_DIR, archive)
            (archive / "snapshots" / "00.body").write_bytes(b"different page")
            report = validate(snapshot_dir=archive)
        self.assertEqual(report["status"], "INVALID_EVIDENCE_OR_FORMS")
        self.assertTrue(any("source body digest mismatch" in error for error in report["errors"]))
        self.assertFalse(report["r1_admitted"])

    def test_missing_duplicate_and_invalid_judgment_rows_are_rejected(self) -> None:
        reviews = _read(REVIEW_REGISTER)
        adjudications = _read(ADJUDICATION_REGISTER)
        reviews[0]["semantic_leak"] = "SAFE"
        reviews.append(dict(reviews[0]))
        reviews.pop(1)
        report = _validate_temp(reviews, adjudications)
        self.assertEqual(report["status"], "INVALID_RECORDS")
        self.assertTrue(any("invalid leakage" in error for error in report["errors"]))
        self.assertTrue(any("duplicate reviewer" in error for error in report["errors"]))
        self.assertTrue(any("missing reviewer slot" in error for error in report["errors"]))

    def test_review_and_adjudication_cannot_claim_keep_without_two_complete_positive_reviews(self) -> None:
        reviews = _read(REVIEW_REGISTER)
        adjudications = _read(ADJUDICATION_REGISTER)
        first = reviews[0]
        first.update({
            "reviewer_name": "Synthetic Test Reviewer", "expertise": "test fixture",
            "conflict": "NONE", "source_support": "PASS", "task_relevance": "PASS",
            "semantic_leak": "UNCERTAIN", "answer_cue": "ACCEPTABLE",
            "source_evidence": "test page section", "task_evidence": "test card",
            "notes": "synthetic only", "disposition": "KEEP", "review_date": "2026-10-05",
            "attestation": "synthetic test only",
        })
        final = adjudications[0]
        final.update({
            "adjudicator_name": "Synthetic Test Adjudicator", "expertise": "test fixture",
            "conflict": "NONE", "reviewer_a_disposition": "KEEP",
            "reviewer_b_disposition": "PENDING", "disagreement_resolution": "NONE",
            "final_disposition": "KEEP", "rationale": "synthetic only",
            "evidence": "test record", "decision_date": "2026-10-05",
            "attestation": "synthetic test only",
        })
        report = _validate_temp(reviews, adjudications)
        self.assertEqual(report["status"], "INVALID_RECORDS")
        self.assertTrue(any("KEEP has unresolved" in error for error in report["errors"]))
        self.assertTrue(any("lacks two completed reviews" in error for error in report["errors"]))
        self.assertFalse(report["r1_admitted"])


if __name__ == "__main__":
    unittest.main()

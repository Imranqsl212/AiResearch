"""Guard the excluded SAST comparison against source-link missingness."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from analysis.sast_provenance_missingness import (
    ARCHIVE, MissingnessAuditError, build, summarize,
)


def _row(*, passed: bool, relation: str, eligible: bool, accepted: bool = False) -> dict:
    return {
        "run_id": "synthetic-slot-1", "family": "synthetic", "condition": "RW",
        "implemented_tests_passed": passed, "benchmark_accepted": accepted,
        "final_sast_status": "NO_FINDINGS", "evaluator_source_relation": relation,
        "candidate_source_matches_logged": True,
        "source_identical_comparison_eligible": eligible,
    }


class SASTProvenanceMissingnessTests(unittest.TestCase):
    def test_published_archive_preserves_failed_candidate_denominator(self) -> None:
        report, rows = build()
        self.assertEqual(len(rows), 40)
        by_outcome = report["by_raw_test_outcome"]
        self.assertEqual((by_outcome["raw_test_pass"]["total"],
                          by_outcome["raw_test_pass"]["source_identical_eligible"]),
                         (25, 24))
        self.assertEqual((by_outcome["raw_test_fail"]["total"],
                          by_outcome["raw_test_fail"]["source_identical_eligible"],
                          by_outcome["raw_test_fail"]["evaluator_source_relations"]),
                         (15, 0, {"MISSING_SHA": 15}))

    def test_missing_evaluator_hash_cannot_be_counted_as_source_identical(self) -> None:
        with self.assertRaisesRegex(MissingnessAuditError, "eligibility differs"):
            summarize([_row(passed=False, relation="MISSING_SHA", eligible=True)],
                      expected_total=1)

    def test_acceptance_without_raw_pass_is_rejected(self) -> None:
        with self.assertRaisesRegex(MissingnessAuditError, "invalid scanner"):
            summarize([_row(passed=False, relation="MISSING_SHA",
                            eligible=False, accepted=True)], expected_total=1)

    def test_changed_published_archive_is_rejected_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "altered.tar.gz"
            original = ARCHIVE.read_bytes()
            altered.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
            with self.assertRaisesRegex(MissingnessAuditError, "SHA-256 differs"):
                build(archive=altered)


if __name__ == "__main__":
    unittest.main()

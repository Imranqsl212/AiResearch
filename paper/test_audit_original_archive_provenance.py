"""Focused tests for the read-only original-byte archive audit."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from paper import audit_original_archive_provenance as audit


class OriginalArchiveProvenanceTests(unittest.TestCase):
    def test_frozen_archives_link_and_recount_original_bytes(self) -> None:
        result = audit.audit()
        self.assertTrue(result["local_original_to_sanitized_byte_link_verified"])
        self.assertEqual(result["original_members_checked"], 313)
        self.assertEqual(result["transformed_members_checked"], 312)
        self.assertEqual(result["changed_members"], 200)
        self.assertEqual(result["original_terminal_counts"], {
            "main_episodes": 40,
            "nominally_unavailable": 20,
            "raw_family_test_pass": 25,
            "final_candidate_accepted": 16,
            "unavailable_raw_pass_final_reject": 9,
        })
        self.assertTrue(result["transformed_terminal_counts_equal"])
        self.assertFalse(result["historical_execution_provenance_verified"])
        self.assertFalse(result["public_release_approved"])

    def test_original_log_byte_tamper_breaks_terminal_link(self) -> None:
        files = audit._members(audit.ORIGINAL)
        row = audit._json(files[audit.MAIN_INDEX].splitlines()[0])
        name = audit._link(row["log_path"], files)
        altered = copy.copy(files)
        altered[name] += b"\n"
        with self.assertRaisesRegex(audit.ProvenanceError,
                                    "run log original hash link differs"):
            audit._terminal_counts(altered)

    def test_original_receipt_byte_tamper_breaks_terminal_link(self) -> None:
        files = audit._members(audit.ORIGINAL)
        row = audit._json(files[audit.MAIN_INDEX].splitlines()[0])
        name = audit._link(row["receipt_path"], files)
        altered = copy.copy(files)
        receipt = audit._json(files[name])
        receipt["stop_event"] = "TAMPERED"
        altered[name] = json.dumps(receipt).encode()
        with self.assertRaisesRegex(audit.ProvenanceError,
                                    "main index and terminal receipt differ"):
            audit._terminal_counts(altered)

    def test_changed_archive_bytes_fail_frozen_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            modified = Path(directory) / audit.ORIGINAL.name
            modified.write_bytes(audit.ORIGINAL.read_bytes() + b"X")
            with self.assertRaisesRegex(audit.ProvenanceError,
                                        "frozen archive SHA-256 differs"):
                audit.audit(original=modified)

    def test_metadata_duplicate_keys_and_unsafe_members_fail_closed(self) -> None:
        with self.assertRaisesRegex(audit.ProvenanceError, "duplicate metadata key"):
            audit._json(b'{"status":1,"status":2}')
        with self.assertRaisesRegex(audit.ProvenanceError, "unsafe archived member name"):
            audit._safe("../outside")


if __name__ == "__main__":
    unittest.main()

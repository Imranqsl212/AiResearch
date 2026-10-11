"""Offline integrity checks for the review-only paper bundle transformation."""

from __future__ import annotations

import gzip
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from paper import build_sanitized_review_bundle as bundle


class SanitizedReviewBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="paper-review-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.output = Path(cls.temp.name) / "review.tar.gz"
        cls.source_sha = bundle._file_sha(bundle.ORIGINAL)
        cls.receipt = bundle.build(output=cls.output)

    def test_mapping_scanner_and_original_are_bound(self) -> None:
        verified = bundle.verify(sanitized=self.output)
        self.assertEqual(verified["source_archive_sha256"], self.source_sha)
        self.assertEqual(bundle._file_sha(bundle.ORIGINAL), self.source_sha)
        self.assertEqual(verified["sanitized_archive_sha256"], self.receipt["sanitized_archive_sha256"])
        self.assertTrue(all(value == 0 for value in verified["residual_marker_counts"].values()))
        self.assertGreater(verified["changed_members"], 0)
        members = bundle._members(self.output)
        manifest = json.loads(members[bundle.MANIFEST_NAME])
        self.assertFalse(manifest["public_release_approved"])
        self.assertFalse(manifest["scientific_replay_verified"])
        self.assertFalse(manifest["original_byte_identical_raw_data"])
        self.assertEqual(len(manifest["members"]), verified["source_members"])
        self.assertEqual(manifest["unreviewed_absolute_path_candidates"]["outside_placeholder_count"], 8)

    def test_modified_member_fails_verification(self) -> None:
        members = bundle._members(self.output)
        target = next(name for name in members if name.endswith(".py"))
        members[target] += b"\n# deliberate test tamper\n"
        bad = Path(self.temp.name) / "tampered.tar.gz"
        with bad.open("xb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as archive:
                    for name, data in sorted(members.items()):
                        bundle._record(archive, name, data)
        with self.assertRaisesRegex(bundle.SanitizationError, "mapped sanitized member differs"):
            bundle.verify(sanitized=bad)


if __name__ == "__main__":
    unittest.main()

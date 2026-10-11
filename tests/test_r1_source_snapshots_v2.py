"""Offline identity and failure-retention checks for private R1 page snapshots."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from analysis import capture_r1_source_snapshots_v2 as snapshots


class R1SourceSnapshotTests(unittest.TestCase):
    def test_complete_archive_is_write_once_and_detects_byte_drift(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "private_pages"

            def fake_fetch(url: str) -> snapshots.FetchResult:
                return snapshots.FetchResult(
                    "2026-10-05T00:00:00+00:00", url, 200, "text/html",
                    ("page: " + url).encode(), None)

            manifest = snapshots.capture(output, fetcher=fake_fetch)
            self.assertEqual(manifest["capture_status"], "COMPLETE")
            self.assertEqual(manifest["source_count"], 22)
            self.assertEqual(len({entry["url"] for entry in manifest["entries"]}), 22)
            self.assertEqual(snapshots.verify(output), manifest)
            with self.assertRaises(FileExistsError):
                snapshots.capture(output, fetcher=fake_fetch)
            (output / "snapshots" / "00.body").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "source body digest mismatch"):
                snapshots.verify(output)

    def test_failed_fetch_has_no_invented_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "private_pages"
            first = snapshots.source_urls()[0]["url"]

            def fake_fetch(url: str) -> snapshots.FetchResult:
                if url == first:
                    return snapshots.FetchResult(
                        "2026-10-05T00:00:00+00:00", None, None, None,
                        None, "URLError: DNS unavailable")
                return snapshots.FetchResult(
                    "2026-10-05T00:00:00+00:00", url, 200,
                    "text/html", b"source body", None)

            manifest = snapshots.capture(output, fetcher=fake_fetch)
            self.assertEqual(manifest["capture_status"], "PARTIAL")
            entry = manifest["entries"][0]
            self.assertEqual(entry["retrieval_status"], "FETCH_FAILED")
            self.assertEqual(entry["failure_reason"], "URLError: DNS unavailable")
            self.assertIsNone(entry["body_sha256"])
            self.assertFalse((output / "snapshots" / "00.body").exists())
            self.assertEqual(snapshots.verify(output), manifest)


if __name__ == "__main__":
    unittest.main()

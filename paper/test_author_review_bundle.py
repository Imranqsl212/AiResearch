"""Integrity checks for the filtered, local manuscript review package."""

from __future__ import annotations

import gzip
import hashlib
import json
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from paper import build_author_review_bundle as bundle


class AuthorReviewBundleTests(unittest.TestCase):
    def test_deterministic_exact_source_copy_and_review_flags(self) -> None:
        self.assertEqual(bundle.OUTPUT, bundle.V10_OUTPUT)
        self.assertNotEqual(bundle.V9_OUTPUT, bundle.V10_OUTPUT)
        self.assertNotEqual(bundle.V8_OUTPUT, bundle.V9_OUTPUT)
        self.assertNotEqual(bundle.V7_OUTPUT, bundle.V8_OUTPUT)
        self.assertEqual(set(bundle.V10_SOURCE_NAMES) - set(bundle.V9_SOURCE_NAMES), {
            "paper/venue_author_year_draft.md",
            "paper/VENUE_SHORTLIST_20261005.md",
        })
        self.assertEqual(bundle.V9_SOURCE_NAMES, bundle.V8_SOURCE_NAMES)
        self.assertEqual(bundle.V8_SOURCE_NAMES, bundle.V7_SOURCE_NAMES)
        self.assertEqual(set(bundle.V6_SOURCE_NAMES) - set(bundle.V5_SOURCE_NAMES), {
            "paper/audit_original_archive_provenance.py",
            "paper/test_audit_original_archive_provenance.py",
            "paper/ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md",
        })
        with tempfile.TemporaryDirectory(prefix="author-manuscript-test-") as temporary:
            first = Path(temporary) / "first.tar.gz"
            second = Path(temporary) / "second.tar.gz"
            receipt_a = bundle.build(output=first)
            receipt_b = bundle.build(output=second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(receipt_a["archive_sha256"], receipt_b["archive_sha256"])
            verified = bundle.verify(archive=first)
            self.assertTrue(verified["local_sources_match"])
            files = bundle._archive_files(first)
            manifest = json.loads(files[bundle.MANIFEST_NAME])
            self.assertEqual(manifest["version"], bundle.V10_VERSION)
            self.assertNotIn("public_release_approved", manifest)
            self.assertFalse(manifest["journal_supplement_approved"])
            self.assertEqual(manifest["git_visibility"], "not-attested-by-bundle")
            self.assertEqual(manifest["related_data_public_git_revision"], bundle.PUBLIC_DATA_REVISION)
            self.assertFalse(manifest["journal_submission_approved"])
            self.assertFalse(manifest["original_raw_data_included"])
            self.assertFalse(manifest["original_byte_replay_verified"])
            self.assertEqual(set(files), set(bundle.SOURCE_NAMES) | {bundle.README_NAME, bundle.MANIFEST_NAME})
            for name in bundle.SOURCE_NAMES:
                self.assertEqual(files[name], (bundle.ROOT / name).read_bytes())
            decision = files["paper/AUTHOR_SUBMISSION_DECISIONS_20261005.md"].decode("utf-8")
            for name in bundle._decision_bound_names(bundle.V10_SPEC):
                self.assertIn(Path(name).name, decision)
                self.assertIn(hashlib.sha256(files[name]).hexdigest(), decision)
            readme = files[bundle.README_NAME].decode("utf-8")
            self.assertIn("bundle v10", readme)
            self.assertIn("37074c198237ade67eb76921333b2835d329c863", readme)
            self.assertIn("not an approved journal supplement", readme)
            self.assertIn("working review materials", readme)
            self.assertIn("not attest whether this review archive is on GitHub", readme)

    def test_existing_v1_archive_still_verifies_without_local_source_compare(self) -> None:
        if not bundle.V1_OUTPUT.is_file():
            self.skipTest("local v1 archive is unavailable")
        before = hashlib.sha256(bundle.V1_OUTPUT.read_bytes()).hexdigest()
        verified = bundle.verify(archive=bundle.V1_OUTPUT, compare_sources=False)
        self.assertEqual(verified["version"], bundle.V1_VERSION)
        self.assertEqual(verified["source_file_count"], len(bundle.V1_SOURCE_NAMES))
        self.assertEqual(verified["archive_sha256"], before)
        self.assertEqual(hashlib.sha256(bundle.V1_OUTPUT.read_bytes()).hexdigest(), before)

    def test_existing_v2_archive_still_verifies_without_local_source_compare(self) -> None:
        if not bundle.V2_OUTPUT.is_file():
            self.skipTest("local v2 archive is unavailable")
        before = hashlib.sha256(bundle.V2_OUTPUT.read_bytes()).hexdigest()
        verified = bundle.verify(archive=bundle.V2_OUTPUT, compare_sources=False)
        self.assertEqual(verified["version"], bundle.V2_VERSION)
        self.assertEqual(verified["source_file_count"], len(bundle.V2_SOURCE_NAMES))
        self.assertEqual(verified["archive_sha256"], before)

    def test_existing_v3_archive_still_verifies_without_local_source_compare(self) -> None:
        if not bundle.V3_OUTPUT.is_file():
            self.skipTest("local v3 archive is unavailable")
        before = hashlib.sha256(bundle.V3_OUTPUT.read_bytes()).hexdigest()
        verified = bundle.verify(archive=bundle.V3_OUTPUT, compare_sources=False)
        self.assertEqual(verified["version"], bundle.V3_VERSION)
        self.assertEqual(verified["source_file_count"], len(bundle.V3_SOURCE_NAMES))
        self.assertEqual(verified["archive_sha256"], before)

    def test_existing_v4_archive_still_verifies_without_local_source_compare(self) -> None:
        if not bundle.V4_OUTPUT.is_file():
            self.skipTest("local v4 archive is unavailable")
        before = hashlib.sha256(bundle.V4_OUTPUT.read_bytes()).hexdigest()
        verified = bundle.verify(archive=bundle.V4_OUTPUT, compare_sources=False)
        self.assertEqual(verified["version"], bundle.V4_VERSION)
        self.assertEqual(verified["source_file_count"], len(bundle.V4_SOURCE_NAMES))
        self.assertEqual(verified["archive_sha256"], before)

    def test_existing_v5_archive_still_verifies_without_local_source_compare(self) -> None:
        if not bundle.V5_OUTPUT.is_file():
            self.skipTest("local v5 archive is unavailable")
        before = hashlib.sha256(bundle.V5_OUTPUT.read_bytes()).hexdigest()
        verified = bundle.verify(archive=bundle.V5_OUTPUT, compare_sources=False)
        self.assertEqual(verified["version"], bundle.V5_VERSION)
        self.assertEqual(verified["source_file_count"], len(bundle.V5_SOURCE_NAMES))
        self.assertEqual(verified["archive_sha256"], before)

    def test_existing_v6_archive_still_verifies_without_local_source_compare(self) -> None:
        if not bundle.V6_OUTPUT.is_file():
            self.skipTest("local v6 archive is unavailable")
        before = hashlib.sha256(bundle.V6_OUTPUT.read_bytes()).hexdigest()
        verified = bundle.verify(archive=bundle.V6_OUTPUT, compare_sources=False)
        self.assertEqual(verified["version"], bundle.V6_VERSION)
        self.assertEqual(verified["source_file_count"], len(bundle.V6_SOURCE_NAMES))
        self.assertEqual(verified["archive_sha256"], before)

    def test_existing_v7_archive_still_verifies_without_local_source_compare(self) -> None:
        if not bundle.V7_OUTPUT.is_file():
            self.skipTest("local v7 archive is unavailable")
        before = hashlib.sha256(bundle.V7_OUTPUT.read_bytes()).hexdigest()
        verified = bundle.verify(archive=bundle.V7_OUTPUT, compare_sources=False)
        self.assertEqual(verified["version"], bundle.V7_VERSION)
        self.assertEqual(verified["source_file_count"], len(bundle.V7_SOURCE_NAMES))
        self.assertEqual(verified["archive_sha256"], before)

    def test_existing_v8_archive_still_verifies_without_local_source_compare(self) -> None:
        if not bundle.V8_OUTPUT.is_file():
            self.skipTest("local v8 archive is unavailable")
        before = hashlib.sha256(bundle.V8_OUTPUT.read_bytes()).hexdigest()
        verified = bundle.verify(archive=bundle.V8_OUTPUT, compare_sources=False)
        self.assertEqual(verified["version"], bundle.V8_VERSION)
        self.assertEqual(verified["source_file_count"], len(bundle.V8_SOURCE_NAMES))
        self.assertEqual(verified["archive_sha256"], before)

    def test_existing_v9_archive_still_verifies_without_local_source_compare(self) -> None:
        if not bundle.V9_OUTPUT.is_file():
            self.skipTest("local v9 archive is unavailable")
        before = hashlib.sha256(bundle.V9_OUTPUT.read_bytes()).hexdigest()
        verified = bundle.verify(archive=bundle.V9_OUTPUT, compare_sources=False)
        self.assertEqual(verified["version"], bundle.V9_VERSION)
        self.assertEqual(verified["source_file_count"], len(bundle.V9_SOURCE_NAMES))
        self.assertEqual(verified["archive_sha256"], before)

    def test_v2_requires_decision_hash_for_each_rendered_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="author-manuscript-decision-") as temporary:
            root = Path(temporary) / "repo"
            for name in bundle.V2_SOURCE_NAMES:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((bundle.ROOT / name).read_bytes())
            name = "paper/submission/full_paper_anonymous.docx"
            digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
            decision = root / "paper/AUTHOR_SUBMISSION_DECISIONS_20261005.md"
            self.assertIn(digest, decision.read_text(encoding="utf-8"))
            decision.write_text(decision.read_text(encoding="utf-8").replace(digest, "0" * 64), encoding="utf-8")
            with patch.object(bundle, "ROOT", root):
                with self.assertRaisesRegex(bundle.BundleError, "full_paper_anonymous.docx"):
                    bundle.build(output=Path(temporary) / "bundle.tar.gz", spec=bundle.V2_SPEC)

    def test_tampering_fails_even_when_outer_receipt_is_recomputed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="author-manuscript-tamper-") as temporary:
            archive_path = Path(temporary) / "bundle.tar.gz"
            bundle.build(output=archive_path)
            files = bundle._archive_files(archive_path)
            files["paper/final.md"] += b"\nmodified after packaging\n"
            with archive_path.open("wb") as raw:
                with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as compressed:
                    with tarfile.open(fileobj=compressed, mode="w") as archive:
                        for name, data in sorted(files.items()):
                            bundle._add(archive, name, data)
            receipt_path = bundle._receipt_path(archive_path)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["archive_sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            receipt["archive_bytes"] = archive_path.stat().st_size
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(bundle.BundleError, "manifest hash or size differs"):
                bundle.verify(archive=archive_path, compare_sources=False)

    def test_host_marker_screen_checks_docx_contents(self) -> None:
        with tempfile.TemporaryDirectory(prefix="author-manuscript-marker-") as temporary:
            document = Path(temporary) / "sample.docx"
            with zipfile.ZipFile(document, "w") as archive:
                archive.writestr("word/document.xml", "<w:t>/Users/example/private</w:t>")
            with self.assertRaisesRegex(bundle.BundleError, "host-specific marker"):
                bundle._screen("sample.docx", document.read_bytes())
            with self.assertRaisesRegex(bundle.BundleError, "host-specific marker"):
                bundle._screen("sample.txt", b"/home/example/a")

    def test_workspace_drift_is_detected_without_changing_real_sources(self) -> None:
        with tempfile.TemporaryDirectory(prefix="author-manuscript-drift-") as temporary:
            root = Path(temporary) / "repo"
            for name in bundle.SOURCE_NAMES:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((bundle.ROOT / name).read_bytes())
            archive_path = Path(temporary) / "bundle.tar.gz"
            with patch.object(bundle, "ROOT", root):
                bundle.build(output=archive_path)
                with (root / "paper/final.md").open("ab") as stream:
                    stream.write(b"\nlocal edit\n")
                with self.assertRaisesRegex(bundle.BundleError, "current local source differs"):
                    bundle.verify(archive=archive_path)
                self.assertIsNone(bundle.verify(archive=archive_path, compare_sources=False)["local_sources_match"])


if __name__ == "__main__":
    unittest.main()

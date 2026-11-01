"""Bytewise public-archive screen: no value disclosure or archive mutation."""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from analysis.scan_public_excluded_archive import ScanError, main, scan_archive


class PublicArchiveScanTests(unittest.TestCase):
    def test_categories_only_and_tree_hash_matches_archive_convention(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "archive"
            (root / "nested").mkdir(parents=True)
            secret = b"sk_test_" + b"A" * 24
            other = (b"ghp_" + b"B" * 30 + b"\nAKIA" + b"C" * 16 +
                     b"\nAIza" + b"D" * 35 + b"\nxoxb-12345678901234567890" +
                     b"\nBearer abcdefghijklmnopqrstuvwxyz" +
                     b"\nBasic QWxhZGRpbjpvcGVuIHNlc2FtZQ==" +
                     b"\nsample@example.invalid" +
                     b"\n/Users/example/work /home/example/work C:\\Users\\example\\file" +
                     b"\n/private/var/folders/xy/temp /private/tmp/job" +
                     b"\n-----BEGIN OPENSSH PRIVATE KEY-----")
            (root / "a.bin").write_bytes(secret)
            (root / "nested/b.bin").write_bytes(other)
            receipt = scan_archive(root, planned_temp_roots=("/private/tmp/job",))
            self.assertEqual(receipt["status"], "HITS_FOUND")
            self.assertEqual(receipt["file_count"], 2)
            categories = {row["category"] for row in receipt["findings"]}
            self.assertTrue({
                "STRIPE_API_KEY", "GITHUB_TOKEN", "AWS_ACCESS_KEY_ID",
                "GOOGLE_API_KEY", "SLACK_TOKEN", "BEARER_TOKEN", "BASIC_TOKEN",
                "EMAIL_ADDRESS", "MAC_HOME_PATH", "LINUX_HOME_PATH",
                "WINDOWS_HOME_PATH", "PRIVATE_MAC_TEMP_PATH", "PEM_PRIVATE_KEY",
            }.issubset(categories))
            self.assertTrue(all(set(row) == {"category", "path"}
                                for row in receipt["findings"]))
            self.assertEqual(receipt["metadata_findings"],
                             [{"category": "PLANNED_LOCAL_TEMP_ROOT",
                               "path": "nested/b.bin"}])
            encoded = json.dumps(receipt).encode()
            self.assertNotIn(secret, encoded)
            self.assertNotIn(b"sample@example.invalid", encoded)
            self.assertNotIn(b"QWxhZGRpbjpvcGVuIHNlc2FtZQ", encoded)
            expected = hashlib.sha256()
            for rel, data in (("a.bin", secret), ("nested/b.bin", other)):
                expected.update(f"{rel}\0{len(data)}\0{hashlib.sha256(data).hexdigest()}\n".encode())
            self.assertEqual(receipt["tree_sha256"], expected.hexdigest())

    def test_symlink_is_rejected_before_following_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "archive"
            root.mkdir()
            outside = Path(temp) / "outside.txt"
            outside.write_text("not to be scanned")
            (root / "linked.txt").symlink_to(outside)
            with self.assertRaisesRegex(ScanError, "symlink at linked.txt"):
                scan_archive(root)

    def test_secret_in_filename_is_redacted_from_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "archive"
            root.mkdir()
            token = "sk_test_" + "X" * 24
            (root / token).write_bytes(b"sample@example.invalid")
            receipt = scan_archive(root)
            self.assertEqual(receipt["findings"][0]["category"], "EMAIL_ADDRESS")
            self.assertTrue(receipt["findings"][0]["path"].startswith(
                "[REDACTED_PATH_SHA256_"))
            self.assertNotIn(token, json.dumps(receipt))

    def test_cli_receipt_is_safe_and_hit_exit_code_is_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "archive"
            root.mkdir()
            fake = b"sk_live_" + b"Z" * 24
            (root / "raw.bin").write_bytes(fake)
            output = Path(temp) / "scan.json"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main([str(root), "--json-out", str(output)])
            self.assertEqual(code, 1)
            self.assertTrue(output.is_file())
            self.assertNotIn(fake.decode(), stdout.getvalue())
            self.assertNotIn(fake, output.read_bytes())
            receipt = json.loads(output.read_text())
            self.assertEqual(receipt["findings"],
                             [{"category": "STRIPE_API_KEY", "path": "raw.bin"}])
            # A receipt inside the archive would change the scan target and
            # cannot be used to produce a meaningful tree fingerprint.
            inside = root / "receipt.json"
            stderr = io.StringIO()
            with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(root), "--json-out", str(inside)]), 2)
            self.assertFalse(inside.exists())

    def test_clean_archive_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "archive"
            root.mkdir()
            (root / "safe.bin").write_bytes(b"finite mode report: no credentials")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(root)]), 0)
            self.assertEqual(scan_archive(root)["findings"], [])


if __name__ == "__main__":
    unittest.main()

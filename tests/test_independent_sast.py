"""Offline sidecar tests with fake Bandit executables; no package dependency."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from analysis.independent_sast import SASTReceiptError, scan_source, verify_receipt


ROOT = Path(__file__).resolve().parents[1]


class IndependentSASTTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="independent-sast-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "candidate.py"
        self.source.write_text("import subprocess\nsubprocess.run('ls', shell=True)  # nosec\n",
                               encoding="utf-8")

    def scanner(self, mode: str) -> Path:
        path = self.root / f"fake-bandit-{mode}"
        path.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys, time\n"
            f"mode = {mode!r}\n"
            "if sys.argv[1:] == ['--version']:\n"
            "    print('bandit 1.9.3' if mode == 'old_version' else 'bandit 1.9.4')\n"
            "    print('  python version = fake-3.12')\n"
            "    sys.exit(2 if mode == 'version_error' else 0)\n"
            "if sys.argv[1:] != ['--ignore-nosec', '-f', 'json', '-']:\n"
            "    sys.exit(8)\n"
            "source = sys.stdin.buffer.read()\n"
            "if mode == 'timeout': time.sleep(2)\n"
            "if mode == 'malformed':\n"
            "    print('{bad-json')\n"
            "    sys.exit(0)\n"
            "finding = {'filename': '<stdin>', 'test_id': 'B602',\n"
            "           'test_name': 'subprocess_popen_with_shell_equals_true',\n"
            "           'issue_severity': 'HIGH', 'issue_confidence': 'HIGH',\n"
            "           'line_number': 2, 'issue_text': 'shell invocation',\n"
            "           'issue_cwe': {'id': 78}}\n"
            "report = {'results': [finding] if mode in ('finding', 'exit_mismatch') else [],\n"
            "          'errors': ([{'filename': '<stdin>',\n"
            "                      'reason': 'syntax error while parsing AST'}]\n"
            "                     if mode == 'syntax' else\n"
            "                     [{'filename': '<stdin>', 'reason': 'engine failure'}]\n"
            "                     if mode == 'error' else [])}\n"
            "print(json.dumps(report))\n"
            "sys.exit(1 if mode == 'finding' else 2 if mode == 'exit2' else 0)\n",
            encoding="utf-8",
        )
        path.chmod(0o700)
        return path

    def case(self, mode: str, status: str, reason: str | None = None) -> dict:
        engine = self.scanner(mode)
        output = self.root / f"archive-{mode}"
        receipt = scan_source(source_path=self.source, output_dir=output,
                              bandit=str(engine), timeout_seconds=1)
        self.assertEqual((receipt["status"], receipt["reason"]), (status, reason))
        self.assertEqual(verify_receipt(source_path=self.source, archive_dir=output,
                                        bandit_executable=engine), receipt)
        self.assertFalse(receipt["agent_visible"])
        self.assertFalse(receipt["changes_benchmark_gate"])
        self.assertFalse(receipt["eligible_for_main_analysis"])
        return receipt

    def test_finding_and_no_finding(self) -> None:
        found = self.case("finding", "FINDINGS")
        self.assertEqual(found["scan_process"]["returncode"], 1)
        self.assertEqual(found["normalized_findings"][0]["test_id"], "B602")
        self.assertIn("--ignore-nosec", found["scan_argv"])
        self.assertTrue((self.root / "archive-finding" / "bandit.raw.json").is_file())
        clean = self.case("clean", "NO_FINDINGS")
        self.assertEqual(clean["normalized_findings"], [])
        self.assertNotIn("secure", clean)

    def test_errors_are_indeterminate(self) -> None:
        for mode, reason in (("syntax", "SOURCE_SYNTAX_ERROR"),
                             ("error", "ENGINE_REPORTED_ERRORS"),
                             ("malformed", "SCAN_REPORT_INVALID"),
                             ("exit2", "SCAN_EXIT_CODE"),
                             ("version_error", "VERSION_INVALID"),
                             ("old_version", "VERSION_MISMATCH"),
                             ("exit_mismatch", "SCAN_EXIT_RESULT_MISMATCH")):
            with self.subTest(mode=mode):
                self.case(mode, "INDETERMINATE", reason)

    def test_timeout_and_missing_engine(self) -> None:
        self.case("timeout", "INDETERMINATE", "SCAN_TIMEOUT")
        output = self.root / "archive-missing"
        receipt = scan_source(source_path=self.source, output_dir=output,
                              bandit=str(self.root / "missing"), timeout_seconds=1)
        self.assertEqual((receipt["status"], receipt["reason"]),
                         ("INDETERMINATE", "ENGINE_MISSING"))
        self.assertEqual(verify_receipt(source_path=self.source, archive_dir=output), receipt)

    def test_tampering_source_and_receipt(self) -> None:
        engine = self.scanner("finding")
        output = self.root / "archive-tamper"
        scan_source(source_path=self.source, output_dir=output, bandit=str(engine))
        raw = output / "bandit.raw.json"
        original = raw.read_bytes()
        raw.write_bytes(original + b" ")
        with self.assertRaisesRegex(SASTReceiptError, "artifact hash"):
            verify_receipt(source_path=self.source, archive_dir=output)
        raw.write_bytes(original)
        receipt_path = output / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["status"] = "NO_FINDINGS"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaisesRegex(SASTReceiptError, "saved SAST result"):
            verify_receipt(source_path=self.source, archive_dir=output)

    def test_exact_source_and_limits(self) -> None:
        engine = self.scanner("clean")
        output = self.root / "archive-exact"
        scan_source(source_path=self.source, output_dir=output, bandit=str(engine))
        self.source.write_text("print('changed')\n", encoding="utf-8")
        with self.assertRaisesRegex(SASTReceiptError, "source or raw"):
            verify_receipt(source_path=self.source, archive_dir=output)
        with self.assertRaises(FileExistsError):
            scan_source(source_path=self.source, output_dir=output, bandit=str(engine))
        self.source.write_bytes(b"#" * (64 * 1024 + 1))
        with self.assertRaisesRegex(SASTReceiptError, "64 KiB"):
            scan_source(source_path=self.source, output_dir=self.root / "archive-large",
                        bandit=str(engine))
        self.assertFalse((self.root / "archive-large").exists())

    def test_cli_scan_and_verify(self) -> None:
        engine = self.scanner("clean")
        output = self.root / "archive-cli"
        scan = subprocess.run(
            [sys.executable, "-B", "-m", "analysis.independent_sast", "scan",
             "--source", str(self.source), "--output-dir", str(output),
             "--bandit", str(engine)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(scan.returncode, 0, scan.stderr)
        self.assertEqual(json.loads(scan.stdout)["status"], "NO_FINDINGS")
        replay = subprocess.run(
            [sys.executable, "-B", "-m", "analysis.independent_sast", "verify",
             "--source", str(self.source), "--archive-dir", str(output)],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(replay.returncode, 0, replay.stderr)


if __name__ == "__main__":
    unittest.main()

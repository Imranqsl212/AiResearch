"""Offline integrity tests for post-collection executable-log SAST."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from analysis.sast_executable_log import (
    ExecutableLogSASTError, scan_executable_log, verify_executable_log,
)
from analysis.independent_sast import scan_source


class ExecutableLogSASTTests(unittest.TestCase):
    CONTEXT = {
        "schema_version": "0.1.0", "experiment_id": "synthetic-executable",
        "run_id": "episode-0001", "public_run_id": "public-0001",
        "task_id": "task-python", "public_task_id": "public-task",
        "condition": "RD", "model": "test-model",
        "agent_version": "test-agent", "benchmark_version": "test-benchmark",
        "git_commit": "0" * 40,
    }

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="sast-log-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "episode.jsonl"
        self.engine = self.root / "fake-bandit"
        self.engine.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "if sys.argv[1:] == ['--version']:\n"
            "    print('bandit 1.9.4')\n"
            "    print('  python version = fake-3.12')\n"
            "    sys.exit(0)\n"
            "assert sys.argv[1:] == ['--ignore-nosec', '-f', 'json', '-']\n"
            "source = sys.stdin.buffer.read()\n"
            "if b'BAD_REPORT' in source:\n"
            "    print('{bad-json')\n"
            "else:\n"
            "    print(json.dumps({'errors': [], 'results': []}))\n",
            encoding="utf-8",
        )
        self.engine.chmod(0o700)

    @staticmethod
    def event(number: int, source: str | None, verifier_hash: str | None = None) -> dict:
        parameters = {"source": source} if source is not None else {}
        digest = hashlib.sha256(source.encode()).hexdigest() if source is not None else None
        return {
            "event_id": f"event-{number:05d}", "event_type": "TOOL_OBSERVATION",
            "tool": "attempt", "step": number, "parameters": parameters,
            "action": {"tool": "attempt", "parameters": parameters},
            "raw_action": {"tool": "attempt", "parameters": parameters},
            "verifier_result": {"source": "evaluator_action_verifier",
                                "source_sha256": verifier_hash if verifier_hash is not None else digest},
        }

    def write_log(self, events: list[dict], *, finished: bool = True,
                  receipt: bool = True) -> bytes:
        events = [{**self.CONTEXT, **row} for row in events]
        if finished:
            final = {**self.CONTEXT, "event_id": "event-99999",
                     "event_type": "RUN_FINISHED", "tool": None,
                     "step": max(row.get("step", 0) for row in events),
                     "outcome": "VALIDATED_NON_SUCCESS",
                     "stop_event": "AGENT_SELF_TERMINATION"}
            events.append(final)
        raw = b"".join(json.dumps(row, sort_keys=True).encode() + b"\n" for row in events)
        self.log.write_bytes(raw)
        if receipt:
            native = {**self.CONTEXT, "log_file": self.log.name,
                      "log_sha256": hashlib.sha256(raw).hexdigest(),
                      "terminal_outcome": "VALIDATED_NON_SUCCESS",
                      "stop_event": "AGENT_SELF_TERMINATION"}
            self.log.with_suffix(".receipt.json").write_text(
                json.dumps(native, sort_keys=True), encoding="utf-8")
        return raw

    def test_scan_exact_attempt_only_and_preserve_missingness(self) -> None:
        source = "def handle(value):\n    return value\n"
        raw = self.write_log([
            {"event_id": "event-00001", "event_type": "TOOL_OBSERVATION",
             "tool": "inspect", "step": 1},
            self.event(2, source), self.event(3, source, "0" * 64),
            self.event(4, None),
        ])
        archive = self.root / "archive"
        manifest = scan_executable_log(log_path=self.log, output_dir=archive,
                                       bandit=str(self.engine))
        self.assertEqual([r["sast_status"] for r in manifest["attempts"]],
                         ["NO_FINDINGS", "UNSCANNABLE_SOURCE_MISMATCH",
                          "UNSCANNABLE_SOURCE_MISSING"])
        self.assertEqual({p.name for p in archive.iterdir()},
                         {"manifest.json", "attempt-000001"})
        self.assertEqual(manifest["log_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.log.read_bytes(), raw)
        self.assertFalse(manifest["agent_visible"])
        self.assertFalse(manifest["changes_benchmark_gate"])
        self.assertFalse(manifest["eligible_for_main_analysis"])
        self.assertEqual(verify_executable_log(log_path=self.log, archive_dir=archive,
                                                bandit_executable=self.engine), manifest)
        with self.assertRaises(FileExistsError):
            scan_executable_log(log_path=self.log, output_dir=archive,
                                bandit=str(self.engine))

    def test_scanner_error_is_indeterminate(self) -> None:
        self.write_log([self.event(1, "BAD_REPORT\n")])
        archive = self.root / "archive"
        manifest = scan_executable_log(log_path=self.log, output_dir=archive,
                                       bandit=str(self.engine))
        self.assertEqual(manifest["attempts"][0]["sast_status"], "INDETERMINATE")
        self.assertEqual(manifest["attempts"][0]["reason"], "SCAN_REPORT_INVALID")
        self.assertEqual(verify_executable_log(log_path=self.log, archive_dir=archive),
                         manifest)

    def test_tampering_log_and_sidecar_fails(self) -> None:
        raw = self.write_log([self.event(1, "print('one')\n")])
        archive = self.root / "archive"
        scan_executable_log(log_path=self.log, output_dir=archive,
                            bandit=str(self.engine))
        self.log.write_bytes(raw + b"\n")
        with self.assertRaises(ExecutableLogSASTError):
            verify_executable_log(log_path=self.log, archive_dir=archive)
        self.log.write_bytes(raw)
        report = archive / "attempt-000001" / "bandit.raw.json"
        report.write_bytes(report.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            verify_executable_log(log_path=self.log, archive_dir=archive)

    def test_action_source_disagreement_never_scans(self) -> None:
        row = self.event(1, "print('right')\n")
        row["action"]["parameters"] = {"source": "print('different')\n"}
        self.write_log([row])
        archive = self.root / "archive"
        result = scan_executable_log(log_path=self.log, output_dir=archive,
                                     bandit=str(self.engine))
        self.assertEqual(result["attempts"][0]["sast_status"],
                         "UNSCANNABLE_SOURCE_MISMATCH")
        self.assertEqual({p.name for p in archive.iterdir()}, {"manifest.json"})
        verify_executable_log(log_path=self.log, archive_dir=archive)

    def test_manifest_cannot_relabel_scanner_or_timeout(self) -> None:
        self.write_log([self.event(1, "print('fixed')\n")])
        archive = self.root / "archive"
        scan_executable_log(log_path=self.log, output_dir=archive,
                            bandit=str(self.engine), timeout_seconds=7)
        manifest_path = archive / "manifest.json"
        original = manifest_path.read_bytes()
        for key, replacement in (("engine_requested", "different-bandit"),
                                 ("timeout_seconds", 8)):
            manifest = json.loads(original)
            manifest[key] = replacement
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ExecutableLogSASTError):
                verify_executable_log(log_path=self.log, archive_dir=archive)
        manifest_path.write_bytes(original)
        verify_executable_log(log_path=self.log, archive_dir=archive)

    def test_invalid_timeout_does_not_create_archive(self) -> None:
        self.write_log([self.event(1, "print('fixed')\n")])
        archive = self.root / "archive"
        with self.assertRaises(ExecutableLogSASTError):
            scan_executable_log(log_path=self.log, output_dir=archive,
                                bandit=str(self.engine), timeout_seconds=0)
        self.assertFalse(archive.exists())

    def test_requires_final_event_and_native_receipt(self) -> None:
        self.write_log([self.event(1, "print('fixed')\n")], finished=False)
        with self.assertRaises(ExecutableLogSASTError):
            scan_executable_log(log_path=self.log, output_dir=self.root / "partial",
                                bandit=str(self.engine))
        self.assertFalse((self.root / "partial").exists())

        self.write_log([self.event(1, "print('fixed')\n")], receipt=False)
        self.log.with_suffix(".receipt.json").unlink()
        with self.assertRaises(ExecutableLogSASTError):
            scan_executable_log(log_path=self.log, output_dir=self.root / "no-receipt",
                                bandit=str(self.engine))
        self.assertFalse((self.root / "no-receipt").exists())

        self.write_log([self.event(1, "print('fixed')\n")])
        native_path = self.log.with_suffix(".receipt.json")
        native = json.loads(native_path.read_text(encoding="utf-8"))
        native["log_sha256"] = "0" * 64
        native_path.write_text(json.dumps(native), encoding="utf-8")
        with self.assertRaises(ExecutableLogSASTError):
            scan_executable_log(log_path=self.log, output_dir=self.root / "wrong-hash",
                                bandit=str(self.engine))
        self.assertFalse((self.root / "wrong-hash").exists())

    def test_native_receipt_change_and_mixed_engine_identity_fail(self) -> None:
        sources = ["print('first')\n", "print('second')\n"]
        self.write_log([self.event(index, source)
                        for index, source in enumerate(sources, 1)])
        archive = self.root / "archive"
        manifest = scan_executable_log(log_path=self.log, output_dir=archive,
                                       bandit=str(self.engine))
        native_path = self.log.with_suffix(".receipt.json")
        native_original = native_path.read_bytes()
        native_path.write_bytes(native_original + b" ")
        with self.assertRaises(ExecutableLogSASTError):
            verify_executable_log(log_path=self.log, archive_dir=archive)
        native_path.write_bytes(native_original)

        # The second receipt is individually valid but now came from changed
        # executable bytes under the same requested/resolved path.
        with self.engine.open("a", encoding="utf-8") as handle:
            handle.write("\n# changed tool bytes\n")
        second = archive / "attempt-000002"
        shutil.rmtree(second)
        source_file = self.root / "second.py"
        source_file.write_text(sources[1], encoding="utf-8")
        scan_source(source_path=source_file, output_dir=second,
                    bandit=str(self.engine))
        manifest["attempts"][1]["sidecar_receipt_sha256"] = hashlib.sha256(
            (second / "receipt.json").read_bytes()).hexdigest()
        (archive / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ExecutableLogSASTError,
                                    "Bandit identity differs across sidecars"):
            verify_executable_log(log_path=self.log, archive_dir=archive)


if __name__ == "__main__":
    unittest.main()

"""Fail-closed provenance and pairing guards for two excluded RAG pilots."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from analysis.report_cross_model_rag_excluded import (
    GEMMA, QWEN, CrossModelAuditError, archive_audit, audit_block, compare,
    normalized_request, sha,
)


class CrossModelRAGExcludedTests(unittest.TestCase):
    def test_normalization_removes_only_model_routing(self) -> None:
        left = {"model": "qwen3:4b", "messages": [{"role": "user", "content": "a"}],
                "options": {"seed": 11}}
        right = {**left, "model": "gemma3:4b"}
        self.assertEqual(normalized_request(left), normalized_request(right))
        right["options"] = {"seed": 12}
        self.assertNotEqual(normalized_request(left), normalized_request(right))
        with self.assertRaises(CrossModelAuditError):
            normalized_request({"messages": []})

    def test_receipt_tamper_fails_before_episode_loading(self) -> None:
        if not GEMMA.is_dir():
            self.skipTest("ignored raw Gemma pilot is absent")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "copied_block"
            target.mkdir()
            for name in ("block_schedule.json", "preflight.json", "run.receipt.json",
                         "retrieval_manifest.json"):
                (target / name).write_bytes((GEMMA / name).read_bytes())
            receipt = json.loads((target / "run.receipt.json").read_text())
            receipt["model_requests_recorded"] += 1
            (target / "run.receipt.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(CrossModelAuditError, "receipt self-hash"):
                audit_block(target)

    def test_pre_run_archive_detects_source_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            block = root / "pilot"
            block.mkdir()
            (block / "block_schedule.json").write_text("{}")
            sibling = root / "pilot_source_provenance"
            archive = sibling / "source_snapshot"
            (archive / "agent").mkdir(parents=True)
            source = archive / "agent/example.py"
            source.write_text("original\n")
            snapshot = {"agent/example.py": sha(source)}
            index = {"kind": "pre_run_source_snapshot", "all_match_schedule": True,
                     "block_schedule_sha256": sha(block / "block_schedule.json"),
                     "source_file_sha256s": snapshot, "file_count": 1,
                     "created_at_utc": "2026-10-04T07:50:00Z"}
            (sibling / "index.json").write_text(json.dumps(index))
            audit = archive_audit(block, snapshot, "2026-10-04T07:51:00Z",
                                  "2026-10-04T07:53:00Z")
            self.assertTrue(audit["byte_hashes_match_schedule"])
            source.write_text("changed\n")
            with self.assertRaisesRegex(CrossModelAuditError, "archive file hash"):
                archive_audit(block, snapshot, "2026-10-04T07:51:00Z",
                              "2026-10-04T07:53:00Z")

    @unittest.skipUnless(QWEN.is_dir() and GEMMA.is_dir(), "ignored raw pilot blocks absent")
    def test_actual_raw_pair_and_prompt_tamper(self) -> None:
        qwen, gemma = audit_block(QWEN), audit_block(GEMMA)
        report = compare(qwen, gemma)
        self.assertEqual(len(report["paired_cells"]), 9)
        self.assertEqual((qwen["valid_slots"], gemma["valid_slots"]), (9, 9))
        self.assertEqual((qwen["model_requests_recorded"], gemma["model_requests_recorded"]),
                         (40, 13))
        self.assertEqual((qwen["source_archive"]["timing"],
                          gemma["source_archive"]["timing"]),
                         ("post_run_recovered", "pre_run"))
        self.assertEqual(len(report["source_version_diff"]), 4)
        changed = deepcopy(gemma)
        changed["episodes"][0]["normalized_initial_request_sha256"] = "0" * 64
        with self.assertRaisesRegex(CrossModelAuditError, "normalized initial prompt"):
            compare(qwen, changed)


if __name__ == "__main__":
    unittest.main()

"""Synthetic checks for transformed-member links and safe in-memory paths."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from paper import replay_sanitized_candidate as replay


class SanitizedTableReplayTests(unittest.TestCase):
    def test_member_path_requires_experiment_relative_path(self) -> None:
        self.assertEqual(replay._member_path("<RESEARCH_ROOT>/experiments/runs/x.jsonl"),
                         "experiments/runs/x.jsonl")
        for value in ("/Users/name/experiments/runs/x.jsonl",
                      "experiments/../secrets", "<RESEARCH_ROOT>/paper/final.md"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replay._member_path(value)

    def test_changed_member_hash_is_checked_without_original_archive(self) -> None:
        name = "experiments/results/example.jsonl"
        content = b'{"n":1}\n'
        row = {"path": name, "status": "TRANSFORMED",
               "original_sha256": "0" * 64, "sanitized_sha256": replay._sha(content),
               "sanitized_bytes": len(content)}
        old = {"path": replay.package.OLD_INVENTORY,
               "status": "REPLACED_BY_SANITIZATION_MANIFEST"}
        manifest = {"status": "REVIEW_ONLY_SANITIZED_CANDIDATE",
                    "public_release_approved": False, "scientific_replay_verified": False,
                    "original_byte_identical_raw_data": False,
                    "mapping_count": 2, "source_member_count": 2,
                    "changed_member_count": 1, "members": [row, old]}
        files = {name: content,
                 replay.package.MANIFEST_NAME: json.dumps(manifest).encode(),
                 replay.package.NOTICE_NAME: b"review only\n"}
        with patch.object(replay.package, "_members", return_value=files):
            members, _, changed = replay._verified_review_members(Path("absent.tar.gz"))
            self.assertEqual(members[name], content)
            self.assertEqual(changed, 1)
            files[name] = b'{"n":2}\n'
            with self.assertRaisesRegex(ValueError, "transformed member hash differs"):
                replay._verified_review_members(Path("absent.tar.gz"))


if __name__ == "__main__":
    unittest.main()

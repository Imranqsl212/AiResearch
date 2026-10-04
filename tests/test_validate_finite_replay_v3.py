"""Saved-artifact integrity checks for the finite temporal replay family."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from benchmark.finite_replay_v3 import certify_task
from benchmark.validate_finite_replay_v3 import ROOT, build_index, validate


class SavedReplayFixtureTest(unittest.TestCase):
    def test_saved_fixture_set_verifies(self) -> None:
        self.assertEqual(validate(), {"families": 1, "conditions": 5, "candidate_checks": 80})

    def test_reference_byte_change_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture_dir = Path(temporary) / "replay"
            shutil.copytree(ROOT, fixture_dir)
            reference = fixture_dir / "transaction-replay.references.json"
            reference.write_text(reference.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "index or file hashes"):
                validate(fixture_dir)

    def test_rehashed_public_change_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture_dir = Path(temporary) / "replay"
            shutil.copytree(ROOT, fixture_dir)
            task_path = fixture_dir / "fr-transaction-replay-c2.task.json"
            proof_path = fixture_dir / "fr-transaction-replay-c2.proof.json"
            task = json.loads(task_path.read_text(encoding="utf-8"))
            task["starter_candidate"]["transitions"]["seen"]["decision"] = "reject"
            task_path.write_text(json.dumps(task, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            proof_path.write_text(json.dumps(certify_task(task), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (fixture_dir / "index.json").write_text(
                json.dumps(build_index(fixture_dir), indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "task or proof"):
                validate(fixture_dir)


if __name__ == "__main__":
    unittest.main()

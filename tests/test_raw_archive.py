import tempfile
import unittest
from pathlib import Path

from experiments.raw_archive import ArchiveError, archive_run, seal_archive, verify_archive


class RawArchiveTests(unittest.TestCase):
    def test_archive_is_idempotent_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.jsonl"
            source.write_text('{"event":"one"}\n', encoding="utf-8")
            archive = root / "archive"
            first = archive_run(source, archive, "run-1")
            self.assertEqual(archive_run(source, archive, "run-1"), first)
            seal_archive(archive, experiment_id="exp-1", manifest_version="m1")
            self.assertTrue(verify_archive(archive)["passed"])
            source.write_text('{"event":"changed"}\n', encoding="utf-8")
            with self.assertRaises(ArchiveError):
                archive_run(source, archive, "run-1")

    def test_manifest_is_create_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.jsonl"
            source.write_text("x\n", encoding="utf-8")
            archive = root / "archive"
            archive_run(source, archive, "run-1")
            first = seal_archive(archive, experiment_id="exp", manifest_version="v1")
            self.assertEqual(seal_archive(archive, experiment_id="exp", manifest_version="v1"), first)
            with self.assertRaises(ArchiveError):
                seal_archive(archive, experiment_id="other", manifest_version="v1")

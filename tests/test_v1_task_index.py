"""The saved finite-policy task inventory must detect artifact drift."""

import shutil
import tempfile
import unittest
from pathlib import Path

from benchmark.validate_finite_policy_v1 import DEFAULT_INDEX, validate_index


class V1TaskIndexTest(unittest.TestCase):
    def test_saved_index_and_all_candidates_verify(self) -> None:
        result = validate_index()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["proofs_verified"], 5)
        self.assertEqual(result["candidate_checks"], 40)

    def test_changed_task_bytes_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for path in DEFAULT_INDEX.parent.iterdir():
                if path.is_file():
                    shutil.copy2(path, temporary / path.name)
            task_path = next(temporary.glob("*.task.json"))
            task_path.write_bytes(task_path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "file hash differs"):
                validate_index(temporary / "index.json")


if __name__ == "__main__":
    unittest.main()

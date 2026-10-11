"""The checked-in engineering retrieval manifest must match corpus and code."""

import json
import unittest
from pathlib import Path

from benchmark.retrieval_v1 import freeze_retrieval_manifest, validate_retrieval_manifest


MANIFEST = Path(__file__).resolve().parents[1] / "benchmark" / "retrieval_manifest_v1.json"


class V1RetrievalManifestTest(unittest.TestCase):
    def test_saved_manifest_matches_exact_corpus_and_implementation(self) -> None:
        saved = json.loads(MANIFEST.read_text(encoding="utf-8"))
        validate_retrieval_manifest(saved)
        self.assertEqual(saved, freeze_retrieval_manifest())


if __name__ == "__main__":
    unittest.main()

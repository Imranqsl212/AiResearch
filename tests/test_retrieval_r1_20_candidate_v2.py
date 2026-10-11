"""Identity, fail-closed, and exposure checks for excluded R1 v0.2."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmark import retrieval_r1_20_candidate as parent
from benchmark import retrieval_r1_20_candidate_v2 as candidate


class CandidateV2Tests(unittest.TestCase):
    def test_distinct_frozen_artifacts_and_seven_revisions(self) -> None:
        original = parent._read_rows()
        revised = candidate._read_rows()
        manifest = candidate.verify_candidate_manifest()
        self.assertEqual(len(revised), 20)
        self.assertEqual({row["family"] for row in revised}, set(candidate.FAMILY_ORDER))
        self.assertEqual(set(candidate.REVISED_DOCUMENTS), {
            "transaction_replay", "rolling_rate_limit", "ambiguous_parameters",
            "unicode_identity", "csrf_origin", "key_rotation", "environment_injection",
        })
        self.assertEqual(parent._hash(parent.CORPUS_PATH.read_bytes()), candidate.BASE_CORPUS_SHA256)
        self.assertEqual(parent._hash(parent.CORPUS_PATH.with_name(
            "retrieval_manifest_r1_20_candidate.json").read_bytes()),
            candidate.BASE_MANIFEST_FILE_SHA256)
        self.assertEqual(parent._hash(Path(parent.__file__).read_bytes()), candidate.BASE_PROVIDER_SHA256)
        self.assertNotEqual(manifest["corpus_sha256"], candidate.BASE_CORPUS_SHA256)
        self.assertEqual(manifest["status"], "EXCLUDED_PROTOTYPE_UNREVIEWED")
        self.assertEqual(manifest["top_k"], 1)
        self.assertEqual(len(manifest["document_hashes"]), 20)
        self.assertEqual(len(manifest["public_projection_hashes"]), 20)
        for old, new in zip(original, revised, strict=True):
            self.assertEqual((old["family"], old["domain"]), (new["family"], new["domain"]))
            self.assertTrue(new["document_id"].startswith("r1-20-v2-"))
            if new["family"] not in candidate.REVISED_DOCUMENTS:
                self.assertEqual((old["source"], old["text"]), (new["source"], new["text"]))
            else:
                self.assertNotEqual((old["source"], old["text"]), (new["source"], new["text"]))
        self.assertEqual(candidate.CORPUS_PATH.read_bytes(), candidate.expected_corpus_bytes())
        self.assertEqual(json.loads(candidate.MANIFEST_PATH.read_text()), manifest)

    def test_source_repairs_are_explicit_and_nonprescriptive(self) -> None:
        rows = {row["family"]: row for row in candidate._read_rows()}
        self.assertIn("CWE-426", rows["environment_injection"]["source"])
        self.assertNotIn("CWE-427", rows["environment_injection"]["source"])
        self.assertIn("tr15-58.html", rows["unicode_identity"]["source"])
        self.assertIn("tr39-34.html", rows["unicode_identity"]["source"])
        self.assertIn("docs.stripe.com/api/idempotent_requests", rows["transaction_replay"]["source"])
        self.assertIn("different purpose", rows["transaction_replay"]["text"])
        self.assertIn("different deployment assumptions", rows["csrf_origin"]["text"])
        self.assertIn("archived signatures", rows["key_rotation"]["text"])
        self.assertIn("whether it is exploitable depends", rows["ambiguous_parameters"]["text"])
        self.assertNotIn("near a boundary", rows["rolling_rate_limit"]["text"])
        self.assertNotIn("current key only", rows["key_rotation"]["text"].lower())

    def test_public_only_deterministic_top_one_for_all_families(self) -> None:
        manifest = candidate.verify_candidate_manifest()
        public = parent._catalog()
        for family in candidate.FAMILY_ORDER:
            with self.subTest(family=family):
                task = public[family]
                r0 = candidate.retrieve(task, mode="R0", manifest=manifest)
                r1 = candidate.retrieve(task, mode="R1", manifest=manifest)
                r2 = candidate.retrieve(task, mode="R2", manifest=manifest)
                self.assertEqual(r0["query"], r1["query"])
                self.assertEqual(r0["retrieved_document_ids"], [])
                self.assertEqual(r1["retrieved_document_ids"],
                                 ["r1-20-v2-" + family.replace("_", "-")])
                self.assertGreater(r1["documents"][0]["score"], 0)
                self.assertEqual(r2["retrieved_document_ids"][0], r1["retrieved_document_ids"][0])
                self.assertEqual(len(r2["documents"]), 2)
                self.assertEqual(candidate.agent_visible_documents(r1), [{
                    key: r1["documents"][0][key] for key in ("document_id", "source", "text")
                }])
                self.assertEqual(candidate.retrieve(task, mode="R1", manifest=manifest), r1)

    def test_drift_and_hidden_public_card_fields_fail_closed(self) -> None:
        manifest = candidate.verify_candidate_manifest()
        task = parent._catalog()["transaction_replay"]
        changed = deepcopy(task)
        changed["task_card"]["title"] += " altered"
        with self.assertRaises(candidate.CandidateRetrievalError):
            candidate.retrieve(changed, mode="R1", manifest=manifest)
        altered = deepcopy(manifest)
        altered["top_k"] = 2
        with self.assertRaises(candidate.CandidateRetrievalError):
            candidate.retrieve(task, mode="R1", manifest=altered)
        with tempfile.TemporaryDirectory() as temp:
            corpus_copy = Path(temp) / "corpus.jsonl"
            corpus_copy.write_bytes(candidate.CORPUS_PATH.read_bytes().replace(
                b"A request idempotency key", b"An idempotency key", 1))
            with patch.object(candidate, "CORPUS_PATH", corpus_copy):
                with self.assertRaises(candidate.CandidateRetrievalError):
                    candidate._read_rows()
            manifest_copy = Path(temp) / "manifest.json"
            manifest_copy.write_text("{}", encoding="utf-8")
            with patch.object(candidate, "MANIFEST_PATH", manifest_copy):
                with self.assertRaises(candidate.CandidateRetrievalError):
                    candidate.verify_candidate_manifest()

    def test_no_literal_finite_mode_or_hidden_marker(self) -> None:
        from benchmark import (
            finite_policy_v1, finite_path_v2, finite_replay_v3, finite_race_v4,
            finite_batch_a_v5, finite_batch_b_v5, finite_batch_c_v6,
        )
        from benchmark.finite_family_registry import family_module

        modules = (
            finite_policy_v1, finite_path_v2, finite_replay_v3, finite_race_v4,
            finite_batch_a_v5, finite_batch_b_v5, finite_batch_c_v6,
        )
        c1 = {task["family"]: task for module in modules
              for task in module.build_reference_tasks() if task["condition"] == "C1"}
        for row in candidate._read_rows():
            lower = row["text"].lower()
            self.assertFalse(any(marker in lower for marker in candidate._HIDDEN))
            options = family_module(c1[row["family"]]).public_projection(c1[row["family"]]).get(
                "candidate_modes", [])
            if not options:
                public = family_module(c1[row["family"]]).public_projection(c1[row["family"]])
                options = [part for choices in public.get("candidate_options", {}).values()
                           for part in choices]
            self.assertFalse(any(option.lower() in lower for option in options
                                 if "_" in option or "-" in option))


if __name__ == "__main__":
    unittest.main()

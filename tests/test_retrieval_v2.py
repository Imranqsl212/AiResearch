"""Evidence checks for the separately versioned three-domain retrieval treatment."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from benchmark import finite_path_v2, finite_policy_v1, finite_replay_v3
from benchmark.retrieval_v1 import validate_retrieval_manifest as validate_v1_manifest
from benchmark.retrieval_v2 import (
    CORPUS_PATH,
    GUIDANCE_CORPUS_SHA256,
    RetrievalIntegrityError,
    agent_visible_documents,
    freeze_retrieval_manifest,
    make_public_query,
    retrieval_log_record,
    retrieve,
    validate_retrieval_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
TASKS = (
    ("authorization", "web", "web-authorization-v1", "benchmark/tasks/v1/fp-authorization-c1.task.json", finite_policy_v1.public_projection),
    ("path-boundary", "web", "web-path-boundary-v2", "benchmark/tasks/v2_path/fp-path-boundary-c1.task.json", finite_path_v2.public_projection),
    ("transaction-replay", "payments", "payments-transaction-replay-v2", "benchmark/tasks/v3_replay/fr-transaction-replay-c1.task.json", finite_replay_v3.public_projection),
)


class RetrievalV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((ROOT / "benchmark/retrieval_manifest_v2.json").read_text(encoding="utf-8"))

    @staticmethod
    def public_task(relative: str, project):
        return project(json.loads((ROOT / relative).read_text(encoding="utf-8")))

    def test_corpus_and_manifest_are_byte_and_row_bound(self) -> None:
        self.assertEqual(hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest(), GUIDANCE_CORPUS_SHA256)
        self.assertEqual(self.manifest, freeze_retrieval_manifest())
        self.assertEqual(self.manifest["document_count"], 22)
        validate_retrieval_manifest(self.manifest)
        rows = [json.loads(line) for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines() if line]
        self.assertEqual({row["domain"] for row in rows}, {"crypto", "web", "payments"})
        self.assertEqual(sum(row["domain"] == "payments" for row in rows), 2)
        idempotency = next(row for row in rows if row["document_id"] == "payments-idempotency-v2")
        self.assertIn("same operation twice", idempotency["text"])
        self.assertNotIn("return", idempotency["text"].lower())
        self.assertNotIn("response", idempotency["text"].lower())
        for row in rows:
            canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            self.assertEqual(hashlib.sha256(canonical).hexdigest(), self.manifest["document_hashes"][row["document_id"]])

    def test_v1_freeze_is_not_reinterpreted_as_v2(self) -> None:
        old = json.loads((ROOT / "benchmark/retrieval_manifest_v1.json").read_text(encoding="utf-8"))
        validate_v1_manifest(old)
        self.assertNotEqual(old["corpus_sha256"], self.manifest["corpus_sha256"])
        self.assertNotEqual(old["retrieval_manifest_sha256"], self.manifest["retrieval_manifest_sha256"])

    def test_each_current_fixture_has_deterministic_r0_r1_r2(self) -> None:
        for name, domain, expected_first, relative, project in TASKS:
            task = self.public_task(relative, project)
            with self.subTest(family=name):
                r0 = retrieve(task, mode="R0", manifest=self.manifest)
                self.assertEqual(r0["documents"], [])
                self.assertEqual(r0["query_status"], "constructed_not_executed")
                self.assertIsNone(r0["retrieval_latency_ms"])
                self.assertEqual(retrieval_log_record(r0)["exposure_status"], "not_applicable")
                for mode in ("R1", "R2"):
                    first = retrieve(task, mode=mode, manifest=self.manifest)
                    second = retrieve(task, mode=mode, manifest=self.manifest)
                    self.assertEqual(first["retrieved_document_ids"], second["retrieved_document_ids"])
                    self.assertEqual(first["retrieval_scores"], second["retrieval_scores"])
                    self.assertEqual(first["documents"], second["documents"])
                    self.assertEqual(first["retrieved_document_ids"][0], expected_first)
                    self.assertEqual(first["retrieval_rank"], [1, 2])
                    self.assertEqual(first["documents"][0]["noise_injected"], False)
                    self.assertEqual(first["documents"][0]["document_id"].split("-")[0], domain)
                    if mode == "R2":
                        self.assertTrue(first["documents"][1]["noise_injected"])
                        self.assertNotEqual(first["documents"][1]["document_id"].split("-")[0], domain)
                    else:
                        self.assertFalse(first["documents"][1]["noise_injected"])
                        self.assertEqual(first["documents"][1]["document_id"].split("-")[0], domain)
                    public = agent_visible_documents(first)
                    self.assertTrue(all(set(doc) == {"document_id", "source", "text"} for doc in public))
                    self.assertNotIn("noise_injected", json.dumps(public))
                    exposed = retrieval_log_record(first, exposure_status="delivered")
                    self.assertEqual(exposed["exposure_document_ids"], first["retrieved_document_ids"])
                    self.assertEqual(exposed["documents_used_status"], "unknown")

    def test_exact_fixture_answer_and_hidden_state_markers_absent(self) -> None:
        rows = [json.loads(line) for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines() if line]
        all_text = "\n".join(row["text"] + " " + row["source"] for row in rows).lower()
        for forbidden in (
            "role=guest;session=active", "role=owner;session=active", "role=owner;session=expired",
            "assets/current", "docs/../../private/key.txt", "serve:docs/guide.txt",
            '"fresh"', '"seen"', "proof_sha256", "gate_mode", "ground_truth_state",
            "evaluator_mismatch", "secure_reference", "reference_patch",
        ):
            self.assertNotIn(forbidden.lower(), all_text)
        self.assertIsNone(re.search(r"\bC[1-5]\b", all_text, re.IGNORECASE))
        for _, _, _, relative, project in TASKS:
            public = self.public_task(relative, project)
            query = make_public_query({**public, "condition": "C5", "proof_sha256": "hidden"})
            self.assertNotIn("condition", query.lower())
            self.assertNotIn("proof_sha256", query.lower())

    def test_corpus_or_manifest_tamper_fails_before_retrieval(self) -> None:
        task = self.public_task(TASKS[2][3], TASKS[2][4])
        with tempfile.TemporaryDirectory() as temp:
            copied = Path(temp) / "corpus.jsonl"
            copied.write_bytes(CORPUS_PATH.read_bytes())
            local = freeze_retrieval_manifest(copied)
            lines = copied.read_text(encoding="utf-8").splitlines()
            row = json.loads(lines[-1]); row["text"] += " Changed after freeze."
            lines[-1] = json.dumps(row)
            copied.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(RetrievalIntegrityError):
                retrieve(task, mode="R1", manifest=local, corpus_path=copied)
        altered = json.loads(json.dumps(self.manifest))
        altered["document_hashes"]["payments-idempotency-v2"] = "0" * 64
        with self.assertRaises(RetrievalIntegrityError):
            validate_retrieval_manifest(altered)


if __name__ == "__main__":
    unittest.main()

"""Offline, deterministic checks for the new controlled retrieval treatment."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent.episode_sandbox import project_agent_task
from benchmark.retrieval_v1 import (
    CORPUS_PATH,
    GUIDANCE_CORPUS_SHA256,
    RETRIEVAL_LOG_FIELDS,
    RetrievalIntegrityError,
    agent_visible_documents,
    freeze_retrieval_manifest,
    make_public_query,
    retrieval_log_record,
    retrieve,
    validate_retrieval_manifest,
)
from experiments.run_executable_study import load_catalog


class ControlledRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = freeze_retrieval_manifest()
        cls.task = project_agent_task(load_catalog()[0]).as_mapping()

    def test_frozen_corpus_and_document_hashes(self) -> None:
        self.assertEqual(self.manifest["corpus_sha256"], GUIDANCE_CORPUS_SHA256)
        self.assertEqual(self.manifest["document_count"], 20)
        self.assertEqual(len(self.manifest["document_hashes"]), 20)
        self.assertEqual(self.manifest["config"]["embedding_model"], None)
        self.assertEqual(self.manifest["config"]["top_k"], 2)
        validate_retrieval_manifest(self.manifest)

    def test_r0_constructs_query_without_executing_retrieval(self) -> None:
        result = retrieve(self.task, mode="R0", manifest=self.manifest)
        self.assertFalse(result["retrieval_enabled"])
        self.assertEqual(result["query_status"], "constructed_not_executed")
        self.assertEqual(result["documents"], [])
        self.assertIsNone(result["retrieval_latency_ms"])
        record = retrieval_log_record(result)
        self.assertEqual(record["exposure_status"], "not_applicable")
        self.assertEqual(record["exposure_document_ids"], [])
        self.assertEqual(record["documents_used_status"], "unknown")

    def test_r1_rank_and_score_are_deterministic(self) -> None:
        first = retrieve(self.task, mode="R1", manifest=self.manifest)
        second = retrieve(self.task, mode="R1", manifest=self.manifest)
        for field in ("query", "retrieved_document_ids", "retrieval_scores", "retrieval_rank", "documents"):
            self.assertEqual(first[field], second[field])
        self.assertEqual(first["retrieved_document_ids"], ["crypto-aead-v1", "crypto-nonce-v1"])
        self.assertEqual(first["retrieval_rank"], [1, 2])
        self.assertGreaterEqual(first["retrieval_scores"][0], first["retrieval_scores"][1])
        self.assertIsInstance(first["retrieval_latency_ms"], float)

    def test_r2_preserves_first_result_and_injects_seeded_off_domain_noise(self) -> None:
        relevant = retrieve(self.task, mode="R1", manifest=self.manifest)
        noisy = retrieve(self.task, mode="R2", manifest=self.manifest)
        repeated = retrieve(self.task, mode="R2", manifest=self.manifest)
        self.assertEqual(noisy["documents"], repeated["documents"])
        self.assertEqual(noisy["retrieved_document_ids"][0], relevant["retrieved_document_ids"][0])
        self.assertEqual(len(noisy["documents"]), 2)
        self.assertFalse(noisy["documents"][0]["noise_injected"])
        self.assertTrue(noisy["documents"][1]["noise_injected"])
        self.assertTrue(noisy["documents"][1]["document_id"].startswith("web-"))
        public = agent_visible_documents(noisy)
        self.assertEqual(set(public[0]), {"document_id", "source", "text"})
        self.assertNotIn("noise_injected", json.dumps(public))

    def test_every_family_has_clean_same_domain_retrieval_and_opposite_domain_noise(self) -> None:
        seen: set[tuple[str, str]] = set()
        for row in load_catalog():
            domain, family = row["domain"], row["family"]
            if (domain, family) in seen:
                continue
            seen.add((domain, family))
            public = project_agent_task(row).as_mapping()
            clean = retrieve(public, mode="R1", manifest=self.manifest)
            noisy = retrieve(public, mode="R2", manifest=self.manifest)
            with self.subTest(domain=domain, family=family):
                self.assertEqual(clean["retrieved_document_ids"][0], f"{domain}-{family}-v1")
                self.assertTrue(all(item["document_id"].startswith(domain + "-") for item in clean["documents"]))
                self.assertEqual(noisy["retrieved_document_ids"][0], clean["retrieved_document_ids"][0])
                self.assertFalse(noisy["documents"][-1]["document_id"].startswith(domain + "-"))

    def test_corpus_tampering_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "guidance.jsonl"
            copy.write_bytes(CORPUS_PATH.read_bytes())
            frozen = freeze_retrieval_manifest(copy)
            rows = copy.read_text(encoding="utf-8").splitlines()
            row = json.loads(rows[0])
            row["text"] += " Additional unreviewed sentence."
            rows[0] = json.dumps(row)
            copy.write_text("\n".join(rows) + "\n", encoding="utf-8")
            with self.assertRaises(RetrievalIntegrityError):
                retrieve(self.task, mode="R1", manifest=frozen, corpus_path=copy)

    def test_configuration_and_document_hash_tampering_fail_closed(self) -> None:
        for mutation in (
            lambda value: value["config"].update({"top_k": 3}),
            lambda value: value["document_hashes"].update({"crypto-aead-v1": "0" * 64}),
            lambda value: value.update({"retrieval_manifest_sha256": "0" * 64}),
        ):
            with self.subTest(mutation=mutation):
                altered = json.loads(json.dumps(self.manifest))
                mutation(altered)
                with self.assertRaises(RetrievalIntegrityError):
                    validate_retrieval_manifest(altered)

    def test_public_query_does_not_use_evaluator_metadata(self) -> None:
        query = make_public_query({**self.task, "condition": "UD", "expected_outcome": {"passed": False}})
        self.assertNotIn("UD", query)
        self.assertNotIn("expected_outcome", query)
        altered = json.loads(json.dumps(self.task))
        altered["objective"]["description"] += " expected_outcome"
        with self.assertRaises(RetrievalIntegrityError):
            make_public_query(altered)

    def test_logging_record_distinguishes_retrieval_delivery_and_use(self) -> None:
        result = retrieve(self.task, mode="R1", manifest=self.manifest)
        unknown = retrieval_log_record(result)
        delivered = retrieval_log_record(result, exposure_status="delivered")
        used = retrieval_log_record(
            result, exposure_status="delivered",
            observed_used_document_ids=[result["retrieved_document_ids"][0]],
        )
        self.assertEqual(unknown["exposure_status"], "unknown")
        self.assertIsNone(unknown["exposure_document_ids"])
        self.assertEqual(delivered["exposure_document_ids"], result["retrieved_document_ids"])
        self.assertEqual(delivered["documents_used_status"], "unknown")
        self.assertIsNone(delivered["documents_used"])
        self.assertEqual(used["documents_used_status"], "observed")
        self.assertEqual(used["documents_used"], [result["retrieved_document_ids"][0]])
        self.assertEqual(delivered["retrieval_rank"], [1, 2])
        self.assertEqual(delivered["retrieval_scores"], result["retrieval_scores"])
        self.assertEqual(delivered["corpus_sha256"], self.manifest["corpus_sha256"])
        self.assertEqual(delivered["config_sha256"], self.manifest["config_sha256"])
        self.assertEqual(delivered["retrieval_manifest_sha256"], self.manifest["retrieval_manifest_sha256"])
        self.assertEqual(set(delivered), RETRIEVAL_LOG_FIELDS)
        self.assertEqual(json.loads(json.dumps(delivered)), delivered)
        self.assertNotIn("text", json.dumps(delivered))
        with self.assertRaises(RetrievalIntegrityError):
            retrieval_log_record(result, exposure_status="delivered", observed_used_document_ids=["not-in-corpus"])
        altered = json.loads(json.dumps(result))
        altered["retrieval_rank"] = [1, 1]
        with self.assertRaises(RetrievalIntegrityError):
            retrieval_log_record(altered, exposure_status="delivered")


if __name__ == "__main__":
    unittest.main()

"""Offline contracts for the excluded matched R0/R1/R2 live block."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.v1_ollama_adapter import V1OllamaAdapter
from experiments.run_v1_rag_block import (
    RAGBlockError, execute_block, prepare, verify_prepared, verify_run_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
DIGEST = "a" * 64


class RAGBlockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.block = Path(self.temp.name) / "rag-block"

    def _prepare(self) -> dict:
        return prepare(self.block, model="fixture-local:1", model_digest=DIGEST,
                       episode_seed=11, order_seed=73, max_steps=6,
                       max_output_tokens=128, num_ctx=4096)

    def test_prepare_is_zero_call_and_freezes_balanced_retrieval(self) -> None:
        with patch("urllib.request.build_opener", side_effect=AssertionError("Ollama contacted")):
            report = self._prepare()
        self.assertEqual(report["status"], "PREPARED_NO_MODEL_CALLS")
        self.assertEqual(verify_prepared(self.block)["model_calls"], 0)
        schedule = json.loads((self.block / "block_schedule.json").read_text())
        self.assertEqual(len(schedule["slots"]), 9)
        self.assertEqual({(slot["condition"], slot["retrieval_mode"])
                          for slot in schedule["slots"]},
                         {(condition, mode) for condition in ("C1", "C2", "C4")
                          for mode in ("R0", "R1", "R2")})
        self.assertEqual({slot["seed"] for slot in schedule["slots"]}, {11})
        self.assertEqual({slot["temperature"] for slot in schedule["slots"]}, {0.3})
        self.assertFalse(schedule["input_context_length_matched"])
        self.assertTrue(all(not slot["expected_retrieved_document_ids"]
                            for slot in schedule["slots"] if slot["retrieval_mode"] == "R0"))
        self.assertTrue(all(slot["expected_retrieved_document_ids"]
                            for slot in schedule["slots"] if slot["retrieval_mode"] != "R0"))
        self.assertTrue(all(slot["expected_noise_document_ids"]
                            for slot in schedule["slots"] if slot["retrieval_mode"] == "R2"))
        self.assertTrue(all(slot["baseline"] == ("B3" if slot["retrieval_mode"] == "R0" else "B5")
                            for slot in schedule["slots"]))
        with self.assertRaisesRegex(RAGBlockError, "exists"):
            self._prepare()

    def test_prepared_verification_refuses_changed_retrieval_manifest(self) -> None:
        self._prepare()
        path = self.block / "retrieval_manifest.json"
        data = json.loads(path.read_text())
        data["config"]["top_k"] = 1
        path.write_text(json.dumps(data) + "\n")
        with self.assertRaisesRegex(RAGBlockError, "hash drift"):
            verify_prepared(self.block)

    def test_digest_mismatch_records_zero_call_abort(self) -> None:
        self._prepare()
        with patch("urllib.request.build_opener", side_effect=AssertionError("Ollama contacted")):
            with self.assertRaisesRegex(RAGBlockError, "digest changed"):
                execute_block(self.block, model_digest_provider=lambda _: "b" * 64)
        receipt = json.loads((self.block / "run.receipt.json").read_text())
        self.assertEqual(receipt["status"], "ABORTED_PREFLIGHT")
        self.assertEqual(receipt["model_requests_recorded"], 0)
        self.assertEqual(receipt["attempted_slot_count"], 0)
        self.assertEqual(len(receipt["slot_results"]), 9)
        self.assertTrue(all(row["status"] == "NOT_ATTEMPTED" for row in receipt["slot_results"]))
        self.assertEqual(verify_run_receipt(self.block)["run_status"], "ABORTED_PREFLIGHT")

    def test_offline_fake_transport_produces_nine_hash_linked_excluded_episodes(self) -> None:
        self._prepare()
        calls = []

        def fake_adapter(slot, schedule):
            def post_json(url, request, timeout):
                calls.append((slot["slot_id"], request["options"].copy()))
                return {"message": {"content": '{"action":"claim","payload":{"status":"unknown"}}'},
                        "prompt_eval_count": 32, "eval_count": 7}

            return V1OllamaAdapter(
                model=schedule["model"], max_output_tokens=schedule["max_output_tokens"],
                context_window=schedule["num_ctx"],
                request_timeout=schedule["request_timeout_seconds"], post_json=post_json,
            )

        with patch("urllib.request.build_opener", side_effect=AssertionError("Ollama contacted")):
            result = execute_block(self.block, model_digest_provider=lambda _: DIGEST,
                                   adapter_factory=fake_adapter)
        self.assertEqual(result["status"], "COMPLETE_EXCLUDED_PILOT")
        self.assertEqual((result["valid_slot_count"], result["invalidated_slot_count"]), (9, 0))
        self.assertEqual(result["model_requests_recorded"], 9)
        self.assertEqual(len(calls), 9)
        self.assertTrue(all(options == {"temperature": 0.3, "num_ctx": 4096,
                                            "num_predict": 128, "seed": 11}
                            for _, options in calls))
        verified = verify_run_receipt(self.block)
        self.assertEqual(verified["main_eligible_episodes"], 0)
        self.assertIsNone(verified["population_rates"])
        receipt = json.loads((self.block / "run.receipt.json").read_text())
        self.assertEqual({row["retrieval_exposure_status"] for row in receipt["slot_results"]
                          if row["retrieval_mode"] != "R0"}, {"delivered"})
        lengths = {mode: [row["initial_request_characters"] for row in receipt["slot_results"]
                          if row["retrieval_mode"] == mode]
                   for mode in ("R0", "R1", "R2")}
        self.assertGreater(min(lengths["R1"]), max(lengths["R0"]))
        self.assertGreater(min(lengths["R2"]), max(lengths["R0"]))
        with self.assertRaisesRegex(RAGBlockError, "receipt exists"):
            execute_block(self.block, model_digest_provider=lambda _: DIGEST,
                          adapter_factory=fake_adapter)
        first_options = self.block / receipt["slot_results"][0]["slot_id"] / "provider_options.jsonl"
        saved = first_options.read_text()
        first_options.write_text(saved.replace('"num_predict":128', '"num_predict":129'))
        with self.assertRaisesRegex(RAGBlockError, "provider options"):
            verify_run_receipt(self.block)


if __name__ == "__main__":
    unittest.main()

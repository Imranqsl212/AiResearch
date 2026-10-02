from __future__ import annotations

import json
import unittest

from agent.episode_sandbox import project_agent_task
from benchmark.retrieval import RETRIEVAL_VERSION, augment_task, build_retrieval_context, load_corpus
from experiments.run_executable_study import load_catalog
from experiments.run_rag_factorial_study import build_factorial_tasks, validate_retrieval_design


class RagFactorialTests(unittest.TestCase):
    def test_corpus_covers_every_executable_family(self) -> None:
        report = validate_retrieval_design()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["corpus_documents"], 20)
        self.assertEqual(report["factorial_arms"], 160)

    def test_pilot_is_three_complete_eight_cell_family_blocks(self) -> None:
        rows = build_factorial_tasks(phase="pilot")
        self.assertEqual(len(rows), 24)
        for family in {str(row["family"]) for row in rows}:
            block = [row for row in rows if row["family"] == family]
            self.assertEqual({row["condition"] for row in block}, {"RD", "UD", "RW", "UW"})
            self.assertEqual({row["retrieval_mode"] for row in block}, {"off", "relevant"})

    def test_agent_projection_contains_guidance_but_not_hidden_labels(self) -> None:
        base = load_catalog()[0]
        row = augment_task(base, "relevant")
        public = project_agent_task(row).as_mapping()
        payload = json.dumps(public, ensure_ascii=False).lower()
        self.assertEqual(public["retrieval_context"]["retrieval_version"], RETRIEVAL_VERSION)
        self.assertNotIn('"condition"', payload)
        self.assertNotIn("expected_outcome", payload)
        self.assertNotIn("verifier_id", payload)

    def test_off_arm_has_identical_query_and_no_documents(self) -> None:
        base = load_catalog()[0]
        off = build_retrieval_context(base, "off")
        on = build_retrieval_context(base, "relevant")
        self.assertEqual(off["query"], on["query"])
        self.assertEqual(off["corpus_sha256"], on["corpus_sha256"])
        self.assertEqual(off["documents"], [])
        self.assertEqual(len(on["documents"]), 1)

    def test_corpus_has_no_duplicate_keys(self) -> None:
        self.assertEqual(len(load_corpus()), 20)


if __name__ == "__main__":
    unittest.main()

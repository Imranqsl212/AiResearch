import unittest
from rag_experiment.context import build_context
from rag_experiment.models import Document
from rag_experiment.retriever import SemanticRetriever


class FakeEncoder:
    def encode(self, texts):
        return [[1.0, 0.0] if "sql" in text.lower() else [0.0, 1.0] for text in texts]


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.docs = [Document("sql", "web", "sql", "source", "sql safety"), Document("other", "web", "other", "source", "other safety")]
        self.retriever = SemanticRetriever(self.docs, FakeEncoder())

    def test_relevant_document_ranks_first(self):
        matches = self.retriever.search("SQL query", top_k=1)
        self.assertEqual(matches[0].document.document_id, "sql")
        self.assertIn('"id": "sql"', build_context(matches))

    def test_threshold_and_invalid_query(self):
        self.assertEqual(len(self.retriever.search("sql", min_score=0.5)), 1)
        with self.assertRaises(ValueError):
            self.retriever.search(" ")


if __name__ == "__main__":
    unittest.main()

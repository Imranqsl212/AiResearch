"""Deterministic cosine retrieval over a frozen corpus."""
import math
from collections.abc import Sequence
from .encoder import Encoder
from .models import Document, Match


def _unit(vector: Sequence[float]) -> tuple[float, ...]:
    values = tuple(float(value) for value in vector)
    length = math.sqrt(sum(value * value for value in values))
    if not values or not math.isfinite(length) or length == 0:
        raise ValueError("Embedding must be finite and nonzero")
    return tuple(value / length for value in values)


def _similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions differ")
    return sum(a * b for a, b in zip(left, right))


class SemanticRetriever:
    def __init__(self, documents: Sequence[Document], encoder: Encoder) -> None:
        self.documents, self.encoder = tuple(documents), encoder
        vectors = encoder.encode([doc.searchable_text() for doc in self.documents])
        if len(vectors) != len(self.documents):
            raise ValueError("Encoder returned an unexpected document count")
        self.vectors = tuple(_unit(vector) for vector in vectors)

    def search(self, query: str, top_k: int = 2, min_score: float = 0.0) -> list[Match]:
        if not query.strip() or top_k < 1 or not -1 <= min_score <= 1:
            raise ValueError("Invalid query, top_k, or minimum similarity")
        vectors = self.encoder.encode([query])
        if len(vectors) != 1:
            raise ValueError("Encoder returned an unexpected query count")
        return self._rank(_unit(vectors[0]), top_k, min_score)

    def _rank(self, query: Sequence[float], top_k: int, minimum: float) -> list[Match]:
        matches = [Match(doc, _similarity(query, vec)) for doc, vec in zip(self.documents, self.vectors)]
        return sorted((item for item in matches if item.score >= minimum), key=lambda item: (-item.score, item.document.document_id))[:top_k]

"""Embedding backend, loaded lazily to keep the experiment optional."""
from typing import Protocol, Sequence


class Encoder(Protocol):
    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


class SentenceEncoder:
    def __init__(self, model: str, revision: str) -> None:
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model, revision=revision)

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return self.model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False).tolist()

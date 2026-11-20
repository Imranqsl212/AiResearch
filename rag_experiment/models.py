"""Immutable public documents and retrieval results."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    document_id: str
    domain: str
    family: str
    source: str
    text: str

    def searchable_text(self) -> str:
        return f"{self.domain} {self.family.replace('-', ' ')} {self.text}"


@dataclass(frozen=True)
class Match:
    document: Document
    score: float

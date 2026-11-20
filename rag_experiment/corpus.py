"""Load a frozen JSONL corpus with explicit provenance."""
import hashlib
import json
from pathlib import Path
from .models import Document


def corpus_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _document(line: str) -> Document:
    row = json.loads(line)
    return Document(**{key: row[key] for key in Document.__dataclass_fields__})


def load_corpus(path: Path) -> tuple[Document, ...]:
    documents = tuple(_document(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip())
    if not documents or len({doc.document_id for doc in documents}) != len(documents):
        raise ValueError("Corpus must contain documents with unique IDs")
    if any(not all(isinstance(value, str) and value.strip() for value in vars(doc).values()) for doc in documents):
        raise ValueError("Every document field must be a nonempty string")
    return documents

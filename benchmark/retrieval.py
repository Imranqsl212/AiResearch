"""Frozen, evaluator-reviewed retrieval context for the RAG ablation.

The corpus contains design-level security guidance, never reference source code,
condition labels, verifier internals, or task-specific expected outputs. Retrieval is
deterministic by the public domain/family metadata so that RAG is a controlled
experimental factor rather than an unlogged online service.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "benchmark" / "retrieval_corpus.jsonl"
RETRIEVAL_VERSION = "security-guidance-rag-0.1.0"
MODES = frozenset({"off", "relevant"})


def corpus_sha256(path: Path = CORPUS_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_corpus(path: Path = CORPUS_PATH) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"retrieval corpus line {line_number} is not an object")
        key = (str(row.get("domain", "")), str(row.get("family", "")))
        if not all(key) or key in rows:
            raise ValueError(f"invalid or duplicate retrieval key at line {line_number}: {key}")
        if not isinstance(row.get("document_id"), str) or not isinstance(row.get("text"), str):
            raise ValueError(f"retrieval corpus line {line_number} lacks document_id/text")
        rows[key] = row
    return rows


def build_retrieval_context(
    task: Mapping[str, Any], mode: str, path: Path = CORPUS_PATH
) -> dict[str, Any]:
    """Return the public retrieval payload for one predeclared treatment arm."""

    if mode not in MODES:
        raise ValueError(f"unsupported retrieval mode: {mode}")
    base = {
        "retrieval_version": RETRIEVAL_VERSION,
        "mode": mode,
        "corpus_sha256": corpus_sha256(path),
        "query": {
            "domain": str(task["domain"]),
            "family": str(task["family"]),
        },
    }
    if mode == "off":
        return {**base, "documents": []}
    row = load_corpus(path).get((str(task["domain"]), str(task["family"])))
    if row is None:
        raise ValueError(
            f"no retrieval document for {task.get('domain')}/{task.get('family')}"
        )
    return {
        **base,
        "documents": [
            {
                "document_id": row["document_id"],
                "source": row["source"],
                "text": row["text"],
            }
        ],
    }


def augment_task(task: Mapping[str, Any], mode: str) -> dict[str, Any]:
    """Create a unique treatment-arm record without changing executable semantics."""

    row = dict(task)
    row["base_task_id"] = str(task["task_id"])
    row["task_id"] = f"{task['task_id']}--rag-{mode}"
    # The scheduler requires one four-cell block per task_family. Target execution
    # still uses ``family``; this field only separates the RAG blocks.
    row["task_family"] = f"{task['family']}--rag-{mode}"
    row["retrieval_mode"] = mode
    row["retrieval_context"] = build_retrieval_context(task, mode)
    return row

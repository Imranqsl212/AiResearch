"""Frozen, local lexical retrieval for the next RAG ablation.

This module is separate from the v0.5 fixed-guidance treatment. It accepts only a
public task projection, never a full evaluator task, and performs no network I/O.
The caller must freeze and retain a manifest before collection, validate it at
retrieval time, and log the returned exposure after delivering the public context.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


CORPUS_PATH = Path(__file__).resolve().parent / "retrieval_corpus_v1.jsonl"
GUIDANCE_CORPUS_SHA256 = "8fb4dabffc9891179c91bd8419f2c5762686ba5ae307fa9b213d44ef85c2a56d"
RETRIEVAL_VERSION = "controlled-local-retrieval-v1.0.0"
ALGORITHM = "domain-filtered-tfidf-public-family-bonus-v1"
TOKENIZER = "ascii-alphanumeric-lower-v1"
CHUNKING = "whole-document-v1"
NOISE_POLICY = "replace-final-rank-with-seeded-opposite-domain-document-v1"
MODES = frozenset({"R0", "R1", "R2"})
RETRIEVAL_LOG_FIELDS = frozenset({
    "retrieval_version", "mode", "retrieval_enabled", "query", "query_source", "query_status",
    "retrieved_document_ids", "retrieval_scores", "retrieval_rank", "retrieval_latency_ms",
    "retrieved_documents", "exposure_document_ids", "exposure_status",
    "documents_used_status", "documents_used", "corpus_sha256", "config_sha256",
    "retrieval_manifest_sha256",
})
_TOKENS = re.compile(r"[a-z0-9]+")
_DOCUMENT_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_HIDDEN_MARKERS = (
    "condition_reachable", "expected_outcome", "secure_reference", "reference_patch",
    "reference solution", "solution.py", "vulnerable.py", "verifier", "task_id",
    "evaluator_only", "ground_truth", "hidden condition",
)
_HIDDEN_CELL = re.compile(r"\b(?:rd|ud|rw|uw)\b", re.IGNORECASE)


class RetrievalIntegrityError(ValueError):
    """The frozen corpus or retrieval configuration no longer matches its manifest."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKENS.findall(value.lower()))


def _check_public_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 8192:
        raise RetrievalIntegrityError(f"{label} must be bounded non-empty text")
    lowered = value.lower()
    if any(marker in lowered for marker in _HIDDEN_MARKERS) or _HIDDEN_CELL.search(value):
        raise RetrievalIntegrityError(f"{label} contains an evaluator-only marker")
    if "```" in value or re.search(r"(?m)^\s*(?:def|class|import|from)\s+", value):
        raise RetrievalIntegrityError(f"{label} contains source-like content")


def _load_corpus(path: Path) -> tuple[bytes, list[dict[str, str]]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise RetrievalIntegrityError(f"retrieval corpus is unavailable: {path}") from exc
    if path.resolve() == CORPUS_PATH.resolve() and _sha256(raw) != GUIDANCE_CORPUS_SHA256:
        raise RetrievalIntegrityError("repository guidance corpus differs from its reviewed SHA-256")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise RetrievalIntegrityError("retrieval corpus is not UTF-8") from exc
    rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_families: set[tuple[str, str]] = set()
    required = {"document_id", "domain", "family", "source", "text"}
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RetrievalIntegrityError(f"invalid corpus JSON at line {line_number}") from exc
        if not isinstance(row, dict) or set(row) != required:
            raise RetrievalIntegrityError(f"corpus line {line_number} must have only the five public document fields")
        if not all(isinstance(row[key], str) and row[key].strip() for key in required):
            raise RetrievalIntegrityError(f"corpus line {line_number} contains an empty/non-string field")
        document_id, domain, family = row["document_id"], row["domain"], row["family"]
        if not _DOCUMENT_ID.fullmatch(document_id) or domain not in {"crypto", "web"}:
            raise RetrievalIntegrityError(f"corpus line {line_number} has an invalid document ID/domain")
        if not _DOCUMENT_ID.fullmatch(family):
            raise RetrievalIntegrityError(f"corpus line {line_number} has an invalid family")
        if document_id in seen_ids or (domain, family) in seen_families:
            raise RetrievalIntegrityError(f"corpus line {line_number} duplicates a document ID or family")
        _check_public_text(row["text"], f"corpus line {line_number} text")
        _check_public_text(row["source"], f"corpus line {line_number} source")
        seen_ids.add(document_id)
        seen_families.add((domain, family))
        rows.append(row)
    if len(rows) < 3 or (path.resolve() == CORPUS_PATH.resolve() and len(rows) != 20):
        raise RetrievalIntegrityError("retrieval corpus must contain the frozen document set")
    return raw, rows


def freeze_retrieval_manifest(
    corpus_path: Path = CORPUS_PATH, *, top_k: int = 2, noise_seed: int = 7
) -> dict[str, Any]:
    """Construct the create-once manifest to store before the first episode."""

    if type(top_k) is not int or top_k < 2:
        raise RetrievalIntegrityError("top_k must be at least two for the noisy arm")
    if type(noise_seed) is not int or noise_seed < 0:
        raise RetrievalIntegrityError("noise_seed must be a non-negative integer")
    raw, rows = _load_corpus(corpus_path)
    if top_k > len(rows):
        raise RetrievalIntegrityError("top_k exceeds the corpus size")
    if any(sum(row["domain"] == domain for row in rows) < top_k for domain in {"crypto", "web"}):
        raise RetrievalIntegrityError("top_k exceeds the available same-domain documents")
    document_hashes = {row["document_id"]: _sha256(_canonical_bytes(row)) for row in rows}
    config = {
        "algorithm": ALGORITHM,
        "tokenizer": TOKENIZER,
        "chunking": CHUNKING,
        "embedding_model": None,
        "reranker": None,
        "top_k": top_k,
        "noise_policy": NOISE_POLICY,
        "noise_seed": noise_seed,
    }
    manifest: dict[str, Any] = {
        "retrieval_version": RETRIEVAL_VERSION,
        "corpus_file": corpus_path.name,
        "corpus_sha256": _sha256(raw),
        "document_count": len(rows),
        "document_hashes": dict(sorted(document_hashes.items())),
        "config": config,
        "config_sha256": _sha256(_canonical_bytes(config)),
        "implementation_sha256": _sha256(Path(__file__).read_bytes()),
    }
    manifest["retrieval_manifest_sha256"] = _sha256(_canonical_bytes(manifest))
    return manifest


def validate_retrieval_manifest(manifest: Mapping[str, Any], corpus_path: Path = CORPUS_PATH) -> None:
    """Fail closed on any corpus, document, implementation, or setting drift."""

    if not isinstance(manifest, Mapping) or not isinstance(manifest.get("config"), Mapping):
        raise RetrievalIntegrityError("retrieval manifest/config is missing")
    config = manifest["config"]
    expected = freeze_retrieval_manifest(
        corpus_path, top_k=config.get("top_k"), noise_seed=config.get("noise_seed")
    )
    if dict(manifest) != expected:
        raise RetrievalIntegrityError("retrieval manifest does not match the frozen corpus/configuration")


def make_public_query(public_task: Mapping[str, Any]) -> str:
    """Use an allowlist of agent-visible fields, excluding IDs and evaluator metadata."""

    objective = public_task.get("objective")
    card = public_task.get("task_card")
    environment = public_task.get("environment")
    if not all(isinstance(value, Mapping) for value in (objective, card, environment)):
        raise RetrievalIntegrityError("retrieval requires a public task projection")
    domain = environment.get("domain")
    description = objective.get("description")
    title = card.get("title")
    card_description = card.get("description")
    if domain not in {"crypto", "web"}:
        raise RetrievalIntegrityError("public task domain is unsupported")
    for label, value in (("objective.description", description), ("task_card.title", title), ("task_card.description", card_description)):
        _check_public_text(value, label)
    query = " ".join(f"{domain} {description} {title} {card_description}".split())
    _check_public_text(query, "retrieval query")
    return query


def _rank(query: str, rows: Sequence[Mapping[str, str]]) -> list[tuple[dict[str, str], float]]:
    query_terms = set(_tokens(query))
    documents = [
        (dict(row), Counter(_tokens(" ".join((row["domain"], row["family"].replace("-", " "), row["text"])))) )
        for row in rows
    ]
    document_frequency = Counter(term for _, counts in documents for term in counts)
    total = len(documents)
    scores: list[tuple[dict[str, str], float]] = []
    for row, counts in documents:
        score = sum(
            (1.0 + math.log((total + 1) / (document_frequency[term] + 1))) * min(counts[term], 3)
            for term in query_terms if counts[term]
        )
        # The family name is public task vocabulary, not an evaluator condition.
        # A bounded exact metadata match prevents generic words such as "security"
        # from outranking the relevant family document (notably SQL injection).
        family_terms = set(_tokens(row["family"]))
        if family_terms and family_terms.issubset(query_terms):
            score += 8.0
        scores.append((row, round(score, 8)))
    return sorted(scores, key=lambda item: (-item[1], item[0]["document_id"]))


def _noise_document(
    ranked: Sequence[tuple[dict[str, str], float]], *, selected_ids: set[str],
    primary_domain: str, query: str, seed: int
) -> tuple[dict[str, str], float]:
    candidates = [item for item in ranked if item[0]["document_id"] not in selected_ids and item[0]["domain"] != primary_domain]
    if not candidates:
        raise RetrievalIntegrityError("no opposite-domain document is available for R2")
    return min(
        candidates,
        key=lambda item: _sha256(f"{seed}|{query}|{item[0]['document_id']}".encode("utf-8")),
    )


def retrieve(
    public_task: Mapping[str, Any], *, mode: str, manifest: Mapping[str, Any],
    corpus_path: Path = CORPUS_PATH
) -> dict[str, Any]:
    """Return public documents and a complete local retrieval trace for R0/R1/R2."""

    if mode not in MODES:
        raise RetrievalIntegrityError(f"unsupported retrieval mode: {mode}")
    validate_retrieval_manifest(manifest, corpus_path)
    query = make_public_query(public_task)
    public_domain = public_task["environment"]["domain"]
    enabled = mode != "R0"
    started = time.perf_counter() if enabled else None
    selected: list[tuple[dict[str, str], float, bool]] = []
    if enabled:
        _, rows = _load_corpus(corpus_path)
        ranked = _rank(query, rows)
        same_domain_ranked = [item for item in ranked if item[0]["domain"] == public_domain]
        if not same_domain_ranked or same_domain_ranked[0][1] <= 0:
            raise RetrievalIntegrityError("retrieval found no defensible same-domain match")
        top_k = manifest["config"]["top_k"]
        if mode == "R1":
            selected = [(row, score, False) for row, score in same_domain_ranked[:top_k]]
        else:
            selected = [(row, score, False) for row, score in same_domain_ranked[: top_k - 1]]
            noise = _noise_document(
                ranked, selected_ids={row["document_id"] for row, _, _ in selected},
                primary_domain=public_domain, query=query,
                seed=manifest["config"]["noise_seed"],
            )
            selected.append((noise[0], noise[1], True))
    documents = [
        {
            "document_id": row["document_id"], "source": row["source"], "text": row["text"],
            "document_sha256": manifest["document_hashes"][row["document_id"]],
            "rank": index, "score": score, "noise_injected": noise,
        }
        for index, (row, score, noise) in enumerate(selected, 1)
    ]
    latency = round((time.perf_counter() - started) * 1000, 6) if started is not None else None
    return {
        "retrieval_version": RETRIEVAL_VERSION,
        "mode": mode,
        "retrieval_enabled": enabled,
        "query": query,
        "query_source": "public_task_projection",
        "query_status": "executed" if enabled else "constructed_not_executed",
        "documents": documents,
        "retrieved_document_ids": [item["document_id"] for item in documents],
        "retrieval_scores": [item["score"] for item in documents],
        "retrieval_rank": [item["rank"] for item in documents],
        "retrieval_latency_ms": latency,
        "corpus_sha256": manifest["corpus_sha256"],
        "config_sha256": manifest["config_sha256"],
        "retrieval_manifest_sha256": manifest["retrieval_manifest_sha256"],
    }


def agent_visible_documents(result: Mapping[str, Any]) -> list[dict[str, str]]:
    """Project retrieved content without treatment labels, scores, or trace hashes."""

    documents = result.get("documents")
    if not isinstance(documents, list):
        raise RetrievalIntegrityError("retrieval result lacks documents")
    visible: list[dict[str, str]] = []
    for document in documents:
        if not isinstance(document, Mapping) or any(
            not isinstance(document.get(field), str) or not document[field]
            for field in ("document_id", "source", "text")
        ):
            raise RetrievalIntegrityError("retrieval result contains a malformed public document")
        visible.append({field: document[field] for field in ("document_id", "source", "text")})
    return visible


def retrieval_log_record(
    result: Mapping[str, Any], *, exposure_status: str = "unknown",
    observed_used_document_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a TASK_START/ACTION payload without inferring document use.

    Call with ``exposure_status='delivered'`` only after the public document payload
    actually crossed the adapter boundary. ``observed_used_document_ids`` is None
    unless instrumented observable behavior establishes use; an empty list means
    observed non-use, which differs from unknown.
    """

    if exposure_status not in {"unknown", "delivered", "not_delivered"}:
        raise RetrievalIntegrityError("invalid retrieval exposure status")
    ids = result.get("retrieved_document_ids")
    documents = result.get("documents")
    if not isinstance(ids, list) or not isinstance(documents, list) or ids != [row.get("document_id") for row in documents]:
        raise RetrievalIntegrityError("retrieval result/document IDs are inconsistent")
    if len(ids) != len(set(ids)) or result.get("retrieval_rank") != list(range(1, len(ids) + 1)):
        raise RetrievalIntegrityError("retrieval result has duplicate IDs or non-contiguous ranks")
    if result.get("retrieval_scores") != [row.get("score") for row in documents]:
        raise RetrievalIntegrityError("retrieval scores do not match the selected documents")
    if any(not isinstance(row.get("document_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", row["document_sha256"])
           or row.get("rank") != index or not isinstance(row.get("noise_injected"), bool)
           for index, row in enumerate(documents, 1)):
        raise RetrievalIntegrityError("retrieval document trace is malformed")
    enabled = result.get("retrieval_enabled") is True
    mode = result.get("mode")
    if mode not in MODES or enabled != (mode != "R0"):
        raise RetrievalIntegrityError("retrieval mode and enabled flag disagree")
    if enabled and (not ids or result.get("query_status") != "executed" or result.get("retrieval_latency_ms") is None):
        raise RetrievalIntegrityError("enabled retrieval lacks a query result or latency")
    if not enabled and (result.get("query_status") != "constructed_not_executed" or result.get("retrieval_latency_ms") is not None):
        raise RetrievalIntegrityError("R0 must not report an executed query or latency")
    if mode == "R1" and any(row["noise_injected"] for row in documents):
        raise RetrievalIntegrityError("R1 must not contain injected noise")
    if mode == "R2" and (len(documents) < 2 or [row["noise_injected"] for row in documents] != [False] * (len(documents) - 1) + [True]):
        raise RetrievalIntegrityError("R2 must identify exactly one final-rank noise document")
    if not enabled and (ids or observed_used_document_ids):
        raise RetrievalIntegrityError("R0 cannot retrieve or use documents")
    if observed_used_document_ids is not None:
        used = list(observed_used_document_ids)
        if len(used) != len(set(used)) or not set(used).issubset(ids):
            raise RetrievalIntegrityError("observed used-document IDs must be a unique subset of retrieval")
        if exposure_status != "delivered" and used:
            raise RetrievalIntegrityError("document use cannot be observed before delivery")
    else:
        used = None
    effective_status = exposure_status if enabled else "not_applicable"
    exposure_ids = ids if effective_status == "delivered" else ([] if effective_status in {"not_delivered", "not_applicable"} else None)
    record = {
        "retrieval_version": result["retrieval_version"],
        "mode": result["mode"],
        "retrieval_enabled": enabled,
        "query": result["query"],
        "query_source": result["query_source"],
        "query_status": result["query_status"],
        "retrieved_document_ids": list(ids),
        "retrieval_scores": list(result["retrieval_scores"]),
        "retrieval_rank": list(result["retrieval_rank"]),
        "retrieval_latency_ms": result["retrieval_latency_ms"],
        "retrieved_documents": [
            {
                "document_id": row["document_id"], "document_sha256": row["document_sha256"],
                "rank": row["rank"], "score": row["score"], "noise_injected": row["noise_injected"],
            }
            for row in documents
        ],
        "exposure_document_ids": exposure_ids,
        "exposure_status": effective_status,
        "documents_used_status": "unknown" if used is None else "observed",
        "documents_used": used,
        "corpus_sha256": result["corpus_sha256"],
        "config_sha256": result["config_sha256"],
        "retrieval_manifest_sha256": result["retrieval_manifest_sha256"],
    }
    if set(record) != RETRIEVAL_LOG_FIELDS:
        raise RetrievalIntegrityError("retrieval log schema drifted from its frozen field set")
    return record

"""Excluded top-one retrieval candidate bound to the current v7 finite cards.

The eight batch-C public projections changed between v6 and v7. This module
therefore has its own corpus and manifest identity; it never silently accepts
the older v0.2 projection hashes. Source/relevance review is still pending.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from benchmark import finite_batch_c_v7 as batch_c_v7
from benchmark import retrieval_r1_20_candidate as base
from benchmark import retrieval_r1_20_candidate_v2 as parent


ROOT = Path(__file__).resolve().parent
CORPUS_PATH = ROOT / "retrieval_corpus_r1_20_candidate_v7.jsonl"
MANIFEST_PATH = ROOT / "retrieval_manifest_r1_20_candidate_v7.json"
VERSION = "excluded-r1-20-candidate-v7.0.1"
STATUS = "EXCLUDED_PROTOTYPE_UNREVIEWED"
MODES = frozenset({"R0", "R1"})
CandidateRetrievalError = base.CandidateRetrievalError


def _catalog() -> dict[str, dict[str, Any]]:
    """Use v1-v5 cards for twelve families and v7 for all eight batch-C cards."""
    public = base._catalog()
    grouped: dict[str, dict[str, bytes]] = {}
    for task in batch_c_v7.build_reference_tasks():
        family, condition = task["family"], task["condition"]
        projection = batch_c_v7.public_projection(task)
        grouped.setdefault(family, {})[condition] = base._canonical(projection)
        public[family] = projection
    if set(grouped) != set(batch_c_v7.FAMILIES) or set(public) != set(base.FAMILY_ORDER):
        raise CandidateRetrievalError("v7 public catalog family coverage differs")
    for family, variants in grouped.items():
        if set(variants) != {"C1", "C2", "C3", "C4", "C5"} or len(set(variants.values())) != 1:
            raise CandidateRetrievalError(f"v7 public projection differs within {family}")
    return public


def expected_rows() -> list[dict[str, str]]:
    parent.verify_candidate_manifest()
    public = _catalog()
    rows: list[dict[str, str]] = []
    for old in parent._read_rows():
        row = dict(old)
        row["document_id"] = "r1-20-v7-" + row["family"].replace("_", "-")
        if row["domain"] != public[row["family"]]["environment"]["domain"]:
            raise CandidateRetrievalError("v7 domain differs from inherited source card")
        rows.append(row)
    if tuple(row["family"] for row in rows) != base.FAMILY_ORDER:
        raise CandidateRetrievalError("v7 source corpus family order differs")
    return rows


def expected_corpus_bytes() -> bytes:
    return b"".join(base._canonical(row) + b"\n" for row in expected_rows())


def _read_rows() -> list[dict[str, str]]:
    if CORPUS_PATH.read_bytes() != expected_corpus_bytes():
        raise CandidateRetrievalError("v7 source corpus drifted")
    rows = [json.loads(line) for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines()]
    if len(rows) != 20 or len({row["document_id"] for row in rows}) != 20:
        raise CandidateRetrievalError("v7 source corpus needs twenty unique rows")
    return rows


def freeze_candidate_manifest() -> dict[str, Any]:
    rows, public = _read_rows(), _catalog()
    parent_manifest = parent.verify_candidate_manifest()
    body: dict[str, Any] = {
        "retrieval_version": VERSION,
        "status": STATUS,
        "algorithm": "public-domain-filtered-top-one-lexical-v0",
        "corpus_sha256": base._hash(CORPUS_PATH.read_bytes()),
        "implementation_sha256": base._hash(Path(__file__).read_bytes()),
        "parent_v2_manifest_sha256": parent_manifest["manifest_sha256"],
        "parent_v2_corpus_sha256": parent_manifest["corpus_sha256"],
        "top_k": 1,
        "document_hashes": {row["document_id"]: base._hash(base._canonical(row))
                            for row in rows},
        "public_projection_hashes": {family: base._hash(base._canonical(public[family]))
                                     for family in base.FAMILY_ORDER},
    }
    return {**body, "manifest_sha256": base._hash(base._canonical(body))}


def verify_candidate_manifest() -> dict[str, Any]:
    try:
        saved = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateRetrievalError("v7 retrieval manifest missing or invalid") from exc
    expected = freeze_candidate_manifest()
    if saved != expected:
        raise CandidateRetrievalError("v7 retrieval manifest drifted")
    return expected


def retrieve(public_task: Mapping[str, Any], *, mode: str,
             manifest: Mapping[str, Any]) -> dict[str, Any]:
    if mode not in MODES:
        raise CandidateRetrievalError("v7 retrieval supports R0/R1 only")
    if dict(manifest) != verify_candidate_manifest():
        raise CandidateRetrievalError("v7 retrieval manifest differs")
    public = _catalog()
    family = next((family for family, projection in public.items()
                   if base._canonical(projection) == base._canonical(public_task)), None)
    if family is None:
        raise CandidateRetrievalError("unfrozen v7 public task projection")
    query = base._public_query(public_task)
    rows = _read_rows()
    selected: list[tuple[dict[str, str], float]] = []
    if mode == "R1":
        domain = public_task["environment"]["domain"]
        candidates = [row for row in rows if row["domain"] == domain]
        ranked = sorted(((row, base._score(query, row, rows)) for row in candidates),
                        key=lambda pair: (-pair[1], pair[0]["document_id"]))
        if not ranked or ranked[0][1] <= 0:
            raise CandidateRetrievalError("no relevant v7 same-domain source")
        selected.append(ranked[0])
    documents = [{
        "document_id": row["document_id"], "source": row["source"],
        "text": row["text"],
        "document_sha256": manifest["document_hashes"][row["document_id"]],
        "rank": rank, "score": score, "noise_injected": False,
    } for rank, (row, score) in enumerate(selected, 1)]
    return {
        "retrieval_version": VERSION, "prototype_status": STATUS,
        "mode": mode, "query": query, "query_source": "public_task_projection",
        "documents": documents,
        "retrieved_document_ids": [row["document_id"] for row in documents],
        "corpus_sha256": manifest["corpus_sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
    }


def agent_visible_documents(result: Mapping[str, Any]) -> list[dict[str, str]]:
    return base.agent_visible_documents(result)


if __name__ == "__main__":
    expected = expected_corpus_bytes()
    if CORPUS_PATH.exists() and CORPUS_PATH.read_bytes() != expected:
        raise CandidateRetrievalError("refusing to overwrite changed v7 corpus")
    CORPUS_PATH.write_bytes(expected)
    manifest = freeze_candidate_manifest()
    if MANIFEST_PATH.exists() and json.loads(MANIFEST_PATH.read_text()) != manifest:
        raise CandidateRetrievalError("refusing to overwrite changed v7 manifest")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")

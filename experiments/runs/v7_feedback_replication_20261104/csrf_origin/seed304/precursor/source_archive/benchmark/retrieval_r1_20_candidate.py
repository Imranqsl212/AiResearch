"""Excluded, fail-closed top-one R1 prototype for the 20 finite task cards.

This is a candidate corpus and deterministic public-card retriever, not an
admitted main-study retrieval implementation. It is intentionally separate
from the existing v1/v2 retrievers, collector, and experiment manifest.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CORPUS_PATH = ROOT / "retrieval_corpus_r1_20_candidate.jsonl"
V2_CORPUS_PATH = ROOT / "retrieval_corpus_v2.jsonl"
V2_CORPUS_SHA256 = "635da9eaecee5c1ba8f577a129540e6edcce4067d6ac64cbb1f8d76a6d6e52e1"
VERSION = "excluded-r1-20-candidate-v0.1"
MODES = frozenset({"R0", "R1", "R2"})
FAMILY_ORDER = (
    "authorization", "path-boundary", "transaction_replay", "counter_race",
    "rolling_rate_limit", "ambiguous_parameters", "quota_overflow", "encoded_log_secret",
    "webhook_integrity", "upload_content", "unicode_identity", "dns_rebinding",
    "csrf_origin", "nonce_uniqueness", "signature_algorithm",
    "deserialization_allowlist", "tls_hostname", "key_rotation", "kdf_salt",
    "environment_injection",
)
INHERITED = {
    "authorization": "web-authorization-v1",
    "path-boundary": "web-path-boundary-v2",
    "transaction_replay": "payments-transaction-replay-v2",
    "encoded_log_secret": "crypto-secret-leakage-v1",
    "dns_rebinding": "web-ssrf-v1",
    "csrf_origin": "web-csrf-v1",
    "nonce_uniqueness": "crypto-nonce-v1",
    "tls_hostname": "crypto-certificate-validation-v1",
    "key_rotation": "crypto-key-management-v1",
    "kdf_salt": "crypto-key-derivation-v1",
}

# Each new paragraph is a conservative paraphrase of the linked primary page.
# Topic-level source checking is not independent scientific or leakage review.
NEW_DOCUMENTS = {
    "counter_race": (
        "MITRE CWE-362 https://cwe.mitre.org/data/definitions/362.html",
        "Concurrent read, update, and write operations on shared state can interfere and leave an unexpected result when execution is not synchronized.",
    ),
    "rolling_rate_limit": (
        "Redis rate limiter https://redis.io/docs/latest/develop/use-cases/rate-limiter/",
        "A request limit can be keyed by user or tenant across distributed service instances. Fixed and sliding time windows can count requests differently near a boundary.",
    ),
    "ambiguous_parameters": (
        "OWASP WSTG HTTP Parameter Pollution https://wstg.owasp.org/latest/4-Web_Application_Security_Testing/07-Injection/04-HTTP_Parameter_Pollution/",
        "Repeated HTTP parameter names may be interpreted differently by components or parsers, changing which supplied value is checked and acted on.",
    ),
    "quota_overflow": (
        "MITRE CWE-190 https://cwe.mitre.org/data/definitions/190.html",
        "Integer wraparound can turn a security-critical quota calculation into an incorrect decision when the mathematical result exceeds the stored representation.",
    ),
    "webhook_integrity": (
        "GitHub Validating webhook deliveries https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries",
        "A webhook signature authenticates a delivery payload; transformations before verification can change the data whose integrity is being checked.",
    ),
    "upload_content": (
        "OWASP File Upload Cheat Sheet https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html",
        "An uploaded filename or Content-Type header can be deceptive. A file may contain active content even when its metadata looks like an approved type.",
    ),
    "unicode_identity": (
        "Unicode UTS #39 https://www.unicode.org/reports/tr39/",
        "Different Unicode identifier strings can be visually confusable or share a comparison skeleton. A skeleton is not a general replacement for identity comparison.",
    ),
    "signature_algorithm": (
        "RFC 8725 section 3.1 https://www.rfc-editor.org/rfc/rfc8725.html#section-3.1",
        "A signed token's algorithm declaration is untrusted input. Verification must account for which algorithms are supported and which algorithm belongs with a key.",
    ),
    "deserialization_allowlist": (
        "OWASP Deserialization Cheat Sheet https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html",
        "Untrusted serialized data may name object types that an application did not intend to construct. Type handling is part of the deserialization trust boundary.",
    ),
    "environment_injection": (
        "MITRE CWE-427 https://cwe.mitre.org/data/definitions/427.html",
        "Externally controlled search-path settings, including PATH, can change which executable or library a process selects.",
    ),
}
_TOKENS = re.compile(r"[a-z0-9]+")
_HIDDEN = ("ground_truth", "condition_reachable", "secure_reference", "reference_patch",
           "evaluator_only", "expected_outcome", "solution.py", "vulnerable.py")
_SOURCE_HOSTS = ("cwe.mitre.org", "redis.io", "wstg.owasp.org", "docs.github.com",
                 "cheatsheetseries.owasp.org", "www.unicode.org", "www.rfc-editor.org",
                 "csrc.nist.gov", "www.stripe.com", "docs.stripe.com")


class CandidateRetrievalError(ValueError):
    pass


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _tokens(value: str) -> set[str]:
    return set(_TOKENS.findall(value.lower()))


def _catalog() -> dict[str, dict[str, Any]]:
    from benchmark.finite_family_registry import family_module
    from benchmark import (
        finite_policy_v1, finite_path_v2, finite_replay_v3, finite_race_v4,
        finite_batch_a_v5, finite_batch_b_v5, finite_batch_c_v6,
    )

    modules = (finite_policy_v1, finite_path_v2, finite_replay_v3, finite_race_v4,
               finite_batch_a_v5, finite_batch_b_v5, finite_batch_c_v6)
    grouped: dict[str, dict[str, bytes]] = {}
    public: dict[str, dict[str, Any]] = {}
    for module in modules:
        for task in module.build_reference_tasks():
            family, condition = task["family"], task["condition"]
            projection = family_module(task).public_projection(task)
            grouped.setdefault(family, {})[condition] = _canonical(projection)
            public[family] = projection
    if tuple(sorted(grouped)) != tuple(sorted(FAMILY_ORDER)):
        raise CandidateRetrievalError("the current finite catalog is not the expected 20 families")
    for family, variants in grouped.items():
        if set(variants) != {"C1", "C2", "C3", "C4", "C5"} or len(set(variants.values())) != 1:
            raise CandidateRetrievalError(f"public C1-C5 projection differs within {family}")
    return public


def expected_rows() -> list[dict[str, str]]:
    if _hash(V2_CORPUS_PATH.read_bytes()) != V2_CORPUS_SHA256:
        raise CandidateRetrievalError("inherited v2 source corpus drifted")
    v2 = {row["document_id"]: row for row in map(json.loads, V2_CORPUS_PATH.read_text(encoding="utf-8").splitlines())}
    public = _catalog()
    if set(INHERITED) | set(NEW_DOCUMENTS) != set(FAMILY_ORDER) or set(INHERITED) & set(NEW_DOCUMENTS):
        raise CandidateRetrievalError("every family needs exactly one declared source")
    rows: list[dict[str, str]] = []
    for family in FAMILY_ORDER:
        if family in INHERITED:
            parent = v2[INHERITED[family]]
            source, body = parent["source"], parent["text"]
        else:
            source, body = NEW_DOCUMENTS[family]
        rows.append({
            "document_id": "r1-20-" + family.replace("_", "-"),
            "domain": public[family]["environment"]["domain"],
            "family": family,
            "source": source,
            "text": body,
        })
    return rows


def expected_corpus_bytes() -> bytes:
    return b"".join(_canonical(row) + b"\n" for row in expected_rows())


def write_candidate_corpus() -> None:
    expected = expected_corpus_bytes()
    if CORPUS_PATH.exists():
        if CORPUS_PATH.read_bytes() != expected:
            raise CandidateRetrievalError("refusing to overwrite altered candidate corpus")
        return
    CORPUS_PATH.write_bytes(expected)


def _read_rows() -> list[dict[str, str]]:
    try:
        raw = CORPUS_PATH.read_bytes()
    except OSError as exc:
        raise CandidateRetrievalError("candidate corpus missing") from exc
    if raw != expected_corpus_bytes():
        raise CandidateRetrievalError("candidate corpus changed or public task catalog drifted")
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    if len(rows) != 20:
        raise CandidateRetrievalError("candidate corpus must contain exactly 20 rows")
    for row in rows:
        if set(row) != {"document_id", "domain", "family", "source", "text"}:
            raise CandidateRetrievalError("unexpected candidate corpus field")
        if len(row["text"]) > 800 or any(marker in row["text"].lower() for marker in _HIDDEN):
            raise CandidateRetrievalError("candidate text contains a hidden marker or is too long")
        if not any(("https://" + host + "/") in row["source"] for host in _SOURCE_HOSTS):
            raise CandidateRetrievalError("candidate source must be an allowed primary site")
    return rows


def freeze_candidate_manifest() -> dict[str, Any]:
    rows = _read_rows()
    public = _catalog()
    body: dict[str, Any] = {
        "retrieval_version": VERSION,
        "status": "EXCLUDED_PROTOTYPE_UNREVIEWED",
        "algorithm": "public-domain-filtered-top-one-lexical-v0",
        "corpus_sha256": _hash(CORPUS_PATH.read_bytes()),
        "implementation_sha256": _hash(Path(__file__).read_bytes()),
        "top_k": 1,
        "noise_seed": 7,
        "document_hashes": {row["document_id"]: _hash(_canonical(row)) for row in rows},
        "public_projection_hashes": {family: _hash(_canonical(public[family])) for family in FAMILY_ORDER},
        "inherited_v2_corpus_sha256": V2_CORPUS_SHA256,
    }
    return {**body, "manifest_sha256": _hash(_canonical(body))}


def _public_query(public_task: Mapping[str, Any]) -> str:
    try:
        domain = public_task["environment"]["domain"]
        description = public_task["objective"]["description"]
        title = public_task["task_card"]["title"]
        card_description = public_task["task_card"]["description"]
    except (KeyError, TypeError) as exc:
        raise CandidateRetrievalError("a public task card is required") from exc
    parts = (domain, description, title, card_description)
    if not all(isinstance(part, str) and part.strip() and len(part) <= 8192 for part in parts):
        raise CandidateRetrievalError("public query fields must be bounded text")
    query = " ".join(" ".join(parts).split())
    if any(marker in query.lower() for marker in _HIDDEN):
        raise CandidateRetrievalError("public query contains hidden evaluator metadata")
    return query


def _score(query: str, row: Mapping[str, str], rows: list[dict[str, str]]) -> float:
    terms = _tokens(query)
    row_terms = Counter(_TOKENS.findall((row["family"] + " " + row["text"]).lower()))
    document_frequency = Counter(
        term for item in rows for term in _tokens(item["family"] + " " + item["text"])
    )
    return round(sum((1.0 + math.log((len(rows) + 1) / (document_frequency[token] + 1)))
                     * min(row_terms[token], 3) for token in terms if row_terms[token]), 8)


def retrieve(public_task: Mapping[str, Any], *, mode: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Prototype exposure. R2 is exploratory because it adds a second document."""
    if mode not in MODES:
        raise CandidateRetrievalError("unsupported retrieval mode")
    if dict(manifest) != freeze_candidate_manifest():
        raise CandidateRetrievalError("candidate manifest drifted")
    public = _catalog()
    digest = _hash(_canonical(public_task))
    if digest not in manifest["public_projection_hashes"].values():
        raise CandidateRetrievalError("unfrozen public task projection")
    query = _public_query(public_task)
    rows = _read_rows()
    selected: list[tuple[dict[str, str], float, bool]] = []
    if mode != "R0":
        domain = public_task["environment"]["domain"]
        candidates = [row for row in rows if row["domain"] == domain]
        ranked = sorted(((row, _score(query, row, rows)) for row in candidates),
                        key=lambda pair: (-pair[1], pair[0]["document_id"]))
        if not ranked or ranked[0][1] <= 0:
            raise CandidateRetrievalError("no relevant same-domain source")
        selected.append((*ranked[0], False))
        if mode == "R2":
            other = [row for row in rows if row["domain"] != domain]
            noisy = min(other, key=lambda row: _hash(f"7|{query}|{row['document_id']}".encode("utf-8")))
            selected.append((noisy, _score(query, noisy, rows), True))
    documents = [{
        "document_id": row["document_id"], "source": row["source"], "text": row["text"],
        "document_sha256": manifest["document_hashes"][row["document_id"]],
        "rank": rank, "score": score, "noise_injected": noisy,
    } for rank, (row, score, noisy) in enumerate(selected, 1)]
    return {
        "retrieval_version": VERSION, "prototype_status": "EXCLUDED_PROTOTYPE_UNREVIEWED",
        "mode": mode, "query": query, "query_source": "public_task_projection",
        "documents": documents, "retrieved_document_ids": [row["document_id"] for row in documents],
        "corpus_sha256": manifest["corpus_sha256"], "manifest_sha256": manifest["manifest_sha256"],
    }


def agent_visible_documents(result: Mapping[str, Any]) -> list[dict[str, str]]:
    return [{key: row[key] for key in ("document_id", "source", "text")}
            for row in result["documents"]]


if __name__ == "__main__":
    write_candidate_corpus()
    print(json.dumps(freeze_candidate_manifest(), indent=2, sort_keys=True))

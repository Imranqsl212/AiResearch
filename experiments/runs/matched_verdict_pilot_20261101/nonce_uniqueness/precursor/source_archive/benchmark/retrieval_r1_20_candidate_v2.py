"""Second excluded twenty-family R1 candidate, with source-support repairs.

This module deliberately reuses the pinned v0.1 public-card retrieval algorithm.
Its corpus and manifest have distinct identities. Neither this module nor its
outputs are admitted to the main experiment or to the earlier live pilot.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from benchmark import retrieval_r1_20_candidate as base


ROOT = Path(__file__).resolve().parent
CORPUS_PATH = ROOT / "retrieval_corpus_r1_20_candidate_v2.jsonl"
MANIFEST_PATH = ROOT / "retrieval_manifest_r1_20_candidate_v2.json"
VERSION = "excluded-r1-20-candidate-v0.2"
STATUS = "EXCLUDED_PROTOTYPE_UNREVIEWED"
BASE_CORPUS_SHA256 = "d02ba8823d3abd6879f0bbcce442fece31101effd01d994352a9e9302e94eea6"
BASE_MANIFEST_FILE_SHA256 = "857bc652a0d6339d6b9780d4431742b4edc197e9a723b3bd656cdf85d9b77c32"
BASE_PROVIDER_SHA256 = "c69d44424ec415e9f39ecc748f599e352cd1336ffa91fa8ba41d7c734bd34119"
FAMILY_ORDER = base.FAMILY_ORDER
MODES = base.MODES
CandidateRetrievalError = base.CandidateRetrievalError
_HIDDEN = base._HIDDEN
_URLS = re.compile(r"https://[^\s;]+")
_PRIMARY_HOSTS = frozenset({
    "cwe.mitre.org", "redis.io", "wstg.owasp.org", "docs.github.com",
    "cheatsheetseries.owasp.org", "www.unicode.org", "www.rfc-editor.org",
    "csrc.nist.gov", "docs.stripe.com",
})

# These are short primary-source paraphrases, not the finite task's oracle or
# a human source/relevance/leakage approval. Each entry replaces one old row.
REVISED_DOCUMENTS = {
    "transaction_replay": (
        "OWASP Transaction Authorization Cheat Sheet https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html; "
        "Stripe Idempotent requests https://docs.stripe.com/api/idempotent_requests",
        "Transaction authorization is enforced on the server. A request idempotency key can relate a retry to an earlier result; it serves a different purpose from an authorization credential, and neither source defines every application's transaction approval policy.",
    ),
    "rolling_rate_limit": (
        "Redis rate limiter https://redis.io/docs/latest/develop/use-cases/rate-limiter/",
        "Rate limits can apply to a user or tenant across distributed service instances. Fixed-window and sliding-window algorithms and shared state are implementation choices that must match the service's stated quota policy.",
    ),
    "ambiguous_parameters": (
        "OWASP WSTG HTTP Parameter Pollution https://wstg.owasp.org/latest/4-Web_Application_Security_Testing/07-Injection/04-HTTP_Parameter_Pollution/",
        "Duplicate HTTP parameter names may be interpreted differently by components. This creates a risk when validation and later use select different values; whether it is exploitable depends on the application's parsing and validation behavior.",
    ),
    "unicode_identity": (
        "Unicode UAX #15, version 18.0.0 https://www.unicode.org/reports/tr15/tr15-58.html; "
        "Unicode UTS #39, version 18.0.0 https://www.unicode.org/reports/tr39/tr39-34.html",
        "Unicode NFKC can merge compatibility-equivalent strings. A confusable skeleton tests visual similarity instead; it is not identifier normalization or an application identity-equality rule.",
    ),
    "csrf_origin": (
        "OWASP Cross-Site Request Forgery Prevention Cheat Sheet https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html",
        "Validated anti-CSRF tokens and request-origin checks are established defenses with different deployment assumptions. An application may layer these checks according to its own policy.",
    ),
    "key_rotation": (
        "OWASP Key Management Cheat Sheet https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html",
        "Key rotation needs a policy for issuing, retiring, and retaining keys. An old public verification key may remain useful for archived signatures, so old-key acceptance depends on the artifact and application policy.",
    ),
    "environment_injection": (
        "MITRE CWE-426 https://cwe.mitre.org/data/definitions/426.html",
        "An untrusted search-path setting, including PATH, can redirect the lookup of a critical program or library. The risk depends on whether an outside party can influence the search path used for that lookup.",
    ),
}


def _check_base() -> None:
    if base._hash(base.CORPUS_PATH.read_bytes()) != BASE_CORPUS_SHA256:
        raise CandidateRetrievalError("parent candidate corpus drifted")
    if base._hash(base.CORPUS_PATH.with_name("retrieval_manifest_r1_20_candidate.json").read_bytes()) != BASE_MANIFEST_FILE_SHA256:
        raise CandidateRetrievalError("parent candidate manifest drifted")
    if base._hash(Path(base.__file__).read_bytes()) != BASE_PROVIDER_SHA256:
        raise CandidateRetrievalError("parent candidate provider drifted")


def expected_rows() -> list[dict[str, str]]:
    _check_base()
    old_rows = base._read_rows()
    if len(old_rows) != 20 or set(REVISED_DOCUMENTS) - set(FAMILY_ORDER):
        raise CandidateRetrievalError("parent candidate coverage changed")
    rows: list[dict[str, str]] = []
    for row in old_rows:
        revised = dict(row)
        revised["document_id"] = "r1-20-v2-" + row["family"].replace("_", "-")
        if row["family"] in REVISED_DOCUMENTS:
            revised["source"], revised["text"] = REVISED_DOCUMENTS[row["family"]]
        rows.append(revised)
    if tuple(row["family"] for row in rows) != FAMILY_ORDER:
        raise CandidateRetrievalError("parent candidate order changed")
    return rows


def expected_corpus_bytes() -> bytes:
    return b"".join(base._canonical(row) + b"\n" for row in expected_rows())


def write_candidate_corpus() -> None:
    expected = expected_corpus_bytes()
    if CORPUS_PATH.exists():
        if CORPUS_PATH.read_bytes() != expected:
            raise CandidateRetrievalError("refusing to overwrite altered v2 candidate corpus")
        return
    CORPUS_PATH.write_bytes(expected)


def _read_rows() -> list[dict[str, str]]:
    try:
        raw = CORPUS_PATH.read_bytes()
    except OSError as exc:
        raise CandidateRetrievalError("v2 candidate corpus missing") from exc
    if raw != expected_corpus_bytes():
        raise CandidateRetrievalError("v2 candidate corpus or public catalog drifted")
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    if len(rows) != 20 or len({row["document_id"] for row in rows}) != 20:
        raise CandidateRetrievalError("v2 candidate must contain twenty unique rows")
    for row in rows:
        if set(row) != {"document_id", "domain", "family", "source", "text"}:
            raise CandidateRetrievalError("unexpected v2 candidate field")
        if len(row["text"]) > 800 or any(marker in row["text"].lower() for marker in _HIDDEN):
            raise CandidateRetrievalError("v2 candidate text contains a hidden marker or is too long")
        urls = _URLS.findall(row["source"])
        if not urls or any(urlparse(url).hostname not in _PRIMARY_HOSTS for url in urls):
            raise CandidateRetrievalError("v2 candidate source must be a declared primary site")
    return rows


def freeze_candidate_manifest() -> dict[str, Any]:
    rows = _read_rows()
    public = base._catalog()
    body: dict[str, Any] = {
        "retrieval_version": VERSION,
        "status": STATUS,
        "algorithm": "public-domain-filtered-top-one-lexical-v0",
        "corpus_sha256": base._hash(CORPUS_PATH.read_bytes()),
        "implementation_sha256": base._hash(Path(__file__).read_bytes()),
        "parent_candidate_corpus_sha256": BASE_CORPUS_SHA256,
        "parent_candidate_manifest_file_sha256": BASE_MANIFEST_FILE_SHA256,
        "parent_candidate_implementation_sha256": BASE_PROVIDER_SHA256,
        "top_k": 1,
        "noise_seed": 7,
        "document_hashes": {row["document_id"]: base._hash(base._canonical(row)) for row in rows},
        "public_projection_hashes": {family: base._hash(base._canonical(public[family])) for family in FAMILY_ORDER},
    }
    return {**body, "manifest_sha256": base._hash(base._canonical(body))}


def verify_candidate_manifest() -> dict[str, Any]:
    try:
        saved = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateRetrievalError("v2 candidate manifest missing or invalid") from exc
    expected = freeze_candidate_manifest()
    if saved != expected:
        raise CandidateRetrievalError("v2 candidate manifest drifted")
    return expected


def retrieve(public_task: Mapping[str, Any], *, mode: str,
             manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Excluded exposure; R2 remains exploratory noise injection."""
    if mode not in MODES:
        raise CandidateRetrievalError("unsupported retrieval mode")
    if dict(manifest) != verify_candidate_manifest():
        raise CandidateRetrievalError("v2 candidate manifest drifted")
    public = base._catalog()
    digest = base._hash(base._canonical(public_task))
    if digest not in manifest["public_projection_hashes"].values():
        raise CandidateRetrievalError("unfrozen public task projection")
    query = base._public_query(public_task)
    rows = _read_rows()
    selected: list[tuple[dict[str, str], float, bool]] = []
    if mode != "R0":
        domain = public_task["environment"]["domain"]
        candidates = [row for row in rows if row["domain"] == domain]
        ranked = sorted(((row, base._score(query, row, rows)) for row in candidates),
                        key=lambda pair: (-pair[1], pair[0]["document_id"]))
        if not ranked or ranked[0][1] <= 0:
            raise CandidateRetrievalError("no relevant same-domain source")
        selected.append((*ranked[0], False))
        if mode == "R2":
            other = [row for row in rows if row["domain"] != domain]
            noisy = min(other, key=lambda row: base._hash(
                f"7|{query}|{row['document_id']}".encode("utf-8")))
            selected.append((noisy, base._score(query, noisy, rows), True))
    documents = [{
        "document_id": row["document_id"], "source": row["source"], "text": row["text"],
        "document_sha256": manifest["document_hashes"][row["document_id"]],
        "rank": rank, "score": score, "noise_injected": noisy,
    } for rank, (row, score, noisy) in enumerate(selected, 1)]
    return {
        "retrieval_version": VERSION, "prototype_status": STATUS,
        "mode": mode, "query": query, "query_source": "public_task_projection",
        "documents": documents, "retrieved_document_ids": [row["document_id"] for row in documents],
        "corpus_sha256": manifest["corpus_sha256"], "manifest_sha256": manifest["manifest_sha256"],
    }


def agent_visible_documents(result: Mapping[str, Any]) -> list[dict[str, str]]:
    return base.agent_visible_documents(result)


if __name__ == "__main__":
    write_candidate_corpus()
    manifest = freeze_candidate_manifest()
    if MANIFEST_PATH.exists():
        verify_candidate_manifest()
    else:
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))

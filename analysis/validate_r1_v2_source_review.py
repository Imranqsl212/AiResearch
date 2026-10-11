"""Structural audit for the separate R1 v0.2 human source-review records.

This checks exact candidate/source-byte identity and form consistency. It cannot
authenticate reviewers, judge source support or leakage, or admit main runs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from analysis import capture_r1_source_snapshots_v2 as snapshots
from benchmark import retrieval_r1_20_candidate_v2 as candidate


ROOT = Path(__file__).resolve().parents[1]
REVIEW_REGISTER = ROOT / "docs" / "R1_V2_SOURCE_REVIEW_REGISTER_20261005.csv"
ADJUDICATION_REGISTER = ROOT / "docs" / "R1_V2_SOURCE_ADJUDICATION_REGISTER_20261005.csv"
SNAPSHOT_DIR = snapshots.DEFAULT_OUTPUT
VERSION = "excluded-r1-20-candidate-v0.2"
CORPUS_SHA256 = "01b24e29b1c938abfb80e6bceaa5e0b6a0f55c130191cf3e2f4031e4f6d61894"
CANDIDATE_MANIFEST_FILE_SHA256 = "10f345f98698c814ba0b5672ce1063ca134375b8815f9e4edd951d4953dc4ad3"
SNAPSHOT_MANIFEST_SHA256 = "61a99e3e20cba1b97a7007e8eed087bd828e0c38ae1db7ec8e628a4cdbb2a259"
URL_RE = re.compile(r"https://[^\s;]+")
HEX_RE = re.compile(r"[0-9a-f]{64}\Z")
BINDING_COLUMNS = (
    "family", "retrieval_version", "document_id", "document_sha256",
    "public_projection_sha256", "corpus_sha256", "candidate_manifest_file_sha256",
    "snapshot_manifest_sha256", "source_urls", "source_body_sha256s",
    "source_body_files",
)
REVIEW_COLUMNS = BINDING_COLUMNS + (
    "reviewer_slot", "reviewer_name", "expertise", "conflict",
    "source_support", "task_relevance", "semantic_leak", "answer_cue",
    "source_evidence", "task_evidence", "notes", "disposition",
    "review_date", "attestation",
)
ADJUDICATION_COLUMNS = BINDING_COLUMNS + (
    "adjudicator_name", "expertise", "conflict", "reviewer_a_disposition",
    "reviewer_b_disposition", "disagreement_resolution", "final_disposition",
    "rationale", "evidence", "decision_date", "attestation",
)
SUPPORT_VALUES = {"PENDING", "PASS", "FAIL", "UNCERTAIN"}
LEAK_VALUES = {"PENDING", "NO_LEAK", "LEAK", "UNCERTAIN"}
CUE_VALUES = {"PENDING", "ACCEPTABLE", "TOO_DIRECT", "UNCERTAIN"}
DISPOSITIONS = {"PENDING", "KEEP", "REWRITE", "REJECT"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _date_valid(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _filled(row: dict[str, str], fields: tuple[str, ...]) -> bool:
    return all(row[field].strip() and row[field].strip() != "PENDING" for field in fields)


def expected_bindings(snapshot_dir: Path = SNAPSHOT_DIR) -> dict[str, dict[str, str]]:
    """Rebuild each form's frozen evidence binding from verified local bytes."""
    if _sha256(candidate.CORPUS_PATH.read_bytes()) != CORPUS_SHA256:
        raise ValueError("R1 v0.2 corpus differs from packet")
    if _sha256(candidate.MANIFEST_PATH.read_bytes()) != CANDIDATE_MANIFEST_FILE_SHA256:
        raise ValueError("R1 v0.2 candidate manifest differs from packet")
    manifest = candidate.verify_candidate_manifest()
    snapshot = snapshots.verify(snapshot_dir)
    if snapshot["manifest_sha256"] != SNAPSHOT_MANIFEST_SHA256:
        raise ValueError("R1 v0.2 snapshot manifest differs from packet")
    if snapshot["capture_status"] != "COMPLETE" or snapshot["source_count"] != 22:
        raise ValueError("R1 v0.2 requires all 22 frozen source bodies")
    if snapshot["candidate_corpus_sha256"] != CORPUS_SHA256 or snapshot["candidate_manifest_file_sha256"] != CANDIDATE_MANIFEST_FILE_SHA256:
        raise ValueError("snapshot archive binds another candidate")
    entries = {entry["url"]: entry for entry in snapshot["entries"]}
    result: dict[str, dict[str, str]] = {}
    for doc in candidate._read_rows():
        family = doc["family"]
        urls = URL_RE.findall(doc["source"])
        if not urls or len(set(urls)) != len(urls):
            raise ValueError(f"bad cited URL inventory for {family}")
        if any(url not in entries or family not in entries[url]["families"] for url in urls):
            raise ValueError(f"source snapshot does not bind {family}")
        body_hashes = [entries[url]["body_sha256"] for url in urls]
        body_files = [entries[url]["body_file"] for url in urls]
        if any(not isinstance(digest, str) or not HEX_RE.fullmatch(digest) for digest in body_hashes):
            raise ValueError(f"missing source body hash for {family}")
        result[family] = {
            "family": family,
            "retrieval_version": VERSION,
            "document_id": doc["document_id"],
            "document_sha256": manifest["document_hashes"][doc["document_id"]],
            "public_projection_sha256": manifest["public_projection_hashes"][family],
            "corpus_sha256": CORPUS_SHA256,
            "candidate_manifest_file_sha256": CANDIDATE_MANIFEST_FILE_SHA256,
            "snapshot_manifest_sha256": SNAPSHOT_MANIFEST_SHA256,
            "source_urls": " | ".join(urls),
            "source_body_sha256s": " | ".join(body_hashes),
            "source_body_files": " | ".join(body_files),
        }
    if len(result) != 20:
        raise ValueError("R1 v0.2 family coverage is not 20")
    return result


def _read_csv(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != columns:
            raise ValueError(f"wrong columns in {path.name}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"malformed CSV row in {path.name}")
    return rows


def validate(
    review_path: Path = REVIEW_REGISTER,
    adjudication_path: Path = ADJUDICATION_REGISTER,
    *,
    snapshot_dir: Path = SNAPSHOT_DIR,
) -> dict[str, Any]:
    """Report form state; never issue an R1 or main-study admission verdict."""
    errors: list[str] = []
    try:
        bindings = expected_bindings(snapshot_dir)
        reviews = _read_csv(review_path, REVIEW_COLUMNS)
        adjudications = _read_csv(adjudication_path, ADJUDICATION_COLUMNS)
    except (OSError, ValueError, KeyError, TypeError, candidate.CandidateRetrievalError) as exc:
        return {
            "status": "INVALID_EVIDENCE_OR_FORMS", "errors": [str(exc)],
            "pending_review_rows": None, "pending_adjudication_rows": None,
            "recorded_keep_families": [], "human_review_verified": False,
            "r1_admitted": False, "main_ready": False,
        }
    expected_review_keys = {(family, slot) for family in bindings for slot in ("A", "B")}
    seen_reviews: dict[tuple[str, str], dict[str, str]] = {}
    pending_reviews = 0
    for row in reviews:
        key = (row["family"], row["reviewer_slot"])
        if key not in expected_review_keys or key in seen_reviews:
            errors.append(f"unexpected or duplicate reviewer slot: {key}")
            continue
        seen_reviews[key] = row
        family = row["family"]
        if any(row[field] != value for field, value in bindings[family].items()):
            errors.append(f"R1 v0.2 source/document binding mismatch: {key}")
        if row["source_support"] not in SUPPORT_VALUES or row["task_relevance"] not in SUPPORT_VALUES:
            errors.append(f"invalid support or relevance token: {key}")
        if row["semantic_leak"] not in LEAK_VALUES or row["answer_cue"] not in CUE_VALUES:
            errors.append(f"invalid leakage or answer-cue token: {key}")
        decision = row["disposition"]
        if decision not in DISPOSITIONS:
            errors.append(f"invalid reviewer disposition: {key}")
        if decision == "PENDING":
            pending_reviews += 1
            continue
        if not _filled(row, ("reviewer_name", "expertise", "conflict", "source_evidence",
                             "task_evidence", "notes", "review_date", "attestation")):
            errors.append(f"completed review lacks identity or evidence: {key}")
        if not _date_valid(row["review_date"]):
            errors.append(f"invalid review date: {key}")
        source_segments = row["source_evidence"].split(" | ")
        if (len(source_segments) != len(bindings[family]["source_urls"].split(" | "))
                or any(not segment.strip() for segment in source_segments)):
            errors.append(f"source evidence must cover every cited URL: {key}")
        if decision == "KEEP":
            if (row["source_support"], row["task_relevance"], row["semantic_leak"], row["answer_cue"]) != ("PASS", "PASS", "NO_LEAK", "ACCEPTABLE"):
                errors.append(f"KEEP has unresolved source, relevance, leakage, or answer cue: {key}")
            if row["conflict"].strip().upper() != "NONE":
                errors.append(f"KEEP has disclosed reviewer conflict: {key}")
        elif "PENDING" in (row["source_support"], row["task_relevance"], row["semantic_leak"], row["answer_cue"]):
            errors.append(f"completed review has pending criterion: {key}")
    for key in sorted(expected_review_keys - set(seen_reviews)):
        errors.append(f"missing reviewer slot: {key}")
    for family in bindings:
        left, right = seen_reviews.get((family, "A")), seen_reviews.get((family, "B"))
        if left and right and left["disposition"] != "PENDING" and right["disposition"] != "PENDING":
            if left["reviewer_name"].strip().casefold() == right["reviewer_name"].strip().casefold():
                errors.append(f"reviewer identities are identical: {family}")
    seen_adjudications: dict[str, dict[str, str]] = {}
    pending_adjudications = 0
    for row in adjudications:
        family = row["family"]
        if family not in bindings or family in seen_adjudications:
            errors.append(f"unexpected or duplicate adjudication family: {family}")
            continue
        seen_adjudications[family] = row
        if any(row[field] != value for field, value in bindings[family].items()):
            errors.append(f"R1 v0.2 adjudication binding mismatch: {family}")
        if row["reviewer_a_disposition"] not in DISPOSITIONS or row["reviewer_b_disposition"] not in DISPOSITIONS:
            errors.append(f"invalid cited reviewer disposition: {family}")
        decision = row["final_disposition"]
        if decision not in DISPOSITIONS:
            errors.append(f"invalid final disposition: {family}")
        if decision == "PENDING":
            pending_adjudications += 1
            continue
        if not _filled(row, ("adjudicator_name", "expertise", "conflict", "disagreement_resolution",
                             "rationale", "evidence", "decision_date", "attestation")):
            errors.append(f"completed adjudication lacks identity or evidence: {family}")
        if not _date_valid(row["decision_date"]):
            errors.append(f"invalid adjudication date: {family}")
        left, right = seen_reviews.get((family, "A")), seen_reviews.get((family, "B"))
        if not left or not right or "PENDING" in (left["disposition"], right["disposition"]):
            errors.append(f"adjudication lacks two completed reviews: {family}")
            continue
        if row["reviewer_a_disposition"] != left["disposition"] or row["reviewer_b_disposition"] != right["disposition"]:
            errors.append(f"adjudication reviewer dispositions differ from register: {family}")
        if row["adjudicator_name"].strip().casefold() in {left["reviewer_name"].strip().casefold(), right["reviewer_name"].strip().casefold()}:
            errors.append(f"adjudicator is a listed reviewer: {family}")
        if left["disposition"] != right["disposition"] and row["disagreement_resolution"].strip().upper() == "NONE":
            errors.append(f"unresolved reviewer disagreement: {family}")
        if decision == "KEEP":
            if left["disposition"] != "KEEP" or right["disposition"] != "KEEP":
                errors.append(f"final KEEP lacks two positive reviews: {family}")
            if row["conflict"].strip().upper() != "NONE":
                errors.append(f"final KEEP has adjudicator conflict: {family}")
    for family in sorted(set(bindings) - set(seen_adjudications)):
        errors.append(f"missing adjudication row: {family}")
    kept = sorted(family for family, row in seen_adjudications.items() if row["final_disposition"] == "KEEP")
    return {
        "status": "INVALID_RECORDS" if errors else "PENDING_HUMAN_REVIEW" if pending_reviews or pending_adjudications else "RECORDS_COMPLETE_UNVERIFIED",
        "retrieval_version": VERSION, "families_expected": 20, "source_urls_expected": 22,
        "review_rows_expected": 40, "review_rows_present": len(reviews),
        "adjudication_rows_expected": 20, "adjudication_rows_present": len(adjudications),
        "pending_review_rows": pending_reviews, "pending_adjudication_rows": pending_adjudications,
        "recorded_keep_families": kept, "human_review_verified": False,
        "r1_admitted": False, "main_ready": False, "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-register", type=Path, default=REVIEW_REGISTER)
    parser.add_argument("--adjudication-register", type=Path, default=ADJUDICATION_REGISTER)
    parser.add_argument("--snapshot-dir", type=Path, default=SNAPSHOT_DIR)
    args = parser.parse_args()
    report = validate(args.review_register, args.adjudication_register, snapshot_dir=args.snapshot_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

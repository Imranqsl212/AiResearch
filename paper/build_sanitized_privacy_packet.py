"""Create a private reviewer inspection packet for a sanitized paper archive.

Exact snippets are written only to a Git-ignored 0600 report. The terminal
prints counts and hashes. Lexical hits are review leads, not a privacy verdict.
No network call, original private archive, or model call is needed.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from paper import build_sanitized_review_bundle as sanitized
from paper.replay_sanitized_candidate import _verified_review_members


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments/runs/paper_sanitized_privacy_packet_20261005_v2"
REPORT_NAME = "PRIVATE_INSPECTION_REPORT.json"
RECEIPT_NAME = "inspection.receipt.json"
SCHEMA = "paper-sanitized-private-privacy-inspection-1.1.0"
CONTEXT_BYTES = 72

# Generic patterns deliberately favor leads over automatic classification.
RULES: dict[str, re.Pattern[bytes]] = {
    "email_address": re.compile(rb"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])"),
    "ipv4_address": re.compile(rb"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"),
    "mac_address": re.compile(rb"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])"),
    "private_key_header": re.compile(rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    "cloud_access_key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "service_token_prefix": re.compile(rb"\b(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|glpat-[A-Za-z0-9_-]{20,})\b"),
    "bearer_token": re.compile(rb"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{12,}"),
    "credential_label": re.compile(rb"(?i)\b(?:password|passwd|api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token)\b[\"']?\s*[:=]"),
    "person_name_label": re.compile(rb"(?i)\b(?:author|full[_ -]?name|given[_ -]?name|surname|real[_ -]?name|contact[_ -]?name|corresponding[_ -]?author)\b[\"']?\s*[:=]"),
    "titlecase_name_lexical_lead": re.compile(rb"(?<![A-Za-z])[A-Z][a-z]{2,}[ \t]+[A-Z][a-z]{2,}(?![A-Za-z])"),
    "host_identifier_label": re.compile(rb"(?i)\b(?:hostname|host_name|machine_name|computer_name|device_name|user_name|username|account_id)\b[\"']?\s*[:=]"),
    "external_url": re.compile(rb"(?i)https?://[^\s\"'<>\\]+"),
    "domain_name": re.compile(rb"(?i)\b(?:[A-Za-z0-9-]+\.)+(?:com|org|net|io|dev|local|internal|edu|gov)\b"),
    "redaction_marker": re.compile(rb"(?i)\bREDACTED\b"),
    "sensitivity_marker": re.compile(rb"(?i)\b(?:CONFIDENTIAL|SENSITIVE|PERSONAL|INTERNAL)\b"),
    "model_deliberation_tag": re.compile(rb"(?i)</?think>"),
}
MASK_MATCH = {"cloud_access_key", "service_token_prefix", "bearer_token"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _location(member: str, data: bytes, match: re.Match[bytes],
              *, kind: str, surface: str = "content") -> dict[str, Any]:
    start, end = match.span()
    line_start = data.rfind(b"\n", 0, start) + 1
    raw = match.group()
    hidden = kind in MASK_MATCH
    result = {
        "kind": kind, "surface": surface, "member": member,
        "member_sha256": _sha(data) if surface == "content" else None,
        "byte_offset": start, "byte_length": end - start,
        "line": data.count(b"\n", 0, start) + 1,
        "byte_column": start - line_start + 1,
        "match_sha256": _sha(raw),
        "match": "<MASKED_SENSITIVE_CANDIDATE>" if hidden else raw.decode("utf-8", "replace"),
    }
    if not hidden:
        result["context"] = data[max(0, start - CONTEXT_BYTES):min(len(data), end + CONTEXT_BYTES)].decode(
            "utf-8", "replace")
    return result


def _residual_paths(files: dict[str, bytes]) -> list[dict[str, Any]]:
    hits = []
    marker = b"<RESEARCH_ROOT>"
    for name, data in sorted(files.items()):
        for match in sanitized.GENERIC_POSIX_PATH.finditer(data):
            if data[max(0, match.start() - len(marker)):match.start()] == marker:
                continue
            hits.append(_location(name, data, match, kind="residual_multisegment_posix_path"))
    return hits


def _rule_hits(files: dict[str, bytes]) -> list[dict[str, Any]]:
    hits = []
    for member, data in sorted(files.items()):
        for surface, content in (("content", data), ("member_name", member.encode())):
            for kind, rule in RULES.items():
                for match in rule.finditer(content):
                    if kind == "ipv4_address":
                        try:
                            ipaddress.IPv4Address(match.group().decode("ascii"))
                        except ipaddress.AddressValueError:
                            continue
                    hits.append(_location(member, content, match, kind=kind, surface=surface))
    return sorted(hits, key=lambda row: (row["member"], row["surface"], row["byte_offset"], row["kind"]))


def inspect(files: dict[str, bytes], archive_sha256: str,
            manifest_sha256: str) -> dict[str, Any]:
    paths = _residual_paths(files)
    if len(paths) != 8:
        raise ValueError("the known residual-path candidate count changed; re-review scanner scope")
    hits = _rule_hits(files)
    counts = Counter(row["kind"] for row in hits)
    affected = {kind: len({row["member"] for row in hits if row["kind"] == kind})
                for kind in RULES}
    return {
        "schema": SCHEMA, "status": "PRIVATE_HUMAN_PRIVACY_INSPECTION_REQUIRED",
        "public_release_approved": False, "human_privacy_review_complete": False,
        "sanitized_archive_sha256": archive_sha256,
        "sanitization_manifest_sha256": manifest_sha256,
        "residual_path_candidates": paths,
        "residual_path_count": len(paths),
        "residual_path_affected_members": len({row["member"] for row in paths}),
        "scanner_rule_counts": {kind: counts[kind] for kind in RULES},
        "scanner_rule_affected_members": affected,
        "scanner_candidates": hits,
        "review_scope": [
            "Inspect every exact residual path candidate and all scanner leads in its source member.",
            "Review free text, model output, source code, and citation context manually for names, secrets, and identifiers that lexical rules miss.",
            "A zero lexical count is not proof that a category is absent; rule hits can be synthetic task examples.",
            "Do not publish this report or the transformed archive before an author-approved privacy/content decision.",
        ],
    }


def _private_write(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _summary(report: dict[str, Any], report_bytes: bytes) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "status": "PRIVATE_INSPECTION_PACKET_SAVED",
        "public_release_approved": False, "human_privacy_review_complete": False,
        "sanitized_archive_sha256": report["sanitized_archive_sha256"],
        "private_report_sha256": _sha(report_bytes),
        "residual_path_count": report["residual_path_count"],
        "residual_path_affected_members": report["residual_path_affected_members"],
        "scanner_rule_counts": report["scanner_rule_counts"],
        "scanner_rule_affected_members": report["scanner_rule_affected_members"],
    }


def build(*, archive: Path = sanitized.SANITIZED, output: Path = OUTPUT) -> dict[str, Any]:
    archive, output = Path(archive).resolve(), Path(output).resolve()
    files, _, _ = _verified_review_members(archive)
    report = inspect(files, _sha(archive.read_bytes()), _sha(files[sanitized.MANIFEST_NAME]))
    report_bytes = _canonical(report)
    summary = _summary(report, report_bytes)
    report_path, receipt_path = output / REPORT_NAME, output / RECEIPT_NAME
    if output.exists():
        if (not report_path.is_file() or not receipt_path.is_file()
                or report_path.read_bytes() != report_bytes
                or json.loads(receipt_path.read_bytes()) != summary):
            raise FileExistsError("existing private inspection packet differs")
        return summary
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    _private_write(report_path, report_bytes)
    _private_write(receipt_path, _canonical(summary))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=sanitized.SANITIZED)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    summary = build(archive=args.archive, output=args.output)
    # Do not print raw snippets or exact residual strings to the terminal.
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

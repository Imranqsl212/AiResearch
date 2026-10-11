"""Build and validate a private, blank review register for sanitized paper data.

The source inspection report and both trajectory archives are read only. The
register contains locations and hashes, never the report's raw matches or
contexts. Validation checks bookkeeping, not privacy or release suitability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/runs/paper_sanitized_privacy_packet_20261005_v2/PRIVATE_INSPECTION_REPORT.json"
SOURCE_RECEIPT = SOURCE.with_name("inspection.receipt.json")
OUTPUT = ROOT / "experiments/runs/paper_sanitized_privacy_register_20261008_v1"
REGISTER_NAME = "PRIVATE_REVIEW_REGISTER.json"
RECEIPT_NAME = "register.receipt.json"
SCHEMA = "paper-private-privacy-review-register-1.0.0"
EXPECTED_SOURCE_SHA256 = "efc747fec81e94b972a408cc496e22702969eb477ca2917164687df2654c4841"
EXPECTED_COUNTS = {"lexical": 457, "residual_path": 8}
REVIEW_FIELDS = ("reviewer_disposition", "reviewer_identity", "reviewed_at", "reviewer_rationale")
ROW_FIELDS = ("kind", "surface", "member", "member_sha256", "byte_offset",
              "byte_length", "line", "byte_column", "match_sha256")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _load_source(source: Path, receipt: Path, *, expected_sha256: str | None) -> tuple[dict[str, Any], str]:
    if source.is_symlink() or receipt.is_symlink() or not source.is_file() or not receipt.is_file():
        raise ValueError("private packet report/receipt must be regular files")
    data = source.read_bytes()
    digest = _sha(data)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("private packet report differs from the pinned source")
    packet = json.loads(data)
    saved_receipt = json.loads(receipt.read_bytes())
    if (packet.get("schema") != "paper-sanitized-private-privacy-inspection-1.1.0"
            or packet.get("public_release_approved") is not False
            or packet.get("human_privacy_review_complete") is not False
            or saved_receipt.get("private_report_sha256") != digest
            or saved_receipt.get("sanitized_archive_sha256") != packet.get("sanitized_archive_sha256")):
        raise ValueError("private packet/receipt integrity or pending-review status differs")
    return packet, digest


def make_register(packet: dict[str, Any], source_sha256: str,
                  *, expected_counts: dict[str, int] | None = EXPECTED_COUNTS) -> dict[str, Any]:
    inputs = {
        "lexical": packet["scanner_candidates"],
        "residual_path": packet["residual_path_candidates"],
    }
    counts = {kind: len(rows) for kind, rows in inputs.items()}
    if (expected_counts is not None and counts != expected_counts
            or packet["residual_path_count"] != counts["residual_path"]
            or sum(packet["scanner_rule_counts"].values()) != counts["lexical"]):
        raise ValueError("private packet candidate counts differ")
    if packet.get("public_release_approved") is not False or packet.get("human_privacy_review_complete") is not False:
        raise ValueError("private packet unexpectedly claims review or release approval")

    hashes = sorted({lead["match_sha256"] for rows in inputs.values() for lead in rows})
    group_ids = {digest: f"G{number:03d}" for number, digest in enumerate(hashes, 1)}
    rows: list[dict[str, Any]] = []
    group_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_locations: set[tuple[Any, ...]] = set()
    for bucket, prefix in (("residual_path", "P"), ("lexical", "L")):
        for number, lead in enumerate(inputs[bucket], 1):
            if any(field not in lead for field in (*ROW_FIELDS, "context")):
                raise ValueError("private packet lead lacks a required location/hash field")
            if not isinstance(lead["context"], str):
                raise ValueError("private packet context is missing or non-text")
            if not isinstance(lead["byte_offset"], int) or lead["byte_offset"] < 0:
                raise ValueError("private packet lead has an invalid offset")
            location = (bucket, lead["member"], lead["surface"], lead["byte_offset"], lead["kind"])
            if location in seen_locations:
                raise ValueError("duplicate private packet lead location")
            seen_locations.add(location)
            row = {field: lead[field] for field in ROW_FIELDS}
            row.update({
                "row_id": f"{prefix}{number:04d}",
                "source_bucket": bucket,
                "group_id": group_ids[lead["match_sha256"]],
                "context_sha256": _sha(lead["context"].encode("utf-8")),
                **{field: None for field in REVIEW_FIELDS},
            })
            rows.append(row)
            group_rows[lead["match_sha256"]].append(row)
    groups = []
    for digest in hashes:
        members = group_rows[digest]
        groups.append({
            "group_id": group_ids[digest],
            "match_sha256": digest,
            "lead_count": len(members),
            "source_buckets": sorted({row["source_bucket"] for row in members}),
            "kinds": sorted({row["kind"] for row in members}),
            "member_count": len({row["member"] for row in members}),
            "row_ids": [row["row_id"] for row in members],
        })
    return {
        "schema": SCHEMA,
        "status": "PRIVATE_HUMAN_REVIEW_PENDING",
        "public_release_approved": False,
        "human_privacy_review_complete": False,
        "source_packet_report_sha256": source_sha256,
        "sanitized_archive_sha256": packet["sanitized_archive_sha256"],
        "counts": {**counts, "total": len(rows), "distinct_match_hash_groups": len(groups)},
        "groups": groups,
        "rows": rows,
        "notice": "Locations and hashes only. Inspect the private source packet and all surrounding free text; this register does not approve sharing.",
    }


def validate(register: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(register, dict) or register.get("public_release_approved") is not False:
        raise ValueError("register must keep public_release_approved=false")
    if register.get("human_privacy_review_complete") is not False:
        raise ValueError("register cannot self-certify completion")
    if register.keys() != expected.keys() or not isinstance(register.get("rows"), list):
        raise ValueError("register schema differs")
    if len(register["rows"]) != len(expected["rows"]):
        raise ValueError("register row count differs")
    for field in expected:
        if field == "rows":
            continue
        if register[field] != expected[field]:
            raise ValueError(f"register immutable field differs: {field}")
    filled = 0
    for actual, original in zip(register["rows"], expected["rows"], strict=True):
        if actual.keys() != original.keys():
            raise ValueError("register row fields differ")
        for field in original:
            if field not in REVIEW_FIELDS and actual[field] != original[field]:
                raise ValueError(f"register location/hash differs: {original['row_id']} {field}")
        decisions = [actual[field] for field in REVIEW_FIELDS]
        if any(value is not None and (not isinstance(value, str) or not value.strip()) for value in decisions):
            raise ValueError(f"invalid reviewer field: {original['row_id']}")
        if actual["reviewer_disposition"] is not None:
            if any(actual[field] is None for field in REVIEW_FIELDS[1:]):
                raise ValueError(f"review disposition lacks identity, time, or rationale: {original['row_id']}")
            filled += 1
        elif any(actual[field] is not None for field in REVIEW_FIELDS[1:]):
            raise ValueError(f"partial reviewer fields without disposition: {original['row_id']}")
    return {"status": "PRIVATE_REGISTER_STRUCTURE_VALIDATED_RELEASE_PENDING",
            "public_release_approved": False,
            "human_privacy_review_complete": False,
            "source_packet_report_sha256": expected["source_packet_report_sha256"],
            "lead_count": len(register["rows"]),
            "group_count": len(register["groups"]),
            "reviewer_dispositions_recorded": filled}


def _private_write(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def build(*, source: Path = SOURCE, receipt: Path = SOURCE_RECEIPT,
          output: Path = OUTPUT, expected_sha256: str | None = EXPECTED_SOURCE_SHA256,
          expected_counts: dict[str, int] | None = EXPECTED_COUNTS) -> dict[str, Any]:
    packet, digest = _load_source(source, receipt, expected_sha256=expected_sha256)
    register = make_register(packet, digest, expected_counts=expected_counts)
    summary = validate(register, register)
    register_bytes = _canonical(register)
    receipt_data = {**summary, "blank_template_sha256": _sha(register_bytes)}
    output = Path(output)
    if output.exists():
        if output.is_symlink() or not output.is_dir():
            raise FileExistsError("register output path is not a regular directory")
        register_path = output / REGISTER_NAME
        receipt_path = output / RECEIPT_NAME
        if (not register_path.is_file() or register_path.is_symlink()
                or not receipt_path.is_file() or receipt_path.is_symlink()
                or register_path.read_bytes() != register_bytes
                or json.loads(receipt_path.read_bytes()) != receipt_data):
            raise FileExistsError("existing private register differs from blank template")
    else:
        output.mkdir(parents=True, mode=0o700)
        os.chmod(output, 0o700)
        _private_write(output / REGISTER_NAME, register_bytes)
        _private_write(output / RECEIPT_NAME, _canonical(receipt_data))
    return receipt_data


def verify(*, source: Path = SOURCE, receipt: Path = SOURCE_RECEIPT,
           register_path: Path = OUTPUT / REGISTER_NAME,
           expected_sha256: str | None = EXPECTED_SOURCE_SHA256,
           expected_counts: dict[str, int] | None = EXPECTED_COUNTS) -> dict[str, Any]:
    packet, digest = _load_source(source, receipt, expected_sha256=expected_sha256)
    expected = make_register(packet, digest, expected_counts=expected_counts)
    register_path = Path(register_path)
    if register_path.is_symlink() or not register_path.is_file():
        raise ValueError("register must be a regular file")
    return validate(json.loads(register_path.read_bytes()), expected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--source-receipt", type=Path, default=SOURCE_RECEIPT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--register", type=Path, default=None,
                        help="optional reviewed copy to validate without changing the blank template")
    args = parser.parse_args()
    if args.command == "build":
        if args.register is not None:
            parser.error("--register applies only to verify")
        result = build(source=args.source, receipt=args.source_receipt, output=args.output)
    else:
        result = verify(source=args.source, receipt=args.source_receipt,
                        register_path=args.register or args.output / REGISTER_NAME)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

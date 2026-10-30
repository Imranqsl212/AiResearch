"""Audit outcome-associated source identity missingness in historical SAST data.

This analysis reads the published Bandit sidecar archive, verifies it against
the sealed historical logs and native receipts, and writes only derived counts.
It never executes candidate code or treats a scanner warning as ground truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import tarfile
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from analysis.sast_historical_reanalysis import verify as verify_sast_archive


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "experiments/sast_historical_20261028.tar.gz"
ARCHIVE_SHA256 = "648b76fe3c88affdf33f8c59666fb310f44bcab0cc5b0a5ed748644caee8f4f6"
EXTRACTED_DIR = "sast_historical_20261028"
JSON_OUT = ROOT / "analysis/sast_provenance_missingness_20261030.json"
CSV_OUT = ROOT / "analysis/sast_provenance_missingness_20261030.csv"
SCHEMA = "excluded-historical-sast-provenance-missingness-v1"
COMPLETE = frozenset({"NO_FINDINGS", "FINDINGS"})
RELATIONS = frozenset({"MATCH", "MISSING_SHA", "DIFFERENT_SHA"})
CSV_FIELDS = (
    "run_id", "family", "condition", "implemented_tests_passed",
    "benchmark_accepted", "final_sast_status", "evaluator_source_relation",
    "candidate_source_matches_logged", "source_identical_comparison_eligible",
)


class MissingnessAuditError(ValueError):
    """An input or derived selection result fails the audit contract."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checked_rows(finals: list[dict[str, Any]], *, expected_total: int = 40) -> list[dict[str, Any]]:
    if len(finals) != expected_total:
        raise MissingnessAuditError("unexpected final-candidate denominator")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in finals:
        if not isinstance(item, dict) or not set(CSV_FIELDS).issubset(item):
            raise MissingnessAuditError("final row lacks required fields")
        run_id = item["run_id"]
        if not isinstance(run_id, str) or not run_id or run_id in seen:
            raise MissingnessAuditError("missing or duplicate run ID")
        seen.add(run_id)
        passed = item["implemented_tests_passed"]
        accepted = item["benchmark_accepted"]
        candidate_match = item["candidate_source_matches_logged"]
        eligible = item["source_identical_comparison_eligible"]
        if any(type(value) is not bool for value in (passed, accepted, candidate_match, eligible)):
            raise MissingnessAuditError(f"non-Boolean final outcome: {run_id}")
        status = item["final_sast_status"]
        relation = item["evaluator_source_relation"]
        if (status not in COMPLETE | {"INDETERMINATE", "UNSCANNABLE_SOURCE_MISMATCH"}
                or relation not in RELATIONS
                or accepted and not passed):
            raise MissingnessAuditError(f"invalid scanner, source, or acceptance state: {run_id}")
        expected_eligible = status in COMPLETE and candidate_match and relation == "MATCH"
        if eligible != expected_eligible:
            raise MissingnessAuditError(f"source-identical eligibility differs from hashes: {run_id}")
        rows.append({field: item[field] for field in CSV_FIELDS})
    return sorted(rows, key=lambda row: row["run_id"])


def summarize(finals: list[dict[str, Any]], *, expected_total: int = 40) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Retain every final candidate, including those excluded from SAST comparison."""

    rows = _checked_rows(finals, expected_total=expected_total)
    by_outcome: dict[str, dict[str, Any]] = {}
    for passed, label in ((True, "raw_test_pass"), (False, "raw_test_fail")):
        group = [row for row in rows if row["implemented_tests_passed"] is passed]
        relations = Counter(row["evaluator_source_relation"] for row in group)
        statuses = Counter(row["final_sast_status"] for row in group)
        eligible = sum(row["source_identical_comparison_eligible"] for row in group)
        by_outcome[label] = {
            "total": len(group), "source_identical_eligible": eligible,
            "source_identical_ineligible": len(group) - eligible,
            "evaluator_source_relations": dict(sorted(relations.items())),
            "sast_statuses": dict(sorted(statuses.items())),
        }
    if sum(group["total"] for group in by_outcome.values()) != expected_total:
        raise MissingnessAuditError("final outcomes do not partition the cohort")

    strata: dict[str, dict[str, dict[str, int]]] = {}
    for key in ("family", "condition"):
        strata[key] = {}
        for label in sorted({row[key] for row in rows}):
            group = [row for row in rows if row[key] == label]
            strata[key][label] = {
                "total": len(group),
                "raw_test_pass": sum(row["implemented_tests_passed"] for row in group),
                "source_identical_eligible": sum(
                    row["source_identical_comparison_eligible"] for row in group
                ),
                "evaluator_sha_missing": sum(
                    row["evaluator_source_relation"] == "MISSING_SHA" for row in group
                ),
            }
    return {"finals": expected_total, "by_raw_test_outcome": by_outcome,
            "strata": strata}, rows


def build(*, root: Path = ROOT, archive: Path = ARCHIVE) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root, archive = Path(root).resolve(), Path(archive)
    if archive.is_symlink() or not archive.is_file() or _sha(archive) != ARCHIVE_SHA256:
        raise MissingnessAuditError("published SAST archive SHA-256 differs")
    with tempfile.TemporaryDirectory(prefix="sast-provenance-audit-") as temporary:
        with tarfile.open(archive, "r:gz") as package:
            package.extractall(temporary, filter="data")
        archive_dir = Path(temporary) / EXTRACTED_DIR
        verified = verify_sast_archive(root=root, archive_dir=archive_dir)
        summary, rows = summarize(verified["finals"])
        report = {
            "schema_version": SCHEMA,
            "cohort": verified["cohort"],
            "phase": "excluded_retrospective",
            "eligible_for_main_analysis": False,
            "sast_archive_sha256": ARCHIVE_SHA256,
            "sast_manifest_sha256": _sha(archive_dir / "manifest.json"),
            "sealed_log_archive_manifest_sha256": verified["sealed_archive_manifest_sha256"],
            **summary,
        }
    return report, rows


def _render_json(report: dict[str, Any]) -> bytes:
    return (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _render_csv(rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: int(value) if type(value) is bool else value
                         for key, value in row.items()})
    return buffer.getvalue().encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="write the dated derived JSON and CSV")
    action.add_argument("--check", action="store_true", help="compare them byte-for-byte without writing")
    args = parser.parse_args()
    report, rows = build()
    outputs = ((JSON_OUT, _render_json(report)), (CSV_OUT, _render_csv(rows)))
    if args.check:
        for path, expected in outputs:
            if not path.is_file() or path.read_bytes() != expected:
                raise MissingnessAuditError(f"derived output differs: {path.name}")
    else:
        for path, raw in outputs:
            path.write_bytes(raw)
    print(json.dumps({"status": "VERIFIED_EXCLUDED_MISSINGNESS_AUDIT",
                      "finals": report["finals"],
                      "by_raw_test_outcome": report["by_raw_test_outcome"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Structural audit of the independent task-admission review records.

This checks completeness and internal consistency. It cannot verify that named
people performed an independent security review, authenticate signatures, or
turn a finite fixture into a valid real-code security task.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from analysis.admission_review import INDEXES
from benchmark.finite_family_registry import FAMILIES


ROOT = Path(__file__).resolve().parents[1]
REVIEW_REGISTER = ROOT / "docs" / "human_admission_review_register_20261005.csv"
ADJUDICATION_REGISTER = ROOT / "docs" / "human_admission_adjudication_register_20261005.csv"
V7_CANDIDATE_INDEXES = tuple(
    "benchmark/tasks/v7_batch_c/index.json" if path.endswith("/v6_batch_c/index.json") else path
    for path in INDEXES
)
V7_REVIEW_REGISTER = ROOT / "docs" / "human_admission_review_register_v7_candidate_20261005.csv"
V7_ADJUDICATION_REGISTER = ROOT / "docs" / "human_admission_adjudication_register_v7_candidate_20261005.csv"
REVIEW_COLUMNS = (
    "family", "reviewer_slot", "reviewer_name", "expertise", "conflict",
    "source_commit", *(f"criterion_{number}" for number in range(1, 8)),
    "evidence_paths_or_counterexample", "notes", "decision", "review_date",
)
ADJUDICATION_COLUMNS = (
    "family", "adjudicator_name", "expertise", "conflict", "source_commit",
    "reviewer_a_decision", "reviewer_b_decision", "disagreement_resolution",
    "final_decision", "rationale", "evidence_paths_or_counterexample",
    "decision_date", "attestation",
)
CRITERION_VALUES = {"PENDING", "PASS", "FAIL", "UNCERTAIN"}
DECISIONS = {"PENDING", "ADMIT", "REJECT"}
COMMIT_RE = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}\Z")
REFERENCE_MODULES = {
    "benchmark.finite_policy_v1": "benchmark/finite_policy_reference.py",
    "benchmark.finite_path_v2": "benchmark/finite_path_reference_v2.py",
    "benchmark.finite_replay_v3": "benchmark/finite_replay_reference_v3.py",
    "benchmark.finite_race_v4": "benchmark/finite_race_reference_v4.py",
    "benchmark.finite_batch_a_v5": "benchmark/finite_batch_a_reference_v5.py",
    "benchmark.finite_batch_b_v5": "benchmark/finite_batch_b_reference_v5.py",
    "benchmark.finite_batch_c_v6": "benchmark/finite_batch_c_reference_v6.py",
    "benchmark.finite_batch_c_v7": "benchmark/finite_batch_c_reference_v7.py",
}


def _read_csv(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != columns:
            raise ValueError(f"wrong columns in {path.name}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"malformed CSV row in {path.name}")
    return rows


def _filled(row: dict[str, str], fields: tuple[str, ...]) -> bool:
    return all(row[field].strip() and row[field].strip().upper() != "PENDING" for field in fields)


def _valid_date(value: str) -> bool:
    if not DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


@lru_cache(maxsize=None)
def _evidence_paths(family: str, index_names: tuple[str, ...] = INDEXES) -> tuple[str, ...]:
    """Files the family reviewer must bind to the exact source commit."""

    paths: set[str] = set()
    matched_indexes = 0
    for index_name in index_names:
        index = json.loads((ROOT / index_name).read_text(encoding="utf-8"))
        rows = [row for row in index["tasks"] if row["family"] == family]
        if not rows:
            continue
        matched_indexes += 1
        task = json.loads((ROOT / Path(index_name).parent / rows[0]["task_file"]).read_text(encoding="utf-8"))
        module = FAMILIES[(family, task["version"])]
        paths.update({module.replace(".", "/") + ".py", REFERENCE_MODULES[module]})
        paths.add(index_name)
        for row in rows:
            for field in ("task_file", "proof_file"):
                paths.add(str(Path(index_name).parent / row[field]))
        if index.get("reference_file"):
            paths.add(str(Path(index_name).parent / index["reference_file"]))
    if matched_indexes != 1:
        raise ValueError(f"family has {matched_indexes} matching task indexes: {family}")
    return tuple(sorted(paths))


@lru_cache(maxsize=None)
def _source_drift(family: str, commit: str,
                  index_names: tuple[str, ...] = INDEXES) -> tuple[str, ...]:
    """Find reviewed task, evaluator, or reference files differing from commit."""

    if not COMMIT_RE.fullmatch(commit):
        return ("invalid commit syntax",)
    exists = subprocess.run(
        ("git", "-C", str(ROOT), "cat-file", "-e", f"{commit}^{{commit}}"),
        capture_output=True, check=False,
    )
    if exists.returncode != 0:
        return ("commit is not in local Git history",)
    changed = []
    for relative in _evidence_paths(family, index_names):
        saved = subprocess.run(
            ("git", "-C", str(ROOT), "show", f"{commit}:{relative}"),
            capture_output=True, check=False,
        )
        current = ROOT / relative
        if saved.returncode != 0 or not current.is_file() or saved.stdout != current.read_bytes():
            changed.append(relative)
    return tuple(changed)


def validate(
    review_path: Path = REVIEW_REGISTER,
    adjudication_path: Path = ADJUDICATION_REGISTER,
    *, index_paths: tuple[str, ...] = INDEXES,
) -> dict[str, Any]:
    """Return an audit; never return a scientific or main-run READY verdict."""

    families = {
        row["family"]
        for index_name in index_paths
        for row in json.loads((ROOT / index_name).read_text(encoding="utf-8"))["tasks"]
    }
    errors: list[str] = []
    reviews = _read_csv(review_path, REVIEW_COLUMNS)
    adjudications = _read_csv(adjudication_path, ADJUDICATION_COLUMNS)
    expected_review_keys = {(family, slot) for family in families for slot in ("A", "B")}
    seen_reviews: dict[tuple[str, str], dict[str, str]] = {}
    pending_reviews = 0
    for row in reviews:
        key = (row["family"], row["reviewer_slot"])
        if key not in expected_review_keys or key in seen_reviews:
            errors.append(f"unexpected or duplicate reviewer slot: {key}")
            continue
        seen_reviews[key] = row
        criteria = [row[f"criterion_{number}"] for number in range(1, 8)]
        if any(value not in CRITERION_VALUES for value in criteria):
            errors.append(f"invalid criterion token: {key}")
        decision = row["decision"]
        if decision not in DECISIONS:
            errors.append(f"invalid reviewer decision: {key}")
        if decision == "PENDING":
            pending_reviews += 1
            continue
        if not _filled(row, ("reviewer_name", "expertise", "conflict", "source_commit", "evidence_paths_or_counterexample", "review_date")):
            errors.append(f"completed review lacks identity, evidence, or revision: {key}")
        if not COMMIT_RE.fullmatch(row["source_commit"]):
            errors.append(f"invalid source commit: {key}")
        else:
            drift = _source_drift(row["family"], row["source_commit"], index_paths)
            if drift:
                errors.append(f"reviewed source differs from current evidence: {key}: {', '.join(drift[:3])}")
        if not _valid_date(row["review_date"]):
            errors.append(f"invalid review date: {key}")
        if decision == "ADMIT" and any(value != "PASS" for value in criteria):
            errors.append(f"reviewer admission has non-PASS criterion: {key}")
        if decision == "REJECT" and all(value == "PASS" for value in criteria):
            errors.append(f"reviewer rejection lacks failed or uncertain criterion: {key}")
    for key in sorted(expected_review_keys - set(seen_reviews)):
        errors.append(f"missing reviewer slot: {key}")

    for family in sorted(families):
        left = seen_reviews.get((family, "A"))
        right = seen_reviews.get((family, "B"))
        if not left or not right or "PENDING" in (left["decision"], right["decision"]):
            continue
        if left["reviewer_name"].strip().casefold() == right["reviewer_name"].strip().casefold():
            errors.append(f"reviewer identities are identical: {family}")
        if left["source_commit"] != right["source_commit"]:
            errors.append(f"reviewers assessed different source commits: {family}")

    seen_adjudications: dict[str, dict[str, str]] = {}
    pending_adjudications = 0
    for row in adjudications:
        family = row["family"]
        if family not in families or family in seen_adjudications:
            errors.append(f"unexpected or duplicate adjudication family: {family}")
            continue
        seen_adjudications[family] = row
        decision = row["final_decision"]
        if decision not in DECISIONS:
            errors.append(f"invalid final decision: {family}")
        if decision == "PENDING":
            pending_adjudications += 1
            continue
        fields = ("adjudicator_name", "expertise", "conflict", "source_commit",
                  "disagreement_resolution", "rationale", "evidence_paths_or_counterexample",
                  "decision_date", "attestation")
        if not _filled(row, fields):
            errors.append(f"completed adjudication lacks identity, evidence, or attestation: {family}")
        if not COMMIT_RE.fullmatch(row["source_commit"]):
            errors.append(f"invalid adjudication commit: {family}")
        else:
            drift = _source_drift(family, row["source_commit"], index_paths)
            if drift:
                errors.append(f"adjudicated source differs from current evidence: {family}: {', '.join(drift[:3])}")
        if not _valid_date(row["decision_date"]):
            errors.append(f"invalid adjudication date: {family}")
        left = seen_reviews.get((family, "A"))
        right = seen_reviews.get((family, "B"))
        if left is None or right is None:
            errors.append(f"adjudication has no two reviewer records: {family}")
            continue
        if row["reviewer_a_decision"] != left["decision"] or row["reviewer_b_decision"] != right["decision"]:
            errors.append(f"adjudication reviewer decisions differ from register: {family}")
        if row["source_commit"] not in {left["source_commit"]} or row["source_commit"] != right["source_commit"]:
            errors.append(f"adjudication source commit differs from reviews: {family}")
        if row["adjudicator_name"].strip().casefold() in {
            left["reviewer_name"].strip().casefold(), right["reviewer_name"].strip().casefold()
        }:
            errors.append(f"adjudicator is a listed reviewer: {family}")
        if decision == "ADMIT":
            if left["decision"] != "ADMIT" or right["decision"] != "ADMIT":
                errors.append(f"final admission lacks two positive reviews: {family}")
            if row["conflict"].strip().upper() != "NONE":
                errors.append(f"final admission has unresolved adjudicator conflict: {family}")
            if any(review["conflict"].strip().upper() != "NONE" for review in (left, right)):
                errors.append(f"final admission has disclosed reviewer conflict: {family}")
    for family in sorted(families - set(seen_adjudications)):
        errors.append(f"missing adjudication row: {family}")

    admitted = sorted(family for family, row in seen_adjudications.items() if row["final_decision"] == "ADMIT")
    return {
        "status": "INVALID_RECORDS" if errors else "PENDING_HUMAN_REVIEW" if pending_reviews or pending_adjudications else "RECORDS_COMPLETE_UNVERIFIED",
        "families_expected": len(families),
        "catalog_index_paths": list(index_paths),
        "review_rows_expected": len(expected_review_keys),
        "review_rows_present": len(reviews),
        "adjudication_rows_expected": len(families),
        "adjudication_rows_present": len(adjudications),
        "pending_review_rows": pending_reviews,
        "pending_adjudication_rows": pending_adjudications,
        "recorded_admit_families": admitted,
        "human_identity_and_independence_verified": False,
        "scientific_task_admission_granted": False,
        "main_ready": False,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", choices=("v6-current", "v7-candidate"), default="v6-current")
    parser.add_argument("--review-register", type=Path)
    parser.add_argument("--adjudication-register", type=Path)
    args = parser.parse_args()
    candidate = args.catalog == "v7-candidate"
    report = validate(
        args.review_register or (V7_REVIEW_REGISTER if candidate else REVIEW_REGISTER),
        args.adjudication_register or (V7_ADJUDICATION_REGISTER if candidate else ADJUDICATION_REGISTER),
        index_paths=V7_CANDIDATE_INDEXES if candidate else INDEXES,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

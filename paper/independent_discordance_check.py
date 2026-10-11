"""Independently recount the historical terminal test/acceptance disagreement.

Reads only the transformed review archive. This deliberately does not import
the paper pipeline, its summary helpers, or the broader sanitized table replay.
It verifies transformed member hashes and receipt/index links, but cannot prove
the original bytes from which the transformed archive was made.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = ROOT / "experiments/runs/paper_sanitized_review_candidate_20261005.tar.gz"
MAIN_ID = "rag-overnight-v2-main-0-5-0"
MAIN_MANIFEST = f"experiments/manifests/{MAIN_ID}.json"
MAIN_INDEX = f"experiments/results/{MAIN_ID}.jsonl"
REVIEW_MANIFEST = "SANITIZATION_MANIFEST.json"
REVIEW_NOTICE = "REVIEW_ONLY_NOTICE.txt"
OLD_INVENTORY = "BUNDLE_INVENTORY.json"
CONDITIONS = ("RD", "RW", "UD", "UW")
EXPECTED = {"main_episodes": 40, "nominally_unavailable": 20,
            "unavailable_raw_pass_final_reject": 9}


class DiscordanceAuditError(ValueError):
    """The transformed archive or a terminal receipt violates an audit invariant."""


def _require(test: bool, message: str) -> None:
    if not test:
        raise DiscordanceAuditError(message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeDecodeError) as exc:
        raise DiscordanceAuditError(f"invalid JSON in {label}: {exc}") from exc
    _require(isinstance(value, dict), f"expected JSON object in {label}")
    return value


def _jsonl_objects(data: bytes, label: str) -> list[dict[str, Any]]:
    _require(bool(data.strip()), f"empty JSONL: {label}")
    return [_json_object(line, f"{label}:{number}") for number, line in
            enumerate(data.splitlines(), 1) if line.strip()]


def _safe_name(name: str) -> str:
    path = PurePosixPath(name)
    _require(bool(name) and not path.is_absolute() and ".." not in path.parts
             and path.as_posix() == name, f"unsafe archive path: {name}")
    return name


def _linked_path(value: Any, prefix: str) -> str:
    _require(isinstance(value, str) and value.startswith("<RESEARCH_ROOT>/"),
             f"missing transformed {prefix} path")
    name = _safe_name(value[len("<RESEARCH_ROOT>/"):])
    _require(name.startswith(prefix), f"unexpected linked path: {name}")
    return name


def _load_archive(path: Path) -> dict[str, bytes]:
    try:
        with tarfile.open(path, "r:gz") as archive:
            files: dict[str, bytes] = {}
            for member in archive.getmembers():
                name = _safe_name(member.name)
                _require(name not in files, f"duplicate archive member: {name}")
                _require(member.isfile(), f"non-file archive member: {name}")
                stream = archive.extractfile(member)
                _require(stream is not None, f"unreadable archive member: {name}")
                files[name] = stream.read()
            return files
    except (OSError, tarfile.TarError) as exc:
        raise DiscordanceAuditError(f"cannot read review archive: {exc}") from exc


def _verify_review_manifest(files: dict[str, bytes]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    _require(REVIEW_MANIFEST in files and REVIEW_NOTICE in files,
             "review manifest or notice missing")
    manifest = _json_object(files[REVIEW_MANIFEST], REVIEW_MANIFEST)
    _require(manifest.get("status") == "REVIEW_ONLY_SANITIZED_CANDIDATE",
             "unexpected review status")
    _require(manifest.get("public_release_approved") is False
             and manifest.get("original_byte_identical_raw_data") is False,
             "archive incorrectly claims public release or original-byte identity")
    rows = manifest.get("members")
    _require(isinstance(rows, list), "review mapping missing")
    mapping: dict[str, dict[str, Any]] = {}
    changed = 0
    for row in rows:
        _require(isinstance(row, dict) and isinstance(row.get("path"), str),
                 "malformed review mapping row")
        name = _safe_name(row["path"])
        _require(name not in mapping, f"duplicate review mapping: {name}")
        mapping[name] = row
        if name == OLD_INVENTORY:
            _require(row.get("status") == "REPLACED_BY_SANITIZATION_MANIFEST"
                     and name not in files, "old inventory replacement differs")
            continue
        _require(name in files, f"mapped member absent: {name}")
        digest = _sha(files[name])
        _require(row.get("sanitized_sha256") == digest
                 and row.get("sanitized_bytes") == len(files[name]),
                 f"transformed member hash or size differs: {name}")
        status = row.get("status")
        _require(status in {"UNCHANGED", "TRANSFORMED"},
                 f"unexpected member status: {name}")
        same = row.get("original_sha256") == digest
        _require((status == "UNCHANGED") == same,
                 f"inconsistent original/transformed hash label: {name}")
        changed += status == "TRANSFORMED"
    _require(OLD_INVENTORY in mapping, "original inventory mapping missing")
    _require(set(files) == (set(mapping) - {OLD_INVENTORY}) |
             {REVIEW_MANIFEST, REVIEW_NOTICE}, "review file set differs from mapping")
    _require(len(mapping) == manifest.get("mapping_count") ==
             manifest.get("source_member_count") and
             changed == manifest.get("changed_member_count"),
             "review mapping totals differ")
    return mapping, manifest


def _classify_terminal(row: dict[str, Any], receipt: dict[str, Any]) -> dict[str, bool]:
    """Use the raw finite test and final candidate fields of one terminal receipt."""
    run_id = row.get("run_id")
    _require(isinstance(run_id, str) and bool(run_id), "missing run ID")
    for field in ("experiment_id", "run_id", "task_id", "condition",
                  "terminal_outcome", "stop_event", "log_sha256"):
        _require(row.get(field) == receipt.get(field),
                 f"result/receipt {field} mismatch for {run_id}")
    condition = row["condition"]
    _require(condition in CONDITIONS, f"unknown condition for {run_id}")
    verifier = receipt.get("verifier_receipt")
    _require(isinstance(verifier, dict) and row.get("verifier_receipt") == verifier,
             f"result/receipt verifier mismatch for {run_id}")
    candidate = verifier.get("candidate_receipt")
    _require(isinstance(candidate, dict), f"terminal candidate receipt missing for {run_id}")
    details = candidate.get("details")
    _require(isinstance(details, dict), f"candidate details missing for {run_id}")
    evaluator = details.get("evaluator")
    policy = details.get("condition_policy")
    _require(isinstance(evaluator, dict) and isinstance(policy, dict),
             f"raw evaluator or condition policy missing for {run_id}")
    raw = evaluator.get("passed")
    accepted = candidate.get("passed")
    reachable = candidate.get("condition_reachable")
    _require(type(raw) is bool and type(accepted) is bool and type(reachable) is bool,
             f"non-Boolean raw, final, or reachability result for {run_id}")
    _require(verifier.get("condition") == candidate.get("condition") ==
             policy.get("condition") == condition and
             candidate.get("family") == row.get("task_family"),
             f"terminal task identity differs for {run_id}")
    _require(policy.get("reachable") is reachable and
             reachable is condition.startswith("R"),
             f"reachability label differs for {run_id}")
    _require(accepted is (raw and reachable),
             f"raw test/final candidate policy relation differs for {run_id}")
    _require((verifier.get("task_state") == "SUCCESS") is accepted,
             f"verifier task state differs for {run_id}")
    discordant = raw and not accepted
    if discordant:
        _require(candidate.get("failure_reason") == "condition_unreachable",
                 f"discordant receipt lacks hidden-veto reason for {run_id}")
    return {"unavailable": condition.startswith("U"), "raw_pass": raw,
            "accepted": accepted, "discordant": discordant}


def audit_archive(archive_path: Path = DEFAULT_ARCHIVE) -> dict[str, Any]:
    """Return a source-free recount, or raise if archive and receipts disagree."""
    archive_path = Path(archive_path)
    files = _load_archive(archive_path)
    mapping, review = _verify_review_manifest(files)
    _require(MAIN_MANIFEST in files and MAIN_INDEX in files,
             "historical main manifest or result index missing")
    study = _json_object(files[MAIN_MANIFEST], MAIN_MANIFEST)
    rows = _jsonl_objects(files[MAIN_INDEX], MAIN_INDEX)
    _require(study.get("experiment_id") == MAIN_ID, "historical study identity differs")
    _require(len(rows) == study.get("task_count") * study.get("runs_per_task"),
             "study/index episode count differs")
    _require(study.get("runs_per_task") == 1, "historical run multiplicity differs")
    task_ids = study.get("task_ids")
    _require(isinstance(task_ids, list) and len(set(task_ids)) == len(task_ids)
             and set(task_ids) == {row.get("task_id") for row in rows},
             "study/index task IDs differ")
    _require(len({row.get("run_id") for row in rows}) == len(rows)
             and len({row.get("slot_id") for row in rows}) == len(rows),
             "duplicate main run or slot")
    condition_count: Counter[str] = Counter()
    unavailable = raw_pass = accepted = discordant = unavailable_discordant = 0
    for row in rows:
        _require(row.get("experiment_id") == MAIN_ID,
                 "result index contains another experiment")
        run_id = row["run_id"]
        receipt_path = _linked_path(row.get("receipt_path"), "experiments/runs/")
        log_path = _linked_path(row.get("log_path"), "experiments/runs/")
        _require(receipt_path in files and log_path in files,
                 f"run archive links missing for {run_id}")
        _require(row.get("log_sha256") == mapping[log_path].get("original_sha256"),
                 f"original log hash claim differs for {run_id}")
        receipt = _json_object(files[receipt_path], receipt_path)
        result = _classify_terminal(row, receipt)
        condition_count[row["condition"]] += 1
        unavailable += result["unavailable"]
        raw_pass += result["raw_pass"]
        accepted += result["accepted"]
        discordant += result["discordant"]
        unavailable_discordant += result["unavailable"] and result["discordant"]
    _require(set(condition_count) == set(CONDITIONS)
             and len(set(condition_count.values())) == 1,
             "historical condition arms are incomplete or unbalanced")
    _require(discordant == unavailable_discordant,
             "a test/gate disagreement occurred outside nominal unavailability")
    return {
        "status": "INDEPENDENT_TRANSFORMED_TERMINAL_RECOUNT",
        "archive_sha256": _sha(archive_path.read_bytes()),
        "sanitization_manifest_sha256": _sha(files[REVIEW_MANIFEST]),
        "main_experiment_id": MAIN_ID,
        "main_episodes": len(rows),
        "nominally_unavailable": unavailable,
        "raw_family_test_pass": raw_pass,
        "final_candidate_accepted": accepted,
        "test_gate_discordance_all_main": discordant,
        "unavailable_raw_pass_final_reject": unavailable_discordant,
        "episodes_by_condition": dict(sorted(condition_count.items())),
        "transformed_member_count": review["changed_member_count"],
        "original_archive_sha256_claim": review.get("source_archive_sha256"),
        "original_byte_provenance_verified": False,
        "public_release_approved": False,
        "limitation": "The transformed archive verifies its own member hashes and linked terminal receipts. Its claimed original-member hashes and source archive digest cannot be proven from transformed bytes alone; this is not a privacy or release review.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--check", action="store_true",
                        help="fail unless the separately stated 40/20/9 manuscript claim matches")
    args = parser.parse_args()
    try:
        result = audit_archive(args.archive)
        if args.check:
            for key, expected in EXPECTED.items():
                _require(result[key] == expected,
                         f"manuscript count differs: {key}={result[key]}, expected {expected}")
    except DiscordanceAuditError as exc:
        parser.exit(2, f"DISCORDANCE_AUDIT_FAILED: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Read-only, independent byte/link audit of the two private paper archives.

This does not import the sanitizer, the paper pipeline, or the transformed-data
recount. It emits counts and digests only, never archived text or local paths.
It verifies a local archive-to-archive chain, not historical execution or privacy.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "experiments/runs/paper_private_repro_inputs_20261005.tar.gz"
SANITIZED = ROOT / "experiments/runs/paper_sanitized_review_candidate_20261005.tar.gz"
ORIGINAL_SHA = "39ded8a4301ba0ebb193b48d71b032b0127a521c381fa378c67d08132319fc26"
SANITIZED_SHA = "48720a5620a1437094268452caab8f0168516454166147e575dea1c1039c0dd3"
MANIFEST_SHA = "a53a24fedc8f0a9f4fce2bf7d4451ebcb62cd06fc8de1d3b8ae465fc74dffef7"
INVENTORY = "BUNDLE_INVENTORY.json"
MANIFEST = "SANITIZATION_MANIFEST.json"
NOTICE = "REVIEW_ONLY_NOTICE.txt"
MAIN_ID = "rag-overnight-v2-main-0-5-0"
MAIN_INDEX = f"experiments/results/{MAIN_ID}.jsonl"
CONDITIONS = ("RD", "RW", "UD", "UW")


class ProvenanceError(ValueError):
    """A stored archive, member, or cross-archive link failed verification."""


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ProvenanceError(reason)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: bytes) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            _require(key not in value, "duplicate metadata key")
            value[key] = item
        return value

    try:
        value = json.loads(data, object_pairs_hook=unique)
    except ProvenanceError:
        raise
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProvenanceError("invalid archived metadata") from exc
    _require(isinstance(value, dict), "archived metadata is not an object")
    return value


def _safe(name: str) -> str:
    path = PurePosixPath(name)
    _require(bool(name) and not path.is_absolute() and ".." not in path.parts
             and path.as_posix() == name and "." not in path.parts,
             "unsafe archived member name")
    return name


def _members(path: Path) -> dict[str, bytes]:
    _require(path.is_file() and not path.is_symlink(), "archive absent or redirected")
    files: dict[str, bytes] = {}
    try:
        with tarfile.open(path, "r:gz") as archive:
            for member in archive:
                name = _safe(member.name)
                _require(member.isfile() and name not in files,
                         "non-file or duplicate archived member")
                stream = archive.extractfile(member)
                _require(stream is not None, "unreadable archived member")
                files[name] = stream.read()
    except (OSError, tarfile.TarError) as exc:
        raise ProvenanceError("cannot read archive") from exc
    return files


def _receipt(path: Path) -> dict[str, Any]:
    _require(path.is_file() and not path.is_symlink(), "archive receipt absent or redirected")
    return _json(path.read_bytes())


def _mapping(files: dict[str, bytes], key: str) -> dict[str, dict[str, Any]]:
    rows = _json(files[key]).get("members" if key == MANIFEST else "files")
    _require(isinstance(rows, list), "archive inventory rows absent")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        _require(isinstance(row, dict) and isinstance(row.get("path"), str),
                 "malformed inventory row")
        name = _safe(row["path"])
        _require(name not in result, "duplicate inventory row")
        result[name] = row
    return result


def _link(value: Any, files: dict[str, bytes]) -> str:
    _require(isinstance(value, str), "missing run member link")
    marker = "/experiments/runs/"
    _require(value.count(marker) == 1, "ambiguous run member link")
    name = _safe("experiments/runs/" + value.split(marker, 1)[1])
    _require(name in files, "linked run member absent")
    return name


def _terminal_counts(files: dict[str, bytes], *, original_log_hashes: dict[str, str] | None = None) -> dict[str, Any]:
    _require(MAIN_INDEX in files, "main result index absent")
    rows = [_json(line) for line in files[MAIN_INDEX].splitlines() if line.strip()]
    _require(len(rows) == 40, "main index does not contain 40 episodes")
    arms: Counter[str] = Counter()
    ids: set[str] = set()
    unavailable = raw_pass = accepted = discordant = 0
    for row in rows:
        _require(row.get("experiment_id") == MAIN_ID and
                 row.get("condition") in CONDITIONS and
                 isinstance(row.get("run_id"), str) and row["run_id"] not in ids,
                 "main run identity or condition differs")
        ids.add(row["run_id"])
        receipt = _json(files[_link(row.get("receipt_path"), files)])
        log_name = _link(row.get("log_path"), files)
        expected_log_sha = (_sha(files[log_name]) if original_log_hashes is None
                            else original_log_hashes[log_name])
        _require(row.get("log_sha256") == expected_log_sha,
                 "run log original hash link differs")
        for field in ("experiment_id", "run_id", "task_id", "condition",
                      "terminal_outcome", "stop_event", "log_sha256"):
            _require(row.get(field) == receipt.get(field),
                     "main index and terminal receipt differ")
        verifier = receipt.get("verifier_receipt")
        _require(isinstance(verifier, dict) and row.get("verifier_receipt") == verifier,
                 "main verifier link differs")
        candidate = verifier.get("candidate_receipt")
        _require(isinstance(candidate, dict), "terminal candidate receipt absent")
        details = candidate.get("details")
        _require(isinstance(details, dict) and isinstance(details.get("evaluator"), dict)
                 and isinstance(details.get("condition_policy"), dict),
                 "terminal evaluator receipt absent")
        condition = row["condition"]
        raw = details["evaluator"].get("passed")
        final = candidate.get("passed")
        reachable = candidate.get("condition_reachable")
        _require(type(raw) is bool and type(final) is bool and type(reachable) is bool,
                 "terminal outcome is not Boolean")
        _require(candidate.get("condition") == condition and
                 details["condition_policy"].get("condition") == condition and
                 details["condition_policy"].get("reachable") is reachable and
                 reachable is condition.startswith("R") and
                 final is (raw and reachable),
                 "terminal condition policy differs")
        if raw and not final:
            _require(candidate.get("failure_reason") == "condition_unreachable",
                     "discordant terminal reason differs")
        arms[condition] += 1
        unavailable += not reachable
        raw_pass += raw
        accepted += final
        discordant += raw and not final
    _require({condition: arms[condition] for condition in CONDITIONS} ==
             {condition: 10 for condition in CONDITIONS},
             "main condition arms differ")
    return {"main_episodes": len(rows), "nominally_unavailable": unavailable,
            "raw_family_test_pass": raw_pass, "final_candidate_accepted": accepted,
            "unavailable_raw_pass_final_reject": discordant}


def _current_ledger_comparison(path: Path, source_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Describe later workspace ledger drift; it is not a core archive gate."""
    if not path.is_file():
        return {"current_ledger_rows": None,
                "current_ledger_member_hashes_match": None,
                "current_ledger_member_hashes_differ": None}
    try:
        rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
    except (OSError, UnicodeError, csv.Error):
        rows = []
    if not rows or any(set(row) != {"path", "sha256"} for row in rows):
        return {"current_ledger_rows": None,
                "current_ledger_member_hashes_match": None,
                "current_ledger_member_hashes_differ": None}
    overlap = [row for row in rows if row["path"] in source_map]
    return {"current_ledger_rows": len(rows),
            "current_ledger_member_hashes_match": sum(
                row["sha256"] == source_map[row["path"]]["sha256"] for row in overlap),
            "current_ledger_member_hashes_differ": sum(
                row["sha256"] != source_map[row["path"]]["sha256"] for row in overlap)}


def audit(*, original: Path = ORIGINAL, sanitized: Path = SANITIZED) -> dict[str, Any]:
    """Verify frozen local bytes, member maps, sidecar receipts, and terminal counts."""
    original = Path(original)
    sanitized = Path(sanitized)
    original_bytes, sanitized_bytes = original.read_bytes(), sanitized.read_bytes()
    source_sha, review_sha = _sha(original_bytes), _sha(sanitized_bytes)
    _require(source_sha == ORIGINAL_SHA and review_sha == SANITIZED_SHA,
             "frozen archive SHA-256 differs")
    source, review = _members(original), _members(sanitized)
    _require(INVENTORY in source and MANIFEST in review and NOTICE in review,
             "archive metadata members absent")
    _require(INVENTORY not in review and MANIFEST not in source,
             "archive inventories confused")
    inventory, manifest = _json(source[INVENTORY]), _json(review[MANIFEST])
    _require(_sha(review[MANIFEST]) == MANIFEST_SHA,
             "frozen sanitization manifest SHA-256 differs")
    private_receipt, review_receipt = (_receipt(original.with_suffix(".receipt.json")),
                                       _receipt(sanitized.with_suffix(".receipt.json")))
    _require(inventory.get("status") == private_receipt.get("status") ==
             "PRIVATE_REVIEW_ONLY_UNREDACTED" and
             inventory.get("public_release_approved") is False and
             private_receipt.get("archive_sha256") == source_sha and
             private_receipt.get("archive_bytes") == len(original_bytes) and
             private_receipt.get("input_file_count") +
             private_receipt.get("additional_file_count") == len(source),
             "private inventory or sidecar receipt differs")
    _require(manifest.get("status") == review_receipt.get("status") ==
             "REVIEW_ONLY_SANITIZED_CANDIDATE" and
             manifest.get("public_release_approved") is False and
             manifest.get("scientific_replay_verified") is False and
             manifest.get("original_byte_identical_raw_data") is False and
             review_receipt.get("public_release_approved") is False and
             review_receipt.get("source_archive_sha256") == source_sha and
             review_receipt.get("sanitized_archive_sha256") == review_sha and
             review_receipt.get("sanitization_manifest_sha256") == MANIFEST_SHA and
             manifest.get("source_archive_sha256") == source_sha and
             manifest.get("source_inventory_sha256") == _sha(source[INVENTORY]),
             "sanitized manifest or sidecar receipt differs")
    source_map, review_map = _mapping(source, INVENTORY), _mapping(review, MANIFEST)
    _require(set(source_map) == set(source) - {INVENTORY} and
             set(review_map) == set(source) and
             set(review) == (set(source) - {INVENTORY}) | {MANIFEST, NOTICE},
             "original or transformed member set differs")
    _require(len(source) == manifest.get("source_member_count") ==
             manifest.get("mapping_count") == review_receipt.get("source_members") and
             len(review) == review_receipt.get("sanitized_members"),
             "member counts differ")
    for name, row in source_map.items():
        data = source[name]
        _require(row.get("sha256") == _sha(data) and row.get("bytes") == len(data),
                 "private inventory member hash or size differs")
    changed = unchanged = 0
    for name, row in review_map.items():
        original_data = source[name]
        _require(row.get("original_sha256") == _sha(original_data) and
                 row.get("original_bytes") == len(original_data),
                 "sanitization manifest original hash or size differs")
        if name == INVENTORY:
            _require(row.get("status") == "REPLACED_BY_SANITIZATION_MANIFEST" and
                     row.get("sanitized_sha256") is None and
                     row.get("sanitized_bytes") is None,
                     "private inventory replacement differs")
            continue
        transformed = review[name]
        _require(row.get("sanitized_sha256") == _sha(transformed) and
                 row.get("sanitized_bytes") == len(transformed),
                 "sanitization manifest transformed hash or size differs")
        same = transformed == original_data
        _require(row.get("status") == ("UNCHANGED" if same else "TRANSFORMED"),
                 "sanitization member change label differs")
        unchanged += same
        changed += not same
    _require(changed == manifest.get("changed_member_count") ==
             review_receipt.get("changed_member_count"),
             "transformed member count differs")
    original_counts = _terminal_counts(source)
    review_counts = _terminal_counts(
        review, original_log_hashes={name: row["original_sha256"]
                                     for name, row in review_map.items()})
    _require(original_counts == review_counts,
             "original and transformed terminal counts differ")
    ledger = ROOT / "paper/artifacts/input_hashes.csv"
    current_ledger_matches_historical_digest = (ledger.is_file() and
        _sha(ledger.read_bytes()) == inventory.get("paper_input_ledger_sha256"))
    return {
        "status": "LOCAL_ARCHIVE_LINK_VERIFIED_REVIEW_ONLY",
        "original_archive_sha256": source_sha,
        "sanitized_archive_sha256": review_sha,
        "sanitization_manifest_sha256": MANIFEST_SHA,
        "original_members_checked": len(source),
        "private_inventory_data_members_checked": len(source_map),
        "transformed_members_checked": changed + unchanged,
        "changed_members": changed,
        "unchanged_members": unchanged,
        "original_terminal_counts": original_counts,
        "transformed_terminal_counts_equal": True,
        "current_ledger_matches_historical_digest": current_ledger_matches_historical_digest,
        **_current_ledger_comparison(ledger, source_map),
        "local_original_to_sanitized_byte_link_verified": True,
        "historical_execution_provenance_verified": False,
        "public_release_approved": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()
    try:
        result = audit()
    except (OSError, ProvenanceError) as exc:
        parser.exit(2, f"ORIGINAL_ARCHIVE_PROVENANCE_FAILED: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

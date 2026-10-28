"""Descriptive C6 summaries derived only from replay-verified excluded archives.

The input is an explicit ledger of screened precursors. Every row names its
declared family and slot, a verified preflight, and optionally a pair archive.
This reader cannot create a prospective result or a confirmatory inference.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.c6_false_pass_integrated_excluded import (
    C6IntegratedError, verify_excluded_c6_pair,
)
from experiments.c6_false_pass_preflight import (
    C6PreflightError, verify_excluded_c6_preflight,
)
from experiments.main_collector import _json_object, _sha


VERSION = "excluded-c6-descriptive-reader-0.1.0"
ARMS = ("TRUTHFUL_FAIL", "FALSE_PASS")
ELIGIBLE = "ELIGIBLE_FIRST_INSECURE_SUBMISSION"
INPUT_FIELDS = frozenset({
    "family", "precursor_slot_id", "precursor_dir", "preflight_dir", "pair_dir",
})


class C6AnalysisError(ValueError):
    """An excluded C6 ledger cannot be reconciled to authenticated archives."""


def _read(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise C6AnalysisError(f"{label} is missing or symlinked")
    return _json_object(path.read_bytes(), label)


def _one(row: Mapping[str, Any], *, source_root: Path
         ) -> tuple[dict[str, Any], tuple[str, str]]:
    if not isinstance(row, Mapping) or set(row) != INPUT_FIELDS:
        raise C6AnalysisError("each C6 ledger row needs exact declared paths and identity")
    family, slot_id = row["family"], row["precursor_slot_id"]
    if not isinstance(family, str) or not family or not isinstance(slot_id, str) or not slot_id:
        raise C6AnalysisError("C6 declared family or precursor slot is malformed")
    if (not isinstance(row["precursor_dir"], (str, Path)) or
            not isinstance(row["preflight_dir"], (str, Path)) or
            (row["pair_dir"] is not None and
             not isinstance(row["pair_dir"], (str, Path)))):
        raise C6AnalysisError("C6 archive paths are malformed")
    precursor_dir, preflight_dir = Path(row["precursor_dir"]), Path(row["preflight_dir"])
    pair_dir = None if row["pair_dir"] is None else Path(row["pair_dir"])
    try:
        preflight = verify_excluded_c6_preflight(
            preflight_dir, precursor_dir=precursor_dir, source_root=source_root)
    except (C6PreflightError, ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        raise C6AnalysisError("C6 preflight failed independent replay") from exc
    plan = _read(precursor_dir / "plan_snapshot.json", "precursor plan")
    slots = [slot for slot in plan.get("slots", []) if isinstance(slot, dict)
             and slot.get("slot_id") == preflight["precursor_slot_id"]]
    if (len(slots) != 1 or family != slots[0].get("family") or
            slot_id != preflight["precursor_slot_id"]):
        raise C6AnalysisError("declared family or slot differs from verified precursor")
    identity = (preflight["precursor_integrated_receipt_sha256"], slot_id)
    status = preflight["status"]
    result: dict[str, Any] = {
        "family": family,
        "precursor_slot_id": slot_id,
        "preflight_status": status,
        "preflight_sha256": _sha((preflight_dir / "preflight.json").read_bytes()),
        "pair_status": None,
        "pair_receipt_sha256": None,
        "terminal_finite_failure_difference": None,
        "unsafe_early_stop_difference": None,
        "arm_statuses": None,
    }
    if status != ELIGIBLE:
        if pair_dir is not None:
            raise C6AnalysisError("nonreach precursor cannot have a C6 pair archive")
        result["pair_status"] = "UNUSED_NONREACH"
        return result, identity
    if pair_dir is None:
        result["pair_status"] = "ELIGIBLE_NO_PAIR_ARCHIVE"
        return result, identity
    try:
        pair = verify_excluded_c6_pair(
            pair_dir, preflight_dir=preflight_dir,
            precursor_dir=precursor_dir, source_root=source_root)
    except (C6IntegratedError, C6PreflightError, ValueError, RuntimeError,
            OSError, KeyError, TypeError) as exc:
        raise C6AnalysisError("C6 pair failed independent replay") from exc
    receipts: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        raw = (pair_dir / f"{arm.lower()}.receipt.json").read_bytes()
        if _sha(raw) != pair["arm_receipt_sha256s"][arm]:
            raise C6AnalysisError("C6 arm receipt changed after independent replay")
        receipts[arm] = _json_object(raw, f"{arm} receipt")
    result["pair_receipt_sha256"] = _sha((pair_dir / "pair_receipt.json").read_bytes())
    result["arm_statuses"] = {arm: receipts[arm]["status"] for arm in ARMS}
    if pair["status"] == "INVALIDATED_EXCLUDED_C6_PAIR":
        result["pair_status"] = "TECHNICALLY_INVALIDATED_PAIR"
        return result, identity
    if pair["status"] != "COMPLETED_EXCLUDED_C6_PAIR":
        raise C6AnalysisError("C6 pair has an unknown replayed status")
    recovered = {
        arm: receipts[arm]["endpoint"]["terminal_finite_property_recovered"]
        for arm in ARMS
    }
    unsafe = {arm: receipts[arm]["unsafe_early_stop"] for arm in ARMS}
    if (any(value not in (0, 1) or type(value) is not int for value in recovered.values())
            or any(type(value) is not bool for value in unsafe.values())):
        result["pair_status"] = "INDETERMINATE_FINAL_PROPERTY"
        return result, identity
    result["pair_status"] = "VALID_EXCLUDED_PAIR"
    result["terminal_finite_failure_difference"] = (
        (1 - recovered["FALSE_PASS"]) - (1 - recovered["TRUTHFUL_FAIL"]))
    result["unsafe_early_stop_difference"] = (
        int(unsafe["FALSE_PASS"]) - int(unsafe["TRUTHFUL_FAIL"]))
    return result, identity


def summarize_excluded_c6_pairs(rows: Sequence[Mapping[str, Any]], *,
                                source_root: Path) -> dict[str, Any]:
    """Summarize declared excluded precursors; never treat pairs as families."""
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise C6AnalysisError("C6 analysis needs an explicit precursor ledger")
    source_root = Path(source_root).resolve()
    pairs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in rows:
        pair, identity = _one(entry, source_root=source_root)
        if identity in seen:
            raise C6AnalysisError("one authenticated precursor is listed more than once")
        seen.add(identity)
        pairs.append(pair)
    pairs.sort(key=lambda pair: (pair["family"], pair["precursor_slot_id"],
                                 pair["preflight_sha256"]))
    status_counts = Counter(pair["pair_status"] for pair in pairs)
    preflight_counts = Counter(pair["preflight_status"] for pair in pairs)
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        by_family[pair["family"]].append(pair)
    families: list[dict[str, Any]] = []
    for family, family_pairs in sorted(by_family.items()):
        valid = [pair for pair in family_pairs
                 if pair["pair_status"] == "VALID_EXCLUDED_PAIR"]
        families.append({
            "family": family,
            "screened_precursors": len(family_pairs),
            "eligible_first_submissions": sum(
                pair["preflight_status"] == ELIGIBLE for pair in family_pairs),
            "valid_pairs": len(valid),
            "terminal_finite_failure_difference": (
                sum(pair["terminal_finite_failure_difference"] for pair in valid) / len(valid)
                if valid else None),
            "unsafe_early_stop_difference": (
                sum(pair["unsafe_early_stop_difference"] for pair in valid) / len(valid)
                if valid else None),
        })
    contributing = [family for family in families if family["valid_pairs"] > 0]
    return {
        "schema_version": VERSION,
        "phase": "pilot",
        "status": "EXCLUDED_DESCRIPTIVE_ONLY",
        "eligible_for_main_analysis": False,
        "confirmatory_inference_available": False,
        "screened_precursor_count": len(pairs),
        "eligible_first_submission_count": preflight_counts[ELIGIBLE],
        "pair_archive_count": sum(pair["pair_receipt_sha256"] is not None for pair in pairs),
        "valid_pair_count": status_counts["VALID_EXCLUDED_PAIR"],
        "technically_invalidated_pair_count": status_counts["TECHNICALLY_INVALIDATED_PAIR"],
        "indeterminate_final_property_pair_count": status_counts["INDETERMINATE_FINAL_PROPERTY"],
        "eligible_without_pair_archive_count": status_counts["ELIGIBLE_NO_PAIR_ARCHIVE"],
        "nonreach_count": status_counts["UNUSED_NONREACH"],
        "preflight_status_counts": dict(sorted(preflight_counts.items())),
        "pair_status_counts": dict(sorted(status_counts.items())),
        "screened_family_count": len(families),
        "contributing_family_count": len(contributing),
        "equal_family_terminal_finite_failure_difference": (
            sum(family["terminal_finite_failure_difference"] for family in contributing)
            / len(contributing) if contributing else None),
        "equal_family_unsafe_early_stop_difference": (
            sum(family["unsafe_early_stop_difference"] for family in contributing)
            / len(contributing) if contributing else None),
        "families": families,
        "pairs": pairs,
    }

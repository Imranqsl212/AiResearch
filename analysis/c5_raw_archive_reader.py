"""Read excluded C5 fixture archives into a paired, family-level diagnostic.

This is deliberately separate from the synthetic ledger and every main writer.
It verifies the existing pair and precursor-link contracts, then derives actions
again from the exact archived response bytes. Supplied oracle receipts and the
claim that a fixture response came from a model remain unverified semantics.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from statistics import fmean
from typing import Any

from analysis.power_simulation import student_t_critical_one_sided, student_t_survival
from experiments.main_c5_fork_scaffold import (
    CAP, VERSION as PAIR_VERSION, _plan_pair, verify_excluded_pair,
)
from experiments.main_c5_precursor_bridge import verify_excluded_precursor_link


VERSION = "excluded-c5-raw-fixture-reader-0.1.0"
MIN_INFERENTIAL_FAMILIES = 15
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_REASON = re.compile(r"[A-Z][A-Z0-9_]{1,79}\Z")
_PRECURSOR_STATES = {"NO_ONSET", "PRE_VERDICT_INVALIDATED", "SECURE_ONSET"}


class C5RawArchiveError(ValueError):
    """A fixture archive is missing, inconsistent, or improperly allocated."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise C5RawArchiveError("duplicate JSON key in archived record")
        value[key] = item
    return value


def _object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_unique)
    except (ValueError, UnicodeDecodeError) as exc:
        raise C5RawArchiveError(f"{label} is not unique-key UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise C5RawArchiveError(f"{label} must be an object")
    return value


def _read(root: Path, name: str) -> bytes:
    if (not root.is_dir() or root.is_symlink() or "/" in name or "\\" in name
            or name.startswith(".")):
        raise C5RawArchiveError("unsafe or missing fixture archive directory")
    file = root / name
    if not file.is_file() or file.is_symlink():
        raise C5RawArchiveError(f"missing or symlinked fixture record: {name}")
    return file.read_bytes()


def _validated_allocation(plan: Mapping[str, Any], family: str, root: Path,
                          ranked_pairs: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Recompute the complete ten-slot allocation, including nonreach and overflow."""
    if _read(root, "plan_snapshot.json") != _canonical(plan):
        raise C5RawArchiveError("family allocation is bound to different plan bytes")
    allocation = _object(_read(root, "family_allocation.json"), "family allocation")
    if (allocation.get("schema_version") != PAIR_VERSION
            or allocation.get("phase") != "pilot"
            or allocation.get("status") != "EXCLUDED_FIXTURE_FAMILY_ALLOCATION_LEDGER"
            or allocation.get("eligible_for_main_analysis") is not False
            or allocation.get("main_dispatch_allowed") is not False
            or allocation.get("model_calls") != 0
            or allocation.get("semantic_oracle_verification") is not False
            or allocation.get("family") != family
            or allocation.get("plan_sha256") != _sha(_canonical(plan))
            or allocation.get("no_replacement") is not True):
        raise C5RawArchiveError("family allocation is not an excluded, plan-bound fixture")
    ids = ranked_pairs[0]["eligible_precursor_slot_ids_in_frozen_order"]
    rows = allocation.get("precursor_ledger")
    if (not isinstance(rows, list) or len(rows) != 10
            or [row.get("slot_id") for row in rows if isinstance(row, dict)] != ids):
        raise C5RawArchiveError("family allocation does not partition ten frozen precursors")
    for row in rows:
        if not isinstance(row, dict) or row.get("status") not in _PRECURSOR_STATES:
            raise C5RawArchiveError("family precursor state is malformed")
        if row["status"] == "SECURE_ONSET":
            if (type(row.get("first_secure_attempt_number")) is not int
                    or row["first_secure_attempt_number"] < 1
                    or not isinstance(row.get("oracle_receipt_sha256"), str)
                    or _HEX64.fullmatch(row["oracle_receipt_sha256"]) is None):
                raise C5RawArchiveError("secure precursor lacks first-attempt receipt")
        elif row.get("oracle_receipt_sha256") is not None:
            raise C5RawArchiveError("non-onset precursor carries a secure receipt")
    secure = [row["slot_id"] for row in rows if row["status"] == "SECURE_ONSET"]
    expected_reservations = [{
        "pair_id": pair["pair_id"], "onset_rank": rank,
        "precursor_slot_id": secure[rank - 1] if rank <= len(secure) else None,
        "status": "SELECTED_FIXTURE_ONSET" if rank <= len(secure) else "UNUSED_NONREACH",
    } for rank, pair in enumerate(ranked_pairs, 1)]
    if (allocation.get("reservations") != expected_reservations
            or allocation.get("selected_count") != min(5, len(secure))
            or allocation.get("exploratory_overflow_slot_ids") != secure[5:]
            or allocation.get("nonreach_count") != sum(row["status"] == "NO_ONSET" for row in rows)
            or allocation.get("pre_verdict_invalidated_count") != sum(
                row["status"] == "PRE_VERDICT_INVALIDATED" for row in rows)):
        raise C5RawArchiveError("family onset rank, nonreach, or invalidation was relabeled")
    return rows, secure


def _raw_action(response_raw: bytes) -> tuple[str, dict[str, Any]]:
    response = _object(response_raw, "archived provider response")
    message = response.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise C5RawArchiveError("archived provider response lacks assistant content")
    action = _object(message["content"].encode("utf-8"), "archived assistant action")
    if not isinstance(action.get("action"), str) or not isinstance(action.get("payload"), dict):
        raise C5RawArchiveError("archived assistant action is malformed")
    return action["action"], action["payload"]


def _arm_from_bytes(pair_dir: Path, arm: str, onset_candidate_hash: str) -> dict[str, Any]:
    receipt = _object(_read(pair_dir, f"{arm.lower()}.receipt.json"), "arm receipt")
    requests = receipt["request_response_archive"]
    hashes: list[str] = []
    actions: list[str] = []
    for row in receipt["actions"]:
        request_row = requests[row["request_sequence"] - 1]
        response_name = request_row["response_path"]
        if not isinstance(response_name, str):
            raise C5RawArchiveError("archived action lacks its response bytes")
        name, payload = _raw_action(_read(pair_dir, response_name))
        if row["action"] != name.upper():
            raise C5RawArchiveError("arm action differs from response bytes")
        actions.append(name.upper())
        if name == "attempt":
            candidate = payload.get("candidate")
            if not isinstance(candidate, dict):
                raise C5RawArchiveError("submitted candidate is not reconstructable")
            digest = _sha(_canonical(candidate))
            if digest != row["candidate_sha256"]:
                raise C5RawArchiveError("submitted candidate hash differs from response bytes")
            hashes.append(digest)
    invalidated = receipt["status"] == "INVALIDATED_EXCLUDED_FIXTURE"
    verdict = _object(_read(pair_dir, "preflight.json"), "preflight")["arm_orientation"][arm]
    return {
        "arm": arm, "public_verdict": verdict,
        "status": receipt["status"], "invalidation_reason": receipt["invalidated_reason"],
        "terminal_cause": receipt["stop_reason"],
        "decisions_used": len(actions), "actions": actions,
        "candidate_submissions": len(hashes), "candidate_sha256s": hashes,
        "distinct_new_candidate_hash_count": len(set(hashes) - {onset_candidate_hash}),
        "onset_candidate_resubmitted": onset_candidate_hash in hashes,
        "early_voluntary_stop": None if invalidated else (
            receipt["stop_reason"] == "VOLUNTARY" and len(actions) < CAP),
    }


def _family_t(differences: list[float]) -> dict[str, Any]:
    """Only a numerical rehearsal on excluded fixture-derived family values."""
    n = len(differences)
    mean = fmean(differences) if n else None
    base = {"n_contributing_families": n, "equal_family_mean_D_f": mean,
            "standard_error": None, "two_sided_p_value": None,
            "student_t_95pct_interval": None, "decision_at_alpha_0_05": None}
    if n < MIN_INFERENTIAL_FAMILIES:
        return {**base, "test_status": "NONESTIMABLE_FEWER_THAN_15_VALID_PAIR_FAMILIES"}
    assert mean is not None
    sum_sq = sum((value - mean) ** 2 for value in differences)
    if sum_sq == 0:
        return {**base, "test_status": "NONESTIMABLE_ZERO_BETWEEN_FAMILY_VARIANCE"}
    se = math.sqrt(sum_sq / ((n - 1) * n))
    critical = student_t_critical_one_sided(n - 1, 0.025)
    p_value = min(1.0, 2 * student_t_survival(abs(mean / se), n - 1))
    return {**base, "test_status": "EXCLUDED_FIXTURE_T_DIAGNOSTIC_ONLY",
            "standard_error": se, "two_sided_p_value": p_value,
            "student_t_95pct_interval": [mean - critical * se, mean + critical * se],
            "decision_at_alpha_0_05": p_value < 0.05}


def audit_excluded_c5_archives(*, plan: Mapping[str, Any],
                               family_ledger_dirs: Mapping[str, Path],
                               pair_archive_dirs: Mapping[str, Path],
                               precursor_trace_dirs: Mapping[str, Path],
                               missing_pair_reasons: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Account for all reserved pairs using verified excluded raw fixture bytes.

    Selected pairs need both complete archives or an explicit infrastructure
    invalidation reason. A missing selected pair is never replaced. An archived
    pair with one invalid arm is retained without a behavioral difference.
    """
    if not isinstance(plan, Mapping) or not all(isinstance(value, Mapping) for value in (
            family_ledger_dirs, pair_archive_dirs, precursor_trace_dirs)):
        raise C5RawArchiveError("plan and archive indexes must be mappings")
    missing_pair_reasons = {} if missing_pair_reasons is None else missing_pair_reasons
    if not isinstance(missing_pair_reasons, Mapping):
        raise C5RawArchiveError("missing-pair reasons must be a mapping")
    pairs = plan.get("c5_branch_pair_reservations")
    if not isinstance(pairs, list) or not pairs:
        raise C5RawArchiveError("proposed C5 pair reservations are absent")
    families: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for pair in pairs:
        if not isinstance(pair, dict) or not isinstance(pair.get("family"), str):
            raise C5RawArchiveError("malformed pair reservation")
        _plan_pair(plan, pair["pair_id"])
        families[pair["family"]].append(pair)
    pair_ids = [pair["pair_id"] for pair in pairs]
    if len(set(pair_ids)) != len(pair_ids) or set(family_ledger_dirs) != set(families):
        raise C5RawArchiveError("every unique scheduled family needs one allocation archive")
    if (set(pair_archive_dirs) != set(precursor_trace_dirs)
            or set(pair_archive_dirs) & set(missing_pair_reasons)
            or any(pair_id not in pair_ids for pair_id in
                   set(pair_archive_dirs) | set(missing_pair_reasons))):
        raise C5RawArchiveError("pair/trace indexes or missing-pair stubs disagree")
    if (len({Path(path).resolve() for path in pair_archive_dirs.values()}) != len(pair_archive_dirs)
            or len({Path(path).resolve() for path in precursor_trace_dirs.values()})
            != len(precursor_trace_dirs)):
        raise C5RawArchiveError("one raw archive cannot fill multiple pair reservations")
    for reason in missing_pair_reasons.values():
        if not isinstance(reason, str) or _REASON.fullmatch(reason) is None:
            raise C5RawArchiveError("missing selected pair needs a structured reason")
    pair_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    for family in sorted(families):
        ranked = sorted(families[family], key=lambda row: row["onset_rank"])
        if len(ranked) != 5 or [row["onset_rank"] for row in ranked] != [1, 2, 3, 4, 5]:
            raise C5RawArchiveError("family lacks five frozen ranked reservations")
        ledger, secure = _validated_allocation(
            plan, family, Path(family_ledger_dirs[family]), ranked)
        slot_ids = ranked[0]["eligible_precursor_slot_ids_in_frozen_order"]
        differences: list[int] = []
        for rank, pair in enumerate(ranked, 1):
            pair_id = pair["pair_id"]
            selected_slot = secure[rank - 1] if rank <= len(secure) else None
            row: dict[str, Any] = {
                "family": family, "pair_id": pair_id, "onset_rank": rank,
                "allocated_precursor_slot_id": selected_slot,
                "status": None, "invalidation_reason": None,
                "branches_by_verdict": None, "paired_early_stop_difference": None,
                "paired_submission_difference": None,
                "pair_receipt_sha256": None, "precursor_slot_receipt_sha256": None,
                "precursor_request_sha256": None, "precursor_response_sha256": None,
            }
            if selected_slot is None:
                if pair_id in pair_archive_dirs or pair_id in missing_pair_reasons:
                    raise C5RawArchiveError("nonreached reservation cannot have a pair archive")
                row["status"] = "UNUSED_NONREACH"
            elif pair_id in missing_pair_reasons:
                row["status"] = "INVALIDATED_MISSING_ARCHIVE"
                row["invalidation_reason"] = missing_pair_reasons[pair_id]
            else:
                if pair_id not in pair_archive_dirs:
                    raise C5RawArchiveError("selected onset lacks a pair archive or invalidation")
                pair_dir = Path(pair_archive_dirs[pair_id])
                trace_dir = Path(precursor_trace_dirs[pair_id])
                if (pair_dir.is_symlink() or trace_dir.is_symlink()
                        or _read(pair_dir, "plan_snapshot.json") != _canonical(plan)):
                    raise C5RawArchiveError("pair archive is unsafe or uses a different plan")
                pair_receipt = verify_excluded_pair(pair_dir)
                link = verify_excluded_precursor_link(trace_dir=trace_dir, pair_dir=pair_dir)
                row["pair_receipt_sha256"] = _sha(_read(pair_dir, "pair.receipt.json"))
                row["precursor_slot_receipt_sha256"] = _sha(
                    _read(trace_dir, "slot_receipt.json"))
                row["precursor_request_sha256"] = link["precursor_request_sha256"]
                row["precursor_response_sha256"] = link["precursor_response_sha256"]
                preflight = _object(_read(pair_dir, "preflight.json"), "pair preflight")
                slot_index = slot_ids.index(selected_slot)
                archived_prefix = json.loads(_read(pair_dir, "precursor_ledger.json"),
                                             object_pairs_hook=_unique)
                if (preflight.get("pair_id") != pair_id
                        or preflight.get("precursor_slot_id") != selected_slot
                        or preflight.get("onset_rank") != rank
                        or archived_prefix != ledger[:slot_index + 1]
                        or link.get("trace_slot_id") != selected_slot
                        or link.get("pair_id") != pair_id):
                    raise C5RawArchiveError("forked onset differs from selected family precursor")
                onset_candidate = _object(_read(pair_dir, "candidate.json"), "onset candidate")
                onset_hash = _sha(_canonical(onset_candidate))
                by_verdict: dict[str, dict[str, Any]] = {}
                for arm in ("A", "B"):
                    branch = _arm_from_bytes(pair_dir, arm, onset_hash)
                    by_verdict[branch["public_verdict"]] = branch
                if set(by_verdict) != {"PASS", "FALSE_FAIL"}:
                    raise C5RawArchiveError("archived pair lacks complementary verdicts")
                row["branches_by_verdict"] = by_verdict
                if pair_receipt["pair_invalidated"]:
                    row["status"] = "INVALIDATED_ARCHIVED_PAIR"
                    reasons = [branch["invalidation_reason"] for branch in by_verdict.values()
                               if branch["invalidation_reason"]]
                    row["invalidation_reason"] = "+".join(sorted(reasons))
                else:
                    row["status"] = "VALID_PAIR"
                    diff = (int(by_verdict["FALSE_FAIL"]["early_voluntary_stop"])
                            - int(by_verdict["PASS"]["early_voluntary_stop"]))
                    row["paired_early_stop_difference"] = diff
                    row["paired_submission_difference"] = (
                        by_verdict["FALSE_FAIL"]["candidate_submissions"]
                        - by_verdict["PASS"]["candidate_submissions"])
                    differences.append(diff)
            pair_rows.append(row)
        family_rows.append({
            "family": family, "precursor_slot_count": len(ledger),
            "precursor_status_counts": dict(sorted(Counter(
                row["status"] for row in ledger).items())),
            "selected_onset_slot_ids": secure[:5],
            "exploratory_overflow_slot_ids": secure[5:],
            "valid_pair_count": len(differences),
            "invalidated_pair_count": sum(row["family"] == family and row["status"].startswith(
                "INVALIDATED") for row in pair_rows),
            "unused_pair_count": sum(row["family"] == family and row["status"] == "UNUSED_NONREACH"
                                     for row in pair_rows),
            "D_f": fmean(differences) if differences else None,
        })
    family_differences = [row["D_f"] for row in family_rows if row["D_f"] is not None]
    return {
        "schema_version": VERSION, "phase": "pilot",
        "status": "EXCLUDED_RAW_FIXTURE_DIAGNOSTIC_ONLY",
        "eligible_for_main_analysis": False, "main_dispatch_allowed": False,
        "model_calls": 0, "semantic_oracle_verification": False,
        "agent_generation_verified": False, "plan_sha256": _sha(_canonical(plan)),
        "family_count": len(family_rows), "onset_producing_family_count": sum(
            bool(row["selected_onset_slot_ids"]) for row in family_rows),
        "valid_pair_family_count": len(family_differences),
        "reserved_pair_count": len(pair_rows),
        "valid_pair_count": sum(row["status"] == "VALID_PAIR" for row in pair_rows),
        "invalidated_pair_count": sum(row["status"].startswith("INVALIDATED") for row in pair_rows),
        "unused_pair_count": sum(row["status"] == "UNUSED_NONREACH" for row in pair_rows),
        "family_accounting": family_rows, "pair_accounting": pair_rows,
        "family_t_diagnostic": _family_t(family_differences),
    }

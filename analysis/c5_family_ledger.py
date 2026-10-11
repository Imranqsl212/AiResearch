"""Mechanical C5 ledger audit on *excluded synthetic* inputs only.

This module checks a proposed 20-family schedule and a complete mock result
ledger. It intentionally has no raw episode reader and no main-release API.
Neither syntactically valid input nor a non-null synthetic t statistic proves
that an onset, fork, oracle result, or model response occurred.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from statistics import fmean
from typing import Any

from analysis.power_simulation import student_t_critical_one_sided, student_t_survival


VERSION = "excluded-synthetic-c5-family-ledger-0.1.0"
PLAN_VERSION = "prospective-primary-main-plan-0.2.0"
FAMILIES = 20
PRECURSORS_PER_FAMILY = 10
ONSET_CAP = 5
DECISION_CAP = 3
MIN_INFERENTIAL_FAMILIES = 15
COMPANIONS = ("C2_MINUS_C1", "C4_MINUS_C3", "R1_MINUS_R0")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_PRECURSOR_STATES = {"VALID_NO_ONSET", "VALID_AGENT_SECURE_ONSET", "INVALIDATED_PRE_VERDICT"}
_PAIR_STATES = {"UNUSED_NO_ONSET", "VALID_PAIR", "INVALIDATED_PAIR"}
_CAUSES = {"VOLUNTARY_STOP", "BUDGET_STOP", "TIMEOUT", "INFRASTRUCTURE_FAILURE"}


class C5LedgerError(ValueError):
    """A synthetic ledger is incomplete, contradictory, or outside this scope."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _record(row: Any, keys: set[str], name: str) -> Mapping[str, Any]:
    if not isinstance(row, Mapping) or set(row) != keys:
        raise C5LedgerError(f"{name} needs exactly {sorted(keys)}")
    return row


def _hash_or_none(value: Any, *, required: bool, name: str) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise C5LedgerError(f"{name} needs an exact lower-case SHA-256")


def _unique_map(rows: Any, key: str, name: str) -> dict[str, Mapping[str, Any]]:
    if not isinstance(rows, list):
        raise C5LedgerError(f"{name} must be a list")
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get(key), str) or not row[key]:
            raise C5LedgerError(f"{name} has an invalid {key}")
        if row[key] in result:
            raise C5LedgerError(f"{name} has a duplicate {key}")
        result[row[key]] = row
    return result


def _schedule(plan: Mapping[str, Any]) -> tuple[dict[str, list[str]], dict[str, Mapping[str, Any]],
                                                 dict[str, dict[str, Mapping[str, Any]]]]:
    """Validate C5-relevant scheduling structure, not its source authenticity."""
    if (plan.get("schema_version") != PLAN_VERSION or plan.get("phase") != "main"
            or plan.get("status") != "PROPOSED_MAIN_UNGATED"
            or plan.get("eligible_for_main_analysis") is not False
            or plan.get("main_execution_implemented") is not False
            or plan.get("family_count") != FAMILIES or plan.get("planned_slot_count") != 600
            or plan.get("planned_c5_pair_capacity") != FAMILIES * ONSET_CAP
            or plan.get("planned_c5_continuation_capacity") != 2 * FAMILIES * ONSET_CAP):
        raise C5LedgerError("expected the ungated 20-family proposed primary schedule")
    slots = _unique_map(plan.get("slots"), "slot_id", "full schedule")
    if len(slots) != 600:
        raise C5LedgerError("full schedule must retain 600 unique slots")
    by_family: dict[str, list[str]] = defaultdict(list)
    cells: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    for slot in plan["slots"]:
        family = slot.get("family")
        if not isinstance(family, str) or not family:
            raise C5LedgerError("full schedule has an unresolved family")
        mode, condition = slot.get("retrieval_mode"), slot.get("condition")
        if not isinstance(mode, str) or not isinstance(condition, str):
            raise C5LedgerError("full schedule has an unresolved mode or condition")
        cells[family][mode, condition] += 1
        if slot.get("retrieval_mode") == "R0" and slot.get("condition") in {"C1", "C2"}:
            by_family[family].append(slot["slot_id"])
    if len(by_family) != FAMILIES or any(len(ids) != PRECURSORS_PER_FAMILY for ids in by_family.values()):
        raise C5LedgerError("exactly ten R0 C1/C2 precursors per family are required")
    required_cells = {("R0", "C1"), ("R0", "C2"), ("R0", "C3"),
                      ("R0", "C4"), ("R1", "C1"), ("R1", "C2")}
    if set(cells) != set(by_family) or any(
        set(family_cells) != required_cells or any(count != 5 for count in family_cells.values())
        for family_cells in cells.values()
    ):
        raise C5LedgerError("full schedule needs five repeats in each of the six planned family cells")
    pairs = _unique_map(plan.get("c5_branch_pair_reservations"), "pair_id", "pair reservations")
    continuations = _unique_map(plan.get("c5_continuation_reservations"), "continuation_id",
                                "continuation reservations")
    if len(pairs) != FAMILIES * ONSET_CAP or len(continuations) != 2 * len(pairs):
        raise C5LedgerError("reservation capacities differ from the proposed design")
    per_family: dict[str, set[int]] = defaultdict(set)
    by_pair: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for pair in pairs.values():
        family, rank = pair.get("family"), pair.get("onset_rank")
        orientation = pair.get("arm_execution_order")
        a_verdict, b_verdict = pair.get("arm_a_verdict"), pair.get("arm_b_verdict")
        if (not isinstance(family, str) or family not in by_family
                or type(rank) is not int or not 1 <= rank <= ONSET_CAP
                or rank in per_family[family]
                or pair.get("eligible_precursor_slot_ids_in_frozen_order") != by_family[family]
                or not isinstance(a_verdict, str) or not isinstance(b_verdict, str)
                or {a_verdict, b_verdict} != {"PASS", "FALSE_FAIL"}
                or orientation not in (["A", "B"], ["B", "A"])):
            raise C5LedgerError("pair rank, precursor order, or frozen orientation differs")
        per_family[family].add(rank)
    if any(ranks != set(range(1, ONSET_CAP + 1)) for ranks in per_family.values()):
        raise C5LedgerError("each family needs ranks one through five")
    for continuation in continuations.values():
        pair_id, arm = continuation.get("pair_id"), continuation.get("arm")
        if not isinstance(pair_id, str) or pair_id not in pairs or arm not in ("A", "B") or arm in by_pair[pair_id]:
            raise C5LedgerError("continuation is unreserved, duplicated, or has no arm")
        pair = pairs[pair_id]
        verdict = pair["arm_a_verdict"] if arm == "A" else pair["arm_b_verdict"]
        if (continuation.get("family") != pair["family"]
                or continuation.get("onset_rank") != pair["onset_rank"]
                or continuation.get("public_verdict") != verdict
                or continuation.get("episode_seed") != pair.get("branch_seed")
                or continuation.get("post_verdict_decision_cap") != DECISION_CAP
                or continuation.get("execution_rank_within_pair") != pair["arm_execution_order"].index(arm) + 1):
            raise C5LedgerError("continuation differs from the frozen pair assignment")
        by_pair[pair_id][arm] = continuation
    if any(set(arms) != {"A", "B"} for arms in by_pair.values()) or len(by_pair) != len(pairs):
        raise C5LedgerError("every pair needs exactly A and B continuation reservations")
    return dict(by_family), pairs, dict(by_pair)


def _precursors(ledger: Mapping[str, Any], by_family: Mapping[str, list[str]]) -> dict[str, Mapping[str, Any]]:
    rows = _unique_map(ledger.get("precursor_results"), "slot_id", "precursor results")
    expected = {slot_id for ids in by_family.values() for slot_id in ids}
    if set(rows) != expected:
        raise C5LedgerError("precursor results must partition all 200 frozen R0 C1/C2 slots")
    keys = {"slot_id", "status", "invalidation_reason", "onset_candidate_sha256",
            "pre_verdict_context_sha256", "oracle_replay_receipt_sha256"}
    for row in rows.values():
        _record(row, keys, "precursor result")
        status = row["status"]
        if not isinstance(status, str) or status not in _PRECURSOR_STATES:
            raise C5LedgerError("unknown precursor status")
        secure = status == "VALID_AGENT_SECURE_ONSET"
        invalid = status == "INVALIDATED_PRE_VERDICT"
        if (invalid and (not isinstance(row["invalidation_reason"], str)
                         or not row["invalidation_reason"].strip())) or (not invalid and row["invalidation_reason"] is not None):
            raise C5LedgerError("precursor invalidation reason disagrees with status")
        for key in ("onset_candidate_sha256", "pre_verdict_context_sha256",
                    "oracle_replay_receipt_sha256"):
            _hash_or_none(row[key], required=secure, name=key)
            if not secure and row[key] is not None:
                raise C5LedgerError("non-onset precursor cannot carry onset evidence")
    return rows


def _continuations(ledger: Mapping[str, Any], expected_ids: set[str]) -> dict[str, Mapping[str, Any]]:
    rows = _unique_map(ledger.get("continuation_results"), "continuation_id", "continuation results")
    if set(rows) != expected_ids:
        raise C5LedgerError("every allocated A/B continuation needs one result or invalidation stub")
    keys = {"continuation_id", "status", "decisions_used", "terminal_cause",
            "candidate_sha256s", "invalidation_reason"}
    for row in rows.values():
        _record(row, keys, "continuation result")
        status, cause, decisions = row["status"], row["terminal_cause"], row["decisions_used"]
        if not isinstance(status, str) or status not in {"VALID", "INVALIDATED"} or not isinstance(cause, str) or cause not in _CAUSES:
            raise C5LedgerError("unknown continuation state or terminal cause")
        if type(decisions) is not int or not 0 <= decisions <= DECISION_CAP:
            raise C5LedgerError("continuation decisions exceed the fixed cap")
        candidate_hashes = row["candidate_sha256s"]
        if not isinstance(candidate_hashes, list) or len(candidate_hashes) > decisions:
            raise C5LedgerError("submissions exceed decisions")
        for candidate_hash in candidate_hashes:
            _hash_or_none(candidate_hash, required=True, name="submitted candidate hash")
        if status == "VALID":
            if cause == "INFRASTRUCTURE_FAILURE" or row["invalidation_reason"] is not None:
                raise C5LedgerError("valid continuation claims infrastructure failure")
            if cause == "BUDGET_STOP" and decisions != DECISION_CAP:
                raise C5LedgerError("budget stop must consume all three decisions")
            if cause == "VOLUNTARY_STOP" and decisions < 1:
                raise C5LedgerError("voluntary stop needs a model decision")
        elif (cause != "INFRASTRUCTURE_FAILURE" or not isinstance(row["invalidation_reason"], str)
              or not row["invalidation_reason"].strip()):
            raise C5LedgerError("invalidated continuation needs infrastructure cause and reason")
    return rows


def _family_t(differences: list[float]) -> dict[str, Any]:
    n = len(differences)
    mean = fmean(differences) if n else None
    base = {"n_contributing_families": n, "equal_family_mean_difference": mean,
            "standard_error": None, "degrees_of_freedom": None,
            "two_sided_p_value": None, "student_t_95pct_interval": None,
            "decision_at_alpha_0_05": None}
    if n < MIN_INFERENTIAL_FAMILIES:
        return {**base, "test_status": "NONESTIMABLE_FEWER_THAN_15_FAMILIES"}
    assert mean is not None
    sum_sq = sum((value - mean) ** 2 for value in differences)
    if sum_sq == 0:
        return {**base, "test_status": "NONESTIMABLE_ZERO_BETWEEN_FAMILY_VARIANCE"}
    se = math.sqrt(sum_sq / ((n - 1) * n))
    critical = student_t_critical_one_sided(n - 1, 0.025)
    p_value = min(1.0, 2 * student_t_survival(abs(mean / se), n - 1))
    return {**base, "test_status": "SYNTHETIC_T_DIAGNOSTIC_ONLY",
            "standard_error": se, "degrees_of_freedom": n - 1,
            "two_sided_p_value": p_value,
            "student_t_95pct_interval": [mean - critical * se, mean + critical * se],
            "decision_at_alpha_0_05": p_value < 0.05}


def holm_three_companions(p_values: Mapping[str, float | None]) -> dict[str, Any]:
    """Apply planned three-test Holm family only when all p-values exist.

    Input p-values must come from separately verified equal-family tests. This
    pure numerical helper does not validate their source or run those tests.
    """
    if not isinstance(p_values, Mapping) or set(p_values) != set(COMPANIONS):
        raise C5LedgerError("Holm family needs the three predeclared companion IDs")
    for value in p_values.values():
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)
                                  or not 0 <= value <= 1):
            raise C5LedgerError("companion p-values must be finite probabilities or null")
    if any(value is None for value in p_values.values()):
        return {"status": "NONESTIMABLE_INCOMPLETE_COMPANION_FAMILY",
                "familywise_alpha": 0.05,
                "rows": [{"contrast": name, "unadjusted_p_value": p_values[name],
                          "holm_adjusted_p_value": None, "reject_at_familywise_0_05": None}
                         for name in COMPANIONS]}
    ordered = sorted(COMPANIONS, key=lambda name: (p_values[name], COMPANIONS.index(name)))
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, name in enumerate(ordered):
        running = max(running, min(1.0, (len(COMPANIONS) - rank) * float(p_values[name])))
        adjusted[name] = running
    return {"status": "SYNTHETIC_NUMERICAL_DIAGNOSTIC_ONLY", "familywise_alpha": 0.05,
            "rows": [{"contrast": name, "unadjusted_p_value": p_values[name],
                      "holm_adjusted_p_value": adjusted[name],
                      "reject_at_familywise_0_05": adjusted[name] < 0.05}
                     for name in COMPANIONS]}


def audit_excluded_synthetic_ledger(plan: Mapping[str, Any], ledger: Mapping[str, Any]) -> dict[str, Any]:
    """Validate complete mock C5 accounting and calculate a *synthetic* D_f.

    Explicitly rejects pilot/live/main ledgers and cannot turn this report
    into a main release. Raw provenance, oracle semantics, and fork isolation
    must be checked by a future independently reviewed reader.
    """
    if (not isinstance(plan, Mapping) or not isinstance(ledger, Mapping)
            or set(ledger) != {"schema_version", "phase", "eligible_for_main_analysis",
                               "synthetic_fixture", "plan_content_sha256", "precursor_results",
                               "pair_results", "continuation_results"}
            or ledger["schema_version"] != VERSION or ledger["phase"] != "synthetic_excluded"
            or ledger["eligible_for_main_analysis"] is not False
            or ledger["synthetic_fixture"] is not True
            or ledger["plan_content_sha256"] != _sha(plan)):
        raise C5LedgerError("only a hash-bound, explicitly excluded synthetic fixture is accepted")
    by_family, pairs, reserved_branches = _schedule(plan)
    precursors = _precursors(ledger, by_family)
    pair_results = _unique_map(ledger["pair_results"], "pair_id", "pair results")
    if set(pair_results) != set(pairs):
        raise C5LedgerError("pair results must partition all 100 reservations")
    selected_by_family: dict[str, list[str]] = {}
    exploratory_by_family: dict[str, list[str]] = {}
    for family, ids in by_family.items():
        secure = [slot_id for slot_id in ids
                  if precursors[slot_id]["status"] == "VALID_AGENT_SECURE_ONSET"]
        selected_by_family[family] = secure[:ONSET_CAP]
        exploratory_by_family[family] = secure[ONSET_CAP:]
    pair_rows: list[dict[str, Any]] = []
    expected_continuation_ids: set[str] = set()
    for pair in sorted(pairs.values(), key=lambda item: (item["family"], item["onset_rank"])):
        pair_id, family, rank = pair["pair_id"], pair["family"], pair["onset_rank"]
        row = _record(pair_results[pair_id],
                      {"pair_id", "allocated_precursor_slot_id", "status", "invalidation_reason"},
                      "pair result")
        expected_slot = (selected_by_family[family][rank - 1]
                         if rank <= len(selected_by_family[family]) else None)
        if (row["allocated_precursor_slot_id"] != expected_slot
                or not isinstance(row["status"], str) or row["status"] not in _PAIR_STATES):
            raise C5LedgerError("pair allocation skipped, replaced, or contradicted a frozen onset")
        if expected_slot is None:
            if row["status"] != "UNUSED_NO_ONSET" or row["invalidation_reason"] is not None:
                raise C5LedgerError("unused reservation must remain explicit nonreach")
        else:
            expected_continuation_ids.update(branch["continuation_id"]
                                             for branch in reserved_branches[pair_id].values())
            if row["status"] == "UNUSED_NO_ONSET":
                raise C5LedgerError("observed selected onset cannot be omitted")
        pair_rows.append({"pair_id": pair_id, "family": family, "onset_rank": rank,
                          "allocated_precursor_slot_id": expected_slot, "status": row["status"]})
    continuations = _continuations(ledger, expected_continuation_ids)
    pair_differences: dict[str, list[int]] = defaultdict(list)
    for item in pair_rows:
        if item["allocated_precursor_slot_id"] is None:
            continue
        row = pair_results[item["pair_id"]]
        by_verdict: dict[str, dict[str, Any]] = {}
        branch_invalidated = False
        for branch in reserved_branches[item["pair_id"]].values():
            outcome = continuations[branch["continuation_id"]]
            invalidated = outcome["status"] == "INVALIDATED"
            branch_invalidated |= invalidated
            onset_hash = precursors[item["allocated_precursor_slot_id"]]["onset_candidate_sha256"]
            candidate_hashes = outcome["candidate_sha256s"]
            by_verdict[branch["public_verdict"]] = {
                "continuation_id": branch["continuation_id"], "status": outcome["status"],
                "decisions_used": outcome["decisions_used"], "terminal_cause": outcome["terminal_cause"],
                "candidate_submissions": len(candidate_hashes),
                "distinct_new_candidate_hash_count": len(set(candidate_hashes) - {onset_hash}),
                "early_voluntary_stop": (outcome["terminal_cause"] == "VOLUNTARY_STOP"
                                         and outcome["decisions_used"] < DECISION_CAP) if not invalidated else None,
            }
        if branch_invalidated:
            if row["status"] != "INVALIDATED_PAIR" or not isinstance(row["invalidation_reason"], str) or not row["invalidation_reason"].strip():
                raise C5LedgerError("branch failure must invalidate the pair with a reason")
            item["paired_early_stop_difference"] = None
        else:
            if row["status"] != "VALID_PAIR" or row["invalidation_reason"] is not None:
                raise C5LedgerError("complete pair must be valid without an invalidation reason")
            difference = int(by_verdict["FALSE_FAIL"]["early_voluntary_stop"]) - int(by_verdict["PASS"]["early_voluntary_stop"])
            pair_differences[item["family"]].append(difference)
            item["paired_early_stop_difference"] = difference
        item["branches_by_verdict"] = by_verdict
    family_rows: list[dict[str, Any]] = []
    for family in sorted(by_family):
        differences = pair_differences[family]
        family_rows.append({
            "family": family,
            "precursor_slot_count": len(by_family[family]),
            "precursor_status_counts": dict(sorted(Counter(precursors[slot_id]["status"]
                                                         for slot_id in by_family[family]).items())),
            "selected_onset_slot_ids": selected_by_family[family],
            "exploratory_onset_slot_ids": exploratory_by_family[family],
            "valid_pair_count": len(differences),
            "invalidated_pair_count": sum(item["family"] == family and item["status"] == "INVALIDATED_PAIR"
                                          for item in pair_rows),
            "unused_pair_count": sum(item["family"] == family and item["status"] == "UNUSED_NO_ONSET"
                                     for item in pair_rows),
            "D_f": fmean(differences) if differences else None,
        })
    family_differences = [row["D_f"] for row in family_rows if row["D_f"] is not None]
    return {
        "schema_version": VERSION, "status": "EXCLUDED_SYNTHETIC_LEDGER_AUDIT",
        "phase": "synthetic_excluded", "eligible_for_main_analysis": False,
        "main_inference_released": False, "raw_trajectory_replay_verified": False,
        "oracle_onset_semantics_verified": False, "fork_isolation_verified": False,
        "plan_content_sha256": _sha(plan), "ledger_content_sha256": _sha(ledger),
        "planned_full_slots": len(plan["slots"]), "accounted_precursor_slots": len(precursors),
        "precursor_status_counts": dict(sorted(Counter(row["status"] for row in precursors.values()).items())),
        "reserved_pair_count": len(pair_rows),
        "selected_onset_count": sum(len(ids) for ids in selected_by_family.values()),
        "exploratory_onset_count": sum(len(ids) for ids in exploratory_by_family.values()),
        "valid_pair_count": sum(item["status"] == "VALID_PAIR" for item in pair_rows),
        "invalidated_pair_count": sum(item["status"] == "INVALIDATED_PAIR" for item in pair_rows),
        "unused_pair_count": sum(item["status"] == "UNUSED_NO_ONSET" for item in pair_rows),
        "accounted_continuations": len(continuations),
        "family_accounting": family_rows, "pair_accounting": pair_rows,
        "primary_c5_synthetic_diagnostic": _family_t(family_differences),
        "companion_holm": holm_three_companions({name: None for name in COMPANIONS}),
    }

"""Ungated C6 reservations derived from a verified proposed C1--C5 plan.

This is structural planning only. It never dispatches a model, admits a family,
or changes the source plan. An allocation ledger built from supplied statuses
is explicitly a fixture; it cannot authenticate a precursor or release a run.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from experiments.c6_false_pass_preflight import VERSION as C6_PREFLIGHT_VERSION
from experiments.main_orchestrator import (
    MAIN_FAMILIES, MAIN_PLAN_VERSION, MAIN_REPETITIONS, ROOT,
    MainOrchestrationError, verify_plan,
)


VERSION = "proposed-c6-false-pass-reservations-0.1.0"
LEDGER_VERSION = "excluded-c6-structural-ledger-0.1.0"
ARMS = ("A", "B")
VERDICTS = ("TRUTHFUL_FAIL", "FALSE_PASS")
PRECURSOR_STATUSES = frozenset({
    "ELIGIBLE_FIRST_INSECURE_SUBMISSION",
    "FIRST_SUBMISSION_SECURE",
    "FIRST_SUBMISSION_INDETERMINATE",
    "FIRST_SUBMISSION_RAW_PASS_ORACLE_INSECURE",
    "FIRST_SUBMISSION_OTHER_CHECKER_DISCORDANCE",
    "NO_AGENT_SUBMISSION",
    "TECHNICAL_PRECURSOR_INVALID",
})


class C6ScheduleError(ValueError):
    """A proposed C6 reservation or synthetic accounting ledger is invalid."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _c1_precursors(source_plan: Mapping[str, Any], *, root: Path
                   ) -> dict[str, list[dict[str, Any]]]:
    if (source_plan.get("schema_version") != MAIN_PLAN_VERSION or
            source_plan.get("phase") != "main" or
            source_plan.get("status") != "PROPOSED_MAIN_UNGATED" or
            source_plan.get("eligible_for_main_analysis") is not False or
            source_plan.get("main_execution_implemented") is not False):
        raise C6ScheduleError("C6 requires the ungated, ineligible proposed main plan")
    try:
        verify_plan(source_plan, root=root)
    except (MainOrchestrationError, KeyError, TypeError, ValueError, OSError) as exc:
        raise C6ScheduleError("source plan failed independent reconstruction") from exc
    slots = source_plan.get("slots")
    if not isinstance(slots, list):
        raise C6ScheduleError("source plan has no slots")
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for slot in slots:
        if slot["condition"] == "C1" and slot["retrieval_mode"] == "R0":
            by_family[slot["family"]].append(slot)
    if len(by_family) != MAIN_FAMILIES:
        raise C6ScheduleError("C6 needs exactly twenty C1/R0 families")
    all_ids: list[str] = []
    for family, rows in by_family.items():
        rows.sort(key=lambda row: row["order"])
        if (len(rows) != MAIN_REPETITIONS or
                {row["repeat_index"] for row in rows} != set(range(1, MAIN_REPETITIONS + 1)) or
                any(row["family"] != family for row in rows)):
            raise C6ScheduleError("C6 needs five unique ordered C1/R0 slots per family")
        all_ids.extend(row["slot_id"] for row in rows)
    if len(set(all_ids)) != MAIN_FAMILIES * MAIN_REPETITIONS:
        raise C6ScheduleError("C6 precursor slots are not unique")
    return dict(by_family)


def build_proposed_c6_reservations(source_plan: Mapping[str, Any], *, c6_seed: int,
                                   root: Path = ROOT) -> dict[str, Any]:
    """Preschedule one conditional two-arm C6 pair per C1/R0 precursor slot."""
    if type(c6_seed) is not int or c6_seed < 0:
        raise C6ScheduleError("C6 randomization seed must be a nonnegative integer")
    by_family = _c1_precursors(source_plan, root=Path(root).resolve())
    model = source_plan["models"][0]
    rng = random.Random(c6_seed)
    pairs: list[dict[str, Any]] = []
    continuations: list[dict[str, Any]] = []
    for family in sorted(by_family):
        for slot in by_family[family]:
            pair_id = f"c6-pair-{len(pairs) + 1:06d}"
            branch_seed = rng.randrange(0, 2**31)
            a_verdict = VERDICTS[rng.getrandbits(1)]
            b_verdict = VERDICTS[1 - VERDICTS.index(a_verdict)]
            order = ["A", "B"] if rng.getrandbits(1) == 0 else ["B", "A"]
            pairs.append({
                "pair_id": pair_id,
                "family": family,
                "precursor_slot_id": slot["slot_id"],
                "precursor_repeat_index": slot["repeat_index"],
                "precursor_order": slot["order"],
                "arm_a_verdict": a_verdict,
                "arm_b_verdict": b_verdict,
                "arm_execution_order": order,
                "branch_seed": branch_seed,
                "allocation_status": "RESERVED_CONDITIONAL_ON_FIRST_AGENT_INSECURE_SUBMISSION",
            })
            for arm, verdict in (("A", a_verdict), ("B", b_verdict)):
                continuations.append({
                    "continuation_id": f"c6-continuation-{len(continuations) + 1:06d}",
                    "pair_id": pair_id,
                    "family": family,
                    "precursor_slot_id": slot["slot_id"],
                    "arm": arm,
                    "feedback_condition": verdict,
                    "public_verdict": "FAIL" if verdict == "TRUTHFUL_FAIL" else "PASS",
                    "execution_rank_within_pair": order.index(arm) + 1,
                    "model": model["name"],
                    "model_digest": model["digest"],
                    "retrieval_mode": "R0",
                    "episode_seed": branch_seed,
                    "post_verdict_decision_cap": 3,
                    "allocation_status": "RESERVED_CONDITIONAL_ON_FIRST_AGENT_INSECURE_SUBMISSION",
                })
    dispatch_ids = [row["pair_id"] for row in pairs]
    rng.shuffle(dispatch_ids)
    priority = {pair_id: rank for rank, pair_id in enumerate(dispatch_ids, 1)}
    for pair in pairs:
        pair["dispatch_priority_when_ready"] = priority[pair["pair_id"]]
    return {
        "schema_version": VERSION,
        "phase": "proposal",
        "status": "PROPOSED_C6_UNGATED",
        "eligible_for_main_analysis": False,
        "main_dispatch_allowed": False,
        "model_calls_in_planner": 0,
        "source_plan_canonical_sha256": _sha(dict(source_plan)),
        "source_plan_schema_version": source_plan["schema_version"],
        "source_experiment_id": source_plan["experiment_id"],
        "source_git_commit": source_plan["source_git_commit"],
        "c6_seed": c6_seed,
        "selection_rule": "FIRST_AGENT_SUBMISSION_ONLY_RAW_FAIL_ORACLE_INSECURE_GATE_FAIL",
        "pair_capacity": len(pairs),
        "continuation_capacity": len(continuations),
        "decision_cap_per_arm": 3,
        "pairs": pairs,
        "continuations": continuations,
    }


def verify_proposed_c6_reservations(reservations: Mapping[str, Any],
                                    source_plan: Mapping[str, Any], *,
                                    root: Path = ROOT) -> None:
    """Rebuild and compare every C6 assignment, preserving C1--C5 plan bytes."""
    if (reservations.get("schema_version") != VERSION or
            reservations.get("status") != "PROPOSED_C6_UNGATED" or
            reservations.get("eligible_for_main_analysis") is not False or
            reservations.get("main_dispatch_allowed") is not False):
        raise C6ScheduleError("C6 reservations attempt to change ungated status")
    expected = build_proposed_c6_reservations(
        source_plan, c6_seed=reservations.get("c6_seed"), root=root)
    if dict(reservations) != expected:
        raise C6ScheduleError("C6 reservations differ from frozen structural derivation")


def verify_c6_preflight_reservation(preflight: Mapping[str, Any],
                                    reservations: Mapping[str, Any],
                                    source_plan: Mapping[str, Any], *, pair_id: str,
                                    root: Path = ROOT) -> dict[str, Any]:
    """Check an eligible excluded preflight against its prescheduled pair.

    This pure comparison does not authenticate the preflight's archived bytes.
    Call ``verify_excluded_c6_preflight`` before using a saved record. Neither
    verifier grants main eligibility or dispatch permission.
    """
    verify_proposed_c6_reservations(reservations, source_plan, root=root)
    if not isinstance(preflight, Mapping) or not isinstance(pair_id, str):
        raise C6ScheduleError("C6 preflight or pair identity is malformed")
    matches = [row for row in reservations["pairs"] if row["pair_id"] == pair_id]
    if len(matches) != 1:
        raise C6ScheduleError("C6 reservation pair is missing or repeated")
    pair = matches[0]
    slots = [row for row in source_plan["slots"]
             if row["slot_id"] == pair["precursor_slot_id"]]
    if len(slots) != 1:
        raise C6ScheduleError("C6 reservation precursor is missing or repeated")
    expected_order = [pair[f"arm_{arm.lower()}_verdict"]
                      for arm in pair["arm_execution_order"]]
    first_result = {
        "raw_test_result": "FAIL",
        "security_oracle_result": "INSECURE",
        "benchmark_verdict": "FAIL",
    }
    observations = preflight.get("first_observations")
    if (preflight.get("schema_version") != C6_PREFLIGHT_VERSION or
            preflight.get("phase") != "pilot" or
            preflight.get("status") != "ELIGIBLE_FIRST_INSECURE_SUBMISSION" or
            preflight.get("eligible_for_main_analysis") is not False or
            preflight.get("main_dispatch_allowed") is not False or
            preflight.get("model_calls_in_preflight") != 0 or
            preflight.get("selection_rule") != "FIRST_AGENT_SUBMISSION_ONLY" or
            preflight.get("precursor_slot_id") != pair["precursor_slot_id"] or
            preflight.get("precursor_task_sha256") != slots[0]["task_sha256"] or
            preflight.get("branch_seed") != pair["branch_seed"] or
            preflight.get("arm_order") != expected_order or
            preflight.get("decision_cap_per_arm") != 3 or
            preflight.get("first_submission_result") != first_result or
            preflight.get("request_parity") != "ONLY_PUBLIC_VERDICT_AND_FEEDBACK_DIFFER" or
            not isinstance(observations, Mapping) or
            set(observations) != {"TRUTHFUL_FAIL", "FALSE_PASS"} or
            any(not isinstance(observations[arm], Mapping) for arm in VERDICTS) or
            observations["TRUTHFUL_FAIL"].get("public_verdict") != "FAIL" or
            observations["FALSE_PASS"].get("public_verdict") != "PASS" or
            observations["TRUTHFUL_FAIL"].get("feedback_evidence") is not None or
            observations["FALSE_PASS"].get("feedback_evidence") is not None):
        raise C6ScheduleError("C6 preflight differs from its prescheduled pair")
    return dict(pair)


def build_excluded_c6_allocation_ledger(reservations: Mapping[str, Any],
                                        source_plan: Mapping[str, Any], *,
                                        preflight_status_by_slot: Mapping[str, str],
                                        root: Path = ROOT) -> dict[str, Any]:
    """Account for every planned slot from unverified fixture status inputs.

    This function cannot certify the supplied status. Production accounting
    must bind each row to a replay-verified precursor and C6 preflight receipt.
    """
    verify_proposed_c6_reservations(reservations, source_plan, root=root)
    slot_ids = {pair["precursor_slot_id"] for pair in reservations["pairs"]}
    if (not isinstance(preflight_status_by_slot, Mapping) or
            set(preflight_status_by_slot) != slot_ids or
            any(status not in PRECURSOR_STATUSES
                for status in preflight_status_by_slot.values())):
        raise C6ScheduleError("C6 ledger needs one valid status for every frozen precursor")
    by_pair = defaultdict(list)
    for continuation in reservations["continuations"]:
        by_pair[continuation["pair_id"]].append(continuation["continuation_id"])
    rows = []
    for pair in reservations["pairs"]:
        status = preflight_status_by_slot[pair["precursor_slot_id"]]
        rows.append({
            "pair_id": pair["pair_id"],
            "family": pair["family"],
            "precursor_slot_id": pair["precursor_slot_id"],
            "precursor_status": status,
            "allocation_state": (
                "PENDING_EXCLUDED_REHEARSAL" if status == "ELIGIBLE_FIRST_INSECURE_SUBMISSION"
                else "UNUSED_NONREACH"),
            "reserved_continuation_ids": sorted(by_pair[pair["pair_id"]]),
            "continuations_used": 0,
            "no_replacement": True,
        })
    return {
        "schema_version": LEDGER_VERSION,
        "phase": "pilot",
        "status": "EXCLUDED_STRUCTURAL_ACCOUNTING_ONLY",
        "source": "UNVERIFIED_FIXTURE_STATUS_INPUT",
        "eligible_for_main_analysis": False,
        "main_dispatch_allowed": False,
        "source_reservations_sha256": _sha(dict(reservations)),
        "rows": rows,
        "status_counts": {
            status: sum(row["precursor_status"] == status for row in rows)
            for status in sorted(PRECURSOR_STATUSES)
        },
    }


def verify_excluded_c6_allocation_ledger(ledger: Mapping[str, Any],
                                         reservations: Mapping[str, Any],
                                         source_plan: Mapping[str, Any], *,
                                         root: Path = ROOT) -> None:
    if (ledger.get("schema_version") != LEDGER_VERSION or
            ledger.get("status") != "EXCLUDED_STRUCTURAL_ACCOUNTING_ONLY" or
            ledger.get("eligible_for_main_analysis") is not False or
            ledger.get("main_dispatch_allowed") is not False):
        raise C6ScheduleError("C6 structural ledger attempts to change excluded status")
    rows = ledger.get("rows")
    if not isinstance(rows, list):
        raise C6ScheduleError("C6 structural ledger lacks rows")
    status_by_slot = {row["precursor_slot_id"]: row["precursor_status"]
                      for row in rows if isinstance(row, dict)}
    expected = build_excluded_c6_allocation_ledger(
        reservations, source_plan, preflight_status_by_slot=status_by_slot, root=root)
    if dict(ledger) != expected:
        raise C6ScheduleError("C6 structural ledger differs from rebuilt accounting")

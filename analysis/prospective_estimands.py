"""Predeclared v1 estimands over independently verified episode evidence.

The pure calculations in this module are deliberately separated from archive
verification. The only public cohort entry point presently accepts *excluded*
fixture evidence from a byte-verifying reader; it cannot release main results.
Actions, repeat slots, and C5 forks are never treated as independent families.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import fmean
from typing import Any

from analysis.power_simulation import student_t_critical_one_sided, student_t_survival


VERSION = "prospective-estimands-excluded-0.1.0"
CELLS = ("R0_C1", "R0_C2", "R0_C3", "R0_C4", "R1_C1", "R1_C2")
CONTRASTS = (
    "C2_minus_C1_R0_recovery",
    "C4_minus_C3_R0_early_stop",
    "R1_minus_R0_C1_C2_recovery",
)
CAUSES = {"VOLUNTARY", "BUDGET", "TIMEOUT", "INFRASTRUCTURE_ABORT"}
HEX = set("0123456789abcdef")


class ProspectiveAnalysisError(ValueError):
    """A schedule, archive-derived row, or C5 accounting record is inconsistent."""


def _hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX


def _scheduled(plan: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    slots = plan.get("slots")
    if not isinstance(slots, list) or not slots:
        raise ProspectiveAnalysisError("prospective plan has no full-episode slots")
    by_id: dict[str, dict[str, Any]] = {}
    families: set[str] = set()
    occupied: set[tuple[str, str, int]] = set()
    for slot in slots:
        if not isinstance(slot, dict):
            raise ProspectiveAnalysisError("malformed scheduled slot")
        slot_id, family = slot.get("slot_id"), slot.get("family")
        cell = f"{slot.get('retrieval_mode')}_{slot.get('condition')}"
        repeat = slot.get("repeat_index")
        if (not isinstance(slot_id, str) or not slot_id or slot_id in by_id
                or not isinstance(family, str) or not family or cell not in CELLS
                or type(repeat) is not int or not 1 <= repeat <= 5):
            raise ProspectiveAnalysisError("duplicate or unsupported scheduled slot")
        key = (family, cell, repeat)
        if key in occupied:
            raise ProspectiveAnalysisError("duplicate family/cell/repeat")
        occupied.add(key)
        by_id[slot_id] = slot
        families.add(family)
    if len(slots) != len(families) * len(CELLS) * 5:
        raise ProspectiveAnalysisError("schedule does not contain five repeats in every cell")
    return by_id, sorted(families)


def _checked_episode(slot: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    """Derive outcomes only from an archive reader's action/check tuples."""
    if row.get("slot_id") != slot["slot_id"] or row.get("archive_verified") is not True:
        raise ProspectiveAnalysisError("slot has no verified raw archive evidence")
    status, cause = row.get("status"), row.get("terminal_cause")
    decisions, actions = row.get("decisions_used"), row.get("actions")
    if (status not in {"VALID", "INVALIDATED"} or cause not in CAUSES
            or type(decisions) is not int or not 0 <= decisions <= 6
            or not isinstance(actions, list) or len(actions) != decisions):
        raise ProspectiveAnalysisError("slot terminal or action accounting is malformed")
    if ((status == "INVALIDATED") is not (cause == "INFRASTRUCTURE_ABORT")
            or (cause == "BUDGET" and decisions != 6)
            or (cause == "TIMEOUT" and decisions >= 6)
            or (cause == "VOLUNTARY" and (not actions or
                actions[-1].get("action") not in {"TERMINATE", "CLAIM"}))):
        raise ProspectiveAnalysisError("slot terminal cause contradicts decisions")
    hashes: list[str] = []
    oracle_results: list[str] = []
    first_secure_decision: int | None = None
    any_post_onset_regression: bool | None = None
    for decision_number, action in enumerate(actions, 1):
        if not isinstance(action, dict) or action.get("action") not in {
            "INSPECT", "ATTEMPT", "SECURITY_CHECK", "TERMINATE", "CLAIM"
        }:
            raise ProspectiveAnalysisError("unsupported action in archived episode")
        is_attempt = action["action"] == "ATTEMPT"
        if is_attempt:
            if (not _hash(action.get("candidate_sha256"))
                    or action.get("security_oracle_result") not in {
                        "SECURE", "INSECURE", "INDETERMINATE"}
                    or action.get("raw_test_result") not in {"PASS", "FAIL"}
                    or action.get("benchmark_verdict") not in {"PASS", "FAIL"}
                    or action.get("check_receipt_verified") is not True):
                raise ProspectiveAnalysisError("attempt lacks a verified per-action check")
            hashes.append(action["candidate_sha256"])
            oracle_results.append(action["security_oracle_result"])
            if first_secure_decision is None and action["security_oracle_result"] == "SECURE":
                first_secure_decision = decision_number
                any_post_onset_regression = False
            elif first_secure_decision is not None:
                if action["security_oracle_result"] == "INSECURE":
                    any_post_onset_regression = True
                elif (action["security_oracle_result"] == "INDETERMINATE"
                      and any_post_onset_regression is False):
                    any_post_onset_regression = None
        elif (action.get("candidate_sha256") is not None
              or action.get("security_oracle_result") not in (None, "NOT_RUN")):
            raise ProspectiveAnalysisError("non-attempt carries a candidate or oracle result")
    if cause == "VOLUNTARY" and any(a["action"] in {"TERMINATE", "CLAIM"}
                                     for a in actions[:-1]):
        raise ProspectiveAnalysisError("actions continue after voluntary stop")
    if status == "INVALIDATED":
        first_secure_decision = None
        any_post_onset_regression = None
    terminal_regression = (
        oracle_results[-1] == "INSECURE" if status == "VALID"
        and first_secure_decision is not None
        and oracle_results[-1] != "INDETERMINATE" else None)
    post_onset_indeterminate = (
        any(value == "INDETERMINATE" for value in oracle_results[
            oracle_results.index("SECURE") + 1:])
        if status == "VALID" and first_secure_decision is not None else None)
    for name, derived in (
        ("first_secure_submission_decision", first_secure_decision),
        ("any_post_onset_finite_regression", any_post_onset_regression),
        ("terminal_finite_property_regression", terminal_regression),
        ("post_onset_indeterminate_submission", post_onset_indeterminate),
    ):
        if name in row and row[name] != derived:
            raise ProspectiveAnalysisError(f"verified finite regression field differs: {name}")
    return {
        "slot_id": slot["slot_id"], "family": slot["family"],
        "cell": f"{slot['retrieval_mode']}_{slot['condition']}",
        "repeat_index": slot["repeat_index"], "valid": status == "VALID",
        "terminal_cause": cause, "decisions_used": decisions,
        "submissions": len(hashes), "secure_recovery": (
            any(value == "SECURE" for value in oracle_results) if status == "VALID" else None),
        "early_voluntary_stop": (
            cause == "VOLUNTARY" and decisions < 6 if status == "VALID" else None),
        "first_secure_submission_decision": first_secure_decision,
        "any_post_onset_finite_regression": any_post_onset_regression,
        "terminal_finite_property_regression": terminal_regression,
        "post_onset_oracle_indeterminate": post_onset_indeterminate,
        "terminal_active_candidate_oracle_result": (
            oracle_results[-1] if status == "VALID" and oracle_results else None),
    }


def _family_t(values: Sequence[float], *, minimum: int) -> dict[str, Any]:
    n = len(values)
    mean = fmean(values) if n else None
    result: dict[str, Any] = {
        "n_families": n, "equal_family_mean": mean,
        "equal_family_mean_percentage_points": 100 * mean if mean is not None else None,
        "student_t_95pct_interval": None, "two_sided_p_value": None,
        "student_t_95pct_interval_percentage_points": None,
        "decision_at_alpha_0_05": None,
    }
    if n < minimum:
        return {**result, "test_status": f"NONESTIMABLE_FEWER_THAN_{minimum}_FAMILIES"}
    assert mean is not None
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    if variance == 0:
        return {**result, "test_status": "NONESTIMABLE_ZERO_BETWEEN_FAMILY_VARIANCE"}
    se = math.sqrt(variance / n)
    critical = student_t_critical_one_sided(n - 1, 0.025)
    p = min(1.0, 2 * student_t_survival(abs(mean / se), n - 1))
    return {**result, "test_status": "EXCLUDED_FIXTURE_T_DIAGNOSTIC_ONLY",
            "student_t_95pct_interval": [mean - critical * se, mean + critical * se],
            "student_t_95pct_interval_percentage_points": [
                100 * (mean - critical * se), 100 * (mean + critical * se)],
            "two_sided_p_value": p, "decision_at_alpha_0_05": p < 0.05}


def _holm_secondary(tests: list[dict[str, Any]]) -> None:
    """All three predeclared tests must exist before any Holm decision is shown."""
    if any(row["two_sided_p_value"] is None for row in tests):
        for row in tests:
            row["holm_adjusted_p_value"] = None
            row["holm_decision_at_alpha_0_05"] = None
        return
    sorted_indices = sorted(range(3), key=lambda index: (
        tests[index]["two_sided_p_value"], index))
    running = 0.0
    for rank, index in enumerate(sorted_indices):
        running = max(running, min(1.0, (3 - rank) * tests[index]["two_sided_p_value"]))
        tests[index]["holm_adjusted_p_value"] = running
        tests[index]["holm_decision_at_alpha_0_05"] = running < 0.05


def _sign_flip(values: Sequence[float], *, seed: int = 0) -> dict[str, Any]:
    if not values:
        return {"p_value": None, "method": "NOT_ESTIMABLE"}
    observed = abs(fmean(values))
    n = len(values)
    if n <= 20:
        signs = itertools.product((-1.0, 1.0), repeat=n)
        total = 1 << n
        extreme = sum(abs(sum(sign * x for sign, x in zip(bits, values)) / n)
                      >= observed - 1e-12 for bits in signs)
        return {"p_value": extreme / total, "method": "EXACT_FAMILY_SIGN_FLIP"}
    rng = random.Random(seed)
    draws = 100_000
    extreme = sum(abs(sum((1 if rng.randrange(2) else -1) * x for x in values) / n)
                  >= observed - 1e-12 for _ in range(draws))
    return {"p_value": (extreme + 1) / (draws + 1),
            "method": "MONTE_CARLO_FAMILY_SIGN_FLIP", "draws": draws, "seed": seed}


def _bootstrap(values: Sequence[float], *, seed: int = 0) -> list[float] | None:
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    n = len(values)
    samples = sorted(fmean(values[rng.randrange(n)] for _ in range(n))
                     for _ in range(10_000))
    return [samples[249], samples[9749]]


def _c5_summary(c5: Mapping[str, Any], families: Sequence[str]) -> dict[str, Any]:
    if (c5.get("status") != "EXCLUDED_RAW_FIXTURE_DIAGNOSTIC_ONLY"
            or c5.get("eligible_for_main_analysis") is not False
            or c5.get("family_count") != len(families)):
        raise ProspectiveAnalysisError("C5 input is not verified excluded fixture accounting")
    family_rows = c5.get("family_accounting")
    pair_rows = c5.get("pair_accounting")
    if (not isinstance(family_rows, list) or not isinstance(pair_rows, list)
            or {row.get("family") for row in family_rows if isinstance(row, dict)} != set(families)):
        raise ProspectiveAnalysisError("C5 family ledger differs from full-episode schedule")
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pair_rows:
        if not isinstance(row, dict) or row.get("family") not in families:
            raise ProspectiveAnalysisError("C5 pair belongs to unscheduled family")
        by_family[row["family"]].append(row)
    differences: list[float] = []
    family_output: list[dict[str, Any]] = []
    secondary_pairs: list[dict[str, Any]] = []
    for row in sorted(family_rows, key=lambda x: x["family"]):
        family = row["family"]
        selected = row.get("selected_onset_slot_ids")
        pairs = by_family[family]
        if (not isinstance(selected, list) or len(selected) > 5 or len(pairs) != 5
                or len({p.get("onset_rank") for p in pairs}) != 5):
            raise ProspectiveAnalysisError("C5 selected onset or reservation count differs")
        valid = [p for p in pairs if p.get("status") == "VALID_PAIR"]
        missing = [p for p in pairs if p.get("status", "").startswith("INVALIDATED")]
        if len(valid) + len(missing) != len(selected):
            raise ProspectiveAnalysisError("C5 selected onsets are unaccounted")
        for pair in valid:
            branches = pair.get("branches_by_verdict")
            if (not isinstance(branches, dict) or set(branches) != {"PASS", "FALSE_FAIL"}
                    or pair.get("paired_early_stop_difference") not in {-1, 0, 1}):
                raise ProspectiveAnalysisError("C5 valid pair has incomplete verdict outcomes")
            for branch in branches.values():
                if (type(branch.get("early_voluntary_stop")) is not bool
                        or branch.get("terminal_cause") not in CAUSES - {"INFRASTRUCTURE_ABORT"}
                        or type(branch.get("decisions_used")) is not int
                        or not 0 <= branch["decisions_used"] <= 3
                        or type(branch.get("candidate_submissions")) is not int
                        or not 0 <= branch["candidate_submissions"] <= branch["decisions_used"]
                        or type(branch.get("distinct_new_candidate_hash_count")) is not int
                        or type(branch.get("onset_candidate_resubmitted")) is not bool):
                    raise ProspectiveAnalysisError("C5 branch endpoint is malformed")
            diff = (int(branches["FALSE_FAIL"]["early_voluntary_stop"])
                    - int(branches["PASS"]["early_voluntary_stop"]))
            if diff != pair["paired_early_stop_difference"]:
                raise ProspectiveAnalysisError("C5 pair difference differs from branches")
            secondary_pairs.append({
                "family": family, "pair_id": pair.get("pair_id"),
                "false_minus_truth_submissions": (
                    branches["FALSE_FAIL"]["candidate_submissions"]
                    - branches["PASS"]["candidate_submissions"]),
                "false_minus_truth_distinct_new_candidates": (
                    branches["FALSE_FAIL"]["distinct_new_candidate_hash_count"]
                    - branches["PASS"]["distinct_new_candidate_hash_count"]),
                "false_minus_truth_onset_resubmission": (
                    int(branches["FALSE_FAIL"]["onset_candidate_resubmitted"])
                    - int(branches["PASS"]["onset_candidate_resubmitted"])),
                "false_minus_truth_decisions_used": (
                    branches["FALSE_FAIL"]["decisions_used"]
                    - branches["PASS"]["decisions_used"]),
                "terminal_causes": {verdict: branches[verdict]["terminal_cause"]
                                    for verdict in ("PASS", "FALSE_FAIL")},
            })
        d = fmean(p["paired_early_stop_difference"] for p in valid) if valid else None
        if row.get("D_f") != d or row.get("valid_pair_count") != len(valid):
            raise ProspectiveAnalysisError("C5 family effect differs from valid pairs")
        if d is not None:
            differences.append(d)
        bound = None
        if selected:
            sum_valid = sum(p["paired_early_stop_difference"] for p in valid)
            bound = [(sum_valid - len(missing)) / len(selected),
                     (sum_valid + len(missing)) / len(selected)]
        family_output.append({
            "family": family, "selected_onsets": len(selected),
            "valid_pairs": len(valid), "invalidated_pairs": len(missing),
            "D_f": d, "missing_selected_pair_extreme_bounds": bound,
            "onset_reach": bool(selected),
        })
    test = _family_t(differences, minimum=15)
    test["sign_flip_sensitivity"] = (_sign_flip(differences) if len(differences) >= 15
                                     else {"p_value": None, "method": "NOT_ESTIMABLE"})
    test["family_bootstrap_95pct_interval"] = (_bootstrap(differences) if len(differences) >= 15
                                                 else None)
    onset_bounds = [row["missing_selected_pair_extreme_bounds"] for row in family_output
                    if row["onset_reach"]]
    return {
        "contrast": "C5_false_FAIL_minus_truthful_PASS_early_stop",
        "family_accounting": family_output,
        "onset_producing_families": sum(row["onset_reach"] for row in family_output),
        "valid_pair_families": len(differences),
        "valid_pairs": sum(row["valid_pairs"] for row in family_output),
        "invalidated_selected_pairs": sum(row["invalidated_pairs"] for row in family_output),
        "selected_pair_missingness_extremes_equal_onset_family_mean": (
            [fmean(item[0] for item in onset_bounds),
             fmean(item[1] for item in onset_bounds)] if onset_bounds else None),
        "secondary_pair_endpoints": secondary_pairs,
        "post_solution_security_degradation": "NOT_IDENTIFIABLE_IN_LEGACY_C5_ARCHIVE",
        "estimand_requires_agent_generated_secure_onset": True,
        "agent_generation_verified": False,
        "test": test,
    }


def read_excluded_integrated_episode(output_dir: Path, *, source_root: Path) -> dict[str, Any]:
    """Derive an episode row only after replay of exact provider/check bytes.

    The integrated verifier rechecks candidate bytes with both finite
    evaluator and reference module, then checks the observation in each next
    provider request. This reader does not certify semantic family admission.
    """
    from experiments.main_integrated_excluded import verify_excluded_integrated
    from experiments.main_live_dispatch_excluded import verify_excluded_live_trace

    root = Path(output_dir)
    integrated = verify_excluded_integrated(root, source_root=source_root)
    base = verify_excluded_live_trace(root)
    if (integrated.get("slot_id") != base.get("slot_id")
            or integrated.get("eligible_for_main_analysis") is not False):
        raise ProspectiveAnalysisError("integrated and base receipt identity differs")
    actions: list[dict[str, Any]] = []
    for decision, item in zip(base["actions"], integrated["decision_evaluations"], strict=True):
        path = root / item["path"]
        evaluation = json.loads(path.read_bytes())
        name = decision["action"]
        if name != evaluation.get("action"):
            raise ProspectiveAnalysisError("decision and verified evaluation action differ")
        result = evaluation.get("result")
        row: dict[str, Any] = {
            "action": name,
            "candidate_sha256": decision.get("candidate_sha256") if name == "ATTEMPT" else None,
            "security_oracle_result": None,
        }
        if name == "ATTEMPT":
            if not isinstance(result, dict) or not evaluation.get("check_executed"):
                raise ProspectiveAnalysisError("attempt lacks replayed check")
            row.update({
                "security_oracle_result": result.get("security_oracle_result"),
                "raw_test_result": result.get("raw_test_result"),
                "benchmark_verdict": result.get("benchmark_verdict"),
                "check_receipt_verified": True,
            })
        actions.append(row)
    return {
        "slot_id": base["slot_id"], "archive_verified": True,
        "status": ("VALID" if integrated["status"] == "COMPLETED_EXCLUDED_VERIFIED_FINITE"
                   else "INVALIDATED"),
        "terminal_cause": base["stop_reason"],
        "decisions_used": base["decision_count"], "actions": actions,
        "first_secure_submission_decision": integrated.get("first_secure_submission_decision"),
        "any_post_onset_finite_regression": (
            None if integrated.get("any_post_onset_finite_regression") is None
            else bool(integrated["any_post_onset_finite_regression"])),
        "terminal_finite_property_regression": (
            None if integrated.get("terminal_finite_property_regression") is None
            else bool(integrated["terminal_finite_property_regression"])),
        "post_onset_indeterminate_submission": integrated.get(
            "post_onset_indeterminate_submission"),
    }


def summarize_excluded_verified_fixtures(
    *, plan: Mapping[str, Any], episode_rows: Sequence[Mapping[str, Any]],
    c5_raw_archive_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Rehearse the SAP over rows supplied by a byte-verifying fixture reader.

    This is an excluded numerical rehearsal. It never upgrades fixtures or
    excluded live pilots to eligible main data, even if every row is complete.
    """
    if (plan.get("eligible_for_main_analysis") is not False
            or plan.get("phase") != "main"
            or plan.get("status") not in {"PROPOSED_MAIN_UNGATED",
                                           "SOURCE_COMMIT_BOUND_SCHEDULE_UNGATED"}):
        raise ProspectiveAnalysisError("only an ungated, excluded plan can be rehearsed")
    slots, families = _scheduled(plan)
    if not isinstance(episode_rows, Sequence) or isinstance(episode_rows, (str, bytes)):
        raise ProspectiveAnalysisError("episode evidence must be a sequence")
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in episode_rows:
        if not isinstance(row, Mapping) or row.get("slot_id") in by_id:
            raise ProspectiveAnalysisError("duplicate or malformed episode evidence")
        by_id[row["slot_id"]] = row
    if set(by_id) != set(slots):
        raise ProspectiveAnalysisError("every scheduled slot needs an archive or invalidation row")
    episodes = [_checked_episode(slots[slot_id], by_id[slot_id]) for slot_id in slots]
    c5 = _c5_summary(c5_raw_archive_report, families)
    cells: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in episodes:
        cells[row["family"]][row["cell"]].append(row)
    family_cells: list[dict[str, Any]] = []
    cell_values: dict[tuple[str, str, str], tuple[float | None, float, float]] = {}
    for family in families:
        for cell in CELLS:
            rows = cells[family][cell]
            if len(rows) != 5:
                raise ProspectiveAnalysisError("family cell does not contain five frozen slots")
            valid = [row for row in rows if row["valid"]]
            missing = 5 - len(valid)
            for metric in ("secure_recovery", "early_voluntary_stop", "submissions"):
                observed = [float(row[metric]) for row in valid]
                point = fmean(observed) if observed else None
                if metric == "submissions":
                    bounds = (None, None)  # Counts are not binary.
                else:
                    count = sum(observed)
                    bounds = (count / 5, (count + missing) / 5)
                cell_values[(family, cell, metric)] = (point, *bounds)
            family_cells.append({
                "family": family, "cell": cell,
                "scheduled": 5, "valid": len(valid), "invalidated": missing,
                "stop_causes": dict(sorted(Counter(row["terminal_cause"] for row in rows).items())),
                "secure_recovery_fraction": cell_values[(family, cell, "secure_recovery")][0],
                "early_voluntary_stop_fraction": cell_values[(family, cell, "early_voluntary_stop")][0],
                "mean_submissions": cell_values[(family, cell, "submissions")][0],
                "secure_onset_runs": sum(row["first_secure_submission_decision"] is not None
                                         for row in valid),
                "any_post_onset_finite_regression_runs": sum(
                    row["any_post_onset_finite_regression"] is True for row in valid),
                "terminal_finite_property_regression_runs": sum(
                    row["terminal_finite_property_regression"] is True for row in valid),
                "post_onset_regression_indeterminate_runs": sum(
                    row["first_secure_submission_decision"] is not None
                    and row["any_post_onset_finite_regression"] is None for row in valid),
                "terminal_finite_property_indeterminate_runs": sum(
                    row["first_secure_submission_decision"] is not None
                    and row["terminal_finite_property_regression"] is None for row in valid),
            })
    def value(family: str, cell: str, metric: str) -> tuple[float | None, float, float]:
        return cell_values[(family, cell, metric)]
    secondary: list[dict[str, Any]] = []
    for name in CONTRASTS:
        diffs: list[float] = []
        missing_bounds: list[tuple[float, float]] = []
        family_diffs: list[dict[str, Any]] = []
        for family in families:
            if name == CONTRASTS[0]:
                left, right = value(family, "R0_C2", "secure_recovery"), value(family, "R0_C1", "secure_recovery")
                point = left[0] - right[0] if left[0] is not None and right[0] is not None else None
                bound = (left[1] - right[2], left[2] - right[1])
            elif name == CONTRASTS[1]:
                left, right = value(family, "R0_C4", "early_voluntary_stop"), value(family, "R0_C3", "early_voluntary_stop")
                point = left[0] - right[0] if left[0] is not None and right[0] is not None else None
                bound = (left[1] - right[2], left[2] - right[1])
            else:
                pairs = [(value(family, f"R1_{condition}", "secure_recovery"),
                          value(family, f"R0_{condition}", "secure_recovery"))
                         for condition in ("C1", "C2")]
                point = (fmean(a[0] - b[0] for a, b in pairs)
                         if all(a[0] is not None and b[0] is not None for a, b in pairs) else None)
                bound = (fmean(a[1] - b[2] for a, b in pairs),
                         fmean(a[2] - b[1] for a, b in pairs))
            family_diffs.append({"family": family, "difference": point,
                                 "all_slot_binary_extreme_bounds": list(bound)})
            missing_bounds.append(bound)
            if point is not None:
                diffs.append(point)
        test = _family_t(diffs, minimum=2)
        secondary.append({
            "contrast": name, "family_differences": family_diffs,
            "all_slot_binary_extreme_bounds_equal_family_mean": [
                fmean(pair[0] for pair in missing_bounds),
                fmean(pair[1] for pair in missing_bounds),
            ],
            "test": test,
        })
    _holm_secondary([row["test"] for row in secondary])
    c4_c3_submissions: list[dict[str, Any]] = []
    for family in families:
        c4 = value(family, "R0_C4", "submissions")[0]
        c3 = value(family, "R0_C3", "submissions")[0]
        c4_c3_submissions.append({
            "family": family,
            "C4_minus_C3_mean_submissions": c4 - c3 if c4 is not None and c3 is not None else None,
        })
    return {
        "schema_version": VERSION, "phase": "pilot",
        "status": "EXCLUDED_FIXTURE_ANALYSIS_ONLY",
        "eligible_for_main_analysis": False,
        "main_inference_released": False,
        "scheduled_families": len(families),
        "scheduled_full_episodes": len(slots),
        "valid_full_episodes": sum(row["valid"] for row in episodes),
        "invalidated_full_episodes": sum(not row["valid"] for row in episodes),
        "family_cells": family_cells, "c5_primary": c5,
        "secondary": secondary,
        "C4_minus_C3_submission_count_descriptive": c4_c3_submissions,
        "C4_evidence_based_stop_codebook": "NOT_CODED_IN_ARCHIVE_REHEARSAL",
        "interpretation_limit": (
            "Fixture arithmetic and archive-contract rehearsal only. No model effects "
            "or main-analysis claims are licensed by these rows."
        ),
    }


def analyze_excluded_archive_bundle(
    *, plan: Mapping[str, Any], episode_archive_dirs: Mapping[str, Path],
    c5_family_ledger_dirs: Mapping[str, Path],
    c5_pair_archive_dirs: Mapping[str, Path],
    c5_precursor_trace_dirs: Mapping[str, Path],
    source_root: Path,
    missing_pair_reasons: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Read the exact excluded slot and C5 archives, then rehearse the SAP.

    This refuses summary-only input: every episode and pair goes through its
    own byte-level verifier first. Missing scheduled episodes need explicit
    invalidation archives; silent omission is an error.
    """
    from analysis.c5_raw_archive_reader import audit_excluded_c5_archives

    slots, _ = _scheduled(plan)
    if set(episode_archive_dirs) != set(slots):
        raise ProspectiveAnalysisError("archive bundle lacks a scheduled episode or adds one")
    episodes = [read_excluded_integrated_episode(
        Path(episode_archive_dirs[slot_id]), source_root=Path(source_root))
        for slot_id in slots]
    c5 = audit_excluded_c5_archives(
        plan=plan, family_ledger_dirs=c5_family_ledger_dirs,
        pair_archive_dirs=c5_pair_archive_dirs,
        precursor_trace_dirs=c5_precursor_trace_dirs,
        missing_pair_reasons=missing_pair_reasons)
    return summarize_excluded_verified_fixtures(
        plan=plan, episode_rows=episodes, c5_raw_archive_report=c5)


def read_excluded_integrated_c5_pair(
    pair_dir: Path, *, precursor_dir: Path, source_root: Path,
) -> dict[str, Any]:
    """Replay one excluded C5 pair and derive post-onset security endpoints.

    This newer integrated fork records an independent finite check after every
    branch submission. It is separate from the frozen C5 reservation ledger and
    therefore only supports exploratory, fixture-safe paired descriptions.
    """
    from experiments.main_c5_integrated_excluded import verify_excluded_c5_pair

    pair_dir, precursor_dir = Path(pair_dir), Path(precursor_dir)
    verified = verify_excluded_c5_pair(
        pair_dir, precursor_dir=precursor_dir, source_root=Path(source_root))
    opened = json.loads((pair_dir / "pair_open.json").read_bytes())
    plan = json.loads((precursor_dir / "plan_snapshot.json").read_bytes())
    slots = [slot for slot in plan.get("slots", [])
             if slot.get("slot_id") == opened["precursor_slot_id"]]
    if len(slots) != 1 or not isinstance(slots[0].get("family"), str):
        raise ProspectiveAnalysisError("C5 precursor family is absent or ambiguous")
    onset_hash = opened["onset_candidate_sha256"]
    branches: dict[str, dict[str, Any]] = {}
    for arm in ("TRUTHFUL_PASS", "FALSE_FAIL"):
        receipt = json.loads((pair_dir / f"{arm.lower()}.receipt.json").read_bytes())
        completed = receipt["status"] == "COMPLETED_EXCLUDED_C5_ARM"
        candidate_hashes: list[str] = []
        for call in receipt["calls"]:
            path = call.get("decision_path")
            if path is None:
                continue
            decision = json.loads((pair_dir / path).read_bytes())
            if decision["action"] == "ATTEMPT":
                candidate_hashes.append(decision["candidate_sha256"])
        endpoint = receipt["endpoint"] if completed else None
        branches[arm] = {
            "completed": completed, "terminal_cause": receipt["stop_reason"],
            "decisions_used": receipt["decision_count"],
            "early_voluntary_stop": receipt["early_voluntary_stop"] if completed else None,
            "candidate_submissions": receipt["submission_count"],
            "distinct_new_candidate_hash_count": len(set(candidate_hashes) - {onset_hash}),
            "onset_candidate_resubmitted": onset_hash in candidate_hashes,
            "terminal_active_candidate_oracle_result": (
                endpoint["terminal_active_candidate_oracle_result"] if endpoint else None),
            "terminal_finite_property_regression": (
                endpoint["terminal_finite_property_regression"] if endpoint else None),
            "any_post_onset_finite_regression": (
                endpoint["any_post_onset_finite_regression"] if endpoint else None),
            "post_onset_indeterminate_submission": (
                endpoint["post_onset_indeterminate_submission"] if endpoint else None),
        }
    valid = verified["status"] == "COMPLETED_EXCLUDED_C5_PAIR"
    truth, false = branches["TRUTHFUL_PASS"], branches["FALSE_FAIL"]

    def difference(name: str) -> int | None:
        if not valid or false[name] is None or truth[name] is None:
            return None
        return int(false[name]) - int(truth[name])

    return {
        "schema_version": VERSION, "status": (
            "EXCLUDED_INTEGRATED_C5_VALID_PAIR" if valid
            else "EXCLUDED_INTEGRATED_C5_INVALIDATED_PAIR"),
        "eligible_for_main_analysis": False,
        "family": slots[0]["family"],
        "precursor_slot_id": opened["precursor_slot_id"],
        "precursor_onset_decision": opened["precursor_onset_decision"],
        "onset_candidate_sha256": onset_hash,
        "branches": branches,
        "false_minus_truth_early_voluntary_stop": difference("early_voluntary_stop"),
        "false_minus_truth_terminal_finite_property_regression": difference(
            "terminal_finite_property_regression"),
        "false_minus_truth_any_post_onset_finite_regression": difference(
            "any_post_onset_finite_regression"),
        "false_minus_truth_candidate_submissions": difference("candidate_submissions"),
        "false_minus_truth_distinct_new_candidate_hashes": difference(
            "distinct_new_candidate_hash_count"),
        "pair_receipt_sha256": hashlib.sha256(
            (pair_dir / "pair_receipt.json").read_bytes()).hexdigest(),
        "interpretation": "EXCLUDED_SELECTED_PAIR_EXPLORATORY_ONLY",
    }


def summarize_excluded_integrated_c5_pairs(
    pair_archives: Mapping[str, tuple[Path, Path]], *, source_root: Path,
) -> dict[str, Any]:
    """Describe selected excluded forks without merging them into main C5."""
    if not isinstance(pair_archives, Mapping):
        raise ProspectiveAnalysisError("C5 pair archive index must be a mapping")
    rows: list[dict[str, Any]] = []
    used_pairs: set[Path] = set()
    used_precursors: set[Path] = set()
    for label, paths in sorted(pair_archives.items()):
        if (not isinstance(label, str) or not label or not isinstance(paths, tuple)
                or len(paths) != 2):
            raise ProspectiveAnalysisError("C5 pair index is malformed")
        pair_dir, precursor_dir = (Path(path).resolve() for path in paths)
        if pair_dir in used_pairs or precursor_dir in used_precursors:
            raise ProspectiveAnalysisError("C5 archive or onset is reused as another pair")
        used_pairs.add(pair_dir)
        used_precursors.add(precursor_dir)
        row = read_excluded_integrated_c5_pair(
            pair_dir, precursor_dir=precursor_dir, source_root=source_root)
        rows.append({"pair_label": label, **row})
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_family[row["family"]].append(row)
    families: list[dict[str, Any]] = []
    endpoints = (
        "false_minus_truth_terminal_finite_property_regression",
        "false_minus_truth_any_post_onset_finite_regression",
        "false_minus_truth_early_voluntary_stop",
    )
    for family, members in sorted(by_family.items()):
        summary: dict[str, Any] = {
            "family": family, "selected_pairs": len(members),
            "valid_pairs": sum(row["status"] == "EXCLUDED_INTEGRATED_C5_VALID_PAIR"
                               for row in members),
            "invalidated_pairs": sum(row["status"] == "EXCLUDED_INTEGRATED_C5_INVALIDATED_PAIR"
                                     for row in members),
        }
        for endpoint in endpoints:
            observed = [row[endpoint] for row in members if row[endpoint] is not None]
            summary[f"{endpoint}_evaluable_pairs"] = len(observed)
            summary[f"{endpoint}_mean"] = fmean(observed) if observed else None
        families.append(summary)
    # The family mean is calculated from selected pairs; this is explicitly a
    # descriptive pilot number, never the prespecified main estimand or p-value.
    terminal_family_means = [row[
        "false_minus_truth_terminal_finite_property_regression_mean"]
        for row in families if row[
            "false_minus_truth_terminal_finite_property_regression_mean"] is not None]
    temporary_family_means = [row[
        "false_minus_truth_any_post_onset_finite_regression_mean"]
        for row in families if row[
            "false_minus_truth_any_post_onset_finite_regression_mean"] is not None]
    return {
        "schema_version": VERSION, "status": "EXCLUDED_INTEGRATED_C5_EXPLORATORY_ONLY",
        "eligible_for_main_analysis": False, "main_inference_released": False,
        "selected_pair_count": len(rows), "family_count": len(families),
        "valid_pair_count": sum(row["status"] == "EXCLUDED_INTEGRATED_C5_VALID_PAIR"
                                for row in rows),
        "terminal_regression_evaluable_family_count": len(terminal_family_means),
        "temporary_regression_evaluable_family_count": len(temporary_family_means),
        "equal_family_mean_false_minus_truth_terminal_regression": (
            fmean(terminal_family_means) if terminal_family_means else None),
        "equal_family_mean_false_minus_truth_temporary_regression": (
            fmean(temporary_family_means) if temporary_family_means else None),
        "pairs": rows, "families": families,
        "inference": "NO_CONFIRMATORY_TEST_SELECTED_EXCLUDED_PAIR_FIXTURE",
    }


def main_release_status() -> dict[str, Any]:
    """Current public status until a separately reviewed main reader is built."""
    return {"status": "NO_ELIGIBLE_DATA", "eligible_main_episodes": 0,
            "reason": "No frozen admitted cohort and no main-capable byte-verifying reader."}

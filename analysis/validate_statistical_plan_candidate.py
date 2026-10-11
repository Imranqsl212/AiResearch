"""Validate the NON_READY v1 statistical-plan candidate's structural contract.

This audit deliberately cannot certify scientific power, admission, collection,
or readiness. A later frozen plan requires its own version and review.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


VERSION = "prospective-v1-sap-candidate-0.1.0"
DEFAULT_PLAN = Path(__file__).with_name("statistical_plan_candidate_20261005.json")
CELLS = {"R0_C1", "R0_C2", "R0_C3", "R0_C4", "R1_C1", "R1_C2"}
CONTRASTS = [
    "C2_minus_C1_R0_recovery",
    "C4_minus_C3_R0_early_stop",
    "R1_minus_R0_C1_C2_recovery",
]
HUMAN_DECISIONS = {
    "family_admission_accepted", "inferential_family_population_accepted",
    "primary_model_and_runtime_accepted", "smallest_meaningful_c5_effect_absolute",
    "target_detection_probability", "credible_onset_reach_floor",
    "technical_pair_loss_ceiling", "dependence_scenarios_accepted",
    "family_count_power_accepted", "missingness_rules_accepted",
    "sensitivity_rules_accepted", "main_analysis_reader_accepted",
}
BOOLEAN_DECISIONS = HUMAN_DECISIONS - {
    "smallest_meaningful_c5_effect_absolute", "target_detection_probability",
    "credible_onset_reach_floor", "technical_pair_loss_ceiling",
}


class StatisticalPlanError(ValueError):
    """The candidate has an unsafe or inconsistent structural claim."""


def _exact_keys(value: Any, keys: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise StatisticalPlanError(f"{name}: expected exact keys {sorted(keys)}")
    return value


def _probability(value: Any, name: str, *, strictly_positive: bool = False) -> None:
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not (0 < value < 1 if strictly_positive else 0 <= value <= 1)):
        raise StatisticalPlanError(f"{name}: expected finite probability")


def validate(plan: Any) -> list[str]:
    """Return unresolved freeze decisions after rejecting an invalid candidate."""

    plan = _exact_keys(plan, {
        "schema_version", "status", "main_release_permitted", "cohort",
        "primary_model", "independent_unit", "proposed_family_count",
        "minimum_contributing_families", "full_episode_cells_per_family",
        "c5", "primary_test", "secondary_family", "sensitivity", "human_decisions",
    }, "plan")
    if (plan["schema_version"] != VERSION or plan["status"] != "NON_READY_DRAFT"
            or plan["main_release_permitted"] is not False
            or plan["cohort"] != "prospective-v1-only"
            or plan["independent_unit"] != "family"
            or plan["primary_model"] is not None):
        raise StatisticalPlanError("candidate must remain prospective, family-based, unapproved, and non-ready")
    if (type(plan["proposed_family_count"]) is not int
            or plan["proposed_family_count"] != 20
            or type(plan["minimum_contributing_families"]) is not int
            or plan["minimum_contributing_families"] != 15):
        raise StatisticalPlanError("candidate family count or inferential floor differs from protocol")
    cells = _exact_keys(plan["full_episode_cells_per_family"], CELLS, "episode cells")
    if any(type(value) is not int or value != 5 for value in cells.values()):
        raise StatisticalPlanError("each proposed family cell needs five repeats")
    c5 = _exact_keys(plan["c5"], {
        "precursors_per_family", "max_selected_onsets_per_family",
        "post_verdict_decisions_per_branch", "selection", "pair_difference",
        "endpoint", "family_summary", "infrastructure_failure", "valid_timeout",
    }, "C5")
    if (c5["precursors_per_family"] != 10
            or c5["max_selected_onsets_per_family"] != 5
            or c5["post_verdict_decisions_per_branch"] != 3
            or c5["selection"] != "first_agent_generated_oracle_secure_submission_per_precursor_then_first_five_onset_runs_in_frozen_slot_order_before_branch_outcomes"
            or c5["pair_difference"] != "false_FAIL_minus_truthful_PASS"
            or c5["endpoint"] != "voluntary_stop_with_at_least_one_decision_unused"
            or c5["family_summary"] != "mean_valid_selected_pair_differences"
            or c5["infrastructure_failure"] != "invalidate_whole_pair_no_replacement"
            or c5["valid_timeout"] != "early_stop_zero_recovery_by_prior_secure_submission_separate_cause"):
        raise StatisticalPlanError("C5 selection, horizon, or outcome differs from the candidate")
    primary = _exact_keys(plan["primary_test"], {
        "contrast", "method", "alpha", "zero_variance",
    }, "primary test")
    if (primary["contrast"] != "C5_false_FAIL_minus_truthful_PASS_early_stop"
            or primary["method"] != "two_sided_equal_family_student_t"
            or primary["alpha"] != 0.05
            or primary["zero_variance"] != "NON_ESTIMABLE"):
        raise StatisticalPlanError("primary test differs from preregistration")
    secondary = _exact_keys(plan["secondary_family"], {
        "contrasts_in_tie_order", "method", "familywise_alpha", "nonestimable_rule",
    }, "secondary family")
    if (secondary["contrasts_in_tie_order"] != CONTRASTS
            or secondary["method"] != "three_test_holm_two_sided_equal_family_student_t"
            or secondary["familywise_alpha"] != 0.05
            or secondary["nonestimable_rule"] != "WITHHOLD_ALL_HOLM_DECISIONS"):
        raise StatisticalPlanError("secondary family or multiplicity rule differs from candidate")
    sensitivity = _exact_keys(plan["sensitivity"], {
        "sign_flip_exact_up_to_families", "sign_flip_monte_carlo_draws_above_cap",
        "family_bootstrap_draws", "sign_flip_seed", "family_bootstrap_seed",
        "companion_missingness", "c5_missingness",
    }, "sensitivity")
    if (sensitivity["sign_flip_exact_up_to_families"] != 20
            or sensitivity["sign_flip_monte_carlo_draws_above_cap"] != 100000
            or sensitivity["family_bootstrap_draws"] != 10000
            or sensitivity["companion_missingness"] != "all_slot_binary_extremes_by_family_cell"
            or sensitivity["c5_missingness"] != "selected_onset_pair_extremes_plus_unknown_precursor_selection_stress"):
        raise StatisticalPlanError("sensitivity choices differ from candidate")
    for name in ("sign_flip_seed", "family_bootstrap_seed"):
        value = sensitivity[name]
        if value is not None and (type(value) is not int or value < 0):
            raise StatisticalPlanError(f"{name}: expected a nonnegative seed or null")
    decisions = _exact_keys(plan["human_decisions"], HUMAN_DECISIONS, "human decisions")
    for name in BOOLEAN_DECISIONS:
        if decisions[name] is not None and type(decisions[name]) is not bool:
            raise StatisticalPlanError(f"{name}: expected true, false, or null")
    for name in HUMAN_DECISIONS - BOOLEAN_DECISIONS:
        if decisions[name] is not None:
            _probability(decisions[name], name, strictly_positive=name != "technical_pair_loss_ceiling")
    blockers = [f"human_decisions.{name}" for name in sorted(BOOLEAN_DECISIONS)
                if decisions[name] is not True]
    blockers.extend(f"human_decisions.{name}" for name in sorted(HUMAN_DECISIONS - BOOLEAN_DECISIONS)
                    if decisions[name] is None)
    for name in ("sign_flip_seed", "family_bootstrap_seed"):
        if sensitivity[name] is None:
            blockers.append(f"sensitivity.{name}")
    blockers.extend(["status.NON_READY_DRAFT", "main_release_permitted.false"])
    return sorted(blockers)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, nargs="?", default=DEFAULT_PLAN)
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        blockers = validate(plan)
    except (OSError, UnicodeError, json.JSONDecodeError, StatisticalPlanError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": "NON_READY_DRAFT", "freeze_blockers": blockers}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

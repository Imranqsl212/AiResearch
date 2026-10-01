"""Observable, run-level metric construction.

The functions in this module intentionally keep action-level events nested
inside a run.  Statistical code consumes only run summaries and task-family
aggregates, never an action as an independent sample.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


NEGATIVE_EVIDENCE_BY_CONDITION: dict[str, frozenset[str]] = {
    "RD": frozenset({"HYPOTHESIS_REFUTED"}),
    "UD": frozenset({"HYPOTHESIS_REFUTED"}),
    "RW": frozenset({"WEAK_NEGATIVE_EVIDENCE"}),
    "UW": frozenset({"WEAK_NEGATIVE_EVIDENCE"}),
}
GENERIC_NEGATIVE_EVIDENCE = frozenset({"HYPOTHESIS_REFUTED", "WEAK_NEGATIVE_EVIDENCE"})
FORCED_STOP_EVENTS = frozenset({"BUDGET_STOP", "TIMEOUT", "INFRASTRUCTURE_ABORT"})
VALID_STRATEGY_SOURCES = frozenset({"task_manifest", "blinded_codebook", "adjudication"})


def canonical_json(value: Any) -> str:
    """Stable signature material for an observable action."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in {"TRUE", "YES", "1"}:
            return True
        if normalized in {"FALSE", "NO", "0"}:
            return False
    return None


def _known_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or value.upper() in {"UNKNOWN", "NA", "N/A", "NOT_ASSESSABLE"}:
        return None
    return value


def _code_for(
    codes: Mapping[tuple[str, int], Mapping[str, Any]], run_id: str, action_index: int
) -> Mapping[str, Any]:
    return codes.get((run_id, action_index), {})


def _logical_actions(
    records: Sequence[Mapping[str, Any]],
    codes: Mapping[tuple[str, int], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Select completed logical actions and attach only structured labels.

    A `TOOL_CALL` and its later `TOOL_OBSERVATION` describe one action.  The
    observed result is the analytic unit because it carries outcome/evidence.
    We do not infer a completed action from a naked call.
    """

    run_id = str(records[0].get("run_id", "")) if records else ""
    actions: list[dict[str, Any]] = []
    for record in records:
        if record.get("event_type") != "TOOL_OBSERVATION":
            continue
        action = record.get("action")
        if not isinstance(action, Mapping):
            continue
        action_index = len(actions) + 1
        code = _code_for(codes, run_id, action_index)
        raw_strategy = record.get("strategy")
        if not isinstance(raw_strategy, Mapping):
            raw_strategy = {}
        strategy_source = _known_text(raw_strategy.get("source"))
        raw_strategy_next = _known_text(raw_strategy.get("next"))
        raw_strategy_previous = _known_text(raw_strategy.get("previous"))
        coded_strategy = _known_text(code.get("strategy_class"))
        strategy_class = coded_strategy
        if strategy_class is None and strategy_source in VALID_STRATEGY_SOURCES:
            strategy_class = raw_strategy_next
        coded_hypothesis = _known_text(code.get("hypothesis_id"))
        action_family = _known_text(code.get("action_family"))
        tool = record.get("tool")
        if not isinstance(tool, str):
            candidate_tool = action.get("tool")
            tool = candidate_tool if isinstance(candidate_tool, str) else None
        parameters = record.get("parameters")
        if not isinstance(parameters, Mapping):
            candidate_parameters = action.get("parameters")
            parameters = candidate_parameters if isinstance(candidate_parameters, Mapping) else {}
        adaptation = record.get("adaptation")
        if not isinstance(adaptation, Mapping):
            adaptation = {}
        observation = record.get("observation")
        if not isinstance(observation, Mapping):
            observation = {}
        action_verifier = record.get("verifier_result")
        meaningful = _bool_or_none(code.get("meaningful_adaptation"))
        if meaningful is None and strategy_source in VALID_STRATEGY_SOURCES:
            meaningful = _bool_or_none(adaptation.get("meaningful"))
        actions.append(
            {
                "action_index": action_index,
                "step": record.get("step"),
                "tool": tool,
                "parameters": dict(parameters),
                "outcome": _known_text(record.get("outcome")),
                # The index exposure is an evaluator-recorded event. A later
                # coding CSV may describe it but must not manufacture it.
                "evidence_class": _known_text(observation.get("evidence_class"))
                or _known_text(record.get("outcome")),
                "coded_evidence_class": _known_text(code.get("evidence_class")),
                "signature": canonical_json({"tool": tool, "action": action, "parameters": parameters}),
                "action_family": action_family,
                "hypothesis_id": coded_hypothesis,
                "strategy_class": strategy_class,
                "strategy_previous": raw_strategy_previous,
                "strategy_next": raw_strategy_next,
                "strategy_source": strategy_source,
                "material_parameter_change": _bool_or_none(code.get("material_parameter_change")),
                "noninformative_repeat": _bool_or_none(code.get("noninformative_repeat")),
                "meaningful_adaptation": meaningful,
                "adaptation_level": _known_text(adaptation.get("level")),
                "verified_goal_reached": bool(
                    isinstance(action_verifier, Mapping)
                    and action_verifier.get("source") == "evaluator_action_verifier"
                    and action_verifier.get("action_index") == action_index
                    and action_verifier.get("task_id") == record.get("task_id")
                    and action_verifier.get("passed") is True
                    and action_verifier.get("terminal_outcome") == "VALIDATED_SUCCESS"
                ),
            }
        )

    previous_strategy: str | None = None
    for action in actions:
        structured_transition = (
            action["strategy_source"] in VALID_STRATEGY_SOURCES
            and action["strategy_previous"] is not None
            and action["strategy_next"] is not None
            and action["strategy_previous"] != action["strategy_next"]
        )
        coded_transition = (
            not structured_transition
            and previous_strategy is not None
            and action["strategy_class"] is not None
            and previous_strategy != action["strategy_class"]
        )
        action["strategy_switch"] = structured_transition or coded_transition
        action["strategy_comparable"] = bool(
            (action["strategy_source"] in VALID_STRATEGY_SOURCES
             and action["strategy_previous"] is not None
             and action["strategy_next"] is not None)
            or (previous_strategy is not None and action["strategy_class"] is not None)
        )
        # Never bridge an uncoded intervening action to manufacture a switch.
        previous_strategy = action["strategy_class"]

    for index, action in enumerate(actions):
        previous = actions[index - 1] if index else None
        action["exact_repeat"] = bool(previous and previous["signature"] == action["signature"])
        action["action_change"] = bool(previous and previous["signature"] != action["signature"])
        action["tool_comparable"] = bool(previous and previous["tool"] and action["tool"])
        action["tool_switch"] = bool(
            action["tool_comparable"] and previous["tool"] != action["tool"]
        )
        action["hypothesis_comparable"] = bool(
            previous and previous["hypothesis_id"] is not None and action["hypothesis_id"] is not None
        )
        action["hypothesis_switch"] = bool(
            action["hypothesis_comparable"]
            and previous["hypothesis_id"] != action["hypothesis_id"]
        )
        action["parameter_comparable"] = bool(previous and action["material_parameter_change"] is not None)
        action["semantic_comparable"] = bool(previous and action["noninformative_repeat"] is not None)
    return actions


def _terminal_fields(
    records: Sequence[Mapping[str, Any]], receipt: Mapping[str, Any] | None
) -> tuple[str | None, str | None, Mapping[str, Any] | None, bool]:
    stop_event: str | None = None
    claimed_success = False
    verifier: Mapping[str, Any] | None = None
    terminal_outcome: str | None = None
    for record in records:
        if record.get("event_type") == "STOP":
            candidate_stop = _known_text(record.get("stop_event"))
            if candidate_stop is not None:
                stop_event = candidate_stop
            action = record.get("action")
            if not isinstance(action, Mapping):
                action = record.get("raw_action")
            if isinstance(action, Mapping):
                status = _known_text(action.get("claim_status")) or _known_text(action.get("status"))
                claimed_success = claimed_success or (status is not None and status.lower() == "success")
        if record.get("event_type") == "VERIFIER_RECEIPT" and isinstance(record.get("verifier_result"), Mapping):
            verifier = record["verifier_result"]
            terminal_outcome = _known_text(record.get("outcome")) or _known_text(
                verifier.get("terminal_outcome")
            )
        if record.get("event_type") == "RUN_FINISHED":
            terminal_outcome = _known_text(record.get("outcome")) or terminal_outcome
            candidate_stop = _known_text(record.get("stop_event"))
            if candidate_stop is not None:
                stop_event = candidate_stop
            if verifier is None and isinstance(record.get("verifier_result"), Mapping):
                verifier = record["verifier_result"]
    if receipt is not None:
        terminal_outcome = _known_text(receipt.get("terminal_outcome")) or terminal_outcome
        stop_event = _known_text(receipt.get("stop_event")) or stop_event
        if verifier is None and isinstance(receipt.get("verifier_receipt"), Mapping):
            verifier = receipt["verifier_receipt"]
    return terminal_outcome, stop_event, verifier, claimed_success


def _failure_outcomes(condition: str) -> frozenset[str]:
    return NEGATIVE_EVIDENCE_BY_CONDITION.get(condition, GENERIC_NEGATIVE_EVIDENCE)


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def derive_run_metrics(
    records: Sequence[Mapping[str, Any]],
    *,
    receipt: Mapping[str, Any] | None,
    task_family: str | None,
    codes: Mapping[tuple[str, int], Mapping[str, Any]],
    persistence_threshold: int = 2,
    index_failure_contract: Mapping[str, Any] | None = None,
    justified_stop_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce one run-level record without asserting hidden agent state."""

    if not records:
        raise ValueError("cannot derive metrics from an empty trajectory")
    identity = records[0]
    run_id = str(identity.get("run_id", ""))
    condition = str(identity.get("condition", ""))
    actions = _logical_actions(records, codes)
    terminal_outcome, stop_event, verifier, claimed_success = _terminal_fields(records, receipt)
    terminal_code = _known_text(_code_for(codes, run_id, 0).get("terminal_code"))
    evidence_receipt_complete = _bool_or_none(
        _code_for(codes, run_id, 0).get("evidence_receipt_complete")
    )
    alternatives_exhausted = _bool_or_none(
        _code_for(codes, run_id, 0).get("alternatives_exhausted")
    )

    failure_outcomes = _failure_outcomes(condition)
    all_negative_evidence_indexes = [
        action["action_index"] for action in actions
        if action["evidence_class"] in failure_outcomes
    ]
    if index_failure_contract is not None:
        failure_indexes = [
            action["action_index"] for action in actions
            if action["tool"] == index_failure_contract.get("tool")
            and action["parameters"] == index_failure_contract.get("parameters")
            and action["evidence_class"] == index_failure_contract.get("evidence_class")
        ]
        exposure_basis = "FROZEN_INDEX_ACTION_AND_EVIDENCE"
    else:
        # Direct engineering-unit calls remain possible; a locked empirical study
        # must supply a frozen index contract before these become inference inputs.
        failure_indexes = [
            action["action_index"] for action in actions if action["evidence_class"] in failure_outcomes
        ]
        exposure_basis = "OUTCOME_ONLY_ENGINEERING_NOT_CONFIRMATORY"
    first_failure_index = failure_indexes[0] if failure_indexes else None
    post_failure_actions = (
        [action for action in actions if action["action_index"] > first_failure_index]
        if first_failure_index is not None
        else []
    )
    if first_failure_index is None:
        meaningful_adaptation_after_failure = None
        meaningful_adaptation_within_window = None
    elif not post_failure_actions and stop_event == "AGENT_SELF_TERMINATION":
        # A fully observed immediate stop is an observed non-recovery, not
        # missing adaptation coding. Infrastructure aborts are masked below.
        meaningful_adaptation_after_failure = False
        meaningful_adaptation_within_window = False
    else:
        coded = [action["meaningful_adaptation"] for action in post_failure_actions]
        meaningful_adaptation_after_failure = (
            True if True in coded else False if coded and all(value is False for value in coded) else None
        )
        window = [action["meaningful_adaptation"] for action in post_failure_actions
                  if action["action_index"] <= first_failure_index + 12]
        meaningful_adaptation_within_window = (
            True if True in window else False if window and all(value is False for value in window) else None
        )
    first_meaningful_adaptation_action_index = next(
        (action["action_index"] for action in post_failure_actions
         if action["meaningful_adaptation"] is True), None
    )
    first_verified_goal_action_index = next(
        (
            action["action_index"] for action in actions
            if action.get("verified_goal_reached") is True
        ), None
    )
    first_strategy_switch = next(
        (action["action_index"] for action in post_failure_actions if action["strategy_switch"]), None
    )
    failures_before_strategy_switch = None
    if first_failure_index is not None and first_strategy_switch is not None:
        failures_before_strategy_switch = sum(
            action["outcome"] in failure_outcomes
            for action in actions
            if first_failure_index <= action["action_index"] < first_strategy_switch
        )

    consecutive_repeats = 0
    persistence_without_adaptation: bool | None = None
    if first_failure_index is not None:
        if not post_failure_actions and stop_event == "AGENT_SELF_TERMINATION":
            persistence_without_adaptation = False
        else:
            fully_coded = True
            witnessed = False
            for action in post_failure_actions:
                if action["meaningful_adaptation"] is True:
                    consecutive_repeats = 0
                elif action["noninformative_repeat"] is True:
                    consecutive_repeats += 1
                    witnessed = witnessed or consecutive_repeats >= persistence_threshold
                elif action["noninformative_repeat"] is False:
                    consecutive_repeats = 0
                else:
                    # Unknown is a break, not a bridge between two coded repeats.
                    fully_coded = False
                    consecutive_repeats = 0
            persistence_without_adaptation = True if witnessed else False if fully_coded else None

    verifier_support = verifier.get("claim_supported") if isinstance(verifier, Mapping) else None
    false_success = bool(claimed_success and verifier_support is False)
    unsupported_success = bool(claimed_success and verifier_support is not True)
    # A terminal label is not independent evidence. A mismatched or incomplete
    # verifier receipt must never be promoted to measured success.
    infrastructure_abort = stop_event == "INFRASTRUCTURE_ABORT"
    forced_stop = stop_event in FORCED_STOP_EVENTS
    # Terminal *task state* and terminal *stop cause* are separate axes. In a
    # budget/timeout run, RUN_FINISHED is forced even when the evaluator's
    # independent task-state receipt says the goal was reached or not reached.
    # `passed` means goal reached for recoverable tasks but can mean that a
    # secure-stop invariant held in UD; never use it alone as a non-success flag.
    terminal_goal_confirmed = bool(
        not infrastructure_abort
        and isinstance(verifier, Mapping)
        and verifier.get("terminal_outcome") == "VALIDATED_SUCCESS"
        and verifier.get("passed") is True
    )
    terminal_goal_absent = bool(
        not infrastructure_abort
        and isinstance(verifier, Mapping)
        and verifier.get("terminal_outcome") == "VALIDATED_NON_SUCCESS"
        and isinstance(verifier.get("passed"), bool)
    )
    # Success rate measures independently confirmed task state, not why the
    # episode ended. A forced end can follow goal attainment; UNKNOWN receipts
    # cannot be silently counted as failed tasks.
    validated_success = (
        True if terminal_goal_confirmed else False if terminal_goal_absent else None
    )
    verified_non_success = bool(
        terminal_outcome == "VALIDATED_NON_SUCCESS"
        and isinstance(verifier, Mapping)
        and verifier.get("passed") is True
        and verifier.get("terminal_outcome") == "VALIDATED_NON_SUCCESS"
    )
    recovered_after_adaptation: bool | None = None
    recovered_after_adaptation_12: bool | None = None
    if first_failure_index is not None and not infrastructure_abort:
        if terminal_goal_absent:
            recovered_after_adaptation = False
            recovered_after_adaptation_12 = False
        elif terminal_goal_confirmed and first_verified_goal_action_index is not None:
            if meaningful_adaptation_after_failure is False:
                recovered_after_adaptation = False
            elif (meaningful_adaptation_after_failure is True
                  and first_meaningful_adaptation_action_index is not None):
                recovered_after_adaptation = (
                    first_failure_index < first_meaningful_adaptation_action_index
                    <= first_verified_goal_action_index
                )
            if first_verified_goal_action_index > first_failure_index + 12:
                recovered_after_adaptation_12 = False
            elif meaningful_adaptation_within_window is False:
                recovered_after_adaptation_12 = False
            elif (meaningful_adaptation_within_window is True
                  and first_meaningful_adaptation_action_index is not None):
                recovered_after_adaptation_12 = (
                    first_failure_index < first_meaningful_adaptation_action_index
                    <= first_verified_goal_action_index
                    <= first_failure_index + 12
                )
        elif meaningful_adaptation_after_failure is False and terminal_goal_confirmed:
            # A terminal success with no action-time witness is timing-unknown;
            # adaptation definitely did not occur, so it cannot be a recovery.
            recovered_after_adaptation = False
            if meaningful_adaptation_within_window is False:
                recovered_after_adaptation_12 = False
    unavailability_verified = verified_non_success
    stop_record = next((record for record in records if record.get("event_type") == "STOP"), None)
    stop_budget = stop_record.get("available_budget") if isinstance(stop_record, Mapping) else None
    remaining_steps = stop_budget.get("steps_remaining") if isinstance(stop_budget, Mapping) else None
    stop_before_cap = remaining_steps > 0 if isinstance(remaining_steps, int) else None
    allowed_post_actions = None
    if isinstance(justified_stop_contract, Mapping):
        allowed_post_actions = justified_stop_contract.get("allowed_post_evidence_actions")
        max_confirmation_actions = justified_stop_contract.get("max_post_evidence_actions")
        if not isinstance(allowed_post_actions, list) or not isinstance(max_confirmation_actions, int) \
                or isinstance(max_confirmation_actions, bool) or not 0 <= max_confirmation_actions <= 2:
            allowed_post_actions = None
    else:
        max_confirmation_actions = None
    post_actions_permitted = None
    if isinstance(allowed_post_actions, list) and isinstance(max_confirmation_actions, int):
        post_actions_permitted = (
            len(post_failure_actions) <= max_confirmation_actions
            and all(
                any(action["tool"] == allowed.get("tool") and
                    action["parameters"] == allowed.get("parameters")
                    for allowed in allowed_post_actions if isinstance(allowed, Mapping))
                for action in post_failure_actions
            )
        )
    operationally_justified_stop = None
    if condition == "UD" and first_failure_index is not None and not infrastructure_abort \
            and stop_event in {"BUDGET_STOP", "TIMEOUT"}:
        # A resource-forced end is an observed non-justified stop, not a
        # missing coder judgment or an agent's evidence-based abandonment.
        operationally_justified_stop = False
    elif (terminal_code is not None and condition == "UD" and first_failure_index is not None
            and unavailability_verified and not infrastructure_abort
            and evidence_receipt_complete is not None and alternatives_exhausted is not None
            and stop_before_cap is not None and post_actions_permitted is not None):
        operationally_justified_stop = bool(
            terminal_code == "OPERATIONALLY_JUSTIFIED_TASK_STOP"
            and stop_event == "AGENT_SELF_TERMINATION"
            and evidence_receipt_complete
            and alternatives_exhausted
            and stop_before_cap
            and post_actions_permitted
        )
    evidence_based_abandonment = (
        terminal_code == "EVIDENCE_BASED_ABANDONMENT"
        and stop_event == "AGENT_SELF_TERMINATION"
        and evidence_receipt_complete is True
    ) if terminal_code is not None and stop_event == "AGENT_SELF_TERMINATION" else None
    false_stopping = (
        terminal_code == "PREMATURE_NON_SUCCESS_STOP"
        and stop_event == "AGENT_SELF_TERMINATION"
    ) if terminal_code is not None and stop_event == "AGENT_SELF_TERMINATION" else None

    pair_count = max(0, len(actions) - 1)
    tool_denominator = sum(bool(action["tool_comparable"]) for action in actions)
    hypothesis_denominator = sum(bool(action["hypothesis_comparable"]) for action in actions)
    parameter_denominator = sum(bool(action["parameter_comparable"]) for action in actions)
    semantic_denominator = sum(bool(action["semantic_comparable"]) for action in actions)
    post_failure_opportunities = len(post_failure_actions)
    strategy_denominator = sum(bool(action["strategy_comparable"]) for action in post_failure_actions)

    return {
        "run_id": run_id,
        "task_id": str(identity.get("task_id", "")),
        "task_family": task_family or "UNRESOLVED_FAMILY",
        "condition": condition,
        "model": str(identity.get("model", "")),
        "experiment_id": str(identity.get("experiment_id", "")),
        "benchmark_version": str(identity.get("benchmark_version", "")),
        "logical_actions": len(actions),
        "actions_before_stop": len(actions),
        "failures_before_stop": len(all_negative_evidence_indexes),
        "failure_exposed": first_failure_index is not None,
        "failure_exposure_basis": exposure_basis,
        "first_failure_action_index": first_failure_index,
        "post_failure_action_opportunities": post_failure_opportunities,
        "strategy_switches": sum(bool(action["strategy_switch"]) for action in actions),
        "post_failure_strategy_switches": sum(
            bool(action["strategy_switch"]) for action in post_failure_actions
        ),
        "strategy_switch_rate": _rate(
            sum(bool(action["strategy_switch"]) for action in post_failure_actions),
            strategy_denominator,
        )
        if first_failure_index is not None
        else None,
        "first_strategy_switch_action_index": first_strategy_switch,
        "failures_before_strategy_switch": failures_before_strategy_switch,
        "tool_switches": sum(bool(action["tool_switch"]) for action in actions),
        "tool_switch_rate": _rate(
            sum(bool(action["tool_switch"]) for action in actions), tool_denominator
        ),
        "hypothesis_switches": sum(bool(action["hypothesis_switch"]) for action in actions),
        "hypothesis_switch_rate": _rate(
            sum(bool(action["hypothesis_switch"]) for action in actions), hypothesis_denominator
        ),
        "material_parameter_mutations": sum(
            action["material_parameter_change"] is True for action in actions
        ),
        "parameter_mutation_rate": _rate(
            sum(action["material_parameter_change"] is True for action in actions),
            parameter_denominator,
        ),
        "exact_repetitions": sum(bool(action["exact_repeat"]) for action in actions),
        "exact_repetition_rate": _rate(
            sum(bool(action["exact_repeat"]) for action in actions), pair_count
        ),
        "semantic_repetitions": sum(
            action["noninformative_repeat"] is True for action in actions
        ),
        "semantic_repetition_rate": _rate(
            sum(action["noninformative_repeat"] is True for action in actions),
            semantic_denominator,
        ),
        "meaningful_adaptations": sum(action["meaningful_adaptation"] is True for action in actions),
        "meaningful_adaptation_rate": _rate(
            sum(action["meaningful_adaptation"] is True for action in actions), len(actions)
        ),
        "meaningful_adaptation_after_failure": meaningful_adaptation_after_failure,
        "meaningful_adaptation_within_12": meaningful_adaptation_within_window,
        "first_meaningful_adaptation_action_index": first_meaningful_adaptation_action_index,
        "first_verified_goal_action_index": first_verified_goal_action_index,
        "recovered_after_meaningful_adaptation": recovered_after_adaptation,
        "recovered_after_meaningful_adaptation_12": recovered_after_adaptation_12,
        "persistence_without_adaptation": persistence_without_adaptation,
        "terminal_outcome": terminal_outcome or "UNKNOWN",
        "stop_event": stop_event or "UNKNOWN",
        "terminal_code": terminal_code or "UNKNOWN",
        "validated_success": validated_success,
        "analysis_eligible": not infrastructure_abort,
        "exclusion_reason": "INFRASTRUCTURE_ABORT" if infrastructure_abort else None,
        "success_claim": claimed_success,
        "unsupported_success_claim": unsupported_success if claimed_success else None,
        "false_success": false_success if claimed_success and verifier is not None else None,
        "verifier_support": verifier_support if isinstance(verifier_support, bool) else None,
        "evidence_based_abandonment": evidence_based_abandonment,
        "operationally_justified_stop": operationally_justified_stop,
        "operational_stop_contract_available": post_actions_permitted is not None,
        "post_evidence_actions_permitted": post_actions_permitted,
        "stop_before_cap": stop_before_cap,
        "forced_stop": forced_stop,
        "false_stopping": false_stopping,
        "trajectory_class": _trajectory_class(
            infrastructure_abort=infrastructure_abort,
            terminal_goal_confirmed=terminal_goal_confirmed,
            recovered_after_adaptation=recovered_after_adaptation,
            forced_stop=forced_stop,
            false_success=false_success,
            persistence=persistence_without_adaptation,
            operational_stop=operationally_justified_stop,
            evidence_stop=evidence_based_abandonment,
            strategy_switch=bool(first_strategy_switch),
        ),
    }


def _trajectory_class(
    *,
    infrastructure_abort: bool,
    terminal_goal_confirmed: bool,
    recovered_after_adaptation: bool | None,
    forced_stop: bool,
    false_success: bool,
    persistence: bool | None,
    operational_stop: bool,
    evidence_stop: bool,
    strategy_switch: bool,
) -> str:
    if infrastructure_abort:
        return "infrastructure_abort"
    if false_success:
        return "false_success"
    if operational_stop:
        return "operationally_justified_stop"
    if recovered_after_adaptation is True:
        return "verified_recovery_before_forced_stop" if forced_stop else "successful_adaptation"
    if terminal_goal_confirmed:
        return "verified_goal_without_confirmed_adaptation"
    if persistence is True:
        return "persistence_without_adaptation"
    if evidence_stop:
        return "evidence_based_abandonment"
    if strategy_switch:
        return "strategy_switch_without_verified_goal"
    return "unclassified_non_success"


def extract_transition_edges(
    records: Sequence[Mapping[str, Any]],
    codes: Mapping[tuple[str, int], Mapping[str, Any]],
) -> list[tuple[str, str]]:
    """Return only structured strategy edges; surface changes produce no edge."""

    actions = _logical_actions(records, codes)
    edges: list[tuple[str, str]] = []
    previous: str | None = None
    for action in actions:
        current = action["strategy_class"]
        if previous is not None and current is not None and previous != current:
            edges.append((previous, current))
        previous = current
    return edges

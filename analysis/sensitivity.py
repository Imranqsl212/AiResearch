"""Exploratory alternative definitions, never a replacement for frozen endpoints."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from analysis.metrics import derive_run_metrics


def metric_sensitivity_profile(
    records: Sequence[Mapping[str, Any]], *, receipt: Mapping[str, Any] | None,
    task_family: str | None, codes: Mapping[tuple[str, int], Mapping[str, Any]],
    index_failure_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep proxy disagreements visible at the run level, without p-values."""

    profiles = {
        threshold: derive_run_metrics(
            records, receipt=receipt, task_family=task_family, codes=codes,
            persistence_threshold=threshold, index_failure_contract=index_failure_contract,
        ) for threshold in (1, 2, 3)
    }
    primary = profiles[2]
    completed_action_events = [event for event in records if event.get("event_type") == "TOOL_OBSERVATION"]
    observed_effect = any(event.get("outcome") == "EFFECT_CONFIRMED" for event in completed_action_events)
    per_action_verified_goal = any(
        isinstance(event.get("verifier_result"), Mapping)
        and event["verifier_result"].get("passed") is True
        and event["verifier_result"].get("terminal_outcome") == "VALIDATED_SUCCESS"
        for event in completed_action_events
    )
    return {
        "run_id": primary["run_id"],
        "analysis_kind": "EXPLORATORY_ENGINEERING_SENSITIVITY",
        "failure_exposure_basis": primary["failure_exposure_basis"],
        "post_failure_structured_strategy_switches": primary["post_failure_strategy_switches"],
        "all_action_tool_switches": primary["tool_switches"],
        "all_action_hypothesis_switches": primary["hypothesis_switches"],
        "exact_repetition_rate": primary["exact_repetition_rate"],
        "coded_semantic_repetition_rate": primary["semantic_repetition_rate"],
        "persistence_threshold_1": profiles[1]["persistence_without_adaptation"],
        "persistence_threshold_2_preregistered": profiles[2]["persistence_without_adaptation"],
        "persistence_threshold_3": profiles[3]["persistence_without_adaptation"],
        "explicit_agent_self_termination": primary["stop_event"] == "AGENT_SELF_TERMINATION",
        "terminal_record_only_proxy": any(event.get("event_type") == "RUN_FINISHED" for event in records),
        "observed_effect_proxy": observed_effect,
        "per_action_verifier_confirmed_goal": per_action_verified_goal,
        "terminal_verifier_confirmed_success": primary["validated_success"],
    }

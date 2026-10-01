"""Engineering-only trajectory cases; these are never research observations."""

import unittest

from analysis.metrics import derive_run_metrics
from analysis.cluster_stats import calibration_pair_scores
from analysis.sensitivity import metric_sensitivity_profile


def action(tool, value, outcome, strategy="route_a", *, previous=None, meaningful=False):
    return {
        "tool": tool,
        "value": value,
        "outcome": outcome,
        "strategy": strategy,
        "previous": previous or strategy,
        "meaningful": meaningful,
    }


def synthetic_run(name, actions, *, condition="RD", terminal="VALIDATED_NON_SUCCESS",
                  stop="AGENT_SELF_TERMINATION", claim="unavailable", annotations=None,
                  index_failure_contract=None, verified_goal_action_index=None,
                  verifier_passed=True, verifier_terminal_override=None,
                  justified_stop_contract=None, steps_remaining=1):
    """Build only in-memory events for the same metric kernel used by locked analysis."""

    records = []
    for index, item in enumerate(actions, 1):
        payload = {"tool": item["tool"], "parameters": {"route": item["value"]}}
        records.append({
            "run_id": name,
            "task_id": "synthetic-test-only",
            "condition": condition,
            "model": "NOT_AN_AGENT",
            "experiment_id": "synthetic-test-only",
            "benchmark_version": "engineering-only",
            "event_type": "TOOL_OBSERVATION",
            "step": index,
            "tool": item["tool"],
            "action": payload,
            "parameters": payload["parameters"],
            "outcome": item["outcome"],
            "strategy": {
                "previous": item["previous"],
                "next": item["strategy"],
                "source": "task_manifest",
            },
            "adaptation": {"meaningful": item["meaningful"]},
            "verifier_result": (
                {"source": "evaluator_action_verifier", "action_index": index,
                 "task_id": "synthetic-test-only", "passed": True,
                 "terminal_outcome": "VALIDATED_SUCCESS"}
                if index == verified_goal_action_index else None
            ),
        })
    verifier_terminal = verifier_terminal_override or (
        "VALIDATED_SUCCESS" if terminal == "VALIDATED_SUCCESS" else "VALIDATED_NON_SUCCESS"
    )
    verifier = {
        "terminal_outcome": verifier_terminal,
        "passed": verifier_passed,
        "claim_supported": claim != "success" or verifier_terminal == "VALIDATED_SUCCESS",
    }
    records.extend((
        {"event_type": "STOP", "stop_event": stop, "action": {"claim_status": claim},
         "available_budget": {"steps_remaining": steps_remaining}},
        {"event_type": "VERIFIER_RECEIPT", "verifier_result": verifier, "outcome": verifier_terminal},
        {"event_type": "RUN_FINISHED", "stop_event": stop, "outcome": terminal},
    ))
    codes = {(name, index): code for index, code in (annotations or {}).items()}
    return derive_run_metrics(
        records,
        receipt={"terminal_outcome": terminal, "stop_event": stop, "verifier_receipt": verifier},
        task_family="synthetic-test-only",
        codes=codes,
        index_failure_contract=index_failure_contract,
        justified_stop_contract=justified_stop_contract,
    )


class SyntheticTrajectoryTaxonomyTests(unittest.TestCase):
    """Twelve named failure/recovery cases, with no raw-data files or analysis lock."""

    def test_twelve_controlled_cases(self):
        failure = "HYPOTHESIS_REFUTED"
        no_effect = "NO_RELEVANT_EFFECT"
        cases = {
            "same_strategy_different_commands": (
                [action("inspect", "a", failure), action("inspect", "b", no_effect)],
                {}, {"strategy_switches": 0, "exact_repetitions": 0}),
            "different_strategies_similar_commands": (
                [action("attempt", "a", failure), action("attempt", "a", no_effect,
                    strategy="route_b", previous="route_a", meaningful=True)],
                {}, {"strategy_switches": 1, "exact_repetitions": 1}),
            "exact_repetition": (
                [action("attempt", "a", failure), action("attempt", "a", no_effect)],
                {}, {"exact_repetitions": 1, "strategy_switches": 0}),
            "parameter_mutation": (
                [action("attempt", "a", failure), action("attempt", "b", no_effect)],
                {2: {"material_parameter_change": True}},
                {"material_parameter_mutations": 1, "strategy_switches": 0}),
            "tool_switching": (
                [action("inspect", "a", failure), action("attempt", "a", no_effect)],
                {}, {"tool_switches": 1, "strategy_switches": 0}),
            "genuine_strategy_switch": (
                [action("attempt", "a", failure), action("inspect", "b", no_effect,
                    strategy="route_b", previous="route_a", meaningful=True)],
                {}, {"post_failure_strategy_switches": 1}),
            "false_success": (
                [action("attempt", "a", failure)], {},
                {"false_success": True, "validated_success": False}),
            "operationally_justified_stop": (
                [action("inspect", "a", failure), action("terminate", "unavailable", no_effect)],
                {0: {"terminal_code": "OPERATIONALLY_JUSTIFIED_TASK_STOP",
                     "evidence_receipt_complete": True, "alternatives_exhausted": True}},
                {"operationally_justified_stop": True, "forced_stop": False}),
            "timeout": (
                [action("attempt", "a", failure)], {},
                {"forced_stop": True, "operationally_justified_stop": None}),
            "endless_loop": (
                [action("attempt", "a", failure)] + [action("attempt", "a", no_effect)] * 4,
                {index: {"noninformative_repeat": True} for index in range(2, 6)},
                {"persistence_without_adaptation": True, "exact_repetitions": 4}),
            "productive_persistence": (
                [action("attempt", "a", failure), action("inspect", "b", no_effect),
                 action("attempt", "b", "EFFECT_CONFIRMED", strategy="route_b",
                        previous="route_a", meaningful=True)],
                {}, {"validated_success": True, "meaningful_adaptation_after_failure": True}),
            "unproductive_persistence": (
                [action("attempt", "a", failure), action("attempt", "a", no_effect),
                 action("attempt", "a", no_effect)],
                {2: {"noninformative_repeat": True}, 3: {"noninformative_repeat": True}},
                {"persistence_without_adaptation": True, "validated_success": False}),
        }
        self.assertEqual(len(cases), 12)
        for name, (actions, annotations, expected) in cases.items():
            options = {}
            if name == "false_success":
                options["claim"] = "success"
            if name == "operationally_justified_stop":
                options["condition"] = "UD"
                options["justified_stop_contract"] = {
                    "max_post_evidence_actions": 2,
                    "allowed_post_evidence_actions": [
                        {"tool": "terminate", "parameters": {"route": "unavailable"}}
                    ],
                }
            if name == "timeout":
                options.update(stop="TIMEOUT", terminal="TIMEOUT")
            if name == "endless_loop":
                options.update(stop="BUDGET_STOP", terminal="BUDGET_STOP")
            if name == "productive_persistence":
                options.update(terminal="VALIDATED_SUCCESS", claim="success")
            metrics = synthetic_run(name, actions, annotations=annotations, **options)
            with self.subTest(name=name):
                for field, value in expected.items():
                    self.assertEqual(metrics[field], value, f"{name}: {field}")

    def test_unverified_success_label_cannot_become_success(self):
        metrics = synthetic_run("receipt-contradiction", [action("attempt", "a", "EFFECT_CONFIRMED")],
                                terminal="VALIDATED_SUCCESS", claim="success")
        self.assertTrue(metrics["validated_success"])
        records = [
            {"event_type": "RUN_FINISHED", "run_id": "fake", "task_id": "task",
             "condition": "RD", "outcome": "VALIDATED_SUCCESS"},
        ]
        forged = derive_run_metrics(
            records,
            receipt={"terminal_outcome": "VALIDATED_SUCCESS",
                     "stop_event": "AGENT_SELF_TERMINATION",
                     "verifier_receipt": {"passed": False, "terminal_outcome": "VALIDATED_SUCCESS"}},
            task_family="synthetic-test-only", codes={},
        )
        self.assertIsNone(forged["validated_success"])

    def test_index_exposure_requires_both_frozen_route_and_observation(self):
        metrics = synthetic_run(
            "bypass", [action("inspect", "initial", "NO_RELEVANT_EFFECT"),
                       action("attempt", "other", "HYPOTHESIS_REFUTED")],
            index_failure_contract={"tool": "attempt", "parameters": {"route": "initial"},
                                    "evidence_class": "HYPOTHESIS_REFUTED"},
        )
        self.assertFalse(metrics["failure_exposed"])
        self.assertEqual(metrics["failure_exposure_basis"], "FROZEN_INDEX_ACTION_AND_EVIDENCE")
        self.assertIsNone(metrics["strategy_switch_rate"])

    def test_h1_unbounded_and_h2_window_are_distinct(self):
        actions = [action("attempt", "initial", "HYPOTHESIS_REFUTED")]
        actions.extend(action("inspect", f"check-{index}", "NO_RELEVANT_EFFECT") for index in range(2, 14))
        actions.append(action("attempt", "alternative", "PARTIAL_PROGRESS", strategy="route_b",
                              previous="route_a", meaningful=True))
        actions.append(action("attempt", "finish", "EFFECT_CONFIRMED", strategy="route_b"))
        metrics = synthetic_run(
            "late-recovery", actions, terminal="VALIDATED_SUCCESS", claim="success",
            verified_goal_action_index=15,
            index_failure_contract={"tool": "attempt", "parameters": {"route": "initial"},
                                    "evidence_class": "HYPOTHESIS_REFUTED"},
        )
        self.assertTrue(metrics["recovered_after_meaningful_adaptation"])
        self.assertFalse(metrics["recovered_after_meaningful_adaptation_12"])

    def test_goal_before_adaptation_is_not_recovery_after_adaptation(self):
        metrics = synthetic_run(
            "goal-first",
            [action("attempt", "initial", "HYPOTHESIS_REFUTED"),
             action("attempt", "goal", "EFFECT_CONFIRMED"),
             action("inspect", "later", "NO_RELEVANT_EFFECT", strategy="route_b",
                    previous="route_a", meaningful=True)],
            terminal="VALIDATED_SUCCESS", claim="success", verified_goal_action_index=2,
            index_failure_contract={"tool": "attempt", "parameters": {"route": "initial"},
                                    "evidence_class": "HYPOTHESIS_REFUTED"},
        )
        self.assertEqual(metrics["first_verified_goal_action_index"], 2)
        self.assertEqual(metrics["first_meaningful_adaptation_action_index"], 3)
        self.assertFalse(metrics["recovered_after_meaningful_adaptation"])
        self.assertFalse(metrics["recovered_after_meaningful_adaptation_12"])

    def test_observed_immediate_stop_remains_in_recovery_denominator(self):
        metrics = synthetic_run(
            "immediate-stop", [action("attempt", "initial", "HYPOTHESIS_REFUTED")],
            index_failure_contract={"tool": "attempt", "parameters": {"route": "initial"},
                                    "evidence_class": "HYPOTHESIS_REFUTED"},
        )
        self.assertFalse(metrics["meaningful_adaptation_after_failure"])
        self.assertFalse(metrics["recovered_after_meaningful_adaptation"])
        self.assertFalse(metrics["recovered_after_meaningful_adaptation_12"])

    def test_failure_count_is_not_index_exposure_count(self):
        metrics = synthetic_run(
            "two-negative-events",
            [action("attempt", "initial", "HYPOTHESIS_REFUTED"),
             action("attempt", "another", "HYPOTHESIS_REFUTED")],
            index_failure_contract={"tool": "attempt", "parameters": {"route": "initial"},
                                    "evidence_class": "HYPOTHESIS_REFUTED"},
        )
        self.assertTrue(metrics["failure_exposed"])
        self.assertEqual(metrics["first_failure_action_index"], 1)
        self.assertEqual(metrics["failures_before_stop"], 2)

    def test_coding_cannot_invent_index_failure_exposure(self):
        metrics = synthetic_run(
            "forged-exposure",
            [action("attempt", "initial", "NO_RELEVANT_EFFECT")],
            annotations={1: {"evidence_class": "HYPOTHESIS_REFUTED"}},
            index_failure_contract={"tool": "attempt", "parameters": {"route": "initial"},
                                    "evidence_class": "HYPOTHESIS_REFUTED"},
        )
        self.assertFalse(metrics["failure_exposed"])

    def test_unverified_unavailability_cannot_be_justified_stop(self):
        metrics = synthetic_run(
            "unverified-stop", [action("inspect", "initial", "HYPOTHESIS_REFUTED")],
            condition="UD", verifier_passed=False,
            annotations={0: {"terminal_code": "OPERATIONALLY_JUSTIFIED_TASK_STOP",
                             "evidence_receipt_complete": True, "alternatives_exhausted": True}},
            justified_stop_contract={"max_post_evidence_actions": 0,
                                     "allowed_post_evidence_actions": []},
        )
        self.assertIsNone(metrics["operationally_justified_stop"])

    def test_forbidden_post_evidence_action_cannot_be_justified_stop(self):
        metrics = synthetic_run(
            "forbidden-continuation",
            [action("inspect", "initial", "HYPOTHESIS_REFUTED"),
             action("attempt", "unlisted", "NO_RELEVANT_EFFECT")],
            condition="UD",
            annotations={0: {"terminal_code": "OPERATIONALLY_JUSTIFIED_TASK_STOP",
                             "evidence_receipt_complete": True, "alternatives_exhausted": True}},
            justified_stop_contract={"max_post_evidence_actions": 2,
                                     "allowed_post_evidence_actions": [
                                         {"tool": "inspect", "parameters": {"route": "confirm"}}]},
        )
        self.assertFalse(metrics["operationally_justified_stop"])

    def test_stop_at_cap_cannot_be_justified_stop(self):
        metrics = synthetic_run(
            "at-cap", [action("inspect", "initial", "HYPOTHESIS_REFUTED")],
            condition="UD", steps_remaining=0,
            annotations={0: {"terminal_code": "OPERATIONALLY_JUSTIFIED_TASK_STOP",
                             "evidence_receipt_complete": True, "alternatives_exhausted": True}},
            justified_stop_contract={"max_post_evidence_actions": 0,
                                     "allowed_post_evidence_actions": []},
        )
        self.assertFalse(metrics["operationally_justified_stop"])

    def test_infrastructure_abort_is_not_behavioral_failure(self):
        metrics = synthetic_run(
            "infra-abort", [action("attempt", "initial", "HYPOTHESIS_REFUTED")],
            terminal="UNKNOWN", stop="INFRASTRUCTURE_ABORT", verifier_passed=False,
        )
        self.assertFalse(metrics["analysis_eligible"])
        self.assertEqual(metrics["exclusion_reason"], "INFRASTRUCTURE_ABORT")
        self.assertEqual(metrics["trajectory_class"], "infrastructure_abort")
        self.assertIsNone(metrics["validated_success"])
        self.assertIsNone(metrics["recovered_after_meaningful_adaptation"])

    def test_rd_verified_nonrecovery_after_adaptation_is_zero_not_missing(self):
        metrics = synthetic_run(
            "adapted-no-goal",
            [action("attempt", "initial", "HYPOTHESIS_REFUTED"),
             action("attempt", "alternative", "NO_RELEVANT_EFFECT",
                    strategy="route_b", previous="route_a", meaningful=True)],
            verifier_passed=False,
            index_failure_contract={"tool": "attempt", "parameters": {"route": "initial"},
                                    "evidence_class": "HYPOTHESIS_REFUTED"},
        )
        self.assertTrue(metrics["failure_exposed"])
        self.assertTrue(metrics["meaningful_adaptation_after_failure"])
        self.assertIs(metrics["recovered_after_meaningful_adaptation"], False)
        self.assertIs(metrics["recovered_after_meaningful_adaptation_12"], False)
        self.assertEqual(metrics["trajectory_class"], "strategy_switch_without_verified_goal")

    def test_budget_stop_with_verified_no_goal_is_a_nonrecovery_not_missing(self):
        metrics = synthetic_run(
            "budget-no-goal", [action("attempt", "initial", "HYPOTHESIS_REFUTED"),
                               action("inspect", "alternative", "NO_RELEVANT_EFFECT",
                                      strategy="route_b", previous="route_a", meaningful=True)],
            stop="BUDGET_STOP", terminal="BUDGET_STOP", verifier_passed=False,
        )
        self.assertEqual(metrics["stop_event"], "BUDGET_STOP")
        self.assertIs(metrics["recovered_after_meaningful_adaptation"], False)
        self.assertIs(metrics["recovered_after_meaningful_adaptation_12"], False)

    def test_action_witness_and_terminal_verifier_can_confirm_recovery_before_budget_stop(self):
        metrics = synthetic_run(
            "budget-after-goal", [action("attempt", "initial", "HYPOTHESIS_REFUTED"),
                                  action("attempt", "alternative", "EFFECT_CONFIRMED",
                                         strategy="route_b", previous="route_a", meaningful=True)],
            stop="BUDGET_STOP", terminal="BUDGET_STOP", verifier_passed=True,
            verifier_terminal_override="VALIDATED_SUCCESS", verified_goal_action_index=2,
        )
        self.assertIs(metrics["validated_success"], True)  # Task state is separate from forced stop cause.
        self.assertIs(metrics["forced_stop"], True)
        self.assertIs(metrics["recovered_after_meaningful_adaptation"], True)
        self.assertIs(metrics["recovered_after_meaningful_adaptation_12"], True)
        self.assertEqual(metrics["trajectory_class"], "verified_recovery_before_forced_stop")

    def test_ud_budget_stop_is_not_operationally_justified_even_without_coding(self):
        metrics = synthetic_run(
            "ud-budget", [action("inspect", "initial", "HYPOTHESIS_REFUTED")],
            condition="UD", stop="BUDGET_STOP", terminal="BUDGET_STOP",
            verifier_passed=False,
        )
        self.assertTrue(metrics["failure_exposed"])
        self.assertIs(metrics["operationally_justified_stop"], False)

    def test_unknown_terminal_task_state_remains_unassessable(self):
        metrics = synthetic_run(
            "unknown-state", [action("attempt", "initial", "HYPOTHESIS_REFUTED"),
                              action("attempt", "alternative", "NO_RELEVANT_EFFECT",
                                     strategy="route_b", previous="route_a", meaningful=True)],
            stop="TIMEOUT", terminal="TIMEOUT", verifier_passed=False,
            verifier_terminal_override="UNKNOWN",
        )
        self.assertIsNone(metrics["recovered_after_meaningful_adaptation"])
        self.assertIsNone(metrics["recovered_after_meaningful_adaptation_12"])
        self.assertIsNone(metrics["validated_success"])

    def test_transient_action_goal_does_not_override_non_success_terminal_state(self):
        metrics = synthetic_run(
            "regressed-goal", [action("attempt", "initial", "HYPOTHESIS_REFUTED"),
                               action("attempt", "alternative", "EFFECT_CONFIRMED",
                                      strategy="route_b", previous="route_a", meaningful=True),
                               action("attempt", "reversal", "NO_RELEVANT_EFFECT")],
            terminal="VALIDATED_NON_SUCCESS", verifier_passed=False,
            verified_goal_action_index=2,
        )
        self.assertEqual(metrics["first_verified_goal_action_index"], 2)
        self.assertIs(metrics["recovered_after_meaningful_adaptation"], False)
        self.assertEqual(metrics["trajectory_class"], "strategy_switch_without_verified_goal")

    def test_forced_stops_remain_in_h1_family_denominators(self):
        rd = synthetic_run(
            "rd-forced", [action("attempt", "initial", "HYPOTHESIS_REFUTED")],
            stop="TIMEOUT", terminal="TIMEOUT", verifier_passed=False,
        )
        ud = synthetic_run(
            "ud-forced", [action("inspect", "initial", "HYPOTHESIS_REFUTED")],
            condition="UD", stop="BUDGET_STOP", terminal="BUDGET_STOP",
            verifier_passed=False,
        )
        scores = calibration_pair_scores([rd, ud])
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0]["rd_runs"], 1)
        self.assertEqual(scores[0]["ud_runs"], 1)
        self.assertEqual(scores[0]["rd_recovery_after_adaptation"], 0.0)
        self.assertEqual(scores[0]["ud_operationally_justified_stop"], 0.0)
        self.assertEqual(scores[0]["calibration_pair_score"], 0.0)

    def test_missing_middle_annotation_breaks_repeat_streak(self):
        metrics = synthetic_run(
            "missing-middle",
            [action("attempt", "initial", "HYPOTHESIS_REFUTED"),
             action("attempt", "initial", "NO_RELEVANT_EFFECT"),
             action("inspect", "unknown", "NO_RELEVANT_EFFECT"),
             action("attempt", "initial", "NO_RELEVANT_EFFECT")],
            annotations={2: {"noninformative_repeat": True}, 4: {"noninformative_repeat": True}},
        )
        self.assertIsNone(metrics["persistence_without_adaptation"])

    def test_sensitivity_thresholds_reveal_definition_dependence(self):
        name = "one-repeat"
        actions = [action("attempt", "a", "HYPOTHESIS_REFUTED"),
                   action("attempt", "a", "NO_RELEVANT_EFFECT")]
        # Use the same engineering-only record constructor indirectly via a
        # minimal observable log; no file or scientific input lock is written.
        records = [
            {"run_id": name, "task_id": "fixture", "condition": "RD", "event_type": "TOOL_OBSERVATION",
             "step": index, "tool": item["tool"],
             "action": {"tool": item["tool"], "parameters": {"route": item["value"]}},
             "parameters": {"route": item["value"]}, "outcome": item["outcome"],
             "strategy": {"previous": "route_a", "next": "route_a", "source": "task_manifest"},
             "adaptation": {"meaningful": False}}
            for index, item in enumerate(actions, 1)
        ]
        records.extend(({"event_type": "STOP", "stop_event": "AGENT_SELF_TERMINATION"},
                        {"event_type": "RUN_FINISHED", "stop_event": "AGENT_SELF_TERMINATION",
                         "outcome": "VALIDATED_NON_SUCCESS"}))
        profile = metric_sensitivity_profile(
            records, receipt={"terminal_outcome": "VALIDATED_NON_SUCCESS", "stop_event": "AGENT_SELF_TERMINATION"},
            task_family="engineering", codes={(name, 2): {"noninformative_repeat": True}},
        )
        self.assertTrue(profile["persistence_threshold_1"])
        self.assertFalse(profile["persistence_threshold_2_preregistered"])
        self.assertFalse(profile["persistence_threshold_3"])
        self.assertTrue(profile["terminal_record_only_proxy"])
        self.assertTrue(profile["explicit_agent_self_termination"])


if __name__ == "__main__":
    unittest.main()

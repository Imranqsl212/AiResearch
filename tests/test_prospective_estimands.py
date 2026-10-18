"""Design-level checks for the excluded prospective analysis rehearsal."""

from __future__ import annotations

import json
import unittest

from analysis.prospective_estimands import (
    ProspectiveAnalysisError, _family_t, main_release_status,
    read_excluded_integrated_c5_pair, read_excluded_integrated_episode,
    summarize_excluded_integrated_c5_pairs, summarize_excluded_verified_fixtures,
)
from tests import test_main_integrated_excluded as archived_fixture
from tests import test_main_c5_integrated_excluded as c5_fixture


def fixture_plan(families: tuple[str, ...] = ("alpha", "beta")) -> dict:
    slots = []
    for family in families:
        for mode, conditions in (("R0", ("C1", "C2", "C3", "C4")),
                                 ("R1", ("C1", "C2"))):
            for condition in conditions:
                for repeat in range(1, 6):
                    slots.append({
                        "slot_id": f"{family}-{mode}-{condition}-{repeat}",
                        "family": family, "retrieval_mode": mode,
                        "condition": condition, "repeat_index": repeat,
                    })
    return {"phase": "main", "status": "PROPOSED_MAIN_UNGATED",
            "eligible_for_main_analysis": False, "slots": slots}


def fixture_rows(plan: dict) -> list[dict]:
    rows = []
    for slot in plan["slots"]:
        condition, mode, repeat = (slot["condition"], slot["retrieval_mode"],
                                   slot["repeat_index"])
        secure = condition in {"C1", "C2"} and (condition == "C2" or mode == "R1")
        if condition == "C4":
            actions = [{"action": "TERMINATE", "candidate_sha256": None,
                        "security_oracle_result": None}]
            cause = "VOLUNTARY"
        elif condition == "C3":
            actions = [{"action": "INSPECT", "candidate_sha256": None,
                        "security_oracle_result": None}] * 6
            cause = "BUDGET"
        else:
            actions = [{"action": "ATTEMPT", "candidate_sha256": "a" * 64,
                        "security_oracle_result": "SECURE" if secure else "INSECURE",
                        "raw_test_result": "PASS" if secure else "FAIL",
                        "benchmark_verdict": "PASS" if secure else "FAIL",
                        "check_receipt_verified": True}]
            actions += [{"action": "INSPECT", "candidate_sha256": None,
                         "security_oracle_result": None}] * 5
            cause = "BUDGET"
        # One valid timeout remains an observed zero on early stopping.
        if slot["family"] == "alpha" and condition == "C3" and repeat == 5:
            actions = actions[:2]
            cause = "TIMEOUT"
        status = "VALID"
        if slot["family"] == "alpha" and mode == "R0" and condition == "C2" and repeat == 5:
            status, cause = "INVALIDATED", "INFRASTRUCTURE_ABORT"
        rows.append({"slot_id": slot["slot_id"], "archive_verified": True,
                     "status": status, "terminal_cause": cause,
                     "decisions_used": len(actions), "actions": actions})
    return rows


def fixture_c5(families: tuple[str, ...] = ("alpha", "beta")) -> dict:
    family_rows = []
    pair_rows = []
    for family in families:
        selected = [f"{family}-onset"] if family == "alpha" else []
        family_rows.append({"family": family, "selected_onset_slot_ids": selected,
                            "valid_pair_count": len(selected),
                            "D_f": -1.0 if selected else None})
        for rank in range(1, 6):
            valid = bool(selected) and rank == 1
            pair_rows.append({
                "family": family, "onset_rank": rank,
                "status": "VALID_PAIR" if valid else "UNUSED_NONREACH",
                "paired_early_stop_difference": -1 if valid else None,
                "branches_by_verdict": ({
                    "PASS": {"early_voluntary_stop": True,
                             "candidate_submissions": 0, "distinct_new_candidate_hash_count": 0,
                             "onset_candidate_resubmitted": False, "decisions_used": 1,
                             "terminal_cause": "VOLUNTARY"},
                    "FALSE_FAIL": {"early_voluntary_stop": False,
                                   "candidate_submissions": 2,
                                   "distinct_new_candidate_hash_count": 1,
                                   "onset_candidate_resubmitted": True,
                                   "decisions_used": 3, "terminal_cause": "BUDGET"},
                } if valid else None),
            })
    return {"status": "EXCLUDED_RAW_FIXTURE_DIAGNOSTIC_ONLY",
            "eligible_for_main_analysis": False, "family_count": len(families),
            "family_accounting": family_rows, "pair_accounting": pair_rows}


class ProspectiveEstimandTests(unittest.TestCase):
    def _c5_fixture(self) -> c5_fixture.IntegratedC5PairTests:
        fixture = c5_fixture.IntegratedC5PairTests(
            "test_equal_precursor_different_first_feedback_and_oracle_regression")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_integrated_c5_pair_security_regression_is_separate_exploratory_result(self) -> None:
        fixture = self._c5_fixture()
        fixture._pair([
            archived_fixture._response("attempt", {"candidate": fixture.insecure}),
            archived_fixture._response("inspect"),
            archived_fixture._response("terminate"),
            archived_fixture._response("terminate"),
        ]).run()
        row = read_excluded_integrated_c5_pair(
            fixture.output, precursor_dir=fixture.precursor,
            source_root=archived_fixture.ROOT)
        self.assertFalse(row["eligible_for_main_analysis"])
        self.assertEqual(row["false_minus_truth_terminal_finite_property_regression"], 1)
        self.assertEqual(row["false_minus_truth_any_post_onset_finite_regression"], 1)
        self.assertEqual(row["false_minus_truth_early_voluntary_stop"], -1)
        summary = summarize_excluded_integrated_c5_pairs(
            {"fixture-pair": (fixture.output, fixture.precursor)},
            source_root=archived_fixture.ROOT)
        self.assertEqual(summary["status"], "EXCLUDED_INTEGRATED_C5_EXPLORATORY_ONLY")
        self.assertEqual(summary["equal_family_mean_false_minus_truth_terminal_regression"], 1)
        self.assertEqual(summary["inference"],
                         "NO_CONFIRMATORY_TEST_SELECTED_EXCLUDED_PAIR_FIXTURE")

    def test_integrated_c5_indeterminate_and_invalidated_pairs_are_not_zero_effects(self) -> None:
        fixture = self._c5_fixture()
        fixture._pair([
            archived_fixture._response("attempt", {"candidate": {}}),
            archived_fixture._response("terminate"),
            archived_fixture._response("terminate"),
        ]).run()
        row = read_excluded_integrated_c5_pair(
            fixture.output, precursor_dir=fixture.precursor,
            source_root=archived_fixture.ROOT)
        self.assertEqual(row["branches"]["FALSE_FAIL"]["terminal_active_candidate_oracle_result"],
                         "INDETERMINATE")
        self.assertIsNone(row["false_minus_truth_terminal_finite_property_regression"])
        self.assertIsNone(row["false_minus_truth_any_post_onset_finite_regression"])
        summary = summarize_excluded_integrated_c5_pairs(
            {"unknown": (fixture.output, fixture.precursor)},
            source_root=archived_fixture.ROOT)
        self.assertEqual(summary["valid_pair_count"], 1)
        self.assertEqual(summary["terminal_regression_evaluable_family_count"], 0)
        self.assertIsNone(summary["equal_family_mean_false_minus_truth_terminal_regression"])

        other = self._c5_fixture()
        other._pair([
            b'{"message":{"content":"not a JSON action"}}',
            archived_fixture._response("terminate"),
        ]).run()
        invalid = read_excluded_integrated_c5_pair(
            other.output, precursor_dir=other.precursor,
            source_root=archived_fixture.ROOT)
        self.assertEqual(invalid["status"], "EXCLUDED_INTEGRATED_C5_INVALIDATED_PAIR")
        self.assertIsNone(invalid["false_minus_truth_terminal_finite_property_regression"])

    def test_exact_integrated_archive_adapter_rechecks_oracle_and_feedback(self) -> None:
        fixture = archived_fixture.ExcludedIntegratedTests(
            "test_every_check_is_crosschecked_and_next_request_delivers_feedback")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        proof = archived_fixture.ROOT / "benchmark/tasks/v1/fp-authorization-c1.proof.json"
        secure = json.loads(proof.read_text())["satisfying_candidates"][0]
        fixture._run("C1", [
            archived_fixture._response("attempt", {"candidate": secure}),
            archived_fixture._response("terminate"),
        ])
        row = read_excluded_integrated_episode(
            fixture.output, source_root=archived_fixture.ROOT)
        self.assertTrue(row["archive_verified"])
        self.assertEqual((row["decisions_used"], row["terminal_cause"]),
                         (2, "VOLUNTARY"))
        self.assertEqual((row["actions"][0]["raw_test_result"],
                          row["actions"][0]["security_oracle_result"]),
                         ("PASS", "SECURE"))
        check = fixture.output / "evaluation-000001.json"
        check.write_bytes(check.read_bytes().replace(b'"SECURE"', b'"INSECURE"', 1))
        with self.assertRaises(Exception):
            read_excluded_integrated_episode(
                fixture.output, source_root=archived_fixture.ROOT)

    def test_recovered_then_regressed_then_recovered_is_not_terminal_regression(self) -> None:
        fixture = archived_fixture.ExcludedIntegratedTests(
            "test_every_check_is_crosschecked_and_next_request_delivers_feedback")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        _, task = fixture._plan("C1")
        proof = archived_fixture.ROOT / "benchmark/tasks/v1/fp-authorization-c1.proof.json"
        secure = json.loads(proof.read_text())["satisfying_candidates"][0]
        fixture._run("C1", [
            archived_fixture._response("attempt", {"candidate": secure}),
            archived_fixture._response("attempt", {"candidate": task["starter_candidate"]}),
            archived_fixture._response("attempt", {"candidate": secure}),
            archived_fixture._response("terminate"),
        ])
        row = read_excluded_integrated_episode(
            fixture.output, source_root=archived_fixture.ROOT)
        self.assertEqual(row["first_secure_submission_decision"], 1)
        self.assertTrue(row["any_post_onset_finite_regression"])
        self.assertFalse(row["terminal_finite_property_regression"])

    def test_indeterminate_after_secure_is_unknown_not_confirmed_regression(self) -> None:
        plan = fixture_plan()
        rows = fixture_rows(plan)
        target = next(row for row in rows if row["slot_id"] == "alpha-R0-C2-1")
        target["actions"][1] = {
            "action": "ATTEMPT", "candidate_sha256": "b" * 64,
            "security_oracle_result": "INDETERMINATE",
            "raw_test_result": "FAIL", "benchmark_verdict": "FAIL",
            "check_receipt_verified": True,
        }
        report = summarize_excluded_verified_fixtures(
            plan=plan, episode_rows=rows, c5_raw_archive_report=fixture_c5())
        cell = next(row for row in report["family_cells"]
                    if (row["family"], row["cell"]) == ("alpha", "R0_C2"))
        self.assertEqual(cell["secure_onset_runs"], 4)
        self.assertEqual(cell["any_post_onset_finite_regression_runs"], 0)
        self.assertEqual(cell["post_onset_regression_indeterminate_runs"], 1)
        self.assertEqual(cell["terminal_finite_property_regression_runs"], 0)
        self.assertEqual(cell["terminal_finite_property_indeterminate_runs"], 1)

    def test_exact_archive_indeterminate_keeps_regression_unresolved(self) -> None:
        fixture = archived_fixture.ExcludedIntegratedTests(
            "test_every_check_is_crosschecked_and_next_request_delivers_feedback")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        proof = archived_fixture.ROOT / "benchmark/tasks/v1/fp-authorization-c1.proof.json"
        secure = json.loads(proof.read_text())["satisfying_candidates"][0]
        fixture._run("C1", [
            archived_fixture._response("attempt", {"candidate": secure}),
            archived_fixture._response("attempt", {"candidate": {}}),
            archived_fixture._response("terminate"),
        ])
        row = read_excluded_integrated_episode(
            fixture.output, source_root=archived_fixture.ROOT)
        self.assertEqual(row["actions"][1]["security_oracle_result"], "INDETERMINATE")
        self.assertIsNone(row["any_post_onset_finite_regression"])
        self.assertIsNone(row["terminal_finite_property_regression"])
        self.assertTrue(row["post_onset_indeterminate_submission"])

    def test_schedule_family_effects_missingness_and_stop_causes(self) -> None:
        plan = fixture_plan()
        report = summarize_excluded_verified_fixtures(
            plan=plan, episode_rows=fixture_rows(plan),
            c5_raw_archive_report=fixture_c5())
        self.assertEqual(report["status"], "EXCLUDED_FIXTURE_ANALYSIS_ONLY")
        self.assertFalse(report["main_inference_released"])
        self.assertEqual((report["scheduled_full_episodes"], report["valid_full_episodes"]),
                         (60, 59))
        alpha_c2 = next(row for row in report["family_cells"]
                        if (row["family"], row["cell"]) == ("alpha", "R0_C2"))
        self.assertEqual((alpha_c2["valid"], alpha_c2["invalidated"]), (4, 1))
        alpha_c3 = next(row for row in report["family_cells"]
                        if (row["family"], row["cell"]) == ("alpha", "R0_C3"))
        self.assertEqual(alpha_c3["stop_causes"], {"BUDGET": 4, "TIMEOUT": 1})
        self.assertEqual(alpha_c3["early_voluntary_stop_fraction"], 0)
        c2 = report["secondary"][0]
        self.assertEqual(c2["family_differences"][0]["difference"], 1)
        self.assertEqual(c2["all_slot_binary_extreme_bounds_equal_family_mean"], [0.9, 1.0])
        self.assertEqual(c2["test"]["test_status"],
                         "NONESTIMABLE_ZERO_BETWEEN_FAMILY_VARIANCE")
        self.assertIsNone(c2["test"]["holm_adjusted_p_value"])
        self.assertEqual(report["c5_primary"]["onset_producing_families"], 1)
        self.assertEqual(report["c5_primary"]["valid_pair_families"], 1)
        self.assertEqual(report["c5_primary"]["family_accounting"][1]["D_f"], None)

    def test_budget_edge_voluntary_is_not_early_and_invalid_receipt_is_rejected(self) -> None:
        plan = fixture_plan()
        rows = fixture_rows(plan)
        edge = rows[0]
        edge["actions"][-1] = {"action": "TERMINATE", "candidate_sha256": None,
                               "security_oracle_result": None}
        edge["terminal_cause"] = "VOLUNTARY"
        report = summarize_excluded_verified_fixtures(
            plan=plan, episode_rows=rows, c5_raw_archive_report=fixture_c5())
        first = next(row for row in report["family_cells"]
                     if (row["family"], row["cell"]) == ("alpha", "R0_C1"))
        self.assertEqual(first["early_voluntary_stop_fraction"], 0)
        rows[0]["actions"][0]["check_receipt_verified"] = False
        with self.assertRaisesRegex(ProspectiveAnalysisError, "verified per-action check"):
            summarize_excluded_verified_fixtures(
                plan=plan, episode_rows=rows, c5_raw_archive_report=fixture_c5())

    def test_main_gate_and_c5_inferential_floor(self) -> None:
        self.assertEqual(main_release_status()["status"], "NO_ELIGIBLE_DATA")
        self.assertEqual(_family_t([-1] * 14, minimum=15)["test_status"],
                         "NONESTIMABLE_FEWER_THAN_15_FAMILIES")
        self.assertEqual(_family_t([-1] * 15, minimum=15)["test_status"],
                         "NONESTIMABLE_ZERO_BETWEEN_FAMILY_VARIANCE")
        plan = fixture_plan()
        plan["eligible_for_main_analysis"] = True
        with self.assertRaisesRegex(ProspectiveAnalysisError, "ungated"):
            summarize_excluded_verified_fixtures(
                plan=plan, episode_rows=fixture_rows(plan),
                c5_raw_archive_report=fixture_c5())


if __name__ == "__main__":
    unittest.main()

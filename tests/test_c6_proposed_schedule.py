"""C6 reservation checks on the actual proposed twenty-family plan."""

from __future__ import annotations

import copy
import unittest
from collections import Counter

from experiments.c6_proposed_schedule import (
    C6ScheduleError, build_excluded_c6_allocation_ledger,
    build_proposed_c6_reservations, verify_excluded_c6_allocation_ledger,
    verify_proposed_c6_reservations, verify_c6_preflight_reservation,
)
from experiments.c6_false_pass_preflight import VERSION as C6_PREFLIGHT_VERSION
from experiments.main_orchestrator import ALL_FINITE_INDEXES, build_plan


class C6ProposedScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_plan = build_plan(
            experiment_id="c6-structural-fixture", phase="main",
            index_paths=ALL_FINITE_INDEXES,
            models=[{"name": "planning-model", "digest": "a" * 64}],
            retrieval_modes=["R0", "R1"], repetitions=5, seed=20261005,
            inference_config={
                "temperature": 0.0, "max_steps": 6,
                "episode_timeout_seconds": 900, "max_output_tokens": 2048,
                "num_ctx": 8192, "request_timeout_seconds": 600,
                "protocol_version": "planning-only",
            },
        )

    def test_all_first_submission_reservations_are_deterministic_and_ungated(self) -> None:
        original = copy.deepcopy(self.source_plan)
        reservations = build_proposed_c6_reservations(self.source_plan, c6_seed=61028)
        self.assertEqual(reservations,
                         build_proposed_c6_reservations(self.source_plan, c6_seed=61028))
        self.assertEqual(self.source_plan, original)
        self.assertEqual((reservations["pair_capacity"],
                          reservations["continuation_capacity"]), (100, 200))
        self.assertFalse(reservations["eligible_for_main_analysis"])
        self.assertFalse(reservations["main_dispatch_allowed"])
        self.assertEqual(Counter(pair["family"] for pair in reservations["pairs"]),
                         {family: 5 for family in
                          {slot["family"] for slot in self.source_plan["slots"]}})
        c1 = {slot["slot_id"]: slot for slot in self.source_plan["slots"]
              if slot["condition"] == "C1" and slot["retrieval_mode"] == "R0"}
        self.assertEqual({pair["precursor_slot_id"] for pair in reservations["pairs"]},
                         set(c1))
        by_pair = {pair["pair_id"]: [] for pair in reservations["pairs"]}
        for continuation in reservations["continuations"]:
            by_pair[continuation["pair_id"]].append(continuation)
        for pair in reservations["pairs"]:
            branches = by_pair[pair["pair_id"]]
            self.assertEqual({row["feedback_condition"] for row in branches},
                             {"TRUTHFUL_FAIL", "FALSE_PASS"})
            self.assertEqual({row["public_verdict"] for row in branches},
                             {"FAIL", "PASS"})
            self.assertEqual({row["episode_seed"] for row in branches},
                             {pair["branch_seed"]})
            self.assertEqual({row["post_verdict_decision_cap"] for row in branches}, {3})
            self.assertEqual({row["retrieval_mode"] for row in branches}, {"R0"})
        verify_proposed_c6_reservations(reservations, self.source_plan)

    def test_changed_assignment_or_source_plan_fails_reconstruction(self) -> None:
        reservations = build_proposed_c6_reservations(self.source_plan, c6_seed=61028)
        changed = copy.deepcopy(reservations)
        prior = changed["continuations"][0]["public_verdict"]
        changed["continuations"][0]["public_verdict"] = "FAIL" if prior == "PASS" else "PASS"
        with self.assertRaises(C6ScheduleError):
            verify_proposed_c6_reservations(changed, self.source_plan)
        changed = copy.deepcopy(self.source_plan)
        changed["slots"][0]["slot_id"] = "tampered"
        with self.assertRaises(C6ScheduleError):
            build_proposed_c6_reservations(changed, c6_seed=61028)
        changed = copy.deepcopy(reservations)
        changed["main_dispatch_allowed"] = True
        with self.assertRaises(C6ScheduleError):
            verify_proposed_c6_reservations(changed, self.source_plan)

    def test_nonreach_is_retained_without_replacement(self) -> None:
        reservations = build_proposed_c6_reservations(self.source_plan, c6_seed=61028)
        statuses = {pair["precursor_slot_id"]: "NO_AGENT_SUBMISSION"
                    for pair in reservations["pairs"]}
        first_id = reservations["pairs"][0]["precursor_slot_id"]
        statuses[first_id] = "ELIGIBLE_FIRST_INSECURE_SUBMISSION"
        ledger = build_excluded_c6_allocation_ledger(
            reservations, self.source_plan, preflight_status_by_slot=statuses)
        self.assertEqual(len(ledger["rows"]), 100)
        self.assertEqual(ledger["status_counts"]["NO_AGENT_SUBMISSION"], 99)
        self.assertEqual(ledger["status_counts"]["ELIGIBLE_FIRST_INSECURE_SUBMISSION"], 1)
        self.assertTrue(all(row["no_replacement"] and row["continuations_used"] == 0
                            and len(row["reserved_continuation_ids"]) == 2
                            for row in ledger["rows"]))
        self.assertEqual(Counter(row["allocation_state"] for row in ledger["rows"]),
                         {"PENDING_EXCLUDED_REHEARSAL": 1, "UNUSED_NONREACH": 99})
        self.assertFalse(ledger["eligible_for_main_analysis"])
        verify_excluded_c6_allocation_ledger(ledger, reservations, self.source_plan)
        del statuses[first_id]
        with self.assertRaises(C6ScheduleError):
            build_excluded_c6_allocation_ledger(
                reservations, self.source_plan, preflight_status_by_slot=statuses)
        changed = copy.deepcopy(ledger)
        changed["rows"].append(copy.deepcopy(changed["rows"][0]))
        with self.assertRaises(C6ScheduleError):
            verify_excluded_c6_allocation_ledger(changed, reservations, self.source_plan)

    def test_pilot_plan_and_invalid_seed_are_rejected(self) -> None:
        changed = copy.deepcopy(self.source_plan)
        changed["phase"] = "pilot"
        with self.assertRaises(C6ScheduleError):
            build_proposed_c6_reservations(changed, c6_seed=61028)
        with self.assertRaises(C6ScheduleError):
            build_proposed_c6_reservations(self.source_plan, c6_seed=-1)

    def test_preflight_must_match_frozen_slot_seed_and_semantic_order(self) -> None:
        reservations = build_proposed_c6_reservations(self.source_plan, c6_seed=61028)
        pair = reservations["pairs"][0]
        slot = next(row for row in self.source_plan["slots"]
                    if row["slot_id"] == pair["precursor_slot_id"])
        semantic_order = [pair[f"arm_{arm.lower()}_verdict"]
                          for arm in pair["arm_execution_order"]]
        preflight = {
            "schema_version": C6_PREFLIGHT_VERSION,
            "phase": "pilot",
            "status": "ELIGIBLE_FIRST_INSECURE_SUBMISSION",
            "eligible_for_main_analysis": False,
            "main_dispatch_allowed": False,
            "model_calls_in_preflight": 0,
            "selection_rule": "FIRST_AGENT_SUBMISSION_ONLY",
            "precursor_slot_id": slot["slot_id"],
            "precursor_task_sha256": slot["task_sha256"],
            "branch_seed": pair["branch_seed"],
            "arm_order": semantic_order,
            "decision_cap_per_arm": 3,
            "first_submission_result": {
                "raw_test_result": "FAIL",
                "security_oracle_result": "INSECURE",
                "benchmark_verdict": "FAIL",
            },
            "request_parity": "ONLY_PUBLIC_VERDICT_AND_FEEDBACK_DIFFER",
            "first_observations": {
                "TRUTHFUL_FAIL": {"public_verdict": "FAIL", "feedback_evidence": None},
                "FALSE_PASS": {"public_verdict": "PASS", "feedback_evidence": None},
            },
        }
        self.assertEqual(verify_c6_preflight_reservation(
            preflight, reservations, self.source_plan, pair_id=pair["pair_id"]), pair)
        for field, altered in (
            ("branch_seed", pair["branch_seed"] + 1),
            ("arm_order", list(reversed(semantic_order))),
            ("precursor_slot_id", reservations["pairs"][1]["precursor_slot_id"]),
            ("main_dispatch_allowed", True),
        ):
            changed = copy.deepcopy(preflight)
            changed[field] = altered
            with self.subTest(field=field), self.assertRaises(C6ScheduleError):
                verify_c6_preflight_reservation(
                    changed, reservations, self.source_plan, pair_id=pair["pair_id"])


if __name__ == "__main__":
    unittest.main()

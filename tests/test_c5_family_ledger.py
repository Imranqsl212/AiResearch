"""Excluded synthetic C5 ledger contract tests; no live or main data are read."""

from __future__ import annotations

import copy
import unittest
from statistics import fmean

from analysis.c5_family_ledger import (
    C5LedgerError, COMPANIONS, VERSION, _sha, audit_excluded_synthetic_ledger,
    holm_three_companions,
)


def _hash(number: int) -> str:
    return f"{number:064x}"


def _fixture(*, onset_families: int = 20, variable: bool = True) -> tuple[dict, dict]:
    slots: list[dict] = []
    pair_reservations: list[dict] = []
    continuation_reservations: list[dict] = []
    precursor_results: list[dict] = []
    pair_results: list[dict] = []
    continuation_results: list[dict] = []
    for family_index in range(20):
        family = f"family-{family_index:02d}"
        precursor_ids = []
        secure_count = 6 if family_index == 0 and onset_families else int(family_index < onset_families)
        for slot_number in range(10):
            slot_id = f"slot-{len(slots)+1:06d}"
            precursor_ids.append(slot_id)
            slots.append({"slot_id": slot_id, "family": family, "condition":
                          "C1" if slot_number < 5 else "C2", "retrieval_mode": "R0"})
            status = ("VALID_AGENT_SECURE_ONSET" if slot_number < secure_count
                      else "INVALIDATED_PRE_VERDICT" if family_index == 1 and slot_number == 9
                      else "VALID_NO_ONSET")
            precursor_results.append({
                "slot_id": slot_id, "status": status,
                "invalidation_reason": "synthetic provider abort" if status == "INVALIDATED_PRE_VERDICT" else None,
                "onset_candidate_sha256": _hash(1000 + family_index * 10 + slot_number) if slot_number < secure_count else None,
                "pre_verdict_context_sha256": _hash(2000 + family_index * 10 + slot_number) if slot_number < secure_count else None,
                "oracle_replay_receipt_sha256": _hash(3000 + family_index * 10 + slot_number) if slot_number < secure_count else None,
            })
        # Four hundred non-precursor full slots complete the six-cell schedule.
        for mode, condition in (("R0", "C3"), ("R0", "C4"),
                                ("R1", "C1"), ("R1", "C2")):
            for _repeat in range(5):
                slots.append({"slot_id": f"slot-{len(slots)+1:06d}", "family": family,
                              "condition": condition, "retrieval_mode": mode})
        for rank in range(1, 6):
            pair_id = f"c5-pair-{len(pair_reservations)+1:06d}"
            a_verdict = "PASS" if family_index % 2 == 0 else "FALSE_FAIL"
            b_verdict = "FALSE_FAIL" if a_verdict == "PASS" else "PASS"
            pair_reservations.append({
                "pair_id": pair_id, "family": family, "onset_rank": rank,
                "eligible_precursor_slot_ids_in_frozen_order": precursor_ids,
                "arm_a_verdict": a_verdict, "arm_b_verdict": b_verdict,
                "arm_execution_order": ["B", "A"] if rank % 2 else ["A", "B"],
                "branch_seed": 10000 + family_index * 5 + rank,
            })
            selected = rank <= min(secure_count, 5)
            invalid_pair = family_index == 1 and rank == 1 and selected
            pair_results.append({
                "pair_id": pair_id,
                "allocated_precursor_slot_id": precursor_ids[rank-1] if selected else None,
                "status": "INVALIDATED_PAIR" if invalid_pair else "VALID_PAIR" if selected else "UNUSED_NO_ONSET",
                "invalidation_reason": "synthetic branch abort" if invalid_pair else None,
            })
            for arm, verdict in (("A", a_verdict), ("B", b_verdict)):
                continuation_id = f"continuation-{len(continuation_reservations)+1:06d}"
                continuation_reservations.append({
                    "continuation_id": continuation_id, "pair_id": pair_id, "family": family,
                    "onset_rank": rank, "arm": arm, "public_verdict": verdict,
                    "episode_seed": 10000 + family_index * 5 + rank,
                    "post_verdict_decision_cap": 3,
                    "execution_rank_within_pair": pair_reservations[-1]["arm_execution_order"].index(arm) + 1,
                })
                if not selected:
                    continue
                invalid_branch = invalid_pair and verdict == "FALSE_FAIL"
                if invalid_branch:
                    cause, decisions = "INFRASTRUCTURE_FAILURE", 1
                elif verdict == "PASS":
                    cause, decisions = ("VOLUNTARY_STOP", 3) if variable and family_index == 0 and rank == 1 else ("VOLUNTARY_STOP", 2)
                elif family_index == 3 and variable:
                    cause, decisions = "TIMEOUT", 1
                elif family_index % 2 == 0 or not variable:
                    cause, decisions = "VOLUNTARY_STOP", 2
                else:
                    cause, decisions = "BUDGET_STOP", 3
                continuation_results.append({
                    "continuation_id": continuation_id,
                    "status": "INVALIDATED" if invalid_branch else "VALID",
                    "decisions_used": decisions, "terminal_cause": cause,
                    "candidate_sha256s": [_hash(4000 + family_index * 10 + rank)] if decisions else [],
                    "invalidation_reason": "synthetic branch abort" if invalid_branch else None,
                })
    plan = {
        "schema_version": "prospective-primary-main-plan-0.2.0", "phase": "main",
        "status": "PROPOSED_MAIN_UNGATED", "eligible_for_main_analysis": False,
        "main_execution_implemented": False, "family_count": 20,
        "planned_slot_count": 600, "planned_c5_pair_capacity": 100,
        "planned_c5_continuation_capacity": 200, "slots": slots,
        "c5_branch_pair_reservations": pair_reservations,
        "c5_continuation_reservations": continuation_reservations,
    }
    ledger = {
        "schema_version": VERSION, "phase": "synthetic_excluded",
        "eligible_for_main_analysis": False, "synthetic_fixture": True,
        "plan_content_sha256": _sha(plan),
        "precursor_results": precursor_results, "pair_results": pair_results,
        "continuation_results": continuation_results,
    }
    return plan, ledger


class C5FamilyLedgerTests(unittest.TestCase):
    def test_full_accounting_equal_family_effect_and_no_main_release(self) -> None:
        plan, ledger = _fixture()
        report = audit_excluded_synthetic_ledger(plan, ledger)
        self.assertEqual(report, audit_excluded_synthetic_ledger(plan, ledger))
        self.assertEqual(report["status"], "EXCLUDED_SYNTHETIC_LEDGER_AUDIT")
        self.assertFalse(report["main_inference_released"])
        self.assertFalse(report["oracle_onset_semantics_verified"])
        self.assertEqual(report["accounted_precursor_slots"], 200)
        self.assertEqual(report["reserved_pair_count"], 100)
        self.assertEqual(report["selected_onset_count"], 24)
        self.assertEqual(report["exploratory_onset_count"], 1)
        self.assertEqual(report["valid_pair_count"], 23)
        self.assertEqual(report["invalidated_pair_count"], 1)
        self.assertEqual(report["unused_pair_count"], 76)
        self.assertEqual(report["accounted_continuations"], 48)
        self.assertEqual(report["primary_c5_synthetic_diagnostic"]["n_contributing_families"], 19)
        self.assertEqual(report["primary_c5_synthetic_diagnostic"]["test_status"], "SYNTHETIC_T_DIAGNOSTIC_ONLY")
        by_family = {row["family"]: row for row in report["family_accounting"]}
        self.assertIsNone(by_family["family-01"]["D_f"])
        self.assertEqual(by_family["family-00"]["valid_pair_count"], 5)
        self.assertEqual(len(by_family["family-00"]["exploratory_onset_slot_ids"]), 1)
        effect = fmean(row["D_f"] for row in report["family_accounting"] if row["D_f"] is not None)
        self.assertAlmostEqual(report["primary_c5_synthetic_diagnostic"]["equal_family_mean_difference"], effect)
        pooled_pairs = fmean(row["paired_early_stop_difference"] for row in report["pair_accounting"]
                             if row.get("paired_early_stop_difference") is not None)
        self.assertNotAlmostEqual(effect, pooled_pairs)
        invalidated = next(row for row in report["pair_accounting"] if row["family"] == "family-01" and row["onset_rank"] == 1)
        self.assertIsNotNone(invalidated["allocated_precursor_slot_id"])
        self.assertIsNone(invalidated["paired_early_stop_difference"])
        # A valid timeout is a fixed-horizon zero; a decision-three voluntary stop is not early.
        timeout_pair = next(row for row in report["pair_accounting"] if row["family"] == "family-03" and row["onset_rank"] == 1)
        self.assertFalse(timeout_pair["branches_by_verdict"]["FALSE_FAIL"]["early_voluntary_stop"])
        edge_pair = next(row for row in report["pair_accounting"] if row["family"] == "family-00" and row["onset_rank"] == 1)
        self.assertFalse(edge_pair["branches_by_verdict"]["PASS"]["early_voluntary_stop"])

    def test_nonestimable_zero_reach_and_zero_variance(self) -> None:
        plan, ledger = _fixture(onset_families=14)
        report = audit_excluded_synthetic_ledger(plan, ledger)
        self.assertEqual(report["primary_c5_synthetic_diagnostic"]["test_status"],
                         "NONESTIMABLE_FEWER_THAN_15_FAMILIES")
        self.assertIsNone(report["primary_c5_synthetic_diagnostic"]["two_sided_p_value"])
        self.assertTrue(any(row["D_f"] is None for row in report["family_accounting"]))
        plan, ledger = _fixture(variable=False)
        report = audit_excluded_synthetic_ledger(plan, ledger)
        self.assertEqual(report["primary_c5_synthetic_diagnostic"]["test_status"],
                         "NONESTIMABLE_ZERO_BETWEEN_FAMILY_VARIANCE")
        self.assertIsNone(report["primary_c5_synthetic_diagnostic"]["two_sided_p_value"])

    def test_missing_or_replaced_slots_and_branches_fail_closed(self) -> None:
        plan, original = _fixture()
        for mutation, pattern in (
            (lambda row: row["precursor_results"].pop(), "partition"),
            (lambda row: row["pair_results"].pop(), "partition"),
            (lambda row: row["continuation_results"].pop(), "continuation"),
            (lambda row: row["pair_results"][0].update(allocated_precursor_slot_id=row["precursor_results"][1]["slot_id"]), "allocation"),
            (lambda row: row["pair_results"][0].update(status="UNUSED_NO_ONSET"), "onset cannot"),
            (lambda row: row["continuation_results"][0].update(decisions_used=4), "decisions"),
        ):
            ledger = copy.deepcopy(original)
            mutation(ledger)
            with self.subTest(pattern=pattern), self.assertRaisesRegex(C5LedgerError, pattern):
                audit_excluded_synthetic_ledger(plan, ledger)

    def test_pilot_or_claimed_main_is_rejected(self) -> None:
        plan, ledger = _fixture()
        for field, value in (("phase", "pilot"), ("phase", "main"),
                             ("eligible_for_main_analysis", True), ("synthetic_fixture", False)):
            changed = copy.deepcopy(ledger)
            changed[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(C5LedgerError):
                audit_excluded_synthetic_ledger(plan, changed)
        plan["status"] = "READY"
        with self.assertRaises(C5LedgerError):
            audit_excluded_synthetic_ledger(plan, ledger)

    def test_schedule_cell_or_orientation_drift_fails_even_when_rehashed(self) -> None:
        plan, ledger = _fixture()
        plan["slots"][10]["condition"] = "C4"
        ledger["plan_content_sha256"] = _sha(plan)
        with self.assertRaisesRegex(C5LedgerError, "six planned family cells"):
            audit_excluded_synthetic_ledger(plan, ledger)
        plan, ledger = _fixture()
        plan["c5_branch_pair_reservations"][0]["arm_a_verdict"] = "FALSE_FAIL"
        ledger["plan_content_sha256"] = _sha(plan)
        with self.assertRaisesRegex(C5LedgerError, "orientation"):
            audit_excluded_synthetic_ledger(plan, ledger)

    def test_holm_exactly_three_and_incomplete_family_is_nonestimable(self) -> None:
        result = holm_three_companions(dict(zip(COMPANIONS, (0.01, 0.04, 0.5))))
        self.assertEqual([row["holm_adjusted_p_value"] for row in result["rows"]],
                         [0.03, 0.08, 0.5])
        self.assertEqual([row["reject_at_familywise_0_05"] for row in result["rows"]],
                         [True, False, False])
        incomplete = holm_three_companions(dict(zip(COMPANIONS, (0.01, None, 0.5))))
        self.assertEqual(incomplete["status"], "NONESTIMABLE_INCOMPLETE_COMPANION_FAMILY")
        self.assertTrue(all(row["holm_adjusted_p_value"] is None for row in incomplete["rows"]))
        with self.assertRaises(C5LedgerError):
            holm_three_companions({COMPANIONS[0]: 0.01})
        with self.assertRaises(C5LedgerError):
            holm_three_companions(dict(zip(COMPANIONS, (0.01, float("nan"), 0.5))))


if __name__ == "__main__":
    unittest.main()

"""Integrity tests for the excluded temperature-0.3 replay, without model calls."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis import v7_temp_variance_20261101 as wave


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _journal(schedule: list[dict], *, pair_first: bool = False,
             stopped_before_dispatch: bool = False) -> list[dict]:
    rows = []
    def append(slot_id: str | None, state: str, **fields: object) -> None:
        rows.append({"sequence": len(rows) + 1, "slot_id": slot_id,
                     "state": state, **fields})
    for slot in schedule:
        append(slot["slot_id"], "SCHEDULED")
    if stopped_before_dispatch:
        append(schedule[0]["slot_id"], "INVALIDATED", error_type="VarianceWaveError")
        append(None, "WAVE_STOPPED", completed_slots=0,
               failed_slot_id=schedule[0]["slot_id"])
        return rows
    for index, slot in enumerate(schedule):
        append(slot["slot_id"], "PRECURSOR_START")
        onset = 1 if pair_first and index == 0 else None
        append(slot["slot_id"], "PRECURSOR_VERIFIED",
               receipt_sha256="a" * 64, secure_onset=onset)
        if onset is None:
            append(slot["slot_id"], "NO_ONSET")
        else:
            append(slot["slot_id"], "PAIR_START")
            append(slot["slot_id"], "PAIR_VERIFIED", pair_receipt_sha256="b" * 64)
    append(None, "WAVE_COMPLETE", completed_slots=32)
    return rows


class V7TempVarianceIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.schedule = wave.fixed_schedule()

    def events(self, rows: list[dict]) -> tuple[dict, str]:
        path = self.root / "events.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows),
                        encoding="utf-8")
        return wave._events(path, self.schedule)

    def test_fixed_schedule_has_32_ordered_balanced_slots(self) -> None:
        self.assertEqual(len(self.schedule), 32)
        self.assertEqual(self.schedule[0]["slot_id"], "csrf_origin-s101")
        self.assertEqual(self.schedule[-1]["slot_id"], "tls_hostname-s104")
        self.assertEqual([row["branch_seed"] for row in self.schedule[:4]],
                         [8000, 8001, 8002, 8003])
        for family in wave.FAMILIES:
            rows = [row for row in self.schedule if row["family"] == family]
            self.assertEqual([row["precursor_seed"] for row in rows], list(wave.SEEDS))
            self.assertEqual(sum(row["branch_seed"] % 2 == 0 for row in rows), 2)

    def test_complete_journal_keeps_all_slots_and_pair_on_onset(self) -> None:
        by_slot, status = self.events(_journal(self.schedule, pair_first=True))
        self.assertEqual(status, "WAVE_COMPLETE")
        self.assertEqual([row["state"] for row in by_slot[self.schedule[0]["slot_id"]]],
                         ["SCHEDULED", "PRECURSOR_START", "PRECURSOR_VERIFIED",
                          "PAIR_START", "PAIR_VERIFIED"])
        self.assertEqual([row["state"] for row in by_slot[self.schedule[1]["slot_id"]]][-1],
                         "NO_ONSET")

    def test_truncated_or_reordered_journal_is_rejected(self) -> None:
        rows = _journal(self.schedule)
        with self.assertRaisesRegex(RuntimeError, "terminal"):
            self.events(rows[:-1])
        rows = _journal(self.schedule)
        rows[32]["slot_id"] = self.schedule[1]["slot_id"]
        with self.assertRaisesRegex(RuntimeError, "fixed schedule order"):
            self.events(rows)
        rows = _journal(self.schedule)
        rows[-1]["completed_slots"] = 31
        with self.assertRaisesRegex(RuntimeError, "completed-slot"):
            self.events(rows)

    def test_preflight_failure_is_not_counted_as_a_completed_slot(self) -> None:
        by_slot, status = self.events(_journal(
            self.schedule, stopped_before_dispatch=True))
        self.assertEqual(status, "WAVE_STOPPED")
        self.assertEqual([row["state"] for row in by_slot[self.schedule[0]["slot_id"]]],
                         ["SCHEDULED", "INVALIDATED"])
        self.assertEqual(len(by_slot[self.schedule[1]["slot_id"]]), 1)

    def test_pair_failure_after_verified_onset_keeps_other_slots_scheduled(self) -> None:
        rows = _journal(self.schedule, stopped_before_dispatch=True)[:32]
        slot_id = self.schedule[0]["slot_id"]
        rows.extend([
            {"sequence": 33, "slot_id": slot_id, "state": "PRECURSOR_START"},
            {"sequence": 34, "slot_id": slot_id, "state": "PRECURSOR_VERIFIED",
             "receipt_sha256": "a" * 64, "secure_onset": 1},
            {"sequence": 35, "slot_id": slot_id, "state": "PAIR_START"},
            {"sequence": 36, "slot_id": slot_id, "state": "INVALIDATED",
             "error_type": "VarianceWaveError"},
            {"sequence": 37, "slot_id": None, "state": "WAVE_STOPPED",
             "completed_slots": 0, "failed_slot_id": slot_id},
        ])
        by_slot, status = self.events(rows)
        self.assertEqual(status, "WAVE_STOPPED")
        self.assertEqual(by_slot[slot_id][-1]["state"], "INVALIDATED")
        self.assertEqual(len(by_slot[self.schedule[1]["slot_id"]]), 1)
        rows[34]["state"] = "PAIR_VERIFIED"
        with self.assertRaisesRegex(RuntimeError, "PAIR_START"):
            self.events(rows)

    def test_unplanned_archive_entry_is_rejected(self) -> None:
        by_slot, _ = self.events(_journal(
            self.schedule, stopped_before_dispatch=True))
        (self.root / "unplanned_seed").mkdir()
        with self.assertRaisesRegex(RuntimeError, "unplanned top-level"):
            wave._check_layout(self.root, self.schedule, by_slot)

    def test_precursor_temperature_and_receipt_are_checked(self) -> None:
        row = self.schedule[0]
        precursor = self.root / "precursor"
        _write_json(precursor / "integrated_receipt.json", {"status": "example"})
        _write_json(precursor / "slot_receipt.json", {
            "actions": [{"action": "ATTEMPT", "candidate_sha256": "c" * 64},
                        {"action": "ATTEMPT", "candidate_sha256": "d" * 64}]})
        _write_json(precursor / "evaluation-000001.json", {
            "action": "ATTEMPT", "result": {
                "raw_test_result": "PASS", "strong_test_result": "PASS",
                "security_oracle_result": "SECURE"}})
        _write_json(precursor / "evaluation-000002.json", {
            "action": "ATTEMPT", "result": {
                "raw_test_result": "PASS", "strong_test_result": "FAIL",
                "security_oracle_result": "INSECURE"}})
        plan = {"slots": [{
            "family": row["family"], "condition": "C1", "episode_seed": 101,
            "retrieval_mode": "R0", "task_path": row["c1_task_path"],
            "proof_path": row["c1_proof_path"], "model": "qwen3:4b",
            "model_digest": wave.MODEL_DIGEST,
        }], "inference_config": {
            "temperature": 0.3, "max_steps": 6,
            "episode_timeout_seconds": 900, "request_timeout_seconds": 180}}
        _write_json(precursor / "plan_snapshot.json", plan)
        verified = {
            "phase": "pilot", "eligible_for_main_analysis": False,
            "main_dispatch_allowed": False,
            "status": "COMPLETED_EXCLUDED_VERIFIED_FINITE",
            "human_semantic_admission": False, "finite_reference_crosscheck": True,
            "error_type": None, "invalidation_reason": None, "decision_count": 2,
            "decision_evaluations": [{"path": "evaluation-000001.json"},
                                     {"path": "evaluation-000002.json"}],
            "first_secure_submission_decision": 1,
            "terminal_active_candidate_oracle_result": "INSECURE",
            "terminal_active_candidate_raw_test_result": "PASS",
        }
        event = {"receipt_sha256": wave.first._sha256(
            (precursor / "integrated_receipt.json").read_bytes()), "secure_onset": 1}
        with patch.object(wave, "verify_excluded_integrated", return_value=verified):
            result = wave._precursor(precursor, row, event)
            self.assertEqual(result["first_secure_submission_decision"], 1)
            self.assertEqual(result["raw_pass_oracle_insecure_attempts"], 1)
            plan["inference_config"]["temperature"] = 0.0
            _write_json(precursor / "plan_snapshot.json", plan)
            with self.assertRaisesRegex(RuntimeError, "temperature"):
                wave._precursor(precursor, row, event)

    def test_paired_discordance_has_explicit_indeterminate_category(self) -> None:
        def pair(truth: int | None, false: int | None) -> dict:
            return {"arms": {
                "TRUTHFUL_PASS": {"terminal_finite_property_regression": truth},
                "FALSE_FAIL": {"terminal_finite_property_regression": false},
            }}
        self.assertEqual(wave._discordance([
            pair(0, 1), pair(1, 0), pair(1, 1), pair(0, 0), pair(None, 1),
        ]), {
            "false_only_regression": 1, "truth_only_regression": 1,
            "both_regress": 1, "neither_regresses": 1, "indeterminate": 1,
        })


if __name__ == "__main__":
    unittest.main()

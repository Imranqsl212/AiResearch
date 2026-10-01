"""Synthetic-only failure injection for the append-only attempt journal.

The shared analysis fixture creates valid evaluator-owned receipts and logs in
a temporary directory. These are not agent observations or scientific results.
"""

import json
import tempfile
import unittest
from pathlib import Path

from analysis.pipeline import freeze_input_lock, verify_input_lock
from experiments.attempt_ledger import AttemptLedgerError, AttemptLedgerWriter


class AttemptLedgerTests(unittest.TestCase):
    def setUp(self):
        # Import locally so unittest discovery does not collect the helper class
        # a second time from this module.
        from test_analysis_pipeline import AnalysisPipelineTests

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.synthetic = AnalysisPipelineTests()
        self.manifest_path, self.coding_path = self.synthetic._build_main_fixture(self.root)
        self.schedule_path = self.root / "experiments/schedules/main-test.json"
        self.ledger_path = self.root / "experiments/ledgers/main-test.json"
        self.ledger_path.unlink()  # Only the generated temporary fixture ledger.
        self.run_dir = self.root / "experiments/runs/main-test"
        self.raw = {path.name: path.read_bytes() for path in self.run_dir.iterdir()}
        for path in self.run_dir.iterdir():
            path.unlink()  # Only generated temporary fixture artifacts.
        self.schedule = json.loads(self.schedule_path.read_text(encoding="utf-8"))
        self.slots = {slot["condition"]: slot["slot_id"] for slot in self.schedule["slots"]}
        self.tasks = [
            {"task_id": slot["task_id"], "condition": slot["condition"],
             "task_family": slot["task_family"]}
            for slot in self.schedule["slots"]
        ]
        self.writer = self._writer()

    def _writer(self):
        return AttemptLedgerWriter(
            root=self.root, manifest_path=self.manifest_path,
            schedule_path=self.schedule_path, tasks=self.tasks,
        )

    def _materialize(self, run_id):
        for suffix in ("jsonl", "receipt.json"):
            name = f"{run_id}.{suffix}"
            (self.run_dir / name).write_bytes(self.raw[name])

    def _selected(self, condition):
        run_id = f"run-{condition.lower()}"
        slot_id = self.slots[condition]
        self.writer.reserve(slot_id=slot_id, run_id=run_id)
        self._materialize(run_id)
        self.writer.complete(slot_id=slot_id, run_id=run_id)

    def _missing_other_slots(self, selected_condition):
        for condition, slot_id in self.slots.items():
            if condition != selected_condition:
                self.writer.mark_missing(slot_id=slot_id, reason="NOT_STARTED")

    def _abort(self, condition, run_id, *, after_action=False, after_stop=False,
               after_initial=False, after_handoff=False):
        slot_id = self.slots[condition]
        self.writer.reserve(slot_id=slot_id, run_id=run_id)
        self.synthetic._make_infrastructure_abort(
            self.root, run_id=run_id, task_id=f"task-{condition.lower()}",
            condition=condition, after_action=after_action, after_stop=after_stop,
            after_initial=after_initial, after_handoff=after_handoff,
        )
        self.writer.complete(slot_id=slot_id, run_id=run_id)

    def test_all_selected_attempts_survive_reopen_and_analysis_lock(self):
        for condition in ("RD", "UD"):
            self._selected(condition)
        self.writer = self._writer()
        for condition in ("RW", "UW"):
            self._selected(condition)
        path = self.writer.finalize()
        self.assertEqual(path, self.writer.finalize())
        ledger = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(ledger["slots"]), 4)
        self.assertTrue(all(row["status"] == "RECORDED" for row in ledger["slots"]))
        lock_path = self.root / "analysis/locks/main-test.json"
        lock = freeze_input_lock(
            root=self.root, manifest_path=self.manifest_path,
            lock_path=lock_path, coding_path=self.coding_path,
        )
        self.assertEqual(len(lock["runs"]), 4)
        self.assertEqual(len(verify_input_lock(self.root, lock_path)["attempts"]), 4)
        with self.assertRaisesRegex(AttemptLedgerError, "finalized ledger"):
            self.writer.reserve(slot_id=self.slots["RD"], run_id="later")

    def test_pending_reservation_survives_reopen_and_blocks_retry_and_finalization(self):
        slot_id = self.slots["RD"]
        self.writer.reserve(slot_id=slot_id, run_id="interrupted-before-log")
        self.writer = self._writer()
        with self.assertRaisesRegex(AttemptLedgerError, "pending or selected"):
            self.writer.reserve(slot_id=slot_id, run_id="retry")
        with self.assertRaisesRegex(AttemptLedgerError, "unresolved reservation"):
            self.writer.mark_missing(slot_id=slot_id, reason="SAFETY_HALT")
        self._missing_other_slots("RD")
        with self.assertRaisesRegex(AttemptLedgerError, "unresolved reservation"):
            self.writer.finalize()
        self.assertFalse(self.ledger_path.exists())

    def test_pre_action_setup_failure_can_retry_once_and_remains_in_ledger(self):
        self._abort("RD", "setup-rd")
        self._selected("RD")
        self._missing_other_slots("RD")
        ledger = json.loads(self.writer.finalize().read_text(encoding="utf-8"))
        rd = next(row for row in ledger["slots"] if row["slot_id"] == self.slots["RD"])
        self.assertEqual([item["classification"] for item in rd["attempts"]],
                         ["SETUP_FAILURE", "SELECTED"])
        lock = freeze_input_lock(
            root=self.root, manifest_path=self.manifest_path,
            lock_path=self.root / "analysis/locks/main-test.json", coding_path=None,
        )
        self.assertEqual(len(lock["attempts"]), 2)
        self.assertEqual(len(lock["runs"]), 1)

    def test_post_action_and_post_stop_aborts_are_selected_not_retryable(self):
        for after_action, after_stop in ((True, False), (False, True)):
            with self.subTest(after_action=after_action, after_stop=after_stop):
                # Separate conditions keep immutable journal history distinct.
                condition = "RD" if after_action else "UD"
                run_id = f"abort-{condition.lower()}"
                self._abort(condition, run_id, after_action=after_action,
                            after_stop=after_stop)
                with self.assertRaisesRegex(AttemptLedgerError, "pending or selected"):
                    self.writer.reserve(slot_id=self.slots[condition], run_id=f"retry-{condition.lower()}")
                with self.assertRaisesRegex(AttemptLedgerError, "selected attempt"):
                    self.writer.mark_missing(slot_id=self.slots[condition], reason="SAFETY_HALT")
        for condition in ("RW", "UW"):
            self.writer.mark_missing(slot_id=self.slots[condition], reason="NOT_STARTED")
        ledger = json.loads(self.writer.finalize().read_text(encoding="utf-8"))
        selected = [row for row in ledger["slots"] if row["status"] == "RECORDED"]
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(row["attempts"][-1]["classification"] == "SELECTED" for row in selected))

    def test_abort_after_initial_task_exposure_cannot_be_retried(self):
        self._abort("RD", "after-exposure", after_initial=True)
        with self.assertRaisesRegex(AttemptLedgerError, "pending or selected"):
            self.writer.reserve(slot_id=self.slots["RD"], run_id="retry-after-exposure")
        self._missing_other_slots("RD")
        ledger = json.loads(self.writer.finalize().read_text(encoding="utf-8"))
        rd = next(row for row in ledger["slots"] if row["slot_id"] == self.slots["RD"])
        self.assertEqual(rd["attempts"], [{"run_id": "after-exposure", "classification": "SELECTED"}])

    def test_abort_during_task_handoff_cannot_be_retried(self):
        self._abort("RD", "during-handoff", after_handoff=True)
        with self.assertRaisesRegex(AttemptLedgerError, "pending or selected"):
            self.writer.reserve(slot_id=self.slots["RD"], run_id="retry-handoff")

    def test_three_setup_failures_require_explicit_exhaustion_reason(self):
        for index in range(1, 4):
            self._abort("RD", f"setup-{index}")
        with self.assertRaisesRegex(AttemptLedgerError, "maximum three"):
            self.writer.reserve(slot_id=self.slots["RD"], run_id="setup-4")
        with self.assertRaisesRegex(AttemptLedgerError, "reason disagrees"):
            self.writer.mark_missing(slot_id=self.slots["RD"], reason="RESOURCE_LIMIT")
        self.writer.mark_missing(slot_id=self.slots["RD"], reason="SETUP_FAILURES_EXHAUSTED")
        self._missing_other_slots("RD")
        ledger = json.loads(self.writer.finalize().read_text(encoding="utf-8"))
        rd = next(row for row in ledger["slots"] if row["slot_id"] == self.slots["RD"])
        self.assertEqual(rd["status"], "MISSING")
        self.assertEqual(len(rd["attempts"]), 3)

    def test_duplicate_run_id_is_rejected(self):
        self.writer.reserve(slot_id=self.slots["RD"], run_id="unique")
        with self.assertRaisesRegex(AttemptLedgerError, "already been reserved"):
            self.writer.reserve(slot_id=self.slots["UD"], run_id="unique")

    def test_existing_raw_attempt_cannot_be_reserved_retroactively(self):
        self._materialize("run-rd")
        with self.assertRaisesRegex(AttemptLedgerError, "reservation must precede"):
            self.writer.reserve(slot_id=self.slots["RD"], run_id="run-rd")

    def test_orphan_raw_attempt_blocks_finalization(self):
        self._selected("RD")
        self._missing_other_slots("RD")
        (self.run_dir / "orphan.jsonl").write_bytes(self.raw["run-rd.jsonl"])
        (self.run_dir / "orphan.receipt.json").write_bytes(self.raw["run-rd.receipt.json"])
        with self.assertRaisesRegex(AttemptLedgerError, "unreserved, partial, or missing attempts"):
            self.writer.finalize()
        self.assertFalse(self.ledger_path.exists())

    def test_raw_or_receipt_mutation_is_detected_after_completion(self):
        self._selected("RD")
        self._missing_other_slots("RD")
        receipt_path = self.run_dir / "run-rd.receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["errors"].append("post-completion change")
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaisesRegex(AttemptLedgerError, "changed after journal write"):
            self.writer.finalize()
        self.assertFalse(self.ledger_path.exists())

    def test_mutated_setup_attempt_cannot_unlock_retry(self):
        self._abort("RD", "setup-rd")
        receipt_path = self.run_dir / "setup-rd.receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["errors"].append("post-completion change")
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaisesRegex(AttemptLedgerError, "changed after journal write"):
            self.writer.reserve(slot_id=self.slots["RD"], run_id="retry")

    def test_interrupted_partial_raw_file_blocks_final_ledger(self):
        for slot_id in self.slots.values():
            self.writer.mark_missing(slot_id=slot_id, reason="NOT_STARTED")
        (self.run_dir / ".unfinished.jsonl.tmp").write_text("partial", encoding="utf-8")
        with self.assertRaisesRegex(AttemptLedgerError, "partial"):
            self.writer.finalize()

    def test_unexpected_journal_entry_blocks_further_writes(self):
        self.writer.mark_missing(slot_id=self.slots["RD"], reason="NOT_STARTED")
        (self.writer.journal_dir / "untracked-slot").mkdir()
        with self.assertRaisesRegex(AttemptLedgerError, "unexpected journal entries"):
            self.writer.mark_missing(slot_id=self.slots["UD"], reason="NOT_STARTED")

    def test_symlinked_generated_artifact_parent_is_rejected(self):
        destination = self.root / "redirect-target"
        destination.mkdir()
        (self.root / "experiments/attempt_journal").symlink_to(
            destination, target_is_directory=True
        )
        with self.assertRaisesRegex(AttemptLedgerError, "redirected or escapes"):
            self.writer.reserve(slot_id=self.slots["RD"], run_id="refuse-symlink")

    def test_manifest_change_after_initialization_blocks_writes(self):
        self.manifest_path.write_text(self.manifest_path.read_text(encoding="utf-8") + "\n",
                                      encoding="utf-8")
        with self.assertRaisesRegex(AttemptLedgerError, "changed after writer initialization"):
            self.writer.mark_missing(slot_id=self.slots["RD"], reason="NOT_STARTED")


if __name__ == "__main__":
    unittest.main()

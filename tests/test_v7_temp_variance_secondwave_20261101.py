"""V2 schedule and archive-boundary tests, without model calls or run data."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis import v7_temp_variance_20261101 as v1
from analysis import v7_temp_variance_secondwave_20261101 as v2
from experiments import run_v7_temp_variance_secondwave_excluded as dispatcher


class V7TempVarianceSecondWaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.schedule = v2.fixed_schedule()

    def test_v2_schedule_is_frozen_and_distinct_from_v1(self) -> None:
        self.assertEqual(len(self.schedule), 32)
        self.assertEqual(self.schedule, dispatcher.schedule())
        self.assertEqual(self.schedule[0]["slot_id"], "csrf_origin-s201")
        self.assertEqual(self.schedule[-1]["slot_id"], "tls_hostname-s204")
        self.assertEqual([row["branch_seed"] for row in self.schedule[:4]],
                         [9000, 9001, 9002, 9003])
        self.assertEqual([row["branch_seed"] for row in self.schedule[-4:]],
                         [9070, 9071, 9072, 9073])
        self.assertFalse({row["slot_id"] for row in self.schedule} &
                         {row["slot_id"] for row in v1.fixed_schedule()})
        self.assertNotEqual(v2.ARCHIVE, v1.ARCHIVE)
        self.assertNotEqual(v2.PLAN, v1.PLAN)
        for family in v2.FAMILIES:
            rows = [row for row in self.schedule if row["family"] == family]
            self.assertEqual([row["precursor_seed"] for row in rows], [201, 202, 203, 204])
            self.assertEqual(sum(row["branch_seed"] % 2 == 0 for row in rows), 2)

    def test_v2_event_parser_keeps_technical_stop_separate(self) -> None:
        rows = []
        def append(slot_id: str | None, state: str, **fields: object) -> None:
            rows.append({"sequence": len(rows) + 1, "slot_id": slot_id,
                         "state": state, **fields})
        for slot in self.schedule:
            append(slot["slot_id"], "SCHEDULED")
        append(self.schedule[0]["slot_id"], "PRECURSOR_START")
        append(self.schedule[0]["slot_id"], "INVALIDATED",
               error_type="VarianceWaveError")
        append(None, "WAVE_STOPPED", completed_slots=0,
               failed_slot_id=self.schedule[0]["slot_id"])
        journal = self.root / "events.jsonl"
        journal.write_text("".join(json.dumps(row) + "\n" for row in rows),
                           encoding="utf-8")
        by_slot, status = v1._events(journal, self.schedule)
        self.assertEqual(status, "WAVE_STOPPED")
        self.assertEqual([event["state"] for event in by_slot[self.schedule[0]["slot_id"]]],
                         ["SCHEDULED", "PRECURSOR_START", "INVALIDATED"])
        self.assertEqual(len(by_slot[self.schedule[1]["slot_id"]]), 1)

    def test_v2_preflight_rejects_v1_schedule_and_missing_identity_timeout(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "V2 preflight schedule"):
            v2._check_preflight({"schedule": v1.fixed_schedule()}, self.schedule)
        manifest = {
            "schedule": self.schedule, "schema_version": v2.SCHEMA_VERSION,
            "phase": "excluded_post_failure_pilot",
            "eligible_for_main_analysis": False,
            "no_replacement": True, "output_root": v2.OUTPUT_ROOT,
            "prior_stopped_wave": "/private/tmp/research-v7-temp03-four-seed-20261101",
            "separate_from_prior_wave": True,
            "plan_path": v1.PLAN.relative_to(v1.ROOT).as_posix(),
            "plan_sha256": v1.first._sha256(v1.PLAN.read_bytes()),
            "v7_index_path": v2.INDEX.relative_to(v2.ROOT).as_posix(),
            "v7_index_sha256": v2.INDEX_SHA256,
            "model": {"name": "qwen3:4b", "digest": v2.MODEL_DIGEST},
            "runtime": {"cli_version": "0.35.0", "server_version": "0.35.0",
                        "model": {"name": "qwen3:4b", "digest": v2.MODEL_DIGEST}},
            "inference_config": {
                "temperature": 0.3, "retrieval_mode": "R0", "condition": "C1",
                "request_timeout_seconds": 180, "precursor_decision_cap": 6,
                "continuation_decision_cap_per_arm": 3,
            },
        }
        with patch.object(v2, "PLAN", v1.PLAN):
            with self.assertRaisesRegex(RuntimeError, "inference config"):
                v2._check_preflight(manifest, self.schedule)

    def test_v2_layout_rejects_output_for_unrun_seed(self) -> None:
        by_slot = {row["slot_id"]: [{"state": "SCHEDULED"}]
                   for row in self.schedule}
        (self.root / "csrf_origin" / "seed201").mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, "unscheduled output"):
            v2._check_layout(self.root, self.schedule, by_slot)

    def test_v2_precursor_requires_60_second_timeout_and_wrapper_sources(self) -> None:
        precursor = self.root / "precursor"
        precursor.mkdir()
        snapshot = {
            "inference_config": {"identity_timeout_seconds": 60},
            "source_file_sha256s": {
                "experiments/run_main_integrated_v2_excluded.py": "a" * 64,
                "experiments/run_main_c5_integrated_v2_excluded.py": "b" * 64,
            },
        }
        (precursor / "plan_snapshot.json").write_text(
            json.dumps(snapshot), encoding="utf-8")
        with patch.object(v2.v1, "_precursor", return_value={"verified_status": "example"}):
            self.assertEqual(v2._precursor(precursor, self.schedule[0], {})[
                "verified_status"], "example")
            snapshot["inference_config"]["identity_timeout_seconds"] = 10
            (precursor / "plan_snapshot.json").write_text(
                json.dumps(snapshot), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "identity timeout"):
                v2._precursor(precursor, self.schedule[0], {})


if __name__ == "__main__":
    unittest.main()

"""Integrity checks for the excluded all-family live feasibility schedule."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.run_full_catalog_live_feasibility import _plan, _validate_plan, prepare


MODEL_DIGEST = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"


class FullCatalogLiveFeasibilityTests(unittest.TestCase):
    def test_deterministic_40_slot_schedule_and_archive_tamper_detection(self) -> None:
        parameters = dict(model="qwen3:4b", model_digest=MODEL_DIGEST,
                          seed=20261005, temperature=0.3)
        plan = _plan(**parameters)
        self.assertEqual(plan, _plan(**parameters))
        self.assertEqual(len(plan["slots"]), 40)
        self.assertEqual(len({(slot["family"], slot["condition"])
                              for slot in plan["slots"]}), 40)
        self.assertEqual(plan["eligible_for_main_analysis"], False)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "excluded"
            prepared = prepare(output, **parameters)
            self.assertEqual(prepared["planned_slots"], 40)
            self.assertEqual(_validate_plan(output), plan)
            with self.assertRaises(FileExistsError):
                prepare(output, **parameters)
            archived = output / "source_archive" / "agent" / "v1_ollama_adapter.py"
            archived.write_bytes(archived.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "source archive hash differs"):
                _validate_plan(output)

    def test_schedule_cannot_be_promoted_to_main(self) -> None:
        parameters = dict(model="qwen3:4b", model_digest=MODEL_DIGEST,
                          seed=20261005, temperature=0.3)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "excluded"
            prepare(output, **parameters)
            schedule_path = output / "schedule.json"
            schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
            schedule["phase"] = "main"
            schedule["eligible_for_main_analysis"] = True
            schedule_path.write_text(json.dumps(schedule), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "excluded live feasibility"):
                _validate_plan(output)


if __name__ == "__main__":
    unittest.main()

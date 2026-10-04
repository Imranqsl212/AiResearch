"""Excluded pilot audits must account for every slot and reject changed bytes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from analysis.audit_excluded_v1 import (
    PilotAuditError, audit_c5_probe, audit_seeded_block, validate_seeded_partition,
)
from experiments import run_c5_false_failure_probe_v1 as probe


ROOT = Path(__file__).resolve().parents[1]


def _bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ExcludedPilotAuditTests(unittest.TestCase):
    def test_missing_raw_archive_fails_closed_at_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "raw-archive-not-present"
            for kind in ("seeded", "c5-probe"):
                completed = subprocess.run(
                    [sys.executable, "-m", "analysis.audit_excluded_v1", kind,
                     "--block-dir", str(missing)],
                    cwd=ROOT, capture_output=True, text=True, check=False,
                )
                self.assertEqual(completed.returncode, 2)
                report = json.loads(completed.stdout)
                self.assertEqual(report["status"], "INVALID_OR_INCOMPLETE_EXCLUDED_PILOT")
                self.assertNotIn("population_rates", report)

    def test_paired_schedule_rejects_missing_duplicate_and_replaced_slots(self) -> None:
        slots = [
            {"index": index, "slot_id": f"slot-{index}", "episode_id": f"episode-{index}",
             "seed": seed, "condition": condition}
            for index, (seed, condition) in enumerate(
                ((11, "C1"), (11, "C2"), (11, "C4"),
                 (23, "C1"), (23, "C2"), (23, "C4")), 1)
        ]
        rows = [{"slot_index": slot["index"], "slot_id": slot["slot_id"],
                 "episode_id": slot["episode_id"], "seed": slot["seed"],
                 "condition": slot["condition"]} for slot in slots]
        validate_seeded_partition(slots, rows)
        with self.assertRaises(PilotAuditError):
            validate_seeded_partition(slots, rows[:-1])
        with self.assertRaises(PilotAuditError):
            validate_seeded_partition(slots, rows[:-1] + [rows[0]])
        bad_slots = [dict(slot) for slot in slots]
        bad_slots[-1]["condition"] = "C2"
        with self.assertRaises(PilotAuditError):
            validate_seeded_partition(bad_slots, rows)

    def test_local_seeded_block_if_archived_here_stays_excluded(self) -> None:
        block = ROOT / "experiments/runs/v1_live_r0_c1_c2_c4_seeds_20261004"
        if not block.is_dir():
            self.skipTest("local ignored pilot archive is absent")
        report = audit_seeded_block(block, source_root=ROOT)
        self.assertEqual(report["status"], "VALIDATED_EXCLUDED_PILOT_BLOCK")
        self.assertEqual(report["planned_slots"], 9)
        self.assertEqual(report["validated_slots"], 9)
        self.assertEqual(report["invalidated_slots"], 0)
        self.assertEqual(report["main_eligible_episodes"], 0)
        self.assertIsNone(report["population_rates"])
        self.assertIsNone(report["causal_effects"])
        self.assertEqual(report["observed_secure_candidate_episodes"], 3)
        inventory = report["condition_inventory"]
        self.assertEqual(inventory["C1"]["observed_initial_evidence_episodes"], 0)
        self.assertEqual(inventory["C2"]["observed_initial_evidence_episodes"], 3)
        self.assertEqual(inventory["C2"]["observed_impossibility_proof_exposed_episodes"], 0)
        self.assertEqual(inventory["C2"]["observed_submissions_after_impossibility_proof"], 0)
        self.assertEqual(inventory["C4"]["observed_initial_evidence_episodes"], 3)
        self.assertEqual(inventory["C4"]["observed_impossibility_proof_exposed_episodes"], 3)
        self.assertEqual(inventory["C4"]["observed_submissions_after_impossibility_proof"], 7)
        self.assertTrue(all(row["submissions_after_impossibility_proof"] is None
                            for row in report["rows"] if row["condition"] == "C2"))

    def test_c5_probe_audits_scripted_handoff_and_rejects_tampered_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            block = Path(directory) / "probe"
            probe.prepare(block, seed=7)
            schedule = json.loads((block / "schedule.json").read_text())
            completed = []
            for arm in schedule["order"]:
                folder = block / "arms" / arm.lower()
                request_path = folder / "request.raw.json"
                response_path = folder / "response.raw.json"
                action_path = folder / "agent.action.json"
                decision = {"assessment": "insufficient_evidence", "action": "stop",
                            "reason": "One supplied response is not a repeated trial."}
                response_path.write_bytes(_bytes({"done": True, "done_reason": "stop",
                                                  "message": {"content": json.dumps(decision)}}))
                action_path.write_bytes(_bytes({
                    "actor": "agent", "agent_generated": True, "kind": "stop",
                    "assessment": decision["assessment"], "reason": decision["reason"],
                    "raw_request_sha256": _sha(request_path),
                    "raw_response_sha256": _sha(response_path),
                }))
                completed.append({"arm": arm, "request_sha256": _sha(request_path),
                                  "response_sha256": _sha(response_path),
                                  "agent_action_sha256": _sha(action_path)})
            (block / "run.receipt.json").write_bytes(_bytes({
                "phase": "excluded_pilot", "status": "COMPLETE_EXCLUDED_PILOT",
                "eligible_for_main_analysis": False, "scripted_submission_counts_as_agent_action": False,
                "preflight_sha256": _sha(block / "preflight.json"),
                "model": schedule["model"], "seed": schedule["seed"],
                "temperature": schedule["temperature"],
                "max_output_tokens": schedule["max_output_tokens"],
                "model_requests_attempted": 4, "agent_actions_recorded": 4,
                "error": None, "completed_arms": completed,
                "expected_arms": list(probe.ARMS),
            }))
            report = audit_c5_probe(block, source_root=ROOT)
            self.assertEqual(report["validated_arms"], 4)
            self.assertEqual(report["main_eligible_episodes"], 0)
            self.assertEqual(report["scripted_submission_agent_actions"], 0)
            self.assertTrue(report["withheld_public_inputs_identical"])
            self.assertTrue(report["withheld_response_bytes_identical"])
            self.assertEqual(set(report["assessment_by_arm"].values()), {"insufficient_evidence"})
            self.assertIsNone(report["population_rates"])
            action_path = block / "arms" / completed[0]["arm"].lower() / "agent.action.json"
            action = json.loads(action_path.read_text())
            action["assessment"] = "evaluator_mismatch"
            action_path.write_bytes(_bytes(action))
            with self.assertRaisesRegex(PilotAuditError, "raw model artifacts"):
                audit_c5_probe(block, source_root=ROOT)


if __name__ == "__main__":
    unittest.main()

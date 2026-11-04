"""Pre-dispatch guards for the fixed six-slot excluded feedback probe."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from experiments import run_v7_feedback_replication_20261104_excluded as wave
from experiments.main_c5_integrated_excluded import ExcludedIntegratedC5Pair, verify_excluded_c5_pair
from experiments.main_integrated_excluded import ExcludedIntegratedFiniteEpisode, verify_excluded_integrated


def _response(action: str, payload: dict | None = None) -> bytes:
    return json.dumps({"done": True, "message": {"content": json.dumps({
        "action": action, "payload": payload or {},
    }, sort_keys=True)}}, sort_keys=True).encode()


class FakeTransport:
    def __init__(self, responses: list[bytes]) -> None:
        self.responses = list(responses)

    def model_identity(self) -> dict[str, str]:
        return dict(wave.MODEL)

    def send(self, request_bytes: bytes, *, endpoint: str) -> bytes:
        if endpoint != "/api/chat" or not request_bytes:
            raise AssertionError("unexpected fake dispatch")
        return self.responses.pop(0)


class FeedbackReplicationWaveTests(unittest.TestCase):
    def test_schedule_order_balance_and_frozen_sources(self) -> None:
        rows = wave.schedule()
        self.assertEqual([(r["family"], r["precursor_seed"], r["branch_seed"])
                          for r in rows], list(zip(
            ("csrf_origin", "key_rotation", "key_rotation", "csrf_origin",
             "csrf_origin", "key_rotation"), (302, 302, 303, 303, 304, 304),
            range(13000, 13006))))
        self.assertEqual(len(wave.core._catalog_inventory(rows)), 9)
        sources = wave._sources(rows)
        self.assertIn(wave.RUNNER_PATH, sources)
        self.assertIn(wave.PLAN_PATH, sources)
        self.assertIn("benchmark/finite_batch_c_reference_v7.py", sources)
        self.assertIn("experiments/run_v7_temp_variance_excluded.py", sources)
        self.assertIn("experiments/run_v7_temp_variance_secondwave_excluded.py", sources)
        for row in rows:
            plan = wave._precursor_plan(row)
            self.assertEqual(plan["inference_config"]["temperature"], 0.3)
            self.assertEqual(plan["slots"][0]["episode_seed"], row["precursor_seed"])
            self.assertEqual(plan["inference_config"]["request_timeout_seconds"], 300)
            self.assertEqual(plan["inference_config"]["identity_timeout_seconds"], 60)
        self.assertEqual(sum(r["branch_seed"] % 2 == 0 for r in rows), 3)

    def test_directional_truth_table_keeps_denial_and_unsafe_accept_distinct(self) -> None:
        csrf = json.loads((wave.ROOT / wave.schedule()[0]["c5_task_path"]).read_bytes())
        key = json.loads((wave.ROOT / wave.schedule()[1]["c5_task_path"]).read_bytes())
        csrf_table = wave.directional_world_table(csrf, {"mode": "reject_all"})
        key_table = wave.directional_world_table(key, {"mode": "accept_known"})
        self.assertEqual([r["outcome"] for r in csrf_table].count("FALSE_DENIAL"), 1)
        self.assertEqual([r["outcome"] for r in csrf_table].count("UNSAFE_ACCEPT"), 0)
        self.assertEqual([r["outcome"] for r in key_table].count("UNSAFE_ACCEPT"), 1)
        self.assertEqual([r["outcome"] for r in key_table].count("FALSE_DENIAL"), 0)
        malformed = wave.directional_world_table(csrf, {":mode": "reject_all"})
        self.assertEqual({r["outcome"] for r in malformed}, {"INDETERMINATE"})

    def test_preflight_requires_committed_inputs_before_model_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(wave, "OUTPUT_ROOT", Path(temporary) / "new-run"), \
             mock.patch.object(wave.core, "_committed_head", side_effect=ValueError("not committed")), \
             mock.patch.object(wave.v2, "_runtime_identity_v2") as identity:
            with self.assertRaisesRegex(ValueError, "not committed"):
                wave._preflight(wave.schedule())
            identity.assert_not_called()

    def test_existing_output_root_blocks_preflight_before_any_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(wave, "OUTPUT_ROOT", Path(temporary)), \
             mock.patch.object(wave.core, "_catalog_inventory") as catalog, \
             mock.patch.object(wave.v2, "_runtime_identity_v2") as identity:
            with self.assertRaisesRegex(wave.core.VarianceWaveError, "cannot rerun"):
                wave._preflight(wave.schedule())
            catalog.assert_not_called()
            identity.assert_not_called()

    def test_no_onset_accounts_for_all_six_without_pair_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "wave"
            manifest = {"source_file_sha256s": {}, "catalog_file_sha256s": {},
                        "plan_path": wave.PLAN_PATH, "plan_sha256": "test"}
            with mock.patch.object(wave, "OUTPUT_ROOT", output), \
                 mock.patch.object(wave, "_preflight", return_value=manifest), \
                 mock.patch.object(wave.core, "_assert_inputs_unchanged"), \
                 mock.patch.object(wave.core, "_sha", return_value="receipt-hash"), \
                 mock.patch.object(wave, "_run_precursor",
                                   return_value={"first_secure_submission_decision": None}), \
                 mock.patch.object(wave, "_run_pair") as pair:
                result = wave.run_wave()
            pair.assert_not_called()
            self.assertEqual(result["status"], "WAVE_COMPLETE")
            self.assertEqual(result["completed_slots"], 6)
            events = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
            self.assertEqual(sum(e["state"] == "SCHEDULED" for e in events), 6)
            self.assertEqual(sum(e["state"] == "NO_ONSET" for e in events), 6)
            self.assertEqual(events[-1]["state"], "WAVE_COMPLETE")

    def test_first_technical_failure_stops_and_leaves_scheduled_slots_unstarted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "wave"
            manifest = {"source_file_sha256s": {}, "catalog_file_sha256s": {},
                        "plan_path": wave.PLAN_PATH, "plan_sha256": "test"}
            with mock.patch.object(wave, "OUTPUT_ROOT", output), \
                 mock.patch.object(wave, "_preflight", return_value=manifest), \
                 mock.patch.object(wave.core, "_assert_inputs_unchanged"), \
                 mock.patch.object(wave, "_run_precursor", side_effect=RuntimeError("transport failed")), \
                 mock.patch.object(wave, "_run_pair") as pair:
                result = wave.run_wave()
            pair.assert_not_called()
            self.assertEqual(result["status"], "WAVE_STOPPED")
            self.assertEqual(result["completed_slots"], 0)
            events = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
            self.assertEqual(sum(e["state"] == "SCHEDULED" for e in events), 6)
            self.assertEqual(sum(e["state"] == "PRECURSOR_START" for e in events), 1)
            self.assertEqual(sum(e["state"] == "INVALIDATED" for e in events), 1)
            self.assertEqual(sum(e["state"] == "UNSTARTED" for e in events), 5)
            self.assertEqual(events[-1]["state"], "WAVE_STOPPED")

    def test_fake_precursor_and_pair_replay(self) -> None:
        slot = wave.schedule()[0]
        plan = wave._precursor_plan(slot)
        with tempfile.TemporaryDirectory() as temporary:
            precursor_dir = Path(temporary) / "precursor"
            episode = ExcludedIntegratedFiniteEpisode(
                plan=plan, slot_id="excluded-slot-000001", source_root=wave.ROOT,
                output_dir=precursor_dir,
                observed_inference_config=plan["inference_config"],
                transport=FakeTransport([
                    _response("attempt", {"candidate": {"mode": "token_and_origin"}}),
                    _response("terminate"),
                ]))
            episode.run()
            precursor = verify_excluded_integrated(precursor_dir, source_root=wave.ROOT)
            self.assertEqual(precursor["first_secure_submission_decision"], 1)
            pair_dir = Path(temporary) / "pair"
            pair = ExcludedIntegratedC5Pair(
                precursor_dir=precursor_dir, source_root=wave.ROOT,
                output_dir=pair_dir, c5_task_path=slot["c5_task_path"],
                c5_proof_path=slot["c5_proof_path"], branch_seed=slot["branch_seed"],
                arm_order=("TRUTHFUL_PASS", "FALSE_FAIL"),
                transport=FakeTransport([_response("terminate"), _response("terminate")]))
            pair.run()
            receipt = verify_excluded_c5_pair(
                pair_dir, precursor_dir=precursor_dir, source_root=wave.ROOT)
            self.assertEqual(receipt["status"], "COMPLETED_EXCLUDED_C5_PAIR")


if __name__ == "__main__":
    unittest.main()

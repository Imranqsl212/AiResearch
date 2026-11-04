"""Pre-dispatch guards for the fixed excluded cross-family probe."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from experiments import run_v7_crossfamily_20261104_excluded as wave
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


class CrossFamilyWaveTests(unittest.TestCase):
    def test_fixed_schedule_and_source_inventory(self) -> None:
        rows = wave.schedule()
        self.assertEqual([row["family"] for row in rows],
                         ["key_rotation", "signature_algorithm", "csrf_origin"])
        self.assertEqual([row["precursor_seed"] for row in rows], [301, 301, 301])
        self.assertEqual([row["branch_seed"] for row in rows], [12000, 12001, 12002])
        self.assertEqual(len(wave.core._catalog_inventory(rows)), 13)
        sources = wave._sources(rows)
        self.assertIn(wave.RUNNER_PATH, sources)
        self.assertIn(wave.PLAN_PATH, sources)
        for row in rows:
            plan = wave._precursor_plan(row)
            self.assertEqual(plan["inference_config"]["temperature"], 0.3)
            self.assertEqual(plan["inference_config"]["request_timeout_seconds"], 300)
            self.assertEqual(plan["inference_config"]["identity_timeout_seconds"], 60)

    def test_preflight_requires_committed_frozen_inputs_before_model_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(wave, "OUTPUT_ROOT", Path(temporary) / "new-run"), \
             mock.patch.object(wave.core, "_committed_head", side_effect=ValueError("not committed")), \
             mock.patch.object(wave.v2, "_runtime_identity_v2") as identity:
            with self.assertRaisesRegex(ValueError, "not committed"):
                wave._preflight(wave.schedule())
            identity.assert_not_called()

    def test_no_onset_accounting_never_opens_a_pair(self) -> None:
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
            self.assertEqual(result["completed_slots"], 3)
            events = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
            self.assertEqual(sum(event["state"] == "SCHEDULED" for event in events), 3)
            self.assertEqual(sum(event["state"] == "NO_ONSET" for event in events), 3)
            self.assertEqual(events[-1]["state"], "WAVE_COMPLETE")

    def test_precursor_and_pair_replay_with_frozen_plan(self) -> None:
        slot = wave.schedule()[0]
        plan = wave._precursor_plan(slot)
        with tempfile.TemporaryDirectory() as temporary:
            precursor_dir = Path(temporary) / "precursor"
            episode = ExcludedIntegratedFiniteEpisode(
                plan=plan, slot_id="excluded-slot-000001", source_root=wave.ROOT,
                output_dir=precursor_dir,
                observed_inference_config=plan["inference_config"],
                transport=FakeTransport([
                    _response("attempt", {"candidate": {"mode": "check_current"}}),
                    _response("terminate"),
                ]))
            episode.run()
            precursor = verify_excluded_integrated(precursor_dir, source_root=wave.ROOT)
            self.assertEqual(precursor["first_secure_submission_decision"], 1)
            pair_dir = Path(temporary) / "pair"
            pair = ExcludedIntegratedC5Pair(
                precursor_dir=precursor_dir, source_root=wave.ROOT,
                output_dir=pair_dir, c5_task_path=slot["c5_task_path"],
                c5_proof_path=slot["c5_proof_path"],
                branch_seed=slot["branch_seed"],
                arm_order=("TRUTHFUL_PASS", "FALSE_FAIL"),
                transport=FakeTransport([_response("terminate"), _response("terminate")]))
            pair.run()
            verified = verify_excluded_c5_pair(
                pair_dir, precursor_dir=precursor_dir, source_root=wave.ROOT)
            self.assertEqual(verified["status"], "COMPLETED_EXCLUDED_C5_PAIR")


if __name__ == "__main__":
    unittest.main()

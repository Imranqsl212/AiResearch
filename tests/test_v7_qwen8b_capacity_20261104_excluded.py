"""Pre-dispatch guards for the fixed excluded Qwen3:8b capacity probe."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from experiments import run_v7_qwen8b_capacity_20261104_excluded as wave
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
        request = json.loads(request_bytes)
        if (endpoint != "/api/chat" or request["model"] != "qwen3:8b"
                or request["stream"] is not False or request["think"] is not False):
            raise AssertionError("unexpected fake dispatch")
        return self.responses.pop(0)


class Qwen8bCapacityTests(unittest.TestCase):
    def test_schedule_is_fixed_and_balanced_with_source_inventory(self) -> None:
        rows = wave.schedule()
        self.assertEqual([(r["family"], r["precursor_seed"], r["branch_seed"])
                          for r in rows], [
            ("csrf_origin", 501, 15000), ("tls_hostname", 502, 15001),
            ("tls_hostname", 503, 15002), ("csrf_origin", 504, 15003)])
        self.assertEqual(wave.MODEL, {"name": "qwen3:8b",
            "digest": "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"})
        self.assertEqual(len(wave.core._catalog_inventory(rows)), 9)
        self.assertEqual(sum(r["branch_seed"] % 2 == 0 for r in rows), 2)
        for family in ("csrf_origin", "tls_hostname"):
            self.assertEqual({r["branch_seed"] % 2 for r in rows if r["family"] == family}, {0, 1})
        sources = wave._sources(rows)
        self.assertIn(wave.RUNNER_PATH, sources)
        self.assertIn(wave.PLAN_PATH, sources)
        for row in rows:
            plan = wave._precursor_plan(row)
            self.assertEqual(plan["slots"][0]["episode_seed"], row["precursor_seed"])
            self.assertEqual(plan["slots"][0]["model"], wave.MODEL["name"])
            self.assertEqual(plan["inference_config"]["temperature"], 0.3)

    def test_runtime_identity_checks_qwen8b_digest(self) -> None:
        with mock.patch.object(wave.subprocess, "run", return_value=mock.Mock(
                 stdout="ollama version is 0.35.0", stderr="")), \
             mock.patch.object(wave.core, "_server_version", return_value="0.35.0"), \
             mock.patch.object(wave, "_transport") as transport:
            transport.return_value.model_identity.return_value = dict(wave.MODEL)
            self.assertEqual(wave._runtime_identity()["model"], wave.MODEL)
            transport.return_value.model_identity.return_value = dict(wave.core.MODEL)
            with self.assertRaisesRegex(wave.core.VarianceWaveError, "Qwen3:8b digest"):
                wave._runtime_identity()

    def test_preflight_rejects_uncommitted_or_existing_root_before_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(wave, "OUTPUT_ROOT", Path(temporary) / "new-run"), \
             mock.patch.object(wave.core, "_committed_head", side_effect=ValueError("not committed")), \
             mock.patch.object(wave, "_runtime_identity") as identity:
            with self.assertRaisesRegex(ValueError, "not committed"):
                wave._preflight(wave.schedule())
            identity.assert_not_called()
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(wave, "OUTPUT_ROOT", Path(temporary)), \
             mock.patch.object(wave, "_runtime_identity") as identity:
            with self.assertRaisesRegex(wave.core.VarianceWaveError, "cannot rerun"):
                wave._preflight(wave.schedule())
            identity.assert_not_called()

    def test_no_onset_is_accounted_without_pair_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "wave"
            with mock.patch.object(wave, "OUTPUT_ROOT", output), \
                 mock.patch.object(wave, "_preflight", return_value={}), \
                 mock.patch.object(wave.core, "_assert_inputs_unchanged"), \
                 mock.patch.object(wave.core, "_sha", return_value="receipt-hash"), \
                 mock.patch.object(wave, "_run_precursor",
                     return_value={"first_secure_submission_decision": None}), \
                 mock.patch.object(wave, "_run_pair") as pair:
                result = wave.run_wave()
            pair.assert_not_called()
            self.assertEqual(result["status"], "WAVE_COMPLETE")
            events = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
            self.assertEqual(sum(e["state"] == "NO_ONSET" for e in events), 4)
            self.assertEqual(events[-1]["state"], "WAVE_COMPLETE")

    def test_first_error_marks_remaining_slots_unstarted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "wave"
            with mock.patch.object(wave, "OUTPUT_ROOT", output), \
                 mock.patch.object(wave, "_preflight", return_value={}), \
                 mock.patch.object(wave.core, "_assert_inputs_unchanged"), \
                 mock.patch.object(wave, "_run_precursor", side_effect=RuntimeError("transport")):
                result = wave.run_wave()
            self.assertEqual(result["status"], "WAVE_STOPPED")
            events = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
            self.assertEqual(sum(e["state"] == "INVALIDATED" for e in events), 1)
            self.assertEqual(sum(e["state"] == "UNSTARTED" for e in events), 3)

    def test_fake_qwen8b_precursor_and_pair_replay(self) -> None:
        slot = wave.schedule()[0]
        plan = wave._precursor_plan(slot)
        with tempfile.TemporaryDirectory() as temporary:
            precursor_dir = Path(temporary) / "precursor"
            episode = ExcludedIntegratedFiniteEpisode(
                plan=plan, slot_id="excluded-slot-000001", source_root=wave.ROOT,
                output_dir=precursor_dir, observed_inference_config=plan["inference_config"],
                transport=FakeTransport([
                    _response("attempt", {"candidate": {"mode": "token_and_origin"}}),
                    _response("terminate"),
                ]))
            episode.run()
            receipt = verify_excluded_integrated(precursor_dir, source_root=wave.ROOT)
            self.assertEqual(receipt["first_secure_submission_decision"], 1)
            pair_dir = Path(temporary) / "pair"
            pair = ExcludedIntegratedC5Pair(
                precursor_dir=precursor_dir, source_root=wave.ROOT,
                output_dir=pair_dir, c5_task_path=slot["c5_task_path"],
                c5_proof_path=slot["c5_proof_path"], branch_seed=slot["branch_seed"],
                arm_order=("TRUTHFUL_PASS", "FALSE_FAIL"),
                transport=FakeTransport([_response("terminate"), _response("terminate")]))
            pair.run()
            self.assertEqual(verify_excluded_c5_pair(
                pair_dir, precursor_dir=precursor_dir, source_root=wave.ROOT)["status"],
                "COMPLETED_EXCLUDED_C5_PAIR")


if __name__ == "__main__":
    unittest.main()

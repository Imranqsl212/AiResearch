"""No-model checks for the fixed excluded temperature-variance dispatcher."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from experiments import run_v7_temp_variance_excluded as wave


def _events(root: Path) -> list[dict]:
    return [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]


class VarianceDispatcherTests(unittest.TestCase):
    def test_dry_run_prints_exact_balanced_32_slot_schedule(self) -> None:
        rows = wave.schedule()
        self.assertEqual(len(rows), 32)
        self.assertEqual(len({row["slot_id"] for row in rows}), 32)
        self.assertEqual([row["family"] for row in rows[::4]], list(wave.FAMILIES))
        for family_index, family in enumerate(wave.FAMILIES):
            group = rows[4 * family_index:4 * family_index + 4]
            self.assertEqual([row["precursor_seed"] for row in group], list(wave.SEEDS))
            self.assertEqual([row["branch_seed"] for row in group],
                             [8000 + 10 * family_index + i for i in range(4)])
            self.assertEqual(sum(row["branch_seed"] % 2 == 0 for row in group), 2)
            self.assertTrue(all(row["family"] == family for row in group))
        with (mock.patch("sys.argv", ["dispatcher"]),
              mock.patch.object(wave, "_preflight") as preflight,
              contextlib.redirect_stdout(io.StringIO()) as output):
            self.assertEqual(wave.main(), 0)
        preflight.assert_not_called()
        printed = json.loads(output.getvalue())
        self.assertEqual(printed["schedule"], rows)
        self.assertEqual(printed["temperature"], 0.3)

    def test_catalog_has_exact_fixed_index_and_tasks(self) -> None:
        inventory = wave._catalog_inventory(wave.schedule())
        self.assertEqual(inventory[wave.INDEX_PATH], wave.INDEX_SHA256)
        self.assertEqual(len(inventory), 33)  # index plus C1/C5 task and proof for eight families

    def test_existing_output_root_blocks_preflight_before_runtime_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(wave, "_runtime_identity") as runtime:
                with self.assertRaisesRegex(wave.VarianceWaveError, "already exists"):
                    wave._preflight(Path(temp), wave.schedule())
            runtime.assert_not_called()

    def test_preflight_records_committed_plan_digest_and_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = root / wave.PLAN_PATH
            plan.parent.mkdir(parents=True)
            plan.write_text("frozen fixture plan\n")
            runtime = {"cli_version": wave.OLLAMA_VERSION,
                       "server_version": wave.OLLAMA_VERSION, "model": wave.MODEL}
            with (mock.patch.object(wave, "ROOT", root),
                  mock.patch.object(wave, "_catalog_inventory", return_value={"index": "a"}),
                  mock.patch.object(wave, "_source_inventory", return_value={"runner": "b"}),
                  mock.patch.object(wave, "_committed_head", return_value="c" * 40) as commit,
                  mock.patch.object(wave, "_runtime_identity", return_value=runtime)):
                manifest = wave._preflight(root / "output", wave.schedule())
            self.assertEqual(manifest["plan_path"], wave.PLAN_PATH)
            self.assertEqual(manifest["plan_sha256"],
                             hashlib.sha256(plan.read_bytes()).hexdigest())
            self.assertEqual(manifest["source_commit"], "c" * 40)
            self.assertEqual(manifest["runtime"], runtime)
            self.assertEqual(len(manifest["schedule"]), 32)
            commit.assert_called_once()
            self.assertIn(wave.PLAN_PATH, commit.call_args.args[0])

    def test_runtime_identity_rejects_version_or_model_drift(self) -> None:
        cli = subprocess.CompletedProcess(["ollama", "--version"], 0,
                                          "ollama version is 0.35.0\n", "")
        with (mock.patch.object(wave.subprocess, "run", return_value=cli),
              mock.patch.object(wave, "_server_version", return_value="0.35.0"),
              mock.patch.object(wave, "ExcludedOllamaHTTPTransport") as transport):
            transport.return_value.model_identity.return_value = dict(wave.MODEL)
            self.assertEqual(wave._runtime_identity()["model"], wave.MODEL)
            transport.return_value.model_identity.return_value = {
                "name": wave.MODEL["name"], "digest": "a" * 64}
            with self.assertRaisesRegex(wave.VarianceWaveError, "differs"):
                wave._runtime_identity()
        with (mock.patch.object(wave.subprocess, "run", return_value=cli),
              mock.patch.object(wave, "_server_version", return_value="0.34.0"),
              mock.patch.object(wave, "ExcludedOllamaHTTPTransport") as transport):
            transport.return_value.model_identity.return_value = dict(wave.MODEL)
            with self.assertRaisesRegex(wave.VarianceWaveError, "differs"):
                wave._runtime_identity()

    def test_dispatch_invokes_once_and_preserves_subprocess_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            argv = ["fake-python", "-m", "fake-runner"]
            result = subprocess.CompletedProcess(argv, 0, '{"status":"ok"}\n', "")
            with mock.patch.object(wave.subprocess, "run", return_value=result) as run:
                wave._dispatch(argv, root, "csrf_origin-s101", "precursor")
            run.assert_called_once()
            log = json.loads((root / "dispatch_logs" /
                              "csrf_origin-s101.precursor.json").read_text())
            self.assertEqual(log["argv"], argv)
            self.assertEqual(log["returncode"], 0)

    def test_complete_wave_pairs_only_verified_onsets_without_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "wave"
            manifest = {"schedule": wave.schedule(), "phase": "excluded_pilot"}

            def precursor(slot: dict, output: Path) -> dict:
                receipt = output / slot["precursor_dir"] / "integrated_receipt.json"
                receipt.parent.mkdir(parents=True)
                receipt.write_text("{}")
                return {"first_secure_submission_decision":
                        1 if slot["precursor_seed"] == 101 else None}

            def pair(slot: dict, output: Path) -> dict:
                receipt = output / slot["pair_dir"] / "pair_receipt.json"
                receipt.parent.mkdir(parents=True)
                receipt.write_text("{}")
                return {"status": "COMPLETED_EXCLUDED_C5_PAIR"}

            with (mock.patch.object(wave, "_preflight", return_value=manifest),
                  mock.patch.object(wave, "_assert_inputs_unchanged"),
                  mock.patch.object(wave, "_run_precursor", side_effect=precursor) as run_precursor,
                  mock.patch.object(wave, "_run_pair", side_effect=pair) as run_pair):
                result = wave.run_wave(root)
            self.assertEqual(result["status"], "WAVE_COMPLETE")
            self.assertEqual(result["completed_slots"], 32)
            self.assertEqual(run_precursor.call_count, 32)
            self.assertEqual(run_pair.call_count, 8)
            events = _events(root)
            self.assertEqual([row["state"] for row in events[:32]], ["SCHEDULED"] * 32)
            self.assertEqual(events[-1]["state"], "WAVE_COMPLETE")
            self.assertEqual(sum(row["state"] == "NO_ONSET" for row in events), 24)
            self.assertEqual(sum(row["state"] == "PAIR_VERIFIED" for row in events), 8)
            self.assertEqual([row["sequence"] for row in events],
                             list(range(1, len(events) + 1)))

    def test_technical_failure_stops_wave_with_remaining_slots_unrun(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "wave"

            def precursor(slot: dict, output: Path) -> dict:
                if slot["precursor_seed"] == 102:
                    raise wave.VarianceWaveError("fixture transport failure")
                receipt = output / slot["precursor_dir"] / "integrated_receipt.json"
                receipt.parent.mkdir(parents=True)
                receipt.write_text("{}")
                return {"first_secure_submission_decision": None}

            with (mock.patch.object(wave, "_preflight", return_value={}),
                  mock.patch.object(wave, "_assert_inputs_unchanged"),
                  mock.patch.object(wave, "_run_precursor", side_effect=precursor) as run_precursor,
                  mock.patch.object(wave, "_run_pair") as run_pair):
                result = wave.run_wave(root)
            self.assertEqual(result["status"], "WAVE_STOPPED")
            self.assertEqual(result["completed_slots"], 1)
            self.assertEqual(result["failed_slot_id"], "csrf_origin-s102")
            self.assertEqual(run_precursor.call_count, 2)
            run_pair.assert_not_called()
            events = _events(root)
            self.assertEqual(events[-2]["state"], "INVALIDATED")
            self.assertEqual(events[-1]["state"], "WAVE_STOPPED")
            self.assertEqual(sum(row["state"] == "SCHEDULED" for row in events), 32)


if __name__ == "__main__":
    unittest.main()

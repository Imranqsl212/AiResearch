"""No-model checks for the separate post-failure V2 variance wave."""

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

from experiments import main_ollama_transport_excluded as transport
from experiments import run_main_c5_integrated_v2_excluded as pair_runner
from experiments import run_main_integrated_v2_excluded as precursor_runner
from experiments import run_v7_temp_variance_excluded as v1
from experiments import run_v7_temp_variance_secondwave_excluded as v2
from experiments.main_c5_integrated_excluded import verify_excluded_c5_pair
from experiments.main_integrated_excluded import verify_excluded_integrated
from tests.test_main_integrated_excluded import FakeTransport, _response


class SecondWaveTests(unittest.TestCase):
    def test_separate_root_seeds_schema_and_balanced_order(self) -> None:
        self.assertNotEqual(v2.OUTPUT_ROOT, v1.OUTPUT_ROOT)
        self.assertNotEqual(v2.SCHEMA_VERSION, v1.SCHEMA_VERSION)
        self.assertEqual(v2.SEEDS, (201, 202, 203, 204))
        rows = v2.schedule()
        self.assertEqual(len(rows), 32)
        self.assertTrue({row["slot_id"] for row in rows}.isdisjoint(
            {row["slot_id"] for row in v1.schedule()}))
        for family_index, family in enumerate(v1.FAMILIES):
            group = rows[4 * family_index:4 * family_index + 4]
            self.assertEqual([row["family"] for row in group], [family] * 4)
            self.assertEqual([row["precursor_seed"] for row in group], list(v2.SEEDS))
            self.assertEqual([row["branch_seed"] for row in group],
                             [9000 + 10 * family_index + i for i in range(4)])
            self.assertEqual(sum(row["branch_seed"] % 2 == 0 for row in group), 2)
        with (mock.patch("sys.argv", ["secondwave"]),
              mock.patch.object(v2, "_preflight") as preflight,
              contextlib.redirect_stdout(io.StringIO()) as output):
            self.assertEqual(v2.main(), 0)
        preflight.assert_not_called()
        printed = json.loads(output.getvalue())
        self.assertEqual(printed["schema_version"], v2.SCHEMA_VERSION)
        self.assertEqual(printed["schedule"], rows)
        self.assertEqual(printed["identity_timeout_seconds"], 60)
        with (mock.patch("sys.argv", ["secondwave", "--output-dir", str(v1.OUTPUT_ROOT)]),
              mock.patch.object(v2, "run_wave") as run,
              contextlib.redirect_stderr(io.StringIO())):
            with self.assertRaises(SystemExit):
                v2.main()
        run.assert_not_called()

    def test_source_inventory_binds_v2_and_sixty_second_transport(self) -> None:
        sources = v2._source_inventory(v2.schedule())
        self.assertIn("experiments/run_v7_temp_variance_secondwave_excluded.py", sources)
        self.assertIn("experiments/run_v7_temp_variance_excluded.py", sources)
        self.assertIn("experiments/run_main_integrated_v2_excluded.py", sources)
        self.assertIn("experiments/run_main_c5_integrated_v2_excluded.py", sources)
        self.assertIn("experiments/main_ollama_transport_excluded.py", sources)
        instance = transport.ExcludedOllamaHTTPTransport(
            model_name=v1.MODEL["name"], model_digest=v1.MODEL["digest"])
        self.assertEqual(instance.identity_timeout_seconds, 10.0)
        self.assertEqual(v2.RUNNER_TIMEOUT_SECONDS, 2400)

    def test_both_v2_wrappers_bind_sixty_seconds_and_verify_archives(self) -> None:
        class V2FakeTransport(FakeTransport):
            def model_identity(self) -> dict[str, str]:
                return dict(precursor_runner.MODEL)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            slot = v2.schedule()[0]
            proof = json.loads((v2.ROOT / slot["c1_proof_path"]).read_text())
            secure = proof["satisfying_candidates"][0]
            precursor_dir = root / "precursor"
            fake = V2FakeTransport([
                _response("attempt", {"candidate": secure}), _response("terminate")])
            argv = ["precursor", "--output-dir", str(precursor_dir),
                    "--task-path", slot["c1_task_path"],
                    "--proof-path", slot["c1_proof_path"], "--seed", "201"]
            with (mock.patch("sys.argv", argv),
                  mock.patch.object(precursor_runner, "ExcludedOllamaHTTPTransport",
                                    return_value=fake) as make_transport,
                  contextlib.redirect_stdout(io.StringIO())):
                self.assertEqual(precursor_runner.main(), 0)
            self.assertEqual(make_transport.call_args.kwargs["identity_timeout_seconds"], 60)
            plan = json.loads((precursor_dir / "plan_snapshot.json").read_text())
            self.assertEqual(plan["inference_config"]["temperature"], 0.3)
            self.assertEqual(plan["inference_config"]["identity_timeout_seconds"], 60)
            for path in precursor_runner.WRAPPER_SOURCES:
                self.assertEqual(plan["source_file_sha256s"][path],
                                 hashlib.sha256((v2.ROOT / path).read_bytes()).hexdigest())
            request = json.loads((precursor_dir / "request-000001.bin").read_bytes())
            self.assertEqual(request["options"]["temperature"], 0.3)
            self.assertEqual(request["options"]["seed"], 201)
            verified = verify_excluded_integrated(precursor_dir, source_root=v2.ROOT)
            self.assertEqual(verified["first_secure_submission_decision"], 1)

            pair_dir = root / "pair"
            pair_fake = V2FakeTransport([_response("terminate"), _response("terminate")])
            pair_argv = ["pair", "--precursor-dir", str(precursor_dir),
                         "--output-dir", str(pair_dir),
                         "--c5-task-path", slot["c5_task_path"],
                         "--c5-proof-path", slot["c5_proof_path"],
                         "--branch-seed", "9000"]
            with (mock.patch("sys.argv", pair_argv),
                  mock.patch.object(pair_runner, "ExcludedOllamaHTTPTransport",
                                    return_value=pair_fake) as make_pair_transport,
                  contextlib.redirect_stdout(io.StringIO())):
                self.assertEqual(pair_runner.main(), 0)
            self.assertEqual(make_pair_transport.call_args.kwargs[
                "identity_timeout_seconds"], 60)
            receipt = verify_excluded_c5_pair(
                pair_dir, precursor_dir=precursor_dir, source_root=v2.ROOT)
            self.assertEqual(receipt["status"], "COMPLETED_EXCLUDED_C5_PAIR")

    def test_preflight_records_separate_plan_and_stopped_prior_wave(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = root / v2.PLAN_PATH
            plan.parent.mkdir(parents=True)
            plan.write_text("separate V2 fixture plan\n")
            runtime = {"cli_version": "0.35.0", "server_version": "0.35.0",
                       "model": v1.MODEL}
            with (mock.patch.object(v2, "ROOT", root),
                  mock.patch.object(v1, "_catalog_inventory", return_value={"index": "a"}),
                  mock.patch.object(v2, "_source_inventory", return_value={"runner": "b"}),
                  mock.patch.object(v1, "_committed_head", return_value="c" * 40),
                  mock.patch.object(v2, "_runtime_identity_v2", return_value=runtime)):
                manifest = v2._preflight(root / "v2", v2.schedule())
            self.assertEqual(manifest["schema_version"], v2.SCHEMA_VERSION)
            self.assertEqual(manifest["phase"], "excluded_post_failure_pilot")
            self.assertFalse(manifest["eligible_for_main_analysis"])
            self.assertEqual(manifest["plan_path"], v2.PLAN_PATH)
            self.assertEqual(manifest["plan_sha256"],
                             hashlib.sha256(plan.read_bytes()).hexdigest())
            self.assertEqual(manifest["prior_stopped_wave"], str(v1.OUTPUT_ROOT))
            self.assertEqual(manifest["inference_config"]["identity_timeout_seconds"], 60)

    def test_existing_v2_root_blocks_before_runtime_or_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(v2, "_runtime_identity_v2") as runtime:
                with self.assertRaisesRegex(v1.VarianceWaveError, "already exists"):
                    v2._preflight(Path(temp), v2.schedule())
            runtime.assert_not_called()

    def test_one_technical_failure_stops_without_retry_or_touching_v1(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "v2"
            def precursor(slot: dict, output: Path) -> dict:
                if slot["precursor_seed"] == 202:
                    raise v1.VarianceWaveError("fixture identity timeout")
                receipt = output / slot["precursor_dir"] / "integrated_receipt.json"
                receipt.parent.mkdir(parents=True)
                receipt.write_text("{}")
                return {"first_secure_submission_decision": None}

            with (mock.patch.object(v2, "_preflight", return_value={}),
                  mock.patch.object(v1, "_assert_inputs_unchanged"),
                  mock.patch.object(v2, "_run_precursor", side_effect=precursor) as run_precursor,
                  mock.patch.object(v2, "_run_pair") as run_pair):
                result = v2._run_wave_at(root)
            self.assertEqual(result["status"], "WAVE_STOPPED")
            self.assertEqual(result["completed_slots"], 1)
            self.assertEqual(result["failed_slot_id"], "csrf_origin-s202")
            self.assertEqual(run_precursor.call_count, 2)
            run_pair.assert_not_called()
            events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
            self.assertEqual(events[-2]["state"], "INVALIDATED")
            self.assertEqual(events[-1]["state"], "WAVE_STOPPED")
            self.assertEqual(sum(row["state"] == "SCHEDULED" for row in events), 32)

    def test_v2_preflight_identity_uses_sixty_seconds_without_model_post(self) -> None:
        cli = subprocess.CompletedProcess(["ollama", "--version"], 0,
                                          "ollama version is 0.35.0\n", "")
        with (mock.patch.object(v2.subprocess, "run", return_value=cli),
              mock.patch.object(v1, "_server_version", return_value="0.35.0"),
              mock.patch.object(v2, "ExcludedOllamaHTTPTransport") as make_transport):
            make_transport.return_value.model_identity.return_value = dict(v1.MODEL)
            self.assertEqual(v2._runtime_identity_v2()["model"], v1.MODEL)
        self.assertEqual(make_transport.call_args.kwargs["identity_timeout_seconds"], 60)
        make_transport.return_value.model_identity.assert_called_once()


if __name__ == "__main__":
    unittest.main()

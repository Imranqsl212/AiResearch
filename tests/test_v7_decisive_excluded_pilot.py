"""Protocol and oracle checks for the separately versioned v7 pilot."""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from benchmark import finite_batch_c_v7 as evaluator
from analysis.v1_pipeline import V1ValidationError, load_episode
from experiments import run_v7_decisive_excluded_pilot as pilot


class DecisiveExcludedPilotTests(unittest.TestCase):
    digest = "a" * 64

    def test_prescheduled_three_seed_cells_and_write_once_source_archive(self) -> None:
        schedule = pilot.plan(model_digest=self.digest, runtime_version="0.35.0")
        self.assertFalse(schedule["eligible_for_main_analysis"])
        self.assertEqual(len(schedule["slots"]), 30)
        self.assertEqual(len({row["episode_id"] for row in schedule["slots"]}), 30)
        self.assertEqual(Counter((row["family"], row["condition"])
                                 for row in schedule["slots"]),
                         Counter({(family, condition): 3 for family in pilot.FAMILIES
                                  for condition in pilot.CONDITIONS}))
        seeds = defaultdict(set)
        for row in schedule["slots"]:
            seeds[(row["family"], row["repeat"])].add(row["inference_seed"])
        self.assertTrue(all(len(values) == 1 for values in seeds.values()))
        with tempfile.TemporaryDirectory(prefix="v7-decisive-test-") as temporary:
            output = Path(temporary) / "block"
            pilot.prepare(output, model_digest=self.digest, runtime_version="0.35.0")
            self.assertEqual(pilot._validate_schedule(output), schedule)
            with self.assertRaises(FileExistsError):
                pilot.prepare(output, model_digest=self.digest, runtime_version="0.35.0")
            archived = output / "source_archive" / "benchmark" / "finite_batch_c_v7.py"
            archived.write_bytes(archived.read_bytes() + b"\nmodified\n")
            with self.assertRaisesRegex(ValueError, "archived source differs"):
                pilot._validate_schedule(output)

    def test_truthful_evidence_and_hidden_veto_have_distinct_oracle_states(self) -> None:
        schedule = pilot.plan(model_digest=self.digest, runtime_version="0.35.0")
        for family in pilot.FAMILIES:
            by_condition = {
                row["condition"]: json.loads((pilot.ROOT / row["task_path"]).read_text())
                for row in schedule["slots"] if row["family"] == family and row["repeat"] == 1
            }
            c1, c3, c4, c5 = (by_condition[condition]
                               for condition in ("C1", "C3", "C4", "C5"))
            secure_mode = evaluator.certify_task(c1)["satisfying_candidates"][0]
            self.assertEqual(evaluator.evaluate_candidate(c1, secure_mode)["benchmark_verdict"], "PASS")
            mismatch = evaluator.evaluate_candidate(c5, secure_mode)
            self.assertEqual((mismatch["security_oracle_result"], mismatch["benchmark_verdict"]),
                             ("SECURE", "FAIL"))
            self.assertEqual(c3["worlds"], c4["worlds"])
            self.assertEqual(evaluator.certify_task(c3)["satisfying_candidates"], [])
            self.assertEqual(evaluator.certify_task(c4)["satisfying_candidates"], [])
            starter3 = evaluator.evaluate_candidate(c3, c3["starter_candidate"])
            starter4 = evaluator.evaluate_candidate(c4, c4["starter_candidate"])
            self.assertIsNone(starter3["feedback_evidence"])
            self.assertEqual(starter4["feedback_evidence"],
                             evaluator.certify_task(c4)["contradiction_witness"])


class RelocatedV7EpisodeTests(unittest.TestCase):
    """The original checkout remains present during these fail-closed checks."""

    def _copy_runtime(self, destination: Path) -> None:
        for package in ("agent", "analysis", "benchmark", "experiments", "reproduction"):
            shutil.copytree(
                pilot.ROOT / package, destination / package,
                ignore=shutil.ignore_patterns("runs", "__pycache__", "*.pyc"),
            )

    @staticmethod
    def _run(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(root)
        return subprocess.run(
            [sys.executable, "-B", *arguments], cwd=root, env=environment,
            capture_output=True, text=True, check=False,
        )

    def _replay(self, root: Path, manifest_path: Path) -> subprocess.CompletedProcess[str]:
        script = (
            "import json, sys\n"
            "from pathlib import Path\n"
            "from analysis.v1_pipeline import load_episode\n"
            "row = load_episode(Path(sys.argv[1]), source_root=Path(sys.argv[2]))\n"
            "print(json.dumps({key: row[key] for key in "
            "('proof_verified', 'candidate_replay_verified', 'git_commit_verified')}))\n"
        )
        return self._run(root, "-c", script, str(manifest_path), str(root))

    def _copy_episode(self, destination: Path) -> tuple[Path, dict]:
        relative = Path(
            "experiments/runs/v7_decisive_excluded_20261005_v1/slot-000022/"
            "v7-environment_injection-c1-r2.manifest.json"
        )
        original = pilot.ROOT / relative
        manifest = json.loads(original.read_text(encoding="utf-8"))
        paths = [original]
        paths.extend(Path(value) for key, value in manifest.items() if key.endswith("_path"))
        paths.extend(Path(row["path"]) for row in manifest["provider_request_archive"])
        for path in paths:
            target = destination / path.relative_to(pilot.ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        return destination / relative, manifest

    def test_relocated_manifest_replays_without_original_path_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="v7-relocated-") as temporary:
            root = Path(temporary)
            self._copy_runtime(root)
            manifest_path, manifest = self._copy_episode(root)
            with self.assertRaisesRegex(V1ValidationError, "imported evaluator differs"):
                load_episode(manifest_path, source_root=root)
            replay = self._replay(root, manifest_path)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertEqual(json.loads(replay.stdout), {
                "proof_verified": True, "candidate_replay_verified": True,
                "git_commit_verified": False,
            })
            request = root / Path(manifest["provider_request_archive"][0]["path"]).relative_to(pilot.ROOT)
            request.unlink()
            self.assertIn("file is missing", self._replay(root, manifest_path).stderr)
            request.symlink_to(manifest["provider_request_archive"][0]["path"])
            self.assertIn("outside declared source root", self._replay(root, manifest_path).stderr)
            request.unlink()
            shutil.copy2(manifest["provider_request_archive"][0]["path"], request)
            request.write_bytes(request.read_bytes() + b"\n")
            self.assertIn("archive bytes differ", self._replay(root, manifest_path).stderr)
            shutil.copy2(manifest["provider_request_archive"][0]["path"], request)
            (root / "benchmark/finite_batch_c_v7.py").unlink()
            self.assertIn("source differs from captured bytes", self._replay(root, manifest_path).stderr)

    def test_relocated_manifest_rejects_recorded_path_outside_checkout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="v7-relocated-") as temporary:
            root = Path(temporary)
            self._copy_runtime(root)
            manifest_path, manifest = self._copy_episode(root)
            manifest["task_path"] = "/private/tmp/unrelated-v7-task.json"
            body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
            manifest["manifest_sha256"] = hashlib.sha256(
                json.dumps(body, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(V1ValidationError, "outside original checkout"):
                load_episode(manifest_path, source_root=root)

    def test_both_v7_audits_replay_from_local_copy_and_reject_missing_input(self) -> None:
        with tempfile.TemporaryDirectory(prefix="v7-audit-relocated-") as temporary:
            root = Path(temporary)
            self._copy_runtime(root)
            pilot_relative = Path("experiments/runs/v7_decisive_excluded_20261005_v1")
            fork_relative = Path("experiments/runs/v7_decisive_c5_fork_20261005_v1")
            for relative in (pilot_relative, fork_relative):
                shutil.copytree(pilot.ROOT / relative, root / relative)
            pilot_check = self._run(root, "-m", "analysis.audit_v7_decisive_excluded_pilot", "--check")
            self.assertEqual(pilot_check.returncode, 0, pilot_check.stderr)
            self.assertEqual(json.loads(pilot_check.stdout)["valid_slots"], 30)
            fork_check = self._run(root, "-m", "analysis.audit_v7_decisive_c5_fork", "--check")
            self.assertEqual(fork_check.returncode, 0, fork_check.stderr)
            self.assertEqual(json.loads(fork_check.stdout)["status"],
                             "VALID_EXCLUDED_DESCRIPTIVE_ONLY")
            local_initial = root / fork_relative / "truthful_pass.initial_request.json"
            local_initial.unlink()
            rejected = self._run(root, "-m", "analysis.audit_v7_decisive_c5_fork", "--check")
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("file is missing", rejected.stderr)


if __name__ == "__main__":
    unittest.main()

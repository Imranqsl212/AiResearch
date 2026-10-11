"""Offline, excluded-only collector and replay checks for batch-C v7."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from agent.v1_ollama_adapter import V1OllamaAdapter
from analysis.v1_pipeline import V1ValidationError, load_episode
from benchmark.finite_family_registry import family_module
from experiments.v1_collector import V1CollectionError, collect_episode


ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "benchmark" / "tasks" / "v7_batch_c"
INDEX = json.loads((INDEX_DIR / "index.json").read_text(encoding="utf-8"))
V7_FILES = (
    "benchmark/finite_batch_c_v7.py", "benchmark/finite_batch_c_reference_v7.py",
)


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _row(family: str, condition: str) -> dict:
    return next(row for row in INDEX["tasks"]
                if row["family"] == family and row["condition"] == condition)


class BatchCV7ExcludedIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)

    def _collect(self, family: str, condition: str, candidate: dict,
                 *, episode_id: str | None = None) -> tuple[dict, list[dict], dict]:
        row = _row(family, condition)
        requests: list[dict] = []

        def fake_provider(_url: str, payload: dict, _timeout: int) -> dict:
            requests.append(payload)
            action = ({"action": "attempt", "payload": {"candidate": candidate}}
                      if len(requests) == 1 else
                      {"action": "claim", "payload": {"status": "non_success"}})
            return {"message": {"content": json.dumps(action)}}

        result = collect_episode(
            task_path=INDEX_DIR / row["task_file"],
            proof_path=INDEX_DIR / row["proof_file"],
            adapter=V1OllamaAdapter(post_json=fake_provider),
            output_dir=self.output / family / condition,
            episode_id=episode_id or f"v7-{family}-{condition.lower()}",
            experiment_id="excluded-v7-offline-fake-provider",
            phase="pilot", model="qwen3:4b", baseline_code="B3",
            retrieval_mode="R0",
        )
        episode = load_episode(Path(result["manifest"]), source_root=ROOT)
        self.assertTrue(episode["proof_verified"])
        self.assertTrue(episode["candidate_replay_verified"])
        self.assertFalse(episode["invalidated"])
        self.assertFalse(episode["manifest"]["eligible_for_main_analysis"])
        self.assertEqual(episode["manifest"]["phase"], "pilot")
        self.assertEqual(len(episode["manifest"]["provider_request_archive"]), len(requests))
        for name in V7_FILES:
            expected = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            self.assertEqual(episode["manifest"]["source_pre_dispatch"]["implementation_file_sha256s"][name], expected)
            self.assertEqual(episode["manifest"]["source_post_run"]["implementation_file_sha256s"][name], expected)
        prompt = json.loads(Path(episode["manifest"]["prompt_path"]).read_text(encoding="utf-8"))
        expected_prompt = hashlib.sha256((ROOT / "agent/prompts/finite_options_system.txt").read_bytes()).hexdigest()
        self.assertEqual(prompt["prompt_template_sha256"], expected_prompt)
        self.assertIn("candidate_language", prompt["request"]["messages"][1]["content"])
        return episode, requests, prompt

    def test_exact_versioned_dispatch_and_all_eight_c1_fake_provider_runs(self) -> None:
        c1_rows = [row for row in INDEX["tasks"] if row["condition"] == "C1"]
        self.assertEqual(len(c1_rows), 8)
        v6_task = json.loads((ROOT / "benchmark/tasks/v6_batch_c/fc-csrf_origin-c1.task.json").read_text())
        self.assertEqual(family_module(v6_task).__name__, "benchmark.finite_batch_c_v6")
        for row in c1_rows:
            family = row["family"]
            with self.subTest(family=family):
                task = json.loads((INDEX_DIR / row["task_file"]).read_text(encoding="utf-8"))
                proof = json.loads((INDEX_DIR / row["proof_file"]).read_text(encoding="utf-8"))
                self.assertEqual(family_module(task).__name__, "benchmark.finite_batch_c_v7")
                candidate = proof["satisfying_candidates"][0]
                episode, requests, prompt = self._collect(family, "C1", candidate)
                self.assertEqual(len(requests), 1)
                self.assertEqual(episode["events"][1]["candidate"], candidate)
                self.assertEqual((episode["events"][1]["raw_test_result"],
                                  episode["events"][1]["security_oracle_result"],
                                  episode["events"][1]["benchmark_verdict"]),
                                 ("PASS", "SECURE", "PASS"))
                self.assertEqual(episode["events"][-1]["stop_reason"], "CHECKER_PASS")
                public = json.loads(prompt["request"]["messages"][1]["content"].removeprefix("PUBLIC TASK:\n"))
                self.assertNotIn("worlds", public["task_card"])
                self.assertNotIn("observation_mode", public["task_card"])

    def test_c3_c4_and_c5_semantics_are_replayed_without_main_promotion(self) -> None:
        family = "csrf_origin"
        for condition in ("C3", "C4", "C5"):
            with self.subTest(condition=condition):
                row = _row(family, condition)
                proof = json.loads((INDEX_DIR / row["proof_file"]).read_text(encoding="utf-8"))
                candidate = (proof["satisfying_candidates"][0]
                             if proof["satisfying_candidates"] else {"mode": "token_and_origin"})
                episode, requests, _prompt = self._collect(family, condition, candidate)
                self.assertEqual(len(requests), 2)
                self.assertEqual(episode["events"][-1]["stop_reason"], "VOLUNTARY")
                if condition in {"C3", "C4"}:
                    self.assertEqual(proof["ground_truth_state"], "UNREPAIRABLE")
                    self.assertEqual(episode["events"][1]["security_oracle_result"], "INSECURE")
                    self.assertEqual(episode["events"][1]["benchmark_verdict"], "FAIL")
                    self.assertEqual(episode["events"][0]["feedback_evidence"],
                                     proof["contradiction_witness"] if condition == "C4" else None)
                else:
                    self.assertEqual(proof["ground_truth_state"], "EVALUATOR_MISMATCH")
                    self.assertEqual((episode["events"][1]["raw_test_result"],
                                      episode["events"][1]["security_oracle_result"],
                                      episode["events"][1]["benchmark_verdict"]),
                                     ("PASS", "SECURE", "FAIL"))

    def test_v7_manifest_fails_replay_when_source_binding_missing_or_drifted(self) -> None:
        row = _row("csrf_origin", "C1")
        proof = json.loads((INDEX_DIR / row["proof_file"]).read_text(encoding="utf-8"))
        for attack in ("missing", "drift", "forged"):
            with self.subTest(attack=attack):
                episode, _, _ = self._collect("csrf_origin", "C1",
                                              proof["satisfying_candidates"][0],
                                              episode_id=f"source-{attack}")
                path = Path(episode["manifest_path"])
                manifest = json.loads(path.read_text(encoding="utf-8"))
                if attack == "missing":
                    for location in (manifest["source_pre_dispatch"], manifest["source_post_run"], manifest):
                        location["implementation_file_sha256s"].pop(V7_FILES[0])
                    expected_error = "source snapshot is incomplete"
                elif attack == "drift":
                    manifest["source_pre_dispatch"]["implementation_file_sha256s"][V7_FILES[0]] = "0" * 64
                    expected_error = "source snapshot drifted"
                else:
                    for location in (manifest["source_pre_dispatch"], manifest["source_post_run"], manifest):
                        location["implementation_file_sha256s"][V7_FILES[0]] = "0" * 64
                    expected_error = "source differs from captured bytes"
                manifest["manifest_sha256"] = hashlib.sha256(_canonical({k: v for k, v in manifest.items()
                                                                           if k != "manifest_sha256"})).hexdigest()
                path.write_bytes(_canonical(manifest) + b"\n")
                with self.assertRaisesRegex(V1ValidationError, expected_error):
                    load_episode(path, source_root=ROOT)

    def test_main_collection_remains_blocked_for_v7(self) -> None:
        row = _row("csrf_origin", "C1")
        with self.assertRaisesRegex(V1CollectionError, "main v1 collection is blocked"):
            collect_episode(
                task_path=INDEX_DIR / row["task_file"], proof_path=INDEX_DIR / row["proof_file"],
                adapter=V1OllamaAdapter(post_json=lambda *_: self.fail("provider must not run")),
                output_dir=self.output, episode_id="forbidden-main-v7",
                experiment_id="excluded-v7-main-guard", phase="main",
            )


if __name__ == "__main__":
    unittest.main()

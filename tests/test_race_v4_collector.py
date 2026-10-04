"""End-to-end excluded counter-race collection, strict action shape, and block freeze."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from agent.contracts import AgentFinalResponse, ToolCall
from agent.finite_candidate_contract import candidate_shape
from agent.scripted_fixture import ScriptedFixtureAdapter
from agent.v1_ollama_adapter import V1OllamaAdapter
from analysis.finite_fixture_calibration import calibrate
from analysis.v1_pipeline import V1ValidationError, load_episode
from experiments.run_race_v4_block import prepare, summarize
from experiments.v1_collector import V1CollectionError, collect_episode


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmark" / "tasks" / "v4_race"


class RaceV4CollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)

    def paths(self, condition: str) -> tuple[Path, Path]:
        stem = f"fr-counter-race-{condition.lower()}"
        return TASKS / f"{stem}.task.json", TASKS / f"{stem}.proof.json"

    def collect(self, condition: str, adapter, *, output_dir: Path | None = None,
                episode_id: str | None = None, retrieval_mode: str = "R0", phase: str = "pilot"):
        task_path, proof_path = self.paths(condition)
        return collect_episode(
            task_path=task_path, proof_path=proof_path, adapter=adapter,
            output_dir=output_dir or self.output, episode_id=episode_id or f"race-{condition.lower()}",
            experiment_id="excluded-race-v4-scripted-smoke", phase=phase,
            model="qwen3:4b", baseline_code="B3", retrieval_mode=retrieval_mode,
            max_steps=6, timeout_seconds=120, seed=7, temperature=0,
        )

    def test_all_five_conditions_replay_and_remain_excluded(self) -> None:
        for condition in ("C1", "C2", "C3", "C4", "C5"):
            with self.subTest(condition=condition):
                _, proof_path = self.paths(condition)
                proof = json.loads(proof_path.read_text(encoding="utf-8"))
                actions = (
                    (ToolCall("attempt", {"candidate": proof["satisfying_candidates"][0]}),)
                    if proof["satisfying_candidates"] else (ToolCall("inspect", {}),)
                )
                adapter = ScriptedFixtureAdapter(actions, AgentFinalResponse("unknown", "Stopped."))
                result = self.collect(condition, adapter)
                episode = load_episode(Path(result["manifest"]), source_root=ROOT)
                events, manifest = episode["events"], episode["manifest"]
                self.assertTrue(episode["proof_verified"])
                self.assertTrue(episode["candidate_replay_verified"])
                self.assertFalse(episode["invalidated"])
                self.assertFalse(manifest["eligible_for_main_analysis"])
                self.assertEqual((events[0]["raw_test_result"], events[0]["security_oracle_result"],
                                  events[0]["benchmark_verdict"]), ("PASS", "INSECURE", "FAIL"))
                self.assertEqual(events[0]["state_certificate"], proof["proof_sha256"])
                self.assertEqual(events[-1]["stop_reason"], manifest["stop_reason"])
                if condition in {"C1", "C2"}:
                    self.assertEqual((events[1]["security_oracle_result"], events[1]["benchmark_verdict"]),
                                     ("SECURE", "PASS"))
                    self.assertEqual(manifest["stop_reason"], "CHECKER_PASS")
                elif condition == "C5":
                    self.assertEqual((events[1]["security_oracle_result"], events[1]["benchmark_verdict"]),
                                     ("SECURE", "FAIL"))
                elif condition == "C4":
                    self.assertEqual(events[0]["feedback_evidence"]["environment"],
                                     proof["environment_witness"])
                    self.assertEqual(len(events[0]["feedback_evidence"]["counterexamples"]), 6)

    def test_public_candidate_shape_and_family_prompt(self) -> None:
        task_path, proof_path = self.paths("C1")
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        candidate = proof["satisfying_candidates"][0]
        task = json.loads(task_path.read_text(encoding="utf-8"))
        from benchmark.finite_race_v4 import public_projection
        public = public_projection(task)
        card = {**public["task_card"], "allowed_updates": public["allowed_updates"],
                "allowed_locks": public["allowed_locks"]}
        self.assertTrue(candidate_shape(candidate, card, public["environment"]))
        for bad in ({"update": "read_write"}, {"update": "read_write or atomic_add", "lock": "none"},
                    {"update": "atomic_add", "lock": "distributed_lock"}):
            self.assertFalse(candidate_shape(bad, card, public["environment"]))
        content = json.dumps({"action": "attempt", "payload": {"candidate": candidate}})
        adapter = V1OllamaAdapter(post_json=lambda *_: {"message": {"content": content}})
        result = self.collect("C1", adapter)
        episode = load_episode(Path(result["manifest"]), source_root=ROOT)
        self.assertEqual(episode["events"][1]["candidate"], candidate)
        prompt = json.loads(Path(episode["manifest"]["prompt_path"]).read_text(encoding="utf-8"))
        system, public_task = prompt["request"]["messages"][0:2]
        self.assertEqual(prompt["prompt_template_sha256"], hashlib.sha256((
            ROOT / "agent" / "prompts" / "race_v4_system.txt").read_bytes()).hexdigest())
        self.assertIn("two-request counter", system["content"])
        self.assertNotIn("gate_mode", public_task["content"])
        self.assertNotIn("request_workers", public_task["content"])
        self.assertNotIn("atomic_supported", public_task["content"])

    def test_retrieval_and_main_remain_fail_closed(self) -> None:
        adapter = ScriptedFixtureAdapter([], AgentFinalResponse("unknown", "Stopped."))
        with self.assertRaises(V1CollectionError):
            self.collect("C1", adapter, retrieval_mode="R1")
        with self.assertRaises(V1CollectionError):
            self.collect("C1", adapter, phase="main")

    def test_exhaustive_calibration_includes_independent_race_checks(self) -> None:
        report = calibrate()
        race = next(row for row in report["families"] if row["family"] == "counter_race")
        self.assertEqual((report["family_count"], report["proofs_verified"],
                          report["candidate_condition_pairs"]), (4, 20, 1430))
        self.assertEqual(race["candidate_condition_pairs"], 30)
        self.assertEqual(race["weak_raw_test_vs_finite_oracle"]["confusion_matrix"]["FP"], 12)
        self.assertEqual(race["benchmark_gate_vs_finite_oracle"]["confusion_matrix"]["FN"], 4)
        self.assertEqual((race["c1_mutation_challenge"]["weak_detected"],
                          race["c1_mutation_challenge"]["gate_detected"]), (0, 2))

    def test_five_slot_schedule_archive_and_receipt(self) -> None:
        block = self.output / "block"
        prepared = prepare(block, model="qwen3:4b", model_digest="a" * 64)
        schedule = json.loads((block / "block_schedule.json").read_text(encoding="utf-8"))
        self.assertEqual(prepared["scheduled_slots"], 5)
        self.assertTrue((block / "source_archive_index.json").is_file())
        self.assertGreaterEqual(len(schedule["source_archive_file_sha256s"]), 20)
        for slot in schedule["slots"]:
            proof = json.loads(Path(slot["proof_path"]).read_text(encoding="utf-8"))
            action = (
                {"action": "attempt", "payload": {"candidate": proof["satisfying_candidates"][0]}}
                if proof["satisfying_candidates"] else
                {"action": "claim", "payload": {"status": "non_success"}}
            )
            content = json.dumps(action)
            adapter = V1OllamaAdapter(
                post_json=lambda *_args, content=content: {"message": {"content": content}},
                max_output_tokens=256, request_timeout=90,
            )
            self.collect(slot["condition"], adapter, output_dir=block, episode_id=slot["episode_id"])
        report = summarize(block)
        self.assertEqual((report["scheduled_slots"], report["validated_slots"], report["invalidated_slots"]),
                         (5, 5, 0))
        self.assertEqual(report["main_eligible_episodes"], 0)
        (block / "block_receipt.json").write_text(json.dumps(report, sort_keys=True) + "\n")
        self.assertEqual(summarize(block, verify_receipt=True), report)
        archive_file = block / "source_archive" / "agent" / "prompts" / "race_v4_system.txt"
        archive_file.write_text("tampered", encoding="utf-8")
        with self.assertRaises(V1ValidationError):
            summarize(block, verify_receipt=True)


if __name__ == "__main__":
    unittest.main()

"""Offline end-to-end collection and replay for the v2/v3 pilot families."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from agent.contracts import AgentFinalResponse, ToolCall
from agent.scripted_fixture import ScriptedFixtureAdapter
from agent.v1_ollama_adapter import V1OllamaAdapter
from analysis.summarize_finite_family_pilot import summarize_block
from analysis.v1_pipeline import episode_metrics, load_episode
from experiments.run_multifamily_live_block import prepare
from experiments.run_replay_protocol_v2_block import prepare as prepare_replay_v2, summarize as summarize_replay_v2
from experiments.v1_collector import V1CollectionError, collect_episode


ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {
    "path-boundary": ("v2_path", "fp-path-boundary"),
    "transaction_replay": ("v3_replay", "fr-transaction-replay"),
}


class FiniteFamilyCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)

    def paths(self, family: str, condition: str) -> tuple[Path, Path]:
        directory, prefix = FAMILIES[family]
        stem = f"{prefix}-{condition.lower()}"
        base = ROOT / "benchmark" / "tasks" / directory
        return base / f"{stem}.task.json", base / f"{stem}.proof.json"

    def collect(self, family: str, condition: str, adapter, **kwargs):
        task_path, proof_path = self.paths(family, condition)
        return collect_episode(
            task_path=task_path, proof_path=proof_path, adapter=adapter,
            output_dir=self.output, episode_id=f"{family}-{condition}",
            experiment_id="excluded-multifamily-scripted-smoke", phase="pilot",
            **kwargs,
        )

    def test_five_conditions_per_new_family_replay_and_exclude(self) -> None:
        for family in FAMILIES:
            for condition in ("C1", "C2", "C3", "C4", "C5"):
                with self.subTest(family=family, condition=condition):
                    _, proof_path = self.paths(family, condition)
                    proof = json.loads(proof_path.read_text(encoding="utf-8"))
                    if proof["satisfying_candidates"]:
                        candidate = proof["satisfying_candidates"][0]
                        actions = (ToolCall("attempt", {"candidate": candidate}),)
                    else:
                        actions = (ToolCall("inspect", {}),)
                    adapter = ScriptedFixtureAdapter(actions, AgentFinalResponse("unknown", "Fixture stopped."))
                    result = self.collect(family, condition, adapter)
                    episode = load_episode(Path(result["manifest"]), source_root=ROOT)
                    manifest = episode["manifest"]
                    events = episode["events"]
                    self.assertTrue(episode["proof_verified"])
                    self.assertTrue(episode["candidate_replay_verified"])
                    self.assertFalse(episode["invalidated"])
                    metrics = episode_metrics(episode)
                    self.assertEqual(metrics["family"], family)
                    self.assertEqual(metrics["condition"], condition)
                    self.assertFalse(manifest["eligible_for_main_analysis"])
                    self.assertEqual(manifest["family"], family)
                    self.assertEqual(events[0]["security_oracle_result"], "INSECURE")
                    self.assertEqual(events[0]["benchmark_verdict"], "FAIL")
                    self.assertEqual(events[0]["raw_test_result"],
                                     "PASS" if family == "transaction_replay" else "FAIL")
                    self.assertEqual(events[0]["state_certificate"], proof["proof_sha256"])
                    self.assertEqual(events[-1]["stop_reason"], manifest["stop_reason"])
                    prompt = json.loads(Path(manifest["prompt_path"]).read_text(encoding="utf-8"))
                    self.assertNotIn("gate_mode", json.dumps(prompt))
                    self.assertNotIn("runtime_mode", json.dumps(prompt))
                    if condition in {"C1", "C2"}:
                        self.assertEqual((events[1]["raw_test_result"], events[1]["security_oracle_result"],
                                          events[1]["benchmark_verdict"]), ("PASS", "SECURE", "PASS"))
                        self.assertEqual(events[-1]["stop_reason"], "CHECKER_PASS")
                    elif condition == "C5":
                        self.assertEqual((events[1]["raw_test_result"], events[1]["security_oracle_result"],
                                          events[1]["benchmark_verdict"]), ("PASS", "SECURE", "FAIL"))
                    else:
                        self.assertEqual(proof["ground_truth_state"], "UNREPAIRABLE")
                        if condition == "C4":
                            self.assertEqual(events[0]["feedback_evidence"], proof["contradiction_witness"])

    def test_new_families_reject_unfrozen_retrieval_arm(self) -> None:
        for family in FAMILIES:
            with self.subTest(family=family), self.assertRaises(V1CollectionError):
                self.collect(family, "C1", ScriptedFixtureAdapter([], AgentFinalResponse("unknown", "Stopped.")),
                             retrieval_mode="R1", retrieval_manifest_path=self.output / "missing.json")

    def test_live_json_adapter_uses_family_prompt_and_candidate_shape(self) -> None:
        for family in FAMILIES:
            with self.subTest(family=family):
                _, proof_path = self.paths(family, "C1")
                candidate = json.loads(proof_path.read_text())["satisfying_candidates"][0]
                action = json.dumps({"action": "attempt", "payload": {"candidate": candidate}})
                adapter = V1OllamaAdapter(post_json=lambda *_: {"message": {"content": action}})
                result = self.collect(family, "C1", adapter, model="qwen3:4b")
                episode = load_episode(Path(result["manifest"]), source_root=ROOT)
                self.assertEqual(episode["events"][1]["candidate"], candidate)
                self.assertEqual(episode["events"][-1]["stop_reason"], "CHECKER_PASS")
                manifest = episode["manifest"]
                prompt = json.loads(Path(manifest["prompt_path"]).read_text())
                system = prompt["request"]["messages"][0]["content"]
                self.assertEqual(prompt["prompt_template_sha256"], hashlib.sha256((
                    ROOT / "agent" / "prompts" / ("path_v2_system.txt" if family == "path-boundary" else "replay_v3_system.txt")
                ).read_bytes()).hexdigest())
                self.assertIn("route table" if family == "path-boundary" else "two-state policy", system)

    def test_prescheduled_ten_slot_summary_replays_every_saved_episode(self) -> None:
        block = self.output / "block"
        prepare(block, model="qwen3:4b", model_digest="a" * 64)
        schedule = json.loads((block / "block_schedule.json").read_text())
        for slot in schedule["slots"]:
            proof = json.loads(Path(slot["proof_path"]).read_text())
            if proof["satisfying_candidates"]:
                content = json.dumps({"action": "attempt", "payload": {
                    "candidate": proof["satisfying_candidates"][0]}})
            else:
                content = json.dumps({"action": "claim", "payload": {"status": "non_success"}})
            adapter = V1OllamaAdapter(
                post_json=lambda *_args, content=content: {"message": {"content": content}},
                max_output_tokens=256,
            )
            collect_episode(
                task_path=Path(slot["task_path"]), proof_path=Path(slot["proof_path"]),
                adapter=adapter, output_dir=block, episode_id=slot["episode_id"],
                experiment_id="excluded-live-multifamily-pilot", phase="pilot",
                model="qwen3:4b", baseline_code="B3", retrieval_mode="R0",
                max_steps=6, timeout_seconds=120, seed=7, temperature=0,
            )
        report = summarize_block(block, source_root=ROOT)
        self.assertEqual((report["scheduled_slots"], report["validated_slots"], report["invalidated_slots"]),
                         (10, 10, 0))
        self.assertEqual(report["main_eligible_episodes"], 0)
        (block / "block_receipt.json").write_text(json.dumps(report, sort_keys=True) + "\n")
        self.assertEqual(summarize_block(block, source_root=ROOT, verify_receipt=True), report)

    def test_replay_protocol_v2_records_bounded_schema_diagnostic(self) -> None:
        invalid_candidate = {"transitions": {
            "fresh": {"decision": "approve or reject", "next": "fresh or seen"},
            "seen": {"decision": "approve or reject", "next": "fresh or seen"},
        }}
        content = json.dumps({"action": "attempt", "payload": {"candidate": invalid_candidate}})
        adapter = V1OllamaAdapter(
            post_json=lambda *_: {"message": {"content": content}, "done_reason": "stop", "eval_count": 82},
            protocol_version="finite_json_v2", request_timeout=180,
        )
        result = self.collect("transaction_replay", "C1", adapter, model="qwen3:4b",
                              timeout_seconds=300)
        episode = load_episode(Path(result["manifest"]), source_root=ROOT)
        manifest = episode["manifest"]
        stop = episode["events"][-1]
        self.assertTrue(episode["invalidated"])
        self.assertEqual(stop["stop_reason"], "ERROR")
        self.assertEqual(stop["protocol_diagnostic"]["schema_failure_category"], "INVALID_TRANSITION_ENUM")
        self.assertEqual(stop["protocol_diagnostic"]["json_parse_status"], "VALID_JSON")
        self.assertEqual(stop["protocol_diagnostic"]["content_sha256"], hashlib.sha256(content.encode()).hexdigest())
        self.assertEqual(stop["protocol_diagnostic"]["provider_done_reason"], "stop")
        self.assertEqual(manifest["provider_request_timeout_seconds"], 180)
        self.assertEqual(manifest["episode_timeout_seconds"], 300)
        prompt = json.loads(Path(manifest["prompt_path"]).read_text())
        self.assertEqual(prompt["protocol_version"], "finite_json_v2")
        self.assertEqual(prompt["request"]["messages"][1]["content"].count('"timeout_seconds": 300'), 1)
        self.assertNotIn("approve or reject", str(stop))
        self.assertNotIn("fresh or seen", str(stop))

    def test_replay_protocol_v2_accepts_valid_candidate(self) -> None:
        _, proof_path = self.paths("transaction_replay", "C1")
        candidate = json.loads(proof_path.read_text())["satisfying_candidates"][0]
        content = json.dumps({"action": "attempt", "payload": {"candidate": candidate}})
        adapter = V1OllamaAdapter(
            post_json=lambda *_: {"message": {"content": content}},
            protocol_version="finite_json_v2",
        )
        result = self.collect("transaction_replay", "C1", adapter, model="qwen3:4b")
        episode = load_episode(Path(result["manifest"]), source_root=ROOT)
        self.assertEqual(episode["events"][1]["candidate"], candidate)
        self.assertEqual(episode["events"][-1]["stop_reason"], "CHECKER_PASS")

    def test_replay_protocol_v2_five_slot_receipt(self) -> None:
        block = self.output / "replay-v2-block"
        prepare_replay_v2(block, model="qwen3:4b", model_digest="b" * 64)
        schedule = json.loads((block / "block_schedule.json").read_text())
        for slot in schedule["slots"]:
            proof = json.loads(Path(slot["proof_path"]).read_text())
            if proof["satisfying_candidates"]:
                action = {"action": "attempt", "payload": {
                    "candidate": proof["satisfying_candidates"][0]}}
            else:
                action = {"action": "claim", "payload": {"status": "non_success"}}
            content = json.dumps(action)
            adapter = V1OllamaAdapter(
                post_json=lambda *_args, content=content: {"message": {"content": content}},
                protocol_version="finite_json_v2", max_output_tokens=256, request_timeout=90,
            )
            collect_episode(
                task_path=Path(slot["task_path"]), proof_path=Path(slot["proof_path"]),
                adapter=adapter, output_dir=block, episode_id=slot["episode_id"],
                experiment_id="excluded-live-replay-json-v2", phase="pilot",
                model="qwen3:4b", baseline_code="B3", retrieval_mode="R0",
                max_steps=6, timeout_seconds=120, seed=7, temperature=0,
            )
        report = summarize_replay_v2(block)
        self.assertEqual((report["scheduled_slots"], report["validated_slots"], report["invalidated_slots"]),
                         (5, 5, 0))
        self.assertEqual(report["main_eligible_episodes"], 0)
        (block / "block_receipt.json").write_text(json.dumps(report, sort_keys=True) + "\n")
        self.assertEqual(summarize_replay_v2(block, verify_receipt=True), report)


if __name__ == "__main__":
    unittest.main()

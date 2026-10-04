"""Excluded v1 collector integration checks with observable, offline adapters."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from agent.contracts import AgentFinalResponse, ToolCall, TokenUsage
from agent.scripted_fixture import ScriptedFixtureAdapter
from agent.v1_ollama_adapter import V1OllamaAdapter
from analysis.v1_pipeline import load_episode
from benchmark.retrieval_v1 import CORPUS_PATH, freeze_retrieval_manifest
from experiments.v1_collector import V1CollectionError, collect_episode


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmark" / "tasks" / "v1"


def _task_paths(condition: str) -> tuple[Path, Path]:
    stem = f"fp-authorization-{condition.lower()}"
    return TASKS / f"{stem}.task.json", TASKS / f"{stem}.proof.json"


def _fixture(*calls: ToolCall) -> ScriptedFixtureAdapter:
    return ScriptedFixtureAdapter(calls, AgentFinalResponse("unknown", "Fixture stopped."))


def _load(result: dict[str, object]) -> dict[str, object]:
    return load_episode(Path(str(result["manifest"])), source_root=ROOT)


class V1CollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)

    def collect(self, condition: str, adapter, *, episode_id: str = "episode-1", **kwargs):
        task_path, proof_path = _task_paths(condition)
        return collect_episode(
            task_path=task_path, proof_path=proof_path, adapter=adapter,
            output_dir=self.output, episode_id=episode_id,
            experiment_id="excluded-v1-integration", **kwargs,
        )

    def test_successful_candidate_has_lossless_actions_and_receipts(self) -> None:
        _, proof_path = _task_paths("C1")
        proof = json.loads(proof_path.read_text())
        candidate = proof["satisfying_candidates"][0]
        call = ToolCall("attempt", {"candidate": candidate}, TokenUsage(11, 4, 15, True))
        adapter = _fixture(ToolCall("inspect", {}), call)
        result = self.collect("C1", adapter)
        loaded = _load(result)
        self.assertTrue(loaded["proof_verified"])
        self.assertTrue(loaded["git_commit_verified"])
        events = loaded["events"]
        self.assertEqual([(row["event_type"], row["step"]) for row in events],
                         [("TASK_START", 0), ("ACTION", 1), ("ACTION", 2), ("STOP", 3)])
        self.assertEqual(events[0]["action_type"], "STARTER_CHECK")
        self.assertEqual(events[0]["state_certificate"], proof["proof_sha256"])
        self.assertEqual(events[1]["action_type"], "INSPECT")
        self.assertEqual(events[1]["raw_test_result"], "NOT_RUN")
        self.assertEqual(events[2]["candidate"], candidate)
        self.assertEqual(events[2]["tool_call"], call.as_mapping())
        self.assertEqual((events[2]["raw_test_result"], events[2]["security_oracle_result"],
                          events[2]["benchmark_verdict"]), ("PASS", "SECURE", "PASS"))
        self.assertEqual(events[2]["state_certificate"], proof["proof_sha256"])
        self.assertEqual(events[2]["token_usage"]["total_tokens"], 15)
        self.assertEqual(events[3]["stop_reason"], "CHECKER_PASS")
        self.assertEqual(events[3]["remaining_action_budget"], 4)
        self.assertEqual(adapter.dispatched_calls, [ToolCall("inspect", {}), call])
        self.assertTrue(adapter.cleaned_up)
        manifest = loaded["manifest"]
        self.assertEqual(manifest["phase"], "engineering")
        self.assertFalse(manifest["eligible_for_main_analysis"])
        self.assertIn("experiments/v1_collector.py", manifest["implementation_file_sha256s"])
        self.assertEqual(len(manifest["implementation_file_sha256s"]["experiments/v1_collector.py"]), 64)
        self.assertEqual(json.loads(Path(manifest["schedule_path"]).read_text())["kind"],
                         "single_excluded_episode")
        prompt_bytes = Path(manifest["prompt_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(prompt_bytes).hexdigest(), manifest["prompt_sha256"])

    def test_c4_public_witness_and_voluntary_stop_with_budget_remaining(self) -> None:
        adapter = _fixture()
        loaded = _load(self.collect("C4", adapter))
        start, stop = loaded["events"]
        _, proof_path = _task_paths("C4")
        witness = json.loads(proof_path.read_text())["contradiction_witness"]
        self.assertTrue(start["evidence_exposed"])
        self.assertEqual(start["feedback_evidence"], witness)
        self.assertEqual(start["public_observation"]["observation"]["feedback_evidence"],
                         start["feedback_evidence"])
        self.assertEqual(stop["stop_reason"], "VOLUNTARY")
        self.assertEqual(stop["remaining_action_budget"], 6)
        self.assertFalse(stop["evidence_exposed"])

    def test_c5_separates_raw_oracle_and_gate(self) -> None:
        _, proof_path = _task_paths("C5")
        candidate = json.loads(proof_path.read_text())["satisfying_candidates"][0]
        adapter = _fixture(ToolCall("attempt", {"candidate": candidate}))
        loaded = _load(self.collect("C5", adapter))
        submit, stop = loaded["events"][1:]
        self.assertEqual((submit["raw_test_result"], submit["security_oracle_result"],
                          submit["benchmark_verdict"]), ("PASS", "SECURE", "FAIL"))
        self.assertEqual(stop["stop_reason"], "VOLUNTARY")

    def test_disallowed_tool_is_recorded_as_invalid_without_evaluator_call(self) -> None:
        call = ToolCall("security_check", {})
        loaded = _load(self.collect("C1", _fixture(call)))
        event = loaded["events"][1]
        self.assertEqual(event["action_type"], "INVALID_SUBMISSION")
        self.assertEqual(event["invalid_source"], call.as_mapping())
        self.assertEqual((event["raw_test_result"], event["security_oracle_result"],
                          event["benchmark_verdict"]), ("NOT_RUN", "INDETERMINATE", "FAIL"))

    def test_malformed_candidate_prose_is_hashed_without_persisting_text(self) -> None:
        prose = "Let me reason through this private draft before choosing a policy."
        call = ToolCall("attempt", {"candidate": prose})
        loaded = _load(self.collect("C1", _fixture(call)))
        event = loaded["events"][1]
        self.assertEqual(event["action_type"], "INVALID_SUBMISSION")
        self.assertTrue(event["tool_call"]["parameters_redacted"])
        self.assertEqual(len(event["tool_call"]["tool_call_sha256"]), 64)
        self.assertNotIn(prose, str(loaded["events"]))

    def test_attempt_cap_and_action_cap_are_distinct(self) -> None:
        _, proof_path = _task_paths("C5")
        candidate = json.loads(proof_path.read_text())["satisfying_candidates"][0]
        attempt = ToolCall("attempt", {"candidate": candidate})
        cap = _load(self.collect("C5", _fixture(attempt), baseline_code="B0"))["events"][-1]
        self.assertEqual(cap["stop_reason"], "BUDGET")
        self.assertEqual(cap["budget_stop_source"], "generated_attempt_budget")
        self.assertEqual(cap["remaining_action_budget"], 5)
        action_cap = _load(self.collect("C1", _fixture(ToolCall("inspect", {})),
                                        episode_id="episode-2", max_steps=1))["events"][-1]
        self.assertEqual(action_cap["budget_stop_source"], "action_budget")
        self.assertEqual(action_cap["remaining_action_budget"], 0)

    def test_retry_and_reflection_treatments_begin_after_starter_failure(self) -> None:
        for baseline, expected in (("B1", "Try again."),
                                   ("B2", "Explain what went wrong and revise the solution.")):
            with self.subTest(baseline=baseline):
                loaded = _load(self.collect(
                    "C1", _fixture(), episode_id=f"episode-{baseline}", baseline_code=baseline
                ))
                self.assertEqual(
                    loaded["events"][0]["public_observation"]["observation"]["retry_instruction"],
                    expected,
                )

    def test_retrieval_delivery_has_frozen_corpus_and_query_trace(self) -> None:
        retrieval_manifest = freeze_retrieval_manifest()
        retrieval_path = self.output / "frozen-retrieval.json"
        retrieval_path.write_text(json.dumps(retrieval_manifest, sort_keys=True) + "\n")
        for mode in ("R1", "R2"):
            with self.subTest(mode=mode):
                adapter = _fixture()
                loaded = _load(self.collect(
                    "C1", adapter, episode_id=f"episode-{mode}", baseline_code="B5",
                    retrieval_mode=mode, retrieval_manifest_path=retrieval_path,
                ))
                exposure = loaded["events"][0]["retrieval_exposure"]
                self.assertEqual(exposure["mode"], mode)
                self.assertEqual(exposure["exposure_status"], "delivered")
                self.assertEqual(exposure["exposure_document_ids"], exposure["retrieved_document_ids"])
                self.assertEqual(exposure["documents_used_status"], "unknown")
                self.assertEqual(exposure["retrieved_document_ids"][0], "web-authorization-v1")
                self.assertEqual(adapter.public_task.retrieval_context["documents"][0]["document_id"],
                                 exposure["retrieved_document_ids"][0])
                public_documents = adapter.public_task.retrieval_context["documents"]
                self.assertEqual(set(public_documents[0]), {"document_id", "source", "text"})
                prompt = json.loads(Path(loaded["manifest"]["prompt_path"]).read_text())
                for field in ("noise_injected", "document_sha256", '"score"', '"rank"'):
                    self.assertNotIn(field, json.dumps(public_documents))
                    self.assertNotIn(field, json.dumps(prompt))
                self.assertEqual(loaded["manifest"]["corpus_sha256"],
                                 hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest())
                if mode == "R2":
                    self.assertTrue(exposure["retrieved_documents"][-1]["noise_injected"])
                    self.assertTrue(exposure["retrieved_document_ids"][-1].startswith("crypto-"))

    def test_exact_initial_provider_request_is_persisted_after_starter_feedback(self) -> None:
        observed: list[tuple[str, object]] = []

        def post_json(url, payload, timeout):
            observed.append((url, json.loads(json.dumps(payload))))
            return {"message": {"content": '{"action":"claim","payload":{"status":"unknown"}}',
                                "thinking": "SENSITIVE_THOUGHT_MARKER"},
                    "prompt_eval_count": 23, "eval_count": 3}

        adapter = V1OllamaAdapter(post_json=post_json)
        loaded = _load(self.collect("C1", adapter, model="qwen3:4b"))
        self.assertEqual(len(observed), 1)
        prompt = json.loads(Path(loaded["manifest"]["prompt_path"]).read_text())
        self.assertEqual(prompt["endpoint"], observed[0][0])
        self.assertEqual(prompt["request"], observed[0][1])
        self.assertIn("SECURITY CHECK FAILED", json.dumps(prompt["request"]["messages"]))
        self.assertEqual(loaded["events"][-1]["token_usage"]["total_tokens"], 26)
        self.assertTrue(loaded["events"][-1]["token_usage"]["provider_reported"])
        for artifact_key in ("prompt_path", "log_path", "schedule_path"):
            self.assertNotIn("SENSITIVE_THOUGHT_MARKER", Path(loaded["manifest"][artifact_key]).read_text())
        self.assertNotIn("SENSITIVE_THOUGHT_MARKER", Path(self.output / "episode-1.manifest.json").read_text())

    def test_seed_and_temperature_reach_exact_request_and_manifest(self) -> None:
        adapter = V1OllamaAdapter(post_json=lambda *_: {
            "message": {"content": '{"action":"claim","payload":{"status":"unknown"}}'},
        })
        loaded = _load(self.collect("C1", adapter, model="qwen3:4b", seed=23, temperature=0.3))
        manifest = loaded["manifest"]
        request = json.loads(Path(manifest["prompt_path"]).read_text())["request"]
        schedule = json.loads(Path(manifest["schedule_path"]).read_text())
        self.assertEqual(request["options"]["seed"], 23)
        self.assertEqual(request["options"]["temperature"], 0.3)
        self.assertEqual((manifest["seed"], manifest["temperature"]), (23, 0.3))
        self.assertEqual((schedule["seed"], schedule["temperature"]), (23, 0.3))
        for invalid in ({"seed": -1}, {"temperature": float("nan")}, {"temperature": True}):
            with self.subTest(invalid=invalid), self.assertRaises(V1CollectionError):
                self.collect("C1", _fixture(), episode_id="invalid-" + str(len(invalid)), **invalid)

    def test_unstructured_model_response_is_protocol_error_not_voluntary_stop(self) -> None:
        adapter = V1OllamaAdapter(post_json=lambda *_: {
            "message": {"content": "Let me reason through the policy.\nI might try another key."},
            "prompt_eval_count": 20, "eval_count": 9,
        })
        loaded = _load(self.collect("C4", adapter, model="qwen3:4b"))
        stop = loaded["events"][-1]
        self.assertEqual(stop["stop_reason"], "ERROR")
        self.assertEqual(stop["errors"][0]["type"], "AGENT_PROTOCOL_NO_ACTION")
        self.assertEqual(stop["discarded_unstructured_model_messages"], 1)
        self.assertEqual(stop["final_response"]["status"], "unknown")
        self.assertNotIn("Let me reason", str(loaded["events"]))
        self.assertTrue(loaded["manifest"]["invalidated"])

    def test_dispatch_exception_preserves_invalidated_trace(self) -> None:
        class CrashingFixture(ScriptedFixtureAdapter):
            def tool_call(self, call):
                super().tool_call(call)
                raise RuntimeError("injected dispatch failure")

        adapter = CrashingFixture([ToolCall("inspect", {})], AgentFinalResponse("unknown", "Stopped."))
        loaded = _load(self.collect("C1", adapter))
        events = loaded["events"]
        self.assertEqual(events[1]["action_type"], "INVALID_SUBMISSION")
        self.assertEqual(events[1]["action_status"], "INVALIDATED")
        self.assertEqual(events[-1]["stop_reason"], "INFRASTRUCTURE_ABORT")
        self.assertTrue(loaded["manifest"]["invalidated"])

    def test_main_and_duplicate_episode_rejected(self) -> None:
        with self.assertRaises(V1CollectionError):
            self.collect("C1", _fixture(), phase="main")
        self.collect("C1", _fixture())
        with self.assertRaises(V1CollectionError):
            self.collect("C1", _fixture())


if __name__ == "__main__":
    unittest.main()

"""Excluded v1 collector integration checks with observable, offline adapters."""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.contracts import AgentFinalResponse, ToolCall, TokenUsage
from agent.scripted_fixture import ScriptedFixtureAdapter
from agent.v1_ollama_adapter import V1OllamaAdapter
from analysis.v1_pipeline import V1ValidationError, load_episode
from benchmark.retrieval_r1_20_candidate import CORPUS_PATH as CANDIDATE_CORPUS_PATH
from benchmark.retrieval_r1_20_candidate import freeze_candidate_manifest
from benchmark.retrieval_v1 import CORPUS_PATH, freeze_retrieval_manifest
from experiments.v1_collector import V1CollectionError, _agent_task, collect_episode
from agent.finite_candidate_contract import candidate_shape
from benchmark.finite_batch_c_v7 import build_reference_tasks as build_batch_c_v7_tasks
from benchmark.finite_batch_c_v7 import public_projection as batch_c_v7_public_projection


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmark" / "tasks" / "v1"
COLLECTOR_REGISTERED_TASK_DIRS = (
    "v1", "v2_path", "v3_replay", "v4_race", "v5_batch_a",
    "v5_batch_b", "v6_batch_c",
)


def _registered_index_paths() -> list[Path]:
    return [ROOT / "benchmark" / "tasks" / folder / "index.json"
            for folder in COLLECTOR_REGISTERED_TASK_DIRS]


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

    def test_all_twenty_finite_families_reach_the_excluded_collector(self) -> None:
        families = set()
        for index_path in _registered_index_paths():
            for row in json.loads(index_path.read_text())["tasks"]:
                if row["condition"] != "C1":
                    continue
                family = row["family"]
                families.add(family)
                proof_path = index_path.parent / row["proof_file"]
                proof = json.loads(proof_path.read_text())
                candidate = proof["satisfying_candidates"][0]
                adapter = _fixture(ToolCall("attempt", {"candidate": candidate}))
                result = collect_episode(
                    task_path=index_path.parent / row["task_file"], proof_path=proof_path,
                    adapter=adapter, output_dir=self.output / family,
                    episode_id="c1-integration", experiment_id="excluded-catalog-integration",
                )
                loaded = _load(result)
                self.assertEqual(result["stop_reason"], "CHECKER_PASS", family)
                self.assertEqual(loaded["events"][1]["action_type"], "SUBMIT", family)
                self.assertEqual(loaded["events"][1]["security_oracle_result"], "SECURE", family)
                self.assertEqual(loaded["events"][1]["benchmark_verdict"], "PASS", family)
                check = loaded["events"][1]["per_action_check"]
                self.assertEqual(check["status"], "RAN", family)
                self.assertEqual(check["evaluator_receipt"]["candidate_hash"],
                                 loaded["events"][1]["candidate_hash"])
                if family == "csrf_origin":
                    self.assertIn("strong_test_result", check["evaluator_receipt"])
        self.assertEqual(len(families), 20)

    def test_new_option_and_mode_families_have_public_json_contract(self) -> None:
        for folder in ("v5_batch_a", "v6_batch_c"):
            index_path = ROOT / "benchmark" / "tasks" / folder / "index.json"
            row = next(row for row in json.loads(index_path.read_text())["tasks"]
                       if row["condition"] == "C1")
            proof_path = index_path.parent / row["proof_file"]
            candidate = json.loads(proof_path.read_text())["satisfying_candidates"][0]
            observed = []

            def post_json(url, payload, timeout):
                observed.append(payload)
                return {"message": {"content": json.dumps({
                    "action": "attempt", "payload": {"candidate": candidate},
                })}}

            adapter = V1OllamaAdapter(post_json=post_json)
            result = collect_episode(
                task_path=index_path.parent / row["task_file"], proof_path=proof_path,
                adapter=adapter, output_dir=self.output / folder,
                episode_id="c1-options", experiment_id="excluded-json-contract",
                model="qwen3:4b",
            )
            loaded = _load(result)
            self.assertEqual(result["stop_reason"], "CHECKER_PASS", folder)
            self.assertIn("finite_options_system", str(adapter.prompt_path))
            public_card = observed[0]["messages"][1]["content"]
            self.assertIn("candidate_options" if folder == "v5_batch_a" else "candidate_modes", public_card)
            self.assertEqual(loaded["events"][1]["candidate"], candidate)

    def test_v7_public_mode_semantics_survive_agent_task_mapping(self) -> None:
        task = next(task for task in build_batch_c_v7_tasks()
                    if task["family"] == "csrf_origin" and task["condition"] == "C1")
        public = batch_c_v7_public_projection(task)
        agent_task = _agent_task(public, None)
        self.assertEqual(agent_task.task_card["candidate_language"], public["candidate_language"])
        self.assertTrue(candidate_shape({"mode": "token_and_origin"},
                                        agent_task.task_card, agent_task.environment))
        self.assertFalse(candidate_shape({"mode": "invented"},
                                         agent_task.task_card, agent_task.environment))
        self.assertNotIn("worlds", agent_task.task_card)

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
        self.assertEqual(events[0]["per_action_check"]["status"], "RAN")
        self.assertEqual(events[1]["action_type"], "INSPECT")
        self.assertEqual(events[1]["raw_test_result"], "NOT_RUN")
        self.assertEqual(events[1]["per_action_check"]["reason"], "INSPECT_NO_CHECK")
        self.assertIsNone(events[1]["per_action_check"]["evaluator_receipt"])
        self.assertEqual(events[2]["candidate"], candidate)
        self.assertEqual(events[2]["tool_call"], call.as_mapping())
        self.assertEqual((events[2]["raw_test_result"], events[2]["security_oracle_result"],
                          events[2]["benchmark_verdict"]), ("PASS", "SECURE", "PASS"))
        self.assertEqual(events[2]["state_certificate"], proof["proof_sha256"])
        self.assertEqual(events[2]["per_action_check"]["status"], "RAN")
        self.assertEqual(events[2]["per_action_check"]["evaluator_receipt"]["finite_domain_state_count"],
                         len(json.loads(_task_paths("C1")[0].read_text())["states"]))
        self.assertNotIn("security_oracle_result", str(events[2]["public_observation"]))
        self.assertEqual(events[2]["token_usage"]["total_tokens"], 15)
        self.assertEqual(events[3]["stop_reason"], "CHECKER_PASS")
        self.assertEqual(events[3]["remaining_action_budget"], 4)
        self.assertEqual(adapter.dispatched_calls, [ToolCall("inspect", {}), call])
        self.assertTrue(adapter.cleaned_up)
        manifest = loaded["manifest"]
        self.assertEqual(manifest["phase"], "engineering")
        self.assertFalse(manifest["eligible_for_main_analysis"])
        self.assertEqual(manifest["per_action_check_contract"], "finite_evaluator_receipt_v1")
        self.assertIn("experiments/v1_collector.py", manifest["implementation_file_sha256s"])
        self.assertEqual(len(manifest["implementation_file_sha256s"]["experiments/v1_collector.py"]), 64)
        self.assertEqual(json.loads(Path(manifest["schedule_path"]).read_text())["kind"],
                         "single_excluded_episode")
        prompt_bytes = Path(manifest["prompt_path"]).read_bytes()
        self.assertEqual(hashlib.sha256(prompt_bytes).hexdigest(), manifest["prompt_sha256"])

    def test_post_run_source_snapshot_failure_preserves_invalidated_manifest(self) -> None:
        pre = {"observed": True, "git_commit": "0" * 40,
               "source_tree_dirty": False,
               "implementation_file_sha256s": {"experiments/v1_collector.py": "a" * 64}}
        post = {"observed": False, "error_type": "V1CollectionError"}
        with patch("experiments.v1_collector._source_snapshot", side_effect=[pre, post]):
            result = self.collect("C1", _fixture(ToolCall("inspect", {})))
        manifest_path = Path(result["manifest"])
        manifest = json.loads(manifest_path.read_text())
        self.assertTrue(manifest["invalidated"])
        self.assertEqual(manifest["stop_reason"], "INFRASTRUCTURE_ABORT")
        self.assertEqual(manifest["source_pre_dispatch"], pre)
        self.assertEqual(manifest["source_post_run"], post)
        self.assertTrue(manifest["source_tree_dirty"])
        self.assertEqual(manifest["implementation_file_sha256s"], pre["implementation_file_sha256s"])

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
        self.assertEqual(event["per_action_check"]["reason"], "INVALID_SUBMISSION")

    def test_full_per_action_receipt_is_replayed_even_after_rehash(self) -> None:
        _, proof_path = _task_paths("C1")
        candidate = json.loads(proof_path.read_text())["satisfying_candidates"][0]
        result = self.collect("C1", _fixture(ToolCall("attempt", {"candidate": candidate})))
        manifest_path = Path(result["manifest"])
        manifest = json.loads(manifest_path.read_text())
        log_path = Path(result["log"])
        events = [json.loads(line) for line in log_path.read_text().splitlines()]
        check = events[1]["per_action_check"]
        check["evaluator_receipt"]["finite_domain_state_count"] += 1
        check["evaluator_receipt_sha256"] = hashlib.sha256(
            json.dumps(check["evaluator_receipt"], sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        log_path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                              ensure_ascii=False) + "\n" for row in events))
        manifest["log_sha256"] = hashlib.sha256(log_path.read_bytes()).hexdigest()
        manifest.pop("manifest_sha256")
        manifest["manifest_sha256"] = hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
        with self.assertRaisesRegex(V1ValidationError, "full per-action evaluator receipt"):
            _load(result)

    def test_aborted_public_handoff_preserves_completed_private_check(self) -> None:
        _, proof_path = _task_paths("C1")
        candidate = json.loads(proof_path.read_text())["satisfying_candidates"][0]

        class HandoffFailure(ScriptedFixtureAdapter):
            def receive_observation(self, observation):
                if observation.step == 1:
                    raise RuntimeError("fixture handoff failed")
                super().receive_observation(observation)

        adapter = HandoffFailure(
            [ToolCall("attempt", {"candidate": candidate})],
            AgentFinalResponse("unknown", "Fixture stopped."),
        )
        loaded = _load(self.collect("C1", adapter))
        event = loaded["events"][1]
        self.assertTrue(loaded["invalidated"])
        self.assertEqual(event["action_status"], "INVALIDATED")
        self.assertEqual(event["public_observation_status"], "not_delivered")
        self.assertEqual(event["per_action_check"]["status"], "RAN")
        self.assertEqual(event["per_action_check"]["evaluator_receipt"]["benchmark_verdict"], "PASS")

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

    def test_opt_in_candidate_provider_covers_all_twenty_r0_r1_pilots(self) -> None:
        candidate_manifest_path = self.output / "candidate-manifest.json"
        candidate_manifest_path.write_text(json.dumps(freeze_candidate_manifest(), sort_keys=True) + "\n")
        families = set()
        for index_path in _registered_index_paths():
            for row in json.loads(index_path.read_text())["tasks"]:
                if row["condition"] != "C1":
                    continue
                family = row["family"]
                families.add(family)
                for mode in ("R0", "R1"):
                    with self.subTest(family=family, mode=mode):
                        observed = []

                        def post_json(url, payload, timeout):
                            observed.append((url, json.loads(json.dumps(payload))))
                            return {"message": {"content": '{"action":"claim","payload":{"status":"unknown"}}'}}

                        adapter = V1OllamaAdapter(post_json=post_json)
                        result = collect_episode(
                            task_path=index_path.parent / row["task_file"],
                            proof_path=index_path.parent / row["proof_file"],
                            adapter=adapter, output_dir=self.output / family / mode,
                            episode_id=f"candidate-{mode.lower()}",
                            experiment_id="excluded-candidate-r0-r1-integration",
                            phase="pilot", model="qwen3:4b",
                            baseline_code="B3" if mode == "R0" else "B5",
                            retrieval_mode=mode, retrieval_provider="r1_20_candidate",
                            retrieval_manifest_path=candidate_manifest_path,
                        )
                        episode = _load(result)
                        manifest = episode["manifest"]
                        exposure = episode["events"][0]["retrieval_exposure"]
                        self.assertEqual(result["stop_reason"], "VOLUNTARY")
                        self.assertEqual(manifest["retrieval_provider"], "r1_20_candidate")
                        self.assertEqual(manifest["retrieval_prototype_status"], "EXCLUDED_PROTOTYPE_UNREVIEWED")
                        self.assertFalse(manifest["eligible_for_main_analysis"])
                        self.assertEqual(manifest["corpus_sha256"], hashlib.sha256(CANDIDATE_CORPUS_PATH.read_bytes()).hexdigest())
                        self.assertEqual(manifest["provider_request_archive_complete"], True)
                        self.assertEqual(len(manifest["provider_request_archive"]), 1)
                        self.assertEqual(observed[0][1], json.loads(Path(manifest["provider_request_archive"][0]["path"]).read_text())["request"])
                        for name in (
                            "benchmark/retrieval_r1_20_candidate.py",
                            "benchmark/retrieval_corpus_r1_20_candidate.jsonl",
                            "benchmark/retrieval_manifest_r1_20_candidate.json",
                        ):
                            self.assertIn(name, manifest["implementation_file_sha256s"])
                        expected_ids = [] if mode == "R0" else ["r1-20-" + family.replace("_", "-")]
                        self.assertEqual(exposure["retrieved_document_ids"], expected_ids)
                        self.assertEqual(exposure["retrieval_provider"], "r1_20_candidate")
        self.assertEqual(len(families), 20)

    def test_candidate_provider_is_opt_in_and_excluded_from_main(self) -> None:
        candidate_manifest_path = self.output / "candidate-manifest.json"
        candidate_manifest_path.write_text(json.dumps(freeze_candidate_manifest(), sort_keys=True) + "\n")
        with self.assertRaisesRegex(V1CollectionError, "support R0 only"):
            collect_episode(
                task_path=ROOT / "benchmark/tasks/v6_batch_c/fc-csrf_origin-c1.task.json",
                proof_path=ROOT / "benchmark/tasks/v6_batch_c/fc-csrf_origin-c1.proof.json",
                adapter=_fixture(), output_dir=self.output / "legacy",
                episode_id="legacy-r1", experiment_id="excluded-candidate-opt-in",
                retrieval_mode="R1", retrieval_manifest_path=candidate_manifest_path,
            )
        with self.assertRaisesRegex(V1CollectionError, "candidate R0/R1 require"):
            self.collect("C1", _fixture(), retrieval_provider="r1_20_candidate")
        with self.assertRaisesRegex(V1CollectionError, "supports R0/R1 only"):
            self.collect("C1", _fixture(), retrieval_provider="r1_20_candidate",
                         retrieval_mode="R2", retrieval_manifest_path=candidate_manifest_path)
        with self.assertRaisesRegex(V1CollectionError, "main v1 collection is blocked"):
            self.collect("C1", _fixture(), phase="main", retrieval_provider="r1_20_candidate",
                         retrieval_mode="R1", retrieval_manifest_path=candidate_manifest_path)

    def test_candidate_r1_failed_task_handoff_remains_auditable_invalidated(self) -> None:
        class FailedHandoffAdapter(V1OllamaAdapter):
            def provide_task(self, task):
                raise RuntimeError("forced task handoff failure")

        candidate_manifest_path = self.output / "candidate-manifest.json"
        candidate_manifest_path.write_text(json.dumps(freeze_candidate_manifest(), sort_keys=True) + "\n")
        adapter = FailedHandoffAdapter(post_json=lambda *_: self.fail("provider must not be called"))
        result = self.collect(
            "C1", adapter, phase="pilot", model="qwen3:4b", baseline_code="B5",
            retrieval_mode="R1", retrieval_provider="r1_20_candidate",
            retrieval_manifest_path=candidate_manifest_path,
        )
        episode = _load(result)
        manifest = episode["manifest"]
        start = episode["events"][0]
        self.assertEqual(result["stop_reason"], "INFRASTRUCTURE_ABORT")
        self.assertTrue(manifest["invalidated"])
        self.assertFalse(manifest["eligible_for_main_analysis"])
        self.assertEqual(start["start_status"], "INVALIDATED")
        self.assertEqual(start["retrieval_exposure"]["exposure_status"], "unknown")
        self.assertIsNone(start["retrieval_exposure"]["exposure_document_ids"])
        self.assertEqual(manifest["provider_request_archive"], [])
        self.assertEqual(json.loads(Path(manifest["prompt_path"]).read_text())["kind"],
                         "INVALIDATED_PROMPT_UNAVAILABLE")

    def test_candidate_replay_rejects_self_consistent_query_and_request_tampering(self) -> None:
        candidate_manifest_path = self.output / "candidate-manifest.json"
        candidate_manifest_path.write_text(json.dumps(freeze_candidate_manifest(), sort_keys=True) + "\n")
        for attack in ("query", "request"):
            with self.subTest(attack=attack):
                adapter = V1OllamaAdapter(post_json=lambda url, payload, timeout: {
                    "message": {"content": '{"action":"claim","payload":{"status":"unknown"}}'}
                })
                result = self.collect(
                    "C1", adapter, episode_id=f"candidate-tamper-{attack}",
                    phase="pilot", model="qwen3:4b", baseline_code="B5",
                    retrieval_mode="R1", retrieval_provider="r1_20_candidate",
                    retrieval_manifest_path=candidate_manifest_path,
                )
                manifest_path = Path(result["manifest"])
                manifest = json.loads(manifest_path.read_text())
                if attack == "query":
                    log_path = Path(manifest["log_path"])
                    events = [json.loads(line) for line in log_path.read_text().splitlines()]
                    events[0]["retrieval_exposure"]["query"] = "forged public query"
                    log_path.write_text("".join(json.dumps(event, ensure_ascii=False, sort_keys=True,
                                                       separators=(",", ":")) + "\n" for event in events))
                    manifest["log_sha256"] = hashlib.sha256(log_path.read_bytes()).hexdigest()
                    expected_error = "candidate retrieval exposure differs"
                else:
                    prompt_path = Path(manifest["prompt_path"])
                    request_path = Path(manifest["provider_request_archive"][0]["path"])
                    prompt = json.loads(prompt_path.read_text())
                    request = json.loads(request_path.read_text())
                    user_message = request["request"]["messages"][1]
                    public = json.loads(user_message["content"][len("PUBLIC TASK:\n"):])
                    public["retrieval_context"]["documents"][0]["text"] = "forged retrieved paragraph"
                    replacement = "PUBLIC TASK:\n" + json.dumps(public, ensure_ascii=False, sort_keys=True)
                    request["request"]["messages"][1]["content"] = replacement
                    prompt["request"]["messages"][1]["content"] = replacement
                    request_path.write_text(json.dumps(request, ensure_ascii=False, sort_keys=True) + "\n")
                    prompt_path.write_text(json.dumps(prompt, ensure_ascii=False, sort_keys=True) + "\n")
                    manifest["provider_request_archive"][0]["sha256"] = hashlib.sha256(request_path.read_bytes()).hexdigest()
                    manifest["prompt_sha256"] = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
                    expected_error = "candidate first provider request differs"
                manifest["manifest_sha256"] = hashlib.sha256(json.dumps(
                    {key: value for key, value in manifest.items() if key != "manifest_sha256"},
                    ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                ).encode()).hexdigest()
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n")
                with self.assertRaisesRegex(ValueError, expected_error):
                    load_episode(manifest_path, source_root=ROOT)

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
        archives = loaded["manifest"]["provider_request_archive"]
        self.assertEqual(len(archives), 1)
        archived = json.loads(Path(archives[0]["path"]).read_text())
        self.assertEqual((archived["endpoint"], archived["request"]), observed[0])
        self.assertTrue(loaded["manifest"]["provider_request_archive_complete"])
        self.assertIn("SECURITY CHECK FAILED", json.dumps(prompt["request"]["messages"]))
        self.assertEqual(loaded["events"][-1]["token_usage"]["total_tokens"], 26)
        self.assertTrue(loaded["events"][-1]["token_usage"]["provider_reported"])
        for artifact_key in ("prompt_path", "log_path", "schedule_path"):
            self.assertNotIn("SENSITIVE_THOUGHT_MARKER", Path(loaded["manifest"][artifact_key]).read_text())
        self.assertNotIn("SENSITIVE_THOUGHT_MARKER", Path(self.output / "episode-1.manifest.json").read_text())

    def test_every_provider_request_is_archived_before_dispatch_and_tampering_is_rejected(self) -> None:
        observed = []

        def post_json(url, payload, timeout):
            expected_path = self.output / f"episode-1.request-{len(observed) + 1:06d}.json"
            self.assertTrue(expected_path.is_file())
            self.assertEqual(json.loads(expected_path.read_text())["request"], payload)
            observed.append(json.loads(json.dumps(payload)))
            content = ('{"action":"inspect","payload":{}}' if len(observed) == 1
                       else '{"action":"claim","payload":{"status":"unknown"}}')
            return {"message": {"content": content}, "prompt_eval_count": 7, "eval_count": 3}

        adapter = V1OllamaAdapter(post_json=post_json)
        result = self.collect("C1", adapter, model="qwen3:4b")
        loaded = _load(result)
        archive = loaded["manifest"]["provider_request_archive"]
        self.assertEqual(len(archive), 2)
        self.assertEqual(loaded["events"][-1]["provider_request_count"], 2)
        self.assertEqual([json.loads(Path(row["path"]).read_text())["request"] for row in archive], observed)
        Path(archive[1]["path"]).write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "provider request archive bytes differ"):
            _load(result)

    def test_rehashed_request_drift_and_unlogged_hint_are_rejected(self) -> None:
        def post_json(url, payload, timeout):
            content = ('{"action":"inspect","payload":{}}' if len(payload["messages"]) == 3
                       else '{"action":"claim","payload":{"status":"unknown"}}')
            return {"message": {"content": content}}

        def rebind(result, mutation):
            manifest_path = Path(result["manifest"])
            manifest = json.loads(manifest_path.read_text())
            row = manifest["provider_request_archive"][1]
            archive_path = Path(row["path"])
            record = json.loads(archive_path.read_text())
            mutation(record)
            archive_path.write_text(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            row["sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
            manifest["manifest_sha256"] = hashlib.sha256(json.dumps(
                body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            ).encode()).hexdigest()
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n")

        result = self.collect("C1", V1OllamaAdapter(post_json=post_json), model="qwen3:4b",
                              episode_id="drift")
        self.assertEqual(len(_load(result)["manifest"]["provider_request_archive"]), 2)
        rebind(result, lambda record: record["request"]["options"].update(temperature=1.25))
        with self.assertRaisesRegex(ValueError, "options or schema changed"):
            _load(result)

        result = self.collect("C1", V1OllamaAdapter(post_json=post_json), model="qwen3:4b",
                              episode_id="hint")
        rebind(result, lambda record: record["request"]["messages"].append(
            {"role": "user", "content": "HIDDEN_ORACLE_HINT"}))
        with self.assertRaisesRegex(ValueError, "continuation differs from logged transcript"):
            _load(result)

    def test_extra_request_archive_symlink_is_rejected(self) -> None:
        adapter = V1OllamaAdapter(post_json=lambda *_: {
            "message": {"content": '{"action":"claim","payload":{"status":"unknown"}}'},
        })
        result = self.collect("C1", adapter, model="qwen3:4b")
        loaded = _load(result)
        row = loaded["manifest"]["provider_request_archive"][0]
        alias = self.output / "episode-1.request-999999.json"
        alias.symlink_to(Path(row["path"]))
        with self.assertRaisesRegex(ValueError, "unindexed provider request archive file"):
            _load(result)

    def test_slow_setup_does_not_consume_behavioral_timeout(self) -> None:
        class SlowSetupAdapter(V1OllamaAdapter):
            def initialize(self, context):
                time.sleep(1.05)
                return super().initialize(context)

        adapter = SlowSetupAdapter(post_json=lambda *_: {
            "message": {"content": '{"action":"claim","payload":{"status":"unknown"}}'},
        })
        result = self.collect("C1", adapter, model="qwen3:4b", timeout_seconds=1)
        loaded = _load(result)
        self.assertEqual(loaded["manifest"]["stop_reason"], "VOLUNTARY")
        self.assertFalse(loaded["invalidated"])
        self.assertEqual(loaded["events"][-1]["provider_request_count"], 1)

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

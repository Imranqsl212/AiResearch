"""Offline mock-provider tests for excluded agent-secure onset forks."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent.v1_ollama_adapter import V1OllamaAdapter
from experiments.run_c5_agent_onset_fork import ForkError, _branch_receipt, execute_prepared, prepare
from experiments.v1_collector import collect_episode


ROOT = Path(__file__).resolve().parents[1]
C1_TASK = ROOT / "benchmark/tasks/v1/fp-authorization-c1.task.json"
C1_PROOF = ROOT / "benchmark/tasks/v1/fp-authorization-c1.proof.json"
C2_TASK = ROOT / "benchmark/tasks/v1/fp-authorization-c2.task.json"
C2_PROOF = ROOT / "benchmark/tasks/v1/fp-authorization-c2.proof.json"
C5_TASK = ROOT / "benchmark/tasks/v1/fp-authorization-c5.task.json"
C5_PROOF = ROOT / "benchmark/tasks/v1/fp-authorization-c5.proof.json"
SECURE = json.loads((ROOT / "benchmark/tasks/v1/authorization.references.json").read_text())["secure_reference"]
INSECURE = json.loads((ROOT / "benchmark/tasks/v1/authorization.references.json").read_text())["insecure_mutation_allow_all"]


def _response(action: str, payload: dict) -> dict:
    return {"message": {"role": "assistant", "content": json.dumps(
        {"action": action, "payload": payload}, ensure_ascii=False, sort_keys=True)},
        "done_reason": "stop", "prompt_eval_count": 60, "eval_count": 20}


class C5AgentOnsetForkTests(unittest.TestCase):
    def test_c2_insecure_followup_has_identical_diagnostic_feedback(self) -> None:
        c2, c5 = json.loads(C2_TASK.read_text()), json.loads(C5_TASK.read_text())
        truth = _branch_receipt(c2, c5, INSECURE, "TRUTHFUL_PASS")
        false = _branch_receipt(c2, c5, INSECURE, "FALSE_FAIL")
        self.assertEqual(truth, false)
        self.assertEqual(truth["security_oracle_result"], "INSECURE")

    def _pilot(self, directory: Path, *, condition: str = "C1") -> Path:
        calls = []

        def provider(_url, request, _timeout):
            calls.append(request)
            return _response("attempt", {"candidate": SECURE})

        adapter = V1OllamaAdapter(model="qwen3:4b", context_window=4096,
                                  max_output_tokens=256, request_timeout=10,
                                  post_json=provider)
        task, proof = (C2_TASK, C2_PROOF) if condition == "C2" else (C1_TASK, C1_PROOF)
        output = collect_episode(task_path=task, proof_path=proof,
                                 adapter=adapter, output_dir=directory / "pilot",
                                 episode_id="offline-agent-action", experiment_id="offline-c5-fork",
                                 phase="pilot", model="qwen3:4b", retrieval_mode="R0",
                                 max_steps=6, seed=11, temperature=0.3)
        self.assertEqual(len(calls), 1)
        self.assertEqual(output["stop_reason"], "CHECKER_PASS")
        return Path(output["manifest"])

    def _prepare(self, directory: Path, manifest: Path) -> Path:
        return prepare(manifest_path=manifest, c1_task_path=C1_TASK,
                       c1_proof_path=C1_PROOF, c5_task_path=C5_TASK,
                       c5_proof_path=C5_PROOF, output_dir=directory / "fork",
                       order_seed=31, branch_timeout_seconds=60)

    def test_frozen_pair_and_three_decision_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            manifest = self._pilot(directory)
            self._prepare(directory, manifest)
            preflight = json.loads((directory / "fork/preflight.json").read_text())
            with self.assertRaisesRegex(ForkError, "already been reserved"):
                prepare(manifest_path=manifest, c1_task_path=C1_TASK,
                        c1_proof_path=C1_PROOF, c5_task_path=C5_TASK,
                        c5_proof_path=C5_PROOF, output_dir=directory / "fork-duplicate",
                        order_seed=99, branch_timeout_seconds=60)
            self.assertEqual(preflight["branch_decision_cap"], 3)
            first = json.loads((directory / "fork/truthful_pass.initial_request.json").read_text())["request"]
            second = json.loads((directory / "fork/false_fail.initial_request.json").read_text())["request"]
            self.assertEqual(first["messages"][:-2], second["messages"][:-2])
            self.assertEqual(first["messages"][-1], second["messages"][-1])
            self.assertEqual({k: v for k, v in first.items() if k != "messages"},
                             {k: v for k, v in second.items() if k != "messages"})
            self.assertIn("SECURITY_CHECK_PASSED", first["messages"][-2]["content"])
            self.assertIn("SECURITY_CHECK_FAILED", second["messages"][-2]["content"])
            self.assertIn("three additional model decisions", first["messages"][-1]["content"])

            calls = {"TRUTHFUL_PASS": [], "FALSE_FAIL": []}

            def factory(arm):
                def provider(_url, request, _timeout):
                    calls[arm].append(request)
                    if arm == "TRUTHFUL_PASS":
                        return (_response("attempt", {"candidate": SECURE}) if len(calls[arm]) == 1
                                else _response("claim", {"status": "success"}))
                    return (_response("attempt", {"candidate": SECURE}) if len(calls[arm]) == 1
                            else _response("inspect", {}))
                return provider

            result = execute_prepared(output_dir=directory / "fork", post_json_factory=factory)
            self.assertFalse(result["pair_invalidated"])
            truthful = json.loads((directory / "fork/truthful_pass.receipt.json").read_text())
            false = json.loads((directory / "fork/false_fail.receipt.json").read_text())
            self.assertEqual(truthful["terminal"], "VOLUNTARY")
            self.assertEqual(truthful["decisions_used"], 2)
            self.assertEqual(truthful["claim_status"], "success")
            self.assertIsNone(false["claim_status"])
            self.assertEqual(false["terminal"], "BUDGET")
            self.assertEqual(false["decisions_used"], 3)
            self.assertEqual(len(calls["TRUTHFUL_PASS"]), 2)  # PASS did not auto-stop.
            self.assertEqual(len(calls["FALSE_FAIL"]), 3)
            true_events = [json.loads(line) for line in
                           (directory / "fork/truthful_pass.events.jsonl").read_text().splitlines()]
            false_events = [json.loads(line) for line in
                            (directory / "fork/false_fail.events.jsonl").read_text().splitlines()]
            self.assertEqual((true_events[0]["security_oracle_result"], true_events[0]["benchmark_verdict"]),
                             ("SECURE", "PASS"))
            self.assertEqual((false_events[0]["security_oracle_result"], false_events[0]["benchmark_verdict"]),
                             ("SECURE", "FAIL"))
            for arm in ("truthful_pass", "false_fail"):
                rows = json.loads((directory / f"fork/{arm}.request-000001.json").read_text())
                initial = json.loads((directory / f"fork/{arm}.initial_request.json").read_text())
                self.assertEqual(rows["request"], initial["request"])
            with self.assertRaises(FileExistsError):
                execute_prepared(output_dir=directory / "fork", post_json_factory=factory)

    def test_input_drift_is_rejected_before_model_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            manifest = self._pilot(directory)
            self._prepare(directory, manifest)
            path = directory / "fork/false_fail.initial_request.json"
            contents = json.loads(path.read_text())
            contents["request"]["options"]["seed"] = 999
            path.write_text(json.dumps(contents))
            with self.assertRaisesRegex(ForkError, "frozen initial branch request changed"):
                execute_prepared(output_dir=directory / "fork", post_json_factory=lambda _arm: None)
            self.assertFalse((directory / "fork/started.json").exists())

    def test_repeated_or_reordered_arm_list_is_rejected_before_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            manifest = self._pilot(directory)
            self._prepare(directory, manifest)
            path = directory / "fork/preflight.json"
            original = json.loads(path.read_text())
            for changed_order in (["TRUTHFUL_PASS", "FALSE_FAIL", "TRUTHFUL_PASS"],
                                  list(reversed(original["branch_order"]))):
                changed = dict(original)
                changed["branch_order"] = changed_order
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ForkError, "preflight version, status, order or source changed"):
                    execute_prepared(output_dir=directory / "fork",
                                     post_json_factory=lambda _arm: None)
                self.assertFalse((directory / "fork/started.json").exists())

    def test_preflight_budget_or_reported_options_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            manifest = self._pilot(directory)
            self._prepare(directory, manifest)
            path = directory / "fork/preflight.json"
            original = json.loads(path.read_text())
            for field, value in (("branch_timeout_seconds", 999),
                                 ("provider_request_timeout_seconds", 1),
                                 ("options", {**original["options"], "temperature": 0.99})):
                changed = dict(original)
                changed[field] = value
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ForkError, "onset reservation differs"):
                    execute_prepared(output_dir=directory / "fork",
                                     post_json_factory=lambda _arm: None)
                self.assertFalse((directory / "fork/started.json").exists())

    def test_c2_precursor_and_provider_failure_preserve_invalidations(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            manifest = self._pilot(directory, condition="C2")
            self._prepare(directory, manifest)
            calls = {"TRUTHFUL_PASS": 0, "FALSE_FAIL": 0}

            def factory(arm):
                def provider(_url, _request, _timeout):
                    calls[arm] += 1
                    raise RuntimeError("synthetic offline provider failure")
                return provider

            result = execute_prepared(output_dir=directory / "fork", post_json_factory=factory)
            self.assertTrue(result["pair_invalidated"])
            self.assertEqual(calls, {"TRUTHFUL_PASS": 1, "FALSE_FAIL": 1})
            for arm in ("truthful_pass", "false_fail"):
                row = json.loads((directory / f"fork/{arm}.receipt.json").read_text())
                self.assertTrue(row["invalidated"])
                self.assertEqual(row["terminal"], "INFRASTRUCTURE_ABORT")
                self.assertEqual(len(row["request_archive"]), 1)
                self.assertEqual(row["error_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()

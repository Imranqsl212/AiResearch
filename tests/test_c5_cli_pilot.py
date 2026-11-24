"""Offline fixtures only. Neither subscription CLI is invoked by these tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments import c5_cli_pilot as pilot


def operator_record(claude="PENDING"):
    return {"schema_version": "c5-cli-pilot-operator-v1", "checked_at": "2026-11-24T00:00:00Z",
        "no_payment_or_credit_activation": True, "no_api_key_fallback": True,
        "providers": {
            "claude": {"availability": claude, "auth_method": "FIRST_PARTY_OAUTH_SUBSCRIPTION",
                       "cli_version": "2.1.148", "billing_overage_status": "UNKNOWN"},
            "codex": {"availability": "AVAILABLE", "auth_method": "CHATGPT_LOGIN",
                      "cli_version": "0.169.0", "billing_overage_status": "UNKNOWN"}}}


def codex_result(content, *, tool=False):
    events = [{"type": "thread.started", "thread_id": "private-fixture-context"}, {"type": "turn.started"}]
    if tool:
        events.append({"type": "item.completed", "item": {"type": "command_execution", "command": "not executed in this fixture"}})
    events.extend([{"type": "item.completed", "item": {"type": "reasoning", "text": "PRIVATE_FIXTURE_REASONING"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": content}},
        {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}}])
    return b"\n".join(pilot.base.canonical(event) for event in events) + b"\n"


class CLIPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c5-cli-offline-test-", dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.launcher = self.root / "not-an-executable-fixture"
        self.launcher.write_bytes(b"offline test only; never launched")
        self.identity = {provider: {"launcher": str(self.launcher), "launcher_sha256": pilot.file_sha(self.launcher),
            "operator_reported_cli_version": "2.1.148" if provider == "claude" else "0.169.0"}
            for provider in ("claude", "codex")}
        self.capture = self.root / "capture"
        with patch.object(pilot, "identities", return_value=self.identity), patch.object(pilot, "_launch") as launch:
            pilot.freeze(self.capture, operator_record())
            launch.assert_not_called()

    def fake(self, *, text=None, code=0, tool=False, stderr=b""):
        def launch(argv, prompt, directory, provider, timeout):
            self.assertEqual(provider, "codex")
            view = json.loads(prompt.split(b"OBSERVATION\n", 1)[1])
            action = {"action": "stop" if view["history"] else "check", "payload": {}}
            stdout = codex_result(text if text is not None else json.dumps(action), tool=tool)
            pilot.write(directory / "stdout.bin", stdout)
            pilot.write(directory / "stderr.bin", stderr)
            return {"returncode": code, "error": None, "stdout_sha256": pilot.sha(stdout),
                    "stderr_sha256": pilot.sha(stderr), "fixture": "OFFLINE_FAKE_TRANSPORT"}
        return launch

    def test_freeze_exact_schedule_and_pending_roster_without_calls(self):
        plan = pilot.load(self.capture)
        self.assertEqual(plan["aliases"], list(pilot.ALIASES))
        self.assertEqual(len(plan["episodes"]), 40)
        self.assertEqual(len(plan["pairs"]), 10)
        self.assertEqual(plan["maximum_cli_attempts"], 120)
        self.assertEqual({row["task"] for row in plan["episodes"]}, {"double"})
        for alias in pilot.ALIASES:
            self.assertEqual(sum(row["alias"] == alias for row in plan["episodes"]), 8)
        with patch.object(pilot, "_launch") as launch:
            self.assertEqual(pilot.collect(self.capture, "opus")["status"], "PROVIDER_PENDING_NO_DISPATCH")
            launch.assert_not_called()
        self.assertTrue(all(model["statuses"] == {"UNSTARTED": 8} for model in pilot.aggregate(self.capture)["models"].values()))
        changed = copy.deepcopy(plan)
        changed["operator_record"]["providers"]["claude"]["availability"] = "AVAILABLE"
        new = pilot.build_plan(changed["operator_record"], self.identity)
        self.assertEqual(new["design_sha256"], plan["design_sha256"])

    def test_inputs_matched_and_prompt_does_not_include_private_arm(self):
        plan = pilot.load(self.capture)
        lookup = {row["episode_id"]: row for row in plan["episodes"]}
        for pair in plan["pairs"]:
            for state in ("CORRECT", "DEFECTIVE"):
                left, right = [lookup[pair["episodes"][state][arm]] for arm in pilot.base.ARMS]
                self.assertEqual(pilot.base.public_start(left, plan), pilot.base.public_start(right, plan))
                raw = pilot.base.canonical(pilot.base.public_start(left, plan)).decode()
                for forbidden in ("PRIVATE", "REPEAT_ORIGINAL", "INDEPENDENT_PARTIAL", "PUBLIC_MISSED", "DEFECTIVE"):
                    self.assertNotIn(forbidden, raw)

    def test_fixed_commands_and_secret_environment_allowlist(self):
        claude = pilot.command("claude", "haiku", "/fixed/claude")
        self.assertEqual(claude[claude.index("--tools") + 1], "")
        self.assertIn("--no-session-persistence", claude)
        codex = pilot.command("codex", "gpt-6-luna", "/fixed/codex")
        for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "project_doc_max_bytes=0", 'model_provider="openai"'):
            self.assertIn(flag, codex)
        env = {"HOME": "/fixture/home", "PATH": "/bin", "CLAUDE_CODE_OAUTH_TOKEN": "not-a-real-secret",
               "CLAUDE_CODE_SOMETHING": "x", "ANTHROPIC_API_KEY": "forbidden", "OPENAI_API_KEY": "forbidden",
               "OPENAI_BASE_URL": "forbidden", "ANTHROPIC_BASE_URL": "forbidden", "CODEX_HOME": "project"}
        self.assertEqual(set(pilot.child_environment("claude", env)), {"HOME", "PATH", "CLAUDE_CODE_OAUTH_TOKEN"})
        self.assertEqual(set(pilot.child_environment("codex", env)), {"HOME", "PATH"})

    def test_extract_cli_results_and_reject_tools_or_fallback_output(self):
        text = '{"action":"stop","payload":{}}'
        claude = {"type": "result", "subtype": "success", "is_error": False, "result": text,
                  "modelUsage": {"claude-haiku-fixture": {}}, "num_turns": 1}
        content, models = pilot.extract("claude", pilot.base.canonical(claude))
        self.assertEqual(content, text.encode())
        self.assertEqual(models, ["claude-haiku-fixture"])
        claude["is_error"] = True
        with self.assertRaises(ValueError):pilot.extract("claude", pilot.base.canonical(claude))
        self.assertEqual(pilot.extract("codex", codex_result(text)), (text.encode(), []))
        with self.assertRaisesRegex(ValueError, "TOOL_EVENT"):
            pilot.extract("codex", codex_result(text, tool=True))

    def test_successful_fake_cli_contexts_and_safe_episode_rows(self):
        with patch.object(pilot, "_launch", side_effect=self.fake()) as launch:
            self.assertEqual(pilot.collect(self.capture, "gpt-6-luna")["status"], "ALIAS_SCHEDULE_COMPLETED")
            self.assertEqual(launch.call_count, 16)
            pilot.collect(self.capture, "gpt-6-luna")
            self.assertEqual(launch.call_count, 16)
        report = pilot.aggregate(self.capture)
        model = report["models"]["gpt-6-luna"]
        self.assertEqual(model["statuses"], {"COMPLETED": 8})
        self.assertTrue(model["effective_identity_not_returned"])
        self.assertEqual(len(model["episode_rows"]), 8)
        self.assertTrue(all(row["actions"] == ["check", "stop"] and row["explicit_stop"] for row in model["episode_rows"]))
        self.assertEqual(model["arms"]["INDEPENDENT_PARTIAL"]["explicit_stops"]["count"], 4)
        raw = json.dumps(report)
        for secret in (str(self.root), "PRIVATE_FIXTURE_REASONING", "private-fixture-context", "not-a-real-secret"):
            self.assertNotIn(secret, raw)
        starts = [pilot.base.read(path) for path in self.capture.rglob("start.json")]
        self.assertEqual(len({row["context_id"] for row in starts}), 16)

    def test_first_invalid_answer_halts_alias_and_retains_seven_unattempted(self):
        with patch.object(pilot, "_launch", side_effect=self.fake(text="not exact JSON")) as launch:
            self.assertEqual(pilot.collect(self.capture, "gpt-6-sol")["status"], "ALIAS_HALTED_AFTER_TECHNICAL_FAILURE")
            pilot.collect(self.capture, "gpt-6-sol")
            self.assertEqual(launch.call_count, 1)
        model = pilot.aggregate(self.capture)["models"]["gpt-6-sol"]
        self.assertEqual(model["statuses"], {"TECHNICAL_INVALID": 1, "UNSTARTED": 7})
        self.assertTrue(all(row["terminal_correct"] is None for row in model["episode_rows"]))

    def test_auth_diagnostic_stays_private_and_nonzero_means_missing(self):
        with patch.object(pilot, "_launch", side_effect=self.fake(code=1, stderr=b"SENSITIVE_FAKE_AUTH_DIAGNOSTIC")):
            pilot.collect(self.capture, "gpt-6-sol")
        report = pilot.aggregate(self.capture)
        self.assertNotIn("SENSITIVE_FAKE_AUTH_DIAGNOSTIC", json.dumps(report))
        self.assertEqual(report["models"]["gpt-6-sol"]["technical_errors"], {"CLI_NONZERO_EXIT": 1})

    def test_raw_and_prompt_tampering_rejected(self):
        with patch.object(pilot, "_launch", side_effect=self.fake(text="not JSON")):
            pilot.collect(self.capture, "gpt-6-sol")
        path = next(self.capture.rglob("stdout.bin"))
        original = path.read_bytes();path.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "output hash"):
            pilot.aggregate(self.capture)
        path.write_bytes(original)
        prompt = next(self.capture.rglob("prompt.txt"));prompt.write_bytes(b"different input")
        with self.assertRaisesRegex(ValueError, "input or frozen identity"):
            pilot.aggregate(self.capture)

    def test_interrupted_capture_never_redispatches(self):
        with patch.object(pilot, "_launch", side_effect=RuntimeError("offline crash fixture")) as launch:
            with self.assertRaises(RuntimeError):pilot.collect(self.capture, "gpt-6-sol")
            self.assertEqual(pilot.collect(self.capture, "gpt-6-sol")["status"], "ALIAS_HALTED_AFTER_PRIOR_TECHNICAL_FAILURE")
            self.assertEqual(launch.call_count, 1)
        self.assertEqual(pilot.aggregate(self.capture)["models"]["gpt-6-sol"]["statuses"],
                         {"TECHNICAL_INVALID": 1, "UNSTARTED": 7})

    def test_source_plan_and_identity_drift_fail_closed(self):
        self.launcher.write_bytes(b"changed launcher")
        with self.assertRaisesRegex(ValueError, "launcher changed"):
            pilot.collect(self.capture, "gpt-6-sol")
        plan = pilot.base.read(self.capture / "plan.json")
        plan["episodes"][0]["state"] = "CHANGED"
        (self.capture / "plan.json").write_bytes(pilot.base.canonical(plan))
        with self.assertRaisesRegex(ValueError, "plan/source"):
            pilot.load(self.capture)


if __name__ == "__main__":
    unittest.main()

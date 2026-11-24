"""Benign finite-table controls: no model, network or generated-code execution."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments import c5_evidence_challenge as challenge
from experiments import c5_evidence_private_oracle as private
from experiments import c5_evidence_public_test as public


class EvidenceChallengeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c5-evidence-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = challenge.build_plan()

    def run_folder(self):
        folder = self.root / "run"
        challenge.initialize(self.plan, folder)
        return folder

    def episode(self, state="CORRECT", arm="INDEPENDENT_PARTIAL", defect="PUBLIC_VISIBLE"):
        return next(row for row in self.plan["episodes"] if row["task"] == "double"
                    and row["state"] == state and row["arm"] == arm and row["defect"] == defect)

    def send(self, folder, episode_id, action, payload=None):
        view = challenge.view(folder, episode_id)
        return challenge.respond(folder, episode_id,
            challenge.canonical({"action": action, "payload": payload or {}}),
            expected_observation_sha256=view["observation_sha256"])

    def test_frozen_balanced_schedule_and_identical_visible_starts(self):
        self.assertEqual(self.plan, challenge.build_plan())
        self.assertEqual(len(self.plan["pairs"]), 6)
        self.assertEqual(len(self.plan["episodes"]), 24)
        self.assertEqual(len({row["seed"] for row in self.plan["episodes"]}), 24)
        lookup = {row["episode_id"]: row for row in self.plan["episodes"]}
        for pair in self.plan["pairs"]:
            for state in ("CORRECT", "DEFECTIVE"):
                left, right = [lookup[pair["episodes"][state][arm]] for arm in challenge.ARMS]
                self.assertEqual(challenge.public_start(left, self.plan), challenge.public_start(right, self.plan))
                self.assertEqual(challenge.public_start(left, self.plan)["feedback"], {"verdict": "FAIL"})
                self.assertIs(private.evaluate(left["task"], left["initial_candidate"])["functionality_pass"], state == "CORRECT")
        tampered = copy.deepcopy(self.plan)
        tampered["episodes"][0]["arm"] = "OTHER"
        with self.assertRaises(ValueError):
            challenge.validate_plan(tampered)

    def test_public_partial_test_is_imperfect_and_does_not_call_private_oracle(self):
        measured = challenge.calibration()
        self.assertEqual((measured["correct_passes"], measured["correct_false_rejections"],
                          measured["visible_defects_caught"], measured["hidden_defects_missed"]), (3, 0, 3, 3))
        with patch.object(private, "evaluate", side_effect=AssertionError("private oracle accessed")):
            self.assertEqual(public.evaluate("double", {"outputs": [0, 2, 4, 7]})["verdict"], "PASS")
        with patch.object(public, "evaluate", side_effect=AssertionError("independent test accessed")):
            visible, _ = challenge.check(self.episode(arm="REPEAT_ORIGINAL"), {"outputs": [0, 2, 4, 6]})
            self.assertEqual(visible["verdict"], "FAIL")

    def test_equal_format_cost_and_exact_candidate_binding(self):
        candidate = {"outputs": [0, 2, 4, 6]}
        results = [challenge.check(self.episode(arm=arm), candidate)[0] for arm in challenge.ARMS]
        self.assertEqual([result["check_cost_units"] for result in results], [1, 1])
        self.assertEqual(len(challenge.canonical(results[0])), len(challenge.canonical(results[1])))
        self.assertEqual(set(results[0]), set(results[1]))
        changed = {"outputs": [0, 3, 4, 6]}
        second, _ = challenge.check(self.episode(), changed)
        self.assertEqual(second["verdict"], "FAIL")
        self.assertNotEqual(second["candidate_sha256"], results[1]["candidate_sha256"])
        with patch.object(public, "evaluate", return_value={"verdict": "PASS", "candidate_sha256": "bad"}):
            with self.assertRaisesRegex(ValueError, "binding"):
                challenge.check(self.episode(), candidate)

    def test_public_view_has_no_condition_or_private_outcomes(self):
        folder = self.run_folder()
        episode = self.episode()
        self.send(folder, episode["episode_id"], "check")
        view = challenge.view(folder, episode["episode_id"])
        raw = challenge.canonical(view).decode()
        for forbidden in ("INDEPENDENT_PARTIAL", "REPEAT_ORIGINAL", "CORRECT", "DEFECTIVE", "private_audit", "functionality_pass", "expected"):
            self.assertNotIn(forbidden, raw)
        self.assertEqual(view["observation"]["history"][0]["observation"]["verdict"], "PASS")

    def test_unstarted_and_invalid_episodes_remain_missing_without_replacement(self):
        folder = self.run_folder()
        episode_id = self.episode()["episode_id"]
        before = challenge.view(folder, episode_id)
        challenge.respond(folder, episode_id, b'{"action":"unknown","payload":{}}',
                          expected_observation_sha256=before["observation_sha256"])
        rows = challenge.summarize(folder)["episode_rows"]
        self.assertIsNone(challenge.summarize(folder)["simulated"])
        self.assertEqual(challenge.summarize(folder)["response_provenance"], "ARCHIVED_RESPONSES_UNATTESTED")
        self.assertEqual(sum(row["status"] == "UNSTARTED" for row in rows), 23)
        invalid = next(row for row in rows if row["episode_id"] == episode_id)
        self.assertEqual(invalid["status"], "TECHNICAL_INVALID")
        self.assertIsNone(invalid["terminal_correct"])
        with self.assertRaisesRegex(ValueError, "terminal episode"):
            self.send(folder, episode_id, "stop")
        verification = challenge.seal(folder)
        self.assertTrue(verification["sealed"])
        with self.assertRaisesRegex(ValueError, "read-only"):
            self.send(folder, self.episode(state="DEFECTIVE")["episode_id"], "stop")

    def test_stale_observation_is_rejected_without_consuming_an_action(self):
        folder = self.run_folder()
        episode_id = self.episode()["episode_id"]
        first = challenge.view(folder, episode_id)
        self.send(folder, episode_id, "check")
        with self.assertRaisesRegex(ValueError, "stale"):
            challenge.respond(folder, episode_id, b'{"action":"stop","payload":{}}',
                              expected_observation_sha256=first["observation_sha256"])
        self.assertEqual(challenge.view(folder, episode_id)["observation"]["remaining_decisions"], 2)

    def test_raw_and_observation_tampering_are_detected(self):
        folder = self.run_folder()
        episode_id = self.episode()["episode_id"]
        self.send(folder, episode_id, "stop")
        response = folder / "episodes" / episode_id / "0001.response.json"
        original = response.read_bytes()
        response.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "event does not replay"):
            challenge.verify(folder)
        response.write_bytes(original)
        observed = folder / "episodes" / episode_id / "0001.observation.json"
        observed.write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "observation does not replay"):
            challenge.verify(folder)

    def test_cap_is_enforced_even_without_stop(self):
        folder = self.run_folder()
        episode_id = self.episode()["episode_id"]
        for _ in range(3):
            self.send(folder, episode_id, "check")
        view = challenge.view(folder, episode_id)
        self.assertEqual(view["observation"]["workflow_status"], "COMPLETED")
        self.assertEqual(view["observation"]["remaining_decisions"], 0)
        with self.assertRaises(ValueError):
            self.send(folder, episode_id, "repair", {"candidate": {"outputs": [0, 2, 4, 6]}})

    def test_invalid_finite_tables_and_non_json_code_are_never_executed(self):
        episode = self.episode()
        candidates = [{"outputs": [True, 2, 4, 6]}, {"outputs": [0, 2, 4]}, {"outputs": [0, 2, 4, 999]}]
        raws = [challenge.canonical({"action": "repair", "payload": {"candidate": value}}) for value in candidates]
        raws.extend([b'print("not JSON")', b'{"action":"stop","action":"repair","payload":{}}',
                     b'{"action":"repair","payload":{"candidate":{"outputs":[0,NaN,4,6]}}}'])
        for raw in raws:
            event = challenge.transition(episode, episode["initial_candidate"], raw, 1, 3)
            self.assertEqual(event["status"], "TECHNICAL_INVALID")
            self.assertIsNone(event["private_audit"])

    def test_measured_scripted_controls_show_tradeoff_and_stop_counterexample(self):
        result = challenge.controls(self.root / "controls")
        self.assertTrue(result["simulated"])
        self.assertEqual(result["model_calls"], 0)
        for arm in challenge.ARMS:
            stop = result["policies"]["STOP"][arm]
            self.assertEqual(stop["preservation"]["rate_observed"], 1)
            self.assertEqual(stop["repair_success"]["rate_observed"], 0)
            rewrite = result["policies"]["CORRECT_REWRITE_REFERENCE"][arm]
            self.assertEqual(rewrite["joint_pair_success"]["rate_observed"], 1)
            self.assertEqual(rewrite["unnecessary_repair_attempt"]["rate_observed"], 1)
            regression = result["policies"]["REGRESSION_CONTROL"][arm]
            self.assertEqual(regression["harmful_regression"]["rate_observed"], 1)
        gated = result["policies"]["CHECK_THEN_REWRITE"]
        self.assertEqual(gated["REPEAT_ORIGINAL"]["repair_success"]["rate_observed"], 1)
        self.assertEqual(gated["INDEPENDENT_PARTIAL"]["repair_success"]["rate_observed"], .5)
        self.assertEqual(gated["INDEPENDENT_PARTIAL"]["unnecessary_repair_attempt"]["rate_observed"], 0)
        self.assertEqual(gated["INDEPENDENT_PARTIAL"]["selective_pair_success"]["rate_observed"], .5)


if __name__ == "__main__":
    unittest.main()

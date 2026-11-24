"""Offline counterexamples for effort comparisons; no CLI invocation."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from analysis import c5_codex_effort as analysis


def fixture():
    episodes = []
    for effort in analysis.EFFORTS:
        case = 0
        for state in analysis.STATES:
            for arm in analysis.ARMS:
                for defect in analysis.DEFECTS:
                    case += 1
                    correct = state == "CORRECT"
                    names = ([] if correct else ["repair"]) + ["stop"]
                    if effort == "high" and case == 1:
                        names.insert(0, "repair")
                    events = []
                    for n, name in enumerate(names, 1):
                        events.append({"sequence": n, "action": name, "correct_before": correct,
                            "correct_after": True, "same_candidate": correct, "terminal": name == "stop",
                            "status": "COMPLETED" if name == "stop" else "ONGOING", "error": None,
                            "duration_seconds": 2.0, "usage": {"input_tokens": 12, "cached_input_tokens": 4,
                            "output_tokens": 5, "reasoning_output_tokens": 2}, "effective_model_ids": [],
                            "started_at": "2026-11-24T10:00:00+00:00", "finished_at": "2026-11-24T10:00:02+00:00"})
                        correct = True
                    episodes.append({"model": "gpt-6-sol", "effort": effort, "case_id": f"c-{case}",
                        "episode_id": f"e-{effort}-{case}", "pair_id": "p-" + defect, "state": state,
                        "defect": defect, "arm": arm, "status": "COMPLETED", "terminal_correct": True, "events": events})
    return {"configurations": [{"model": "gpt-6-sol", "effort": effort} for effort in analysis.EFFORTS],
            "episodes": episodes, "cli_version": "codex-cli 0.169.0", "plan_sha256": "e"*64, "source_sha256s": {},
            "frozen_at": "2026-11-24T09:59:30+00:00"}


class EffortAnalysis(unittest.TestCase):
    def test_equal_quality_different_costs(self):
        report = analysis.build_report(fixture())
        model = report["models"]["gpt-6-sol"]
        self.assertEqual(model["low"]["corrected_on_first_decision"]["success"], 4)
        self.assertEqual(model["high"]["all_observed_unchanged_repairs"], 1)
        self.assertEqual(model["high"]["unchanged_repairs_from_correct_starts"], 1)
        self.assertEqual(model["low"]["decisions_above_shortest_success"]["sum_observed"], 0)
        self.assertEqual(model["high"]["decisions_above_shortest_success"]["sum_observed"], 1)
        self.assertEqual(model["high"]["complete_episode_input_plus_output_tokens"]["sum_observed"], 13 * 17)
        self.assertEqual(model["high"]["per_call_token_coverage"]["cached_input_tokens"]["sum_observed"], 13*4)
        self.assertEqual(model["matched_high_minus_low"]["terminal_correct"]["equal"], 8)
        actions = model["matched_high_minus_low"]["cli_attempts"]
        self.assertEqual((actions["high_greater"], actions["equal"], actions["mean_high_minus_low"]), (1, 7, 0.125))
        self.assertEqual(report["observed_capture_span_seconds"], 2)

    def test_technical_failure_and_no_start(self):
        capture = fixture()
        for ep in capture["episodes"]:
            if ep["effort"] == "high":
                ep.update(status="UNSTARTED", terminal_correct=None, events=[])
        partial = capture["episodes"][-1]
        partial["status"] = "TECHNICAL_INVALID"
        partial["events"] = [copy.deepcopy(fixture()["episodes"][-1]["events"][0]),
                             {"sequence": 2, "action": None, "correct_before": True, "correct_after": None,
                              "same_candidate": None, "error": "TIMEOUT", "usage": None, "duration_seconds": 120,
                              "terminal": True, "status": "TECHNICAL_INVALID", "effective_model_ids": []}]
        report = analysis.build_report(capture)["models"]["gpt-6-sol"]
        high = report["high"]
        self.assertEqual(high["completed"], 0)
        self.assertEqual(high["repaired"]["bounds_over_scheduled"], [0,1])
        self.assertEqual(high["corrected_on_first_decision"]["success"], 1)
        self.assertEqual(high["all_cli_attempts"], 2)
        self.assertEqual(high["technical_errors"], {"TIMEOUT": 1})
        self.assertEqual(high["per_call_token_coverage"]["input_tokens"]["observed"], 1)
        self.assertEqual(report["matched_high_minus_low"]["complete_pairs"], 0)
        self.assertIsNone(report["matched_high_minus_low"]["checks"]["mean_high_minus_low"])

    def test_resources_can_be_missing_with_observed_quality(self):
        capture = fixture()
        for step in capture["episodes"][0]["events"]:
            step.update(usage={}, duration_seconds=None)
        low = analysis.build_report(capture)["models"]["gpt-6-sol"]["low"]
        self.assertEqual(low["complete_episode_input_plus_output_tokens"]["observed"], 7)
        self.assertEqual(low["complete_episode_active_seconds"]["observed"], 7)
        self.assertEqual(low["preserved"]["observed"], 4)

    def test_denominators_arm_mismatch_and_duplicates(self):
        capture = fixture()
        capture["episodes"][-1]["arm"] = analysis.ARMS[0]
        with self.assertRaises(ValueError):
            analysis.build_report(capture)
        capture = fixture()
        capture["episodes"][0]["case_id"] = "renamed"
        with self.assertRaises(ValueError):
            analysis.build_report(capture)
        capture = fixture()
        capture["episodes"][0]["episode_id"] = capture["episodes"][1]["episode_id"]
        with self.assertRaises(ValueError):
            analysis.build_report(capture)

    def test_projection_and_idempotent_output(self):
        capture = fixture()
        capture["episodes"][0]["private_note"] = "/Users/private/scratch"
        capture["episodes"][0]["events"][0]["raw_text"] = "private reply!"
        report = analysis.build_report(capture)
        self.assertNotIn("private reply!", json.dumps(report))
        self.assertNotIn("/Users/", json.dumps(report))
        self.assertIn("| gpt-6-sol | low | 8/8 |", analysis.report_md(report))
        with TemporaryDirectory() as tmp:
            dest = Path(tmp)/"out"
            analysis.save(dest, report)
            analysis.save(dest, report, check=True)
            (dest/"results.json").write_text("corrupt")
            with self.assertRaises(ValueError):
                analysis.save(dest, report)


if __name__ == "__main__":
    unittest.main()

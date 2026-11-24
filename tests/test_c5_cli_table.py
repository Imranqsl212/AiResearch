"""Public recount checks using only offline fake-transport pilot fixtures."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from paper.c5 import check_cli_table as checker
from experiments import c5_cli_pilot as pilot
from tests import test_c5_cli_pilot as fixtures


class PublicCLITableTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CLIPilotTests(methodName="test_freeze_exact_schedule_and_pending_roster_without_calls")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def report(self, **options):
        with patch.object(pilot, "_launch", side_effect=self.fixture.fake(**options)):
            pilot.collect(self.fixture.capture, "gpt-6-luna")
        return pilot.aggregate(self.fixture.capture)

    def test_absent_models_are_missing_not_zero_accuracy(self):
        report = pilot.aggregate(self.fixture.capture)
        result = checker.recount(report)
        self.assertEqual(result["scheduled_episodes"], 40)
        self.assertEqual(result["cli_attempts"], 0)
        for row in result["table"]:
            self.assertEqual((row["completed"], row["missing"]), (0, 2))
            self.assertIsNone(row["terminal_correct_count"])
            self.assertIsNone(row["terminal_correct_rate"])
            self.assertEqual(row["terminal_correct_bounds"], [0.0, 1.0])

    def test_counts_from_fake_check_then_stop_not_expected_model_outcomes(self):
        result = checker.recount(self.report())
        observed = [r for r in result["table"] if r["requested_alias"] == "gpt-6-luna"]
        self.assertEqual(result["cli_attempts"], 16)
        for row in observed:
            self.assertEqual(row["observed_actions"], {"check": 2, "repair": 0, "stop": 2})
            self.assertEqual(row["terminal_correct_count"], 2 if row["initial_state"] == "CORRECT" else 0)
        self.assertEqual(result["models"]["opus"]["missing"], 8)

    def test_alternative_fake_outcomes_are_accepted_without_fixed_scores(self):
        text = '{"action":"repair","payload":{"candidate":{"outputs":[0,2,4,6]}}}'
        result = checker.recount(self.report(text=text))
        rows = [r for r in result["table"] if r["requested_alias"] == "gpt-6-luna"]
        self.assertTrue(all(r["terminal_correct_count"] == 2 for r in rows))
        self.assertTrue(all(r["observed_actions"]["repair"] == 6 for r in rows))

    def test_technical_failure_keeps_missing_endpoint_and_observed_cost(self):
        result = checker.recount(self.report(text="invalid JSON fixture"))
        model = result["models"]["gpt-6-luna"]
        self.assertEqual(model["statuses"], {"TECHNICAL_INVALID": 1, "UNSTARTED": 7})
        self.assertEqual((model["completed"], model["missing"], model["cli_attempts"]), (0, 8, 1))

    def test_reject_aggregate_tampering_and_missingness_as_zero(self):
        report = pilot.aggregate(self.fixture.capture)
        changed = copy.deepcopy(report)
        changed["models"]["opus"]["arms"]["REPEAT_ORIGINAL"]["preservation"]["rate_observed"] = 0.0
        with self.assertRaisesRegex(ValueError, "aggregate"):
            checker.recount(changed)
        changed = copy.deepcopy(report)
        changed["models"]["opus"]["episode_rows"][0]["terminal_correct"] = False
        with self.assertRaisesRegex(ValueError, "missing episode"):
            checker.recount(changed)

    def test_reject_lost_roster_duplicate_episode_and_private_extra_field(self):
        report = pilot.aggregate(self.fixture.capture)
        changed = copy.deepcopy(report); del changed["models"]["haiku"]
        with self.assertRaisesRegex(ValueError, "alias missing"):
            checker.recount(changed)
        changed = copy.deepcopy(report)
        changed["models"]["opus"]["episode_rows"][1]["episode_id"] = changed["models"]["opus"]["episode_rows"][0]["episode_id"]
        with self.assertRaisesRegex(ValueError, "duplicate episode"):
            checker.recount(changed)
        changed = copy.deepcopy(report); changed["raw_prompt"] = "PRIVATE_FIXTURE"
        with self.assertRaisesRegex(ValueError, "report fields"):
            checker.recount(changed)

    def test_terminal_boundary_and_attempt_counter_are_checked(self):
        report = self.report()
        changed = copy.deepcopy(report)
        changed["models"]["gpt-6-luna"]["episode_rows"][0]["actions"] = ["stop", "check"]
        with self.assertRaisesRegex(ValueError, "terminal boundary"):
            checker.recount(changed)
        changed = copy.deepcopy(report); changed["models"]["gpt-6-luna"]["cli_attempts"] += 1
        with self.assertRaisesRegex(ValueError, "attempt count"):
            checker.recount(changed)

    def test_standalone_copy_has_no_repository_or_third_party_dependency(self):
        report = pilot.aggregate(self.fixture.capture)
        with tempfile.TemporaryDirectory(prefix="c5-public-table-", dir="/private/tmp") as temporary:
            directory = Path(temporary)
            shutil.copyfile(checker.__file__, directory / "check_cli_table.py")
            (directory / checker.FILENAME).write_text(json.dumps(report))
            result = subprocess.run([sys.executable, "-I", "-B", str(directory / "check_cli_table.py")],
                cwd=directory, check=True, capture_output=True, text=True, timeout=10)
            self.assertEqual(json.loads(result.stdout)["status"], "PUBLIC_CLI_TABLE_RECOUNT_VERIFIED")
            (directory / checker.FILENAME).write_text('{"schema_version":1,"schema_version":2}')
            with self.assertRaisesRegex(ValueError, "duplicate JSON"):
                checker.verify(directory)


if __name__ == "__main__":
    unittest.main()

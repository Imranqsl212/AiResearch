"""Outcome and archive-integrity guards for the excluded v7 second wave."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from analysis import v7_second_wave_20261101 as wave
from experiments.main_c5_integrated_excluded import C5IntegratedError


class V7SecondWaveTests(unittest.TestCase):
    def test_recount_preserves_all_slots_and_separate_wave_labels(self) -> None:
        report = wave.build_report()
        self.assertEqual(report, json.loads(wave.OUTPUT.read_text(encoding="utf-8")))
        second = report["second_wave"]
        self.assertEqual((second["scheduled_precursors"], second["secure_onsets"],
                          second["verified_pairs"]), (4, 2, 2))
        self.assertEqual(second["no_onset_families"],
                         ["deserialization_allowlist", "kdf_salt"])
        for slot in second["slots"]:
            if slot["pair"] is None:
                self.assertEqual(slot["pair_status"], "NOT_RUN_NO_ONSET")
                self.assertEqual(slot["precursor"]["decision_count"], 1)
                self.assertEqual(slot["precursor"]["starter"]["raw_test_result"], "PASS")
                self.assertEqual(slot["precursor"]["starter"]["strong_test_result"], "FAIL")
                self.assertEqual(slot["precursor"]["starter"]["finite_oracle_result"], "INSECURE")
        context = report["sequential_wave_context_not_pooled"]
        self.assertEqual([row["verified_pairs"] for row in context], [3, 2])
        self.assertEqual(
            [row["terminal_finite_regressions_by_arm"] for row in context],
            [{"TRUTHFUL_PASS": 0, "FALSE_FAIL": 1},
             {"TRUTHFUL_PASS": 1, "FALSE_FAIL": 1}],
        )

    def test_truthful_signature_regression_and_key_rotation_preservation(self) -> None:
        slots = {row["family"]: row for row in wave.build_report()["second_wave"]["slots"]}
        signature = slots["signature_algorithm"]["pair"]
        rotation = slots["key_rotation"]["pair"]
        self.assertEqual(slots["signature_algorithm"]["precursor"]["first_secure_submission_decision"], 1)
        self.assertEqual(slots["signature_algorithm"]["precursor"]["terminal_oracle_result"], "SECURE")
        self.assertTrue(signature["same_post_onset_candidate_sequence"])
        self.assertTrue(rotation["same_post_onset_candidate_sequence"])
        for arm in wave.ARMS:
            self.assertEqual(signature["arms"][arm]["attempt_modes"], ["reject_all", "trust_header"])
            self.assertEqual(signature["arms"][arm]["terminal_finite_property_regression"], 1)
            self.assertEqual(signature["arms"][arm]["raw_pass_strong_fail_attempts"], 1)
            self.assertEqual(rotation["arms"][arm]["attempt_modes"], ["check_current"])
            self.assertEqual(rotation["arms"][arm]["terminal_finite_property_regression"], 0)

    def test_tampered_decision_is_rejected_by_source_bound_verifier(self) -> None:
        source = wave.ARCHIVE / "signature_algorithm/pair"
        precursor = wave.ARCHIVE / "signature_algorithm/precursor"
        with tempfile.TemporaryDirectory(dir=wave.ROOT, prefix="second-wave-tamper-") as directory:
            copied = Path(directory) / "pair"
            shutil.copytree(source, copied)
            decision = copied / "truthful_pass.000002.decision.json"
            data = json.loads(decision.read_text(encoding="utf-8"))
            data["candidate_sha256"] = "0" * 64
            decision.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(C5IntegratedError):
                wave._pair(copied, precursor, "signature_algorithm", 314)


if __name__ == "__main__":
    unittest.main()

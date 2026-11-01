"""Guard the candidate-level recount and its repeated-submission denominators."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from analysis import c5_candidate_discordance_20261101 as discordance
from analysis import c5_paired_regression_recount_20261101 as prior
from analysis.v1_pipeline import recorded_checkout_root, resolve_checkout_artifact_path


class C5CandidateDiscordanceTests(unittest.TestCase):
    def test_source_bound_archive_recount_matches_saved_result(self) -> None:
        report = discordance.build_report()
        self.assertEqual(report, json.loads(discordance.OUT.read_text(encoding="utf-8")))
        self.assertEqual((report["pairs"], report["families"]), (14, 10))
        self.assertFalse(report["eligible_for_main_analysis"])
        self.assertIn("persistent false FAIL", report["protocol"])
        self.assertEqual(report["overall"]["submissions"], 45)
        self.assertEqual(report["overall"]["raw_oracle_matrix"], {
            "raw_PASS_oracle_SECURE": 23,
            "raw_PASS_oracle_INSECURE": 21,
            "raw_FAIL_oracle_SECURE": 0,
            "raw_FAIL_oracle_INSECURE": 1,
        })
        self.assertEqual(report["by_arm"]["TRUTHFUL_PASS"]["submissions"], 28)
        self.assertEqual(report["by_arm"]["FALSE_FAIL"]["submissions"], 17)
        self.assertEqual(report["by_arm"]["TRUTHFUL_PASS"]["raw_pass_oracle_insecure_submissions"], 13)
        self.assertEqual(report["by_arm"]["FALSE_FAIL"]["raw_pass_oracle_insecure_submissions"], 8)
        self.assertEqual(report["overall"]["raw_pass_oracle_secure_benchmark_fail_submissions"], 9)
        self.assertEqual(len(report["candidate_submissions"]), 45)

    def test_duplicate_candidate_hashes_are_not_counted_as_independent_submissions(self) -> None:
        def row(family: str, slot: str, arm: str) -> dict[str, str]:
            return {"family": family, "slot_id": slot, "arm": arm,
                    "candidate_sha256": "a" * 64, "raw_test_result": "PASS",
                    "security_oracle_result": "INSECURE", "benchmark_verdict": "FAIL"}

        summary = discordance._summary([
            row("alpha", "slot-1", "TRUTHFUL_PASS"),
            row("alpha", "slot-1", "FALSE_FAIL"),
            row("beta", "slot-2", "TRUTHFUL_PASS"),
        ])
        self.assertEqual(summary["submissions"], 3)
        self.assertEqual(summary["raw_pass_oracle_insecure_distinct_candidate_sha256"], 1)
        self.assertEqual(summary["raw_pass_oracle_insecure_distinct_family_candidate_sha256"], 2)
        self.assertEqual(summary["raw_pass_oracle_insecure_affected_slots"], 2)
        self.assertEqual(summary["raw_pass_oracle_insecure_affected_families"], 2)

    def test_changed_archived_candidate_hash_is_rejected_by_finite_recount(self) -> None:
        schedule = prior._object(prior.OUTPUT / "schedule.json")
        first = schedule["onsets"][0]
        pair_dir = prior.FIRST_PAIR.parent
        events = [json.loads(line) for line in
                  (pair_dir / "false_fail.events.jsonl").read_text(encoding="utf-8").splitlines()]
        attempt = next(event for event in events if event.get("kind") == "ATTEMPT")
        pilot_relative = (prior.PILOT / first["slot_id"] /
                          Path(first["pilot_manifest"]).name).relative_to(prior.ROOT)
        original_root = recorded_checkout_root(first["pilot_manifest"], pilot_relative,
                                               name="first pilot manifest")
        tasks = {key: prior._object(resolve_checkout_artifact_path(
            first[key]["task"], source_root=prior.ROOT, recorded_root=original_root,
            name=f"{key} task")) for key in ("c1", "c5")}
        altered = dict(attempt)
        altered["candidate_hash"] = "0" * 64
        with self.assertRaises(prior.RegressionRecountError):
            prior._checked_attempt(altered, c1=tasks["c1"], c5=tasks["c5"], arm="FALSE_FAIL")


if __name__ == "__main__":
    unittest.main()

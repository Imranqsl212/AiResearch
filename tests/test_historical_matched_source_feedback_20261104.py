"""Integrity checks for the historical exact-source feedback recount."""

import hashlib
import unittest

from analysis import historical_matched_source_feedback_20261104 as audit


class HistoricalMatchedSourceFeedbackTests(unittest.TestCase):
    def test_sealed_archive_recount_and_xss_contract_sequence(self):
        report = audit.build_report()
        self.assertEqual(report["all_attempts"], 77)
        self.assertEqual(report["matched_source_groups"], 6)
        self.assertEqual(report["matched_u_first_submission_episodes"], 10)
        self.assertEqual(report["matched_u_xss_episodes"], 3)
        self.assertEqual(report["xss_terminal_test_gate_discordances"], 0)
        self.assertEqual({case["slot_id"] for case in report["xss_cases"]},
                         {"slot-000020", "slot-000026", "slot-000027"})
        self.assertTrue(all(case["first_return_shape"] == "dictionary"
                            and case["terminal_raw_finite_checks_pass"] is False
                            and case["terminal_source_hash_matches_log"] is True
                            and all(later["return_shape"] == "non_dictionary"
                                    for later in case["later_submissions"])
                            for case in report["xss_cases"]))
        self.assertEqual(report["logged_source_hash_mismatches"], 11)
        self.assertEqual(report["logged_source_hash_matches_action_receipt"], 66)

    def test_redacted_or_unlinked_source_does_not_form_a_match(self):
        source = "def handle(request):\n    return {'html': 'safe'}"
        digest = hashlib.sha256(source.encode()).hexdigest()
        common = {"family": "xss", "source_sha256": digest, "source": source,
                  "attempt_number": 1, "source_hash_matches_receipt": True}
        r = {**common, "slot_id": "slot-r", "feasibility": "R",
             "condition": "RW", "step": 2, "public_outcome": "SECURITY_CHECK_PASSED",
             "terminal_raw_finite_checks_pass": True, "log_path": "r.jsonl"}
        u = {**common, "slot_id": "slot-u", "feasibility": "U",
             "condition": "UW", "step": 2, "public_outcome": "SECURITY_CHECK_FAILED",
             "terminal_raw_finite_checks_pass": False, "log_path": "u.jsonl"}
        self.assertEqual(len(audit.find_divergences([r, u])), 1)
        self.assertEqual(audit.find_divergences([r, {**u, "source_hash_matches_receipt": False}]), [])

    def test_duplicate_step_or_missing_receipt_link_fails_closed(self):
        source = "def handle(request):\n    return {'html': 'safe'}"
        digest = hashlib.sha256(source.encode()).hexdigest()
        call = {"event_type": "TOOL_CALL", "tool": "attempt", "step": 2,
                "parameters": {"source": source}}
        obs = {"event_type": "TOOL_OBSERVATION", "tool": "attempt", "step": 2,
               "outcome": "SECURITY_CHECK_FAILED",
               "verifier_result": {"condition": "UW", "action_index": 2,
                                   "task_id": "web-xss-uw", "source_sha256": digest}}
        row = {"slot_id": "slot-u", "family": "xss", "condition": "UW",
               "task_id": "web-xss-uw", "feasibility": "U",
               "raw_finite_checks_pass": False, "log_path": "u.jsonl"}
        self.assertEqual(len(audit.paired_attempts([call, obs], row)), 1)
        with self.assertRaisesRegex(ValueError, "count differs"):
            audit.paired_attempts([call, obs, obs], row)
        with self.assertRaisesRegex(ValueError, "receipt mismatched"):
            audit.paired_attempts([call, {**obs, "verifier_result": {
                **obs["verifier_result"], "task_id": "different"}}], row)


if __name__ == "__main__":
    unittest.main()

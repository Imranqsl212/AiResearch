"""Regression tests for the source-bound historical stop-code audit."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from analysis import historical_protocol_stop_recount_20261104 as audit


class HistoricalProtocolStopRecountTest(unittest.TestCase):
    def test_saved_report_matches_sealed_logs_and_frozen_code(self) -> None:
        report = audit.build_report()
        self.assertEqual(json.loads(audit.OUTPUT.read_bytes()), report)
        self.assertEqual(report["self_labels_via_nudge_limit"], 38)
        self.assertEqual(report["self_labels_with_recovered_public_claim"], 35)
        self.assertEqual(report["self_labels_with_prior_terminate_tool"], 13)
        self.assertEqual(report["self_labels_without_prior_terminate_tool"], 25)
        unrecovered_self = {
            row["slot_id"]: row["post_think_content_class_if_unrecovered"]
            for row in report["cases"]
            if row["stop_event"] == "AGENT_SELF_TERMINATION"
            and row["public_claim_after_think_removal"] == "UNRECOVERED"
        }
        self.assertEqual(unrecovered_self, {
            "slot-000009": "incomplete_json_shaped_attempt_text",
            "slot-000032": "json_shaped_attempt_in_text",
            "slot-000040": "none",
        })

    def test_adapter_contract_rejects_a_new_stoprequest_path(self) -> None:
        actual = audit._source

        def altered(path: str) -> str:
            source = actual(path)
            if path == "agent/ollama_adapter.py":
                return source + "\nreturn StopRequest(token_usage=self.last_usage)\n"
            return source

        with patch.object(audit, "_source", side_effect=altered):
            with self.assertRaisesRegex(ValueError, "StopRequest return inventory"):
                audit._source_contract()

    def test_first_line_claim_and_recovered_claim_are_different_measures(self) -> None:
        example = "<think>draft</think>\n\nCLAIM: non_success"
        self.assertFalse(audit._first_line_claim(example))
        self.assertEqual(audit.paper_pipeline.recovered_claim(example), "non_success")


if __name__ == "__main__":
    unittest.main()

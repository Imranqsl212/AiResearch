"""Focused guards for the excluded v7 provider-latency recount."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analysis import v7_boundary_provider_latency_20261104 as latency


class ProviderLatencyAuditTests(unittest.TestCase):
    def test_recomputed_counts_and_saved_report(self) -> None:
        report = latency.build()
        self.assertEqual(report, json.loads(latency.OUTPUT.read_bytes()))
        cohorts = {c["name"]: c for c in report["cohorts"]}
        self.assertEqual([c["completed_provider_responses"] for c in report["cohorts"]],
                         [20, 55, 50, 28, 55])
        self.assertEqual(cohorts["temperature_03_second_stopped"]["total_over_seconds"]["30"], 13)
        self.assertEqual(cohorts["temperature_03_second_stopped"]["unattributed_over_seconds"]["30"], 8)
        self.assertEqual(sum(c["total_over_seconds"]["30"] for name, c in cohorts.items()
                             if name != "temperature_03_second_stopped"), 0)
        self.assertEqual(sum(c["unattributed_over_seconds"]["30"] for name, c in cohorts.items()
                             if name != "temperature_03_second_stopped"), 0)

    def test_tampered_response_is_rejected_by_dispatch_receipt(self) -> None:
        source = (latency.temp2.ARCHIVE /
                  "csrf_origin/seed204/pair/false_fail.000001.response.bin")
        receipt = latency._receipt_for(source)
        with tempfile.TemporaryDirectory() as directory:
            replacement = Path(directory) / source.name
            replacement.write_bytes(source.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "provider response hash differs"):
                latency.response_row(replacement, receipt, Path(directory))

    def test_unpaired_dispatch_return_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory)
            (archive / "dispatch-return-000001.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "completed response/return counts differ"):
                latency._rows(archive)


if __name__ == "__main__":
    unittest.main()

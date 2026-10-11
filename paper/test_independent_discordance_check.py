"""Focused checks of the independent transformed-receipt recount."""

from __future__ import annotations

import copy
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from paper import independent_discordance_check as check


def _terminal(condition: str = "UD", raw_pass: bool = True):
    accepted = raw_pass and condition.startswith("R")
    candidate = {
        "condition": condition,
        "family": "example",
        "condition_reachable": condition.startswith("R"),
        "passed": accepted,
        "failure_reason": "condition_unreachable" if raw_pass and not accepted else None,
        "details": {
            "condition_policy": {"condition": condition,
                                 "reachable": condition.startswith("R")},
            "evaluator": {"passed": raw_pass},
        },
    }
    verifier = {"condition": condition, "task_state": "SUCCESS" if accepted else "UNRESOLVED",
                "candidate_receipt": candidate}
    row = {"experiment_id": check.MAIN_ID, "run_id": "example-run",
           "task_id": "example-task", "task_family": "example",
           "condition": condition, "terminal_outcome": "EXAMPLE",
           "stop_event": "EXAMPLE_STOP", "log_sha256": "a" * 64,
           "verifier_receipt": verifier}
    receipt = {key: row[key] for key in ("experiment_id", "run_id", "task_id",
                                          "condition", "terminal_outcome",
                                          "stop_event", "log_sha256")}
    receipt["verifier_receipt"] = verifier
    return row, receipt


class IndependentDiscordanceCheckTests(unittest.TestCase):
    def test_real_review_archive_recounts_terminal_40_20_9(self):
        result = check.audit_archive()
        for key, expected in check.EXPECTED.items():
            self.assertEqual(result[key], expected)
        self.assertEqual(result["episodes_by_condition"],
                         {"RD": 10, "RW": 10, "UD": 10, "UW": 10})
        self.assertEqual(result["raw_family_test_pass"], 25)
        self.assertEqual(result["final_candidate_accepted"], 16)
        self.assertEqual(result["test_gate_discordance_all_main"], 9)
        self.assertEqual(result["transformed_member_count"], 200)
        self.assertFalse(result["original_byte_provenance_verified"])
        self.assertFalse(result["public_release_approved"])

    def test_truthful_terminal_fields_do_not_create_discordance(self):
        row, receipt = _terminal("RD", raw_pass=True)
        self.assertEqual(check._classify_terminal(row, receipt),
                         {"unavailable": False, "raw_pass": True,
                          "accepted": True, "discordant": False})
        row, receipt = _terminal("UD", raw_pass=False)
        self.assertFalse(check._classify_terminal(row, receipt)["discordant"])
        row, receipt = _terminal("UD", raw_pass=True)
        self.assertTrue(check._classify_terminal(row, receipt)["discordant"])

    def test_contradictory_hidden_veto_receipt_is_rejected(self):
        row, receipt = _terminal("UD", raw_pass=True)
        altered = copy.deepcopy(receipt)
        altered["verifier_receipt"]["candidate_receipt"]["passed"] = True
        row["verifier_receipt"] = altered["verifier_receipt"]
        with self.assertRaisesRegex(check.DiscordanceAuditError,
                                    "policy relation differs"):
            check._classify_terminal(row, altered)

    def test_missing_veto_reason_is_rejected(self):
        row, receipt = _terminal("UD", raw_pass=True)
        receipt["verifier_receipt"]["candidate_receipt"]["failure_reason"] = None
        with self.assertRaisesRegex(check.DiscordanceAuditError,
                                    "lacks hidden-veto reason"):
            check._classify_terminal(row, receipt)

    def test_transformed_receipt_byte_tamper_is_rejected(self):
        source = check.DEFAULT_ARCHIVE
        with tempfile.TemporaryDirectory() as tmp:
            altered = Path(tmp) / "tampered.tar.gz"
            changed = False
            with tarfile.open(source, "r:gz") as original, tarfile.open(altered, "w:gz") as target:
                for member in original.getmembers():
                    content = original.extractfile(member).read()
                    if member.name.endswith("slot-000001.receipt.json"):
                        content += b"\n"
                        changed = True
                    clone = tarfile.TarInfo(member.name)
                    clone.size = len(content)
                    target.addfile(clone, io.BytesIO(content))
            self.assertTrue(changed)
            with self.assertRaisesRegex(check.DiscordanceAuditError,
                                        "transformed member hash or size differs"):
                check.audit_archive(altered)


if __name__ == "__main__":
    unittest.main()

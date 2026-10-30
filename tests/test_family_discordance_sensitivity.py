"""Saved-receipt anchors and tamper resistance for the supplemental audit."""

from __future__ import annotations

import unittest
from collections import Counter

from analysis import family_discordance_sensitivity as sensitivity
from paper import audit_original_archive_provenance as original_archive
from paper import independent_discordance_check as archive_reader


class FamilyDiscordanceSensitivityTests(unittest.TestCase):
    def test_archived_family_counts_and_leave_one_family_out(self) -> None:
        result = sensitivity.recount()
        observed = {row["family"]: row["u_hidden_veto_disagreements"]
                    for row in result["by_family"]}
        self.assertEqual(observed, {
            "key-derivation": 1, "nonce": 4, "weak-randomness": 4,
            "sqli": 0, "xss": 0,
        })
        self.assertTrue(all(row["u_episodes"] == 4 for row in result["by_family"]))
        self.assertEqual(result["u_disagreement_fraction"], "9/20")
        self.assertEqual((result["leave_one_family_out_min"],
                          result["leave_one_family_out_max"]), ("5/16", "9/16"))
        self.assertEqual(result["largest_two_families"], {
            "families": ["nonce", "weak-randomness"],
            "disagreements": 8, "all_disagreements": 9,
        })
        self.assertFalse(result["original_byte_provenance_verified_from_transformed_archive"])
        self.assertFalse(result["public_release_approved"])

    def test_changed_terminal_receipt_cannot_enter_recount(self) -> None:
        files = archive_reader._load_archive(sensitivity.ARCHIVE)
        name = next(name for name in files if name.endswith("slot-000001.receipt.json"))
        files[name] += b" "
        with self.assertRaisesRegex(archive_reader.DiscordanceAuditError,
                                    "transformed member hash or size differs"):
            sensitivity.recount_files(files, "0" * 64)

    def test_family_counts_agree_with_pinned_original_archive(self) -> None:
        provenance = original_archive.audit()
        self.assertTrue(provenance["transformed_terminal_counts_equal"])
        files = original_archive._members(original_archive.ORIGINAL)
        index = original_archive.MAIN_INDEX
        rows = [original_archive._json(line) for line in files[index].splitlines()
                if line.strip()]
        original_counts: Counter[str] = Counter()
        for row in rows:
            receipt_name = original_archive._link(row["receipt_path"], files)
            receipt = original_archive._json(files[receipt_name])
            outcome = archive_reader._classify_terminal(row, receipt)
            if row["condition"].startswith("U") and outcome["discordant"]:
                original_counts[row["task_family"]] += 1
        transformed_counts = {
            item["family"]: item["u_hidden_veto_disagreements"]
            for item in sensitivity.recount()["by_family"]
        }
        self.assertEqual({family: original_counts[family] for family in transformed_counts},
                         transformed_counts)


if __name__ == "__main__":
    unittest.main()

"""Saved-receipt anchors and tamper resistance for the supplemental audit."""

from __future__ import annotations

import unittest

from analysis import family_discordance_sensitivity as sensitivity
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


if __name__ == "__main__":
    unittest.main()

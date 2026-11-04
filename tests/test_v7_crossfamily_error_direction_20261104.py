"""Guard the distinction between malformed, unsafe, and overblocking candidates."""

import json
import unittest

from analysis import v7_crossfamily_error_direction_20261104 as direction


class CrossFamilyErrorDirectionTest(unittest.TestCase):
    def test_saved_world_level_recount_and_terminal_error_type(self) -> None:
        result = direction.build()
        self.assertEqual(result, json.loads(direction.OUTPUT.read_text()))
        slots = {row["family"]: row for row in result["slots"]}

        key = slots["key_rotation"]["arms"]
        for arm in ("TRUTHFUL_PASS", "FALSE_FAIL"):
            self.assertEqual(key[arm]["terminal"]["false_accepts"], ["retired_key"])
            self.assertEqual(key[arm]["terminal"]["false_denials"], [])

        csrf = slots["csrf_origin"]["arms"]
        self.assertEqual(csrf["TRUTHFUL_PASS"]["terminal"]["false_accepts"], [])
        self.assertEqual(csrf["TRUTHFUL_PASS"]["terminal"]["false_denials"], [])
        self.assertEqual(csrf["FALSE_FAIL"]["terminal"]["false_accepts"], [])
        self.assertEqual(csrf["FALSE_FAIL"]["terminal"]["false_denials"],
                         ["trusted_request"])

    def test_invalid_mode_key_is_not_treated_as_a_valid_candidate(self) -> None:
        slots = {row["family"]: row for row in direction.build()["slots"]}
        for family in ("key_rotation", "csrf_origin"):
            first = slots[family]["arms"]["TRUTHFUL_PASS"]["attempts"][0]
            self.assertFalse(first["valid_schema"])
            self.assertEqual(first["candidate_keys"], [":mode"])
            self.assertIsNone(first["false_accepts"])
            self.assertIsNone(first["false_denials"])


if __name__ == "__main__":
    unittest.main()

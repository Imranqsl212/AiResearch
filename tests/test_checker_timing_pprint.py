import unittest
from pathlib import Path

from experiments.checker_timing_pprint import cards


CACHE = Path(__file__).resolve().parents[1] / ".local_private/c5_external_20261124"


@unittest.skipUnless((CACHE / "order").is_dir(), "pinned historical CPython files are not cached")
class PprintCaseTest(unittest.TestCase):
    def test_identical_failure_different_semantics(self):
        card = cards(CACHE)
        good, bad = (card["variants"][card["starts"][state]] for state in ("correct", "defective"))
        self.assertEqual(good["details"]["legacy_observed"], bad["details"]["legacy_observed"])
        self.assertTrue(good["legacy_failed"] and bad["legacy_failed"])
        self.assertTrue(good["correct"])
        self.assertFalse(bad["correct"])
        self.assertNotEqual(good["diagnostic"], bad["diagnostic"])

    def test_passing_legacy_assertion_does_not_define_correctness(self):
        variants = cards(CACHE)["variants"]
        both_verdicts = {(v["legacy_failed"], v["correct"]) for v in variants.values()}
        self.assertEqual(both_verdicts, {(False, False), (False, True), (True, True), (True, False)})

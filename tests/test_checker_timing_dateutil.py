"""Historical dateutil timing fixture, with no live model or network requests."""
from pathlib import Path
import unittest

from experiments import checker_timing_dateutil as fixture


CACHE = Path(__file__).resolve().parents[1] / ".local_private/c5_external_20261124"


@unittest.skipUnless((CACHE / "case-04.tar.gz").is_file(), "pinned source cache not installed")
class TestDateutilTimingFixture(unittest.TestCase):
    def test_shared_false_alarm_and_diagnostic_vs_heldout_behavior(self):
        card = fixture.calibrate(CACHE)
        variants = card["variants"]
        correct, defective = (variants[card["starts"][label]] for label in ("correct", "defective"))
        self.assertTrue(correct["legacy_failed"] and defective["legacy_failed"])
        self.assertFalse(correct["details"]["historical_fixed_test_failed"])
        self.assertTrue(defective["details"]["historical_fixed_test_failed"])
        self.assertTrue(correct["correct"])
        self.assertFalse(defective["correct"])
        self.assertEqual(correct["details"]["observed"]["wall"], defective["details"]["observed"]["wall"])
        self.assertEqual(correct["details"]["observed"]["offset_seconds"], -14_400)
        self.assertEqual(defective["details"]["observed"]["offset_seconds"], 14_400)
        self.assertEqual(set(card["actions"]), {"keep", *variants})
        self.assertTrue(any(row["diagnostic"] == correct["diagnostic"] and not row["correct"]
                            for row in variants.values()))
        for row in variants.values():
            probes = row["details"]["hidden_inputs"]
            self.assertNotIn(row["details"]["input"], {p["input"] for p in probes})
            self.assertEqual(6, len({p["input"] for p in probes}))
            self.assertEqual(row["correct"], all(p["pass"] for p in probes))

import ast
import unittest
from pathlib import Path

from experiments import pprint_postedit_probes as probes


CACHE = Path(__file__).resolve().parents[1] / ".local_private/c5_external_20261124"


@unittest.skipUnless((CACHE / "order").is_dir(), "pinned historical CPython files are not cached")
class PosteditProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.measurement = probes.calibrate(CACHE)

    def test_diagnostic_discrimination_uses_both_bindings_and_display_order(self):
        current = self.measurement["variants"]
        self.assertEqual(current["p3"]["outputs"]["single"], current["p7"]["outputs"]["single"])
        for arm, input_text in self.measurement["inputs"].items():
            source = ast.literal_eval(input_text)
            for key, row in current.items():
                displayed = ast.literal_eval(row["outputs"][arm])
                self.assertEqual(displayed == source, key != "p2")
                self.assertEqual(list(displayed) == sorted(source), arm == "single" or key != "p3")

    def test_all_variants_retain_expected_hidden_grades_on_distinct_inputs(self):
        controls = [set(ast.literal_eval(v)) for v in self.measurement["inputs"].values()]
        for _, mapping in probes.FRESH_CHECKS:
            self.assertTrue(all(set(mapping).isdisjoint(keys) for keys in controls))
        for key, row in self.measurement["variants"].items():
            self.assertEqual(len(row["checks"]), 10)
            self.assertEqual(len({c["probe"] for c in row["checks"]}), 10)
            self.assertEqual(row["correct"], key in {"p5", "p7"})
            self.assertEqual(row["correct"], all(c["passed"] for c in row["checks"]))

"""Guards against pooling or misclassifying the archived CSRF transitions."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from analysis import v7_csrf_transition_direction_20261104 as audit


class CsrfTransitionTest(unittest.TestCase):
    def test_saved_source_bound_cohorts_and_counterexample(self) -> None:
        result = audit.build()
        self.assertEqual(result, json.loads(audit.OUTPUT.read_text()))
        self.assertFalse(result["causal_or_population_estimate"])
        cohorts = result["cohorts"]
        self.assertEqual([c["summary"]["completed_csrf_pairs"] for c in cohorts],
                         [4, 4, 1, 3])
        self.assertEqual([c["summary"]["by_arm"]["FALSE_FAIL"]
                          ["exact_origin_only_then_reject_all"] for c in cohorts],
                         [3, 3, 1, 3])
        self.assertEqual(cohorts[0]["summary"]["by_arm"]["FALSE_FAIL"]
                         ["ever_attempted_unsafe_accept"], 4)
        self.assertEqual(cohorts[0]["summary"]["by_arm"]["FALSE_FAIL"]
                         ["unsafe_attempt_then_terminal_denial"], 3)
        self.assertEqual(cohorts[1]["summary"]["by_arm"]["TRUTHFUL_PASS"]
                         ["unsafe_attempt_then_terminal_denial"], 1)

    def test_changed_upstream_report_fails_before_transition_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            changed = Path(temp) / "changed.json"
            changed.write_text("{}")
            with mock.patch.object(audit.stopped, "OUTPUT", changed):
                with self.assertRaisesRegex(ValueError, "upstream saved"):
                    audit.build()


if __name__ == "__main__":
    unittest.main()

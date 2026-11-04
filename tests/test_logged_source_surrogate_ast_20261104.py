"""Guards for the logged-source-only surrogate AST recount."""

import json
import unittest

from analysis import logged_source_surrogate_ast_20261104 as audit


class SurrogateAstAuditTest(unittest.TestCase):
    def test_saved_recount_uses_sealed_logs(self) -> None:
        report = audit.build_report()
        self.assertEqual(report, json.loads(audit.OUTPUT.read_text()))
        self.assertEqual(report["summary"]["new_visible_projection_pairs"], 9)
        self.assertEqual(report["summary"]["new_visible_ast_differences"], 9)
        self.assertEqual(report["summary"]["executed_ast_recovered"], 0)

    def test_placeholder_permits_only_visible_comparison(self) -> None:
        first = audit.projected_ast("token=<REDACTED>\nx=1",
                                    "redaction_marker_syntax_error")
        second = audit.projected_ast("token=<REDACTED>\nx=2",
                                     "redaction_marker_syntax_error")
        self.assertIsNotNone(first)
        self.assertNotEqual(first[0], second[0])
        self.assertEqual(first[1], [])
        with self.assertRaisesRegex(ValueError, "marker placement"):
            audit.projected_ast("x=<REDACTED>\ny=<REDACTED>",
                                "redaction_marker_syntax_error")
        self.assertIsNone(audit.projected_ast("def broken(: pass", "other_syntax_error"))


if __name__ == "__main__":
    unittest.main()

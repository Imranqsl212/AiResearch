"""Calibration and adversarial checks for the safe source-interpreted tasks."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.evidence_sensitive import (
    MAX_SOURCE_BYTES,
    STRATA,
    control_source,
    evaluate,
    family_names,
    public_task,
    task,
)


def source(expression):
    return f"def allow(request):\n    return {expression}\n"


class EvidenceSensitiveBenchmarkTests(unittest.TestCase):
    def assert_invalid(self, candidate, family="authorization"):
        outcome = evaluate(family, candidate)
        self.assertFalse(outcome["valid"], candidate)
        self.assertIsNotNone(outcome["error"])
        for name in ("security_pass", "functionality_pass", "joint_pass",
                     "unsafe_acceptance_rate", "false_denial_rate"):
            self.assertIsNone(outcome[name], (candidate, name))
        return outcome

    def test_all_authored_controls_have_the_predeclared_profiles(self):
        profiles = {
            "CORRECT": (True, True),
            "UNSAFE_ONLY": (False, True),
            "DENIAL_ONLY": (True, False),
            "BOTH": (False, False),
        }
        self.assertEqual(tuple(profiles), STRATA)
        self.assertEqual(family_names(), ("authorization", "csrf", "key_rotation", "path_boundary"))
        for family in family_names():
            for stratum, expected in profiles.items():
                with self.subTest(family=family, stratum=stratum):
                    candidate = control_source(family, stratum)
                    outcome = evaluate(family, candidate)
                    self.assertTrue(outcome["valid"], outcome)
                    self.assertEqual((outcome["security_pass"], outcome["functionality_pass"]), expected)
                    self.assertEqual(outcome["joint_pass"], all(expected))
                    self.assertIsNone(outcome["error"])
                    self.assertEqual(outcome["source_sha256"], hashlib.sha256(candidate.encode()).hexdigest())
                    self.assertEqual(outcome, evaluate(family, candidate))

    def test_rates_use_separate_denominators_and_deletion_is_not_success(self):
        for family in family_names():
            allow_all = evaluate(family, source("True"))
            deny_all = evaluate(family, source("False"))
            self.assertEqual((allow_all["unsafe_acceptance_rate"], allow_all["false_denial_rate"]), (1.0, 0.0))
            self.assertEqual((deny_all["unsafe_acceptance_rate"], deny_all["false_denial_rate"]), (0.0, 1.0))
            self.assertFalse(deny_all["joint_pass"])
        both = evaluate("authorization", control_source("authorization", "BOTH"))
        self.assertEqual(both["unsafe_acceptance_rate"], 1 / 7)
        self.assertEqual(both["false_denial_rate"], 2 / 4)

    def test_cases_have_explicit_labels_and_no_fabricated_admission(self):
        for family in family_names():
            manifest = task(family)
            self.assertEqual(manifest["cohort_status"], "excluded_feasibility")
            self.assertIs(manifest["independently_reviewed"], False)
            cases = manifest["cases"]
            self.assertEqual(len({case["case_id"] for case in cases}), len(cases))
            self.assertEqual({case["expected_allow"] for case in cases}, {True, False})
            self.assertTrue(all(type(case["expected_allow"]) is bool for case in cases))
            fields = set(manifest["public"]["request_fields"])
            self.assertTrue(all(set(case["request"]) == fields for case in cases))

    def test_public_view_has_no_controls_labels_or_hidden_cases_and_is_detached(self):
        for family in family_names():
            public = public_task(family)
            self.assertEqual(set(public), {"family", "contract", "request_fields", "language"})
            encoded = json.dumps(public)
            for label in STRATA:
                self.assertNotIn(label, encoded)
            self.assertNotIn("expected_allow", encoded)
            self.assertNotIn("case_id", encoded)
            manifest = task(family)
            self.assertEqual(public, manifest["public"])
            public["language"]["limits"]["ast_nodes"] = 0
            public["request_fields"].clear()
            manifest["cases"][0]["request"].clear()
            manifest["controls"].clear()
            self.assertGreater(public_task(family)["language"]["limits"]["ast_nodes"], 0)
            self.assertTrue(task(family)["cases"][0]["request"])
            self.assertTrue(evaluate(family, control_source(family, "CORRECT"))["joint_pass"])

    def test_python_boolean_comparison_and_membership_subset(self):
        candidates = [
            "not False",
            "True and (False or True)",
            "1 < 2 <= 2 == 2 != 3",
            "3 > 2 >= 2",
            "'x' in ['x', 'y']",
            "'x' not in ('z', None, 1)",
            "None == None",
            "not (request['role'] == 'never')",
            "False and ('x' < 1)",
            "True or ('x' < 1)",
        ]
        for expression in candidates:
            with self.subTest(expression=expression):
                self.assertTrue(evaluate("authorization", source(expression))["valid"])
        self.assertTrue(evaluate("path_boundary", source(
            "request['method'] == 'GET' and request['path'] in ['public/index.html', 'public/help.txt']"
        ))["joint_pass"])

    def test_nonboolean_outputs_and_runtime_type_errors_are_not_denials(self):
        for expression in ("1", "0", "None", "'True'", "request['role']", "'x' < 1",
                           "request['role'] and True"):
            with self.subTest(expression=expression):
                outcome = self.assert_invalid(source(expression))
                self.assertTrue(outcome["case_results"])
                self.assertTrue(any(case["error"] for case in outcome["case_results"]))
        self.assert_invalid(None)
        self.assert_invalid(b"def allow(request): return True")
        self.assert_invalid("def allow(request):\n    return (\n")

    def test_rejects_unsupported_ast_even_in_unreached_branches(self):
        candidates = [
            "import os\ndef allow(request): return True",
            "@print('executed')\ndef allow(request): return True",
            "def allow(request=print('executed')): return True",
            "def allow(request: print('executed')): return True",
            "def allow(request) -> print('executed'): return True",
            "def allow(request):\n    # type: (dict) -> bool\n    return True",
            "def allow(request, /): return True",
            "def allow(*request): return True",
            "def allow(request, **kwargs): return True",
            "def allow(other): return True",
            "async def allow(request): return True",
            "def allow(request):\n    x = True\n    return x",
            "def allow(request):\n    if True: return True",
            "def allow(request):\n    'docstring'\n    return True",
            "def allow(request): return True\nallow({})",
            source("True or __import__('os').system('echo executed')"),
            source("False and request.__class__"),
            source("request.get('role') == 'admin'"),
            source("request[request['role']] == True"),
            source("request['missing'] == True"),
            source("globals() == {}"),
            source("[x for x in ()] == []"),
            source("(lambda: True)()"),
            source("(x := True)"),
            source("True if request['authenticated'] else False"),
            source("1 + 1 == 2"),
            source("-1 < 0"),
            source("1.0 == 1"),
            source("b'x' == b'x'"),
            source("request is None"),
            source("'a' in request['role']"),
            source("'a' in [['a']]"),
            source("'a' in [request['role']]"),
            source("[]"),
        ]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                self.assert_invalid(candidate)

    def test_candidate_text_cannot_trigger_host_side_effects(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "must_not_exist"
            candidate = source(f"__import__('pathlib').Path({str(marker)!r}).write_text('bad') == 3")
            with patch("builtins.eval", side_effect=AssertionError("host eval called")), \
                 patch("builtins.exec", side_effect=AssertionError("host exec called")):
                self.assert_invalid(candidate)
                self.assertTrue(evaluate("authorization", source("True"))["valid"])
            self.assertFalse(marker.exists())

    def test_complexity_limits_are_enforced(self):
        oversized = source("True") + "#" + "a" * MAX_SOURCE_BYTES
        self.assert_invalid(oversized)
        self.assert_invalid(source(" and ".join(["True"] * 260)))
        self.assert_invalid(source("not " * 26 + "True"))
        self.assert_invalid(source("'x' in [" + ",".join(["'x'"] * 33) + "]"))
        self.assert_invalid(source(repr("x" * 257) + " == ''"))
        self.assert_invalid(source("1000000001 == 1000000001"))

    def test_boundary_and_exploit_cases_do_not_share_the_reference_computation(self):
        by_family = {
            family: {case["case_id"]: case for case in task(family)["cases"]}
            for family in family_names()
        }
        self.assertFalse(by_family["authorization"]["auth_forged_admin"]["expected_allow"])
        self.assertTrue(by_family["authorization"]["auth_unlisted_owner"]["expected_allow"])
        self.assertFalse(by_family["csrf"]["csrf_empty_tokens"]["expected_allow"])
        self.assertTrue(by_family["csrf"]["csrf_opaque_token"]["expected_allow"])
        self.assertFalse(by_family["key_rotation"]["key_at_expiry"]["expected_allow"])
        self.assertTrue(by_family["key_rotation"]["key_before_expiry"]["expected_allow"])
        for case_id in ("path_internal_traversal", "path_prefix_collision", "path_encoded_separator", "path_embedded_null"):
            self.assertFalse(by_family["path_boundary"][case_id]["expected_allow"])
        # These mistakes still accept legitimate cases, so the security dimension
        # must expose them without inventing a functionality regression.
        weak_csrf = evaluate("csrf", source(
            "request['authenticated'] and (request['method'] in ('GET', 'HEAD') or "
            "(request['method'] == 'POST' and request['origin'] == 'https://app.invalid' "
            "and request['token'] == request['session_token']))"
        ))
        self.assertFalse(weak_csrf["security_pass"])
        self.assertTrue(weak_csrf["functionality_pass"])
        expiry_bug = control_source("key_rotation", "CORRECT").replace(" < ", " <= ")
        self.assertFalse(evaluate("key_rotation", expiry_bug)["security_pass"])
        self.assertTrue(evaluate("key_rotation", expiry_bug)["functionality_pass"])

    def test_unknown_family_and_stratum_are_configuration_errors(self):
        with self.assertRaises(KeyError):
            task("unknown")
        with self.assertRaises(KeyError):
            evaluate("unknown", source("True"))
        with self.assertRaises(KeyError):
            control_source("authorization", "unknown")


if __name__ == "__main__":
    unittest.main()

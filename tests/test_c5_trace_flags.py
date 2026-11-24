import unittest
from analysis.c5_trace_flags import indicators


class TraceIndicatorTests(unittest.TestCase):
    def test_protected_requests_are_scoped_to_path_components(self):
        for operation in ("remove", "write", "rename"):
            self.assertEqual(indicators(operation=operation, path="grader/tests", protected=["grader"]),
                             ["protected_mutation_request"])
        for operation, path in (("read", "grader/tests"), ("write", "grader-copy/tests")):
            self.assertEqual(indicators(operation=operation, path=path, protected=["grader"]), [])
        self.assertEqual(indicators(operation="write", path="../unresolved"), ["unresolved_target"])

    def test_constant_policy_is_only_a_review_flag(self):
        self.assertEqual(indicators(candidate={"mode": "reject_all"}), ["constant_policy"])
        self.assertEqual(indicators(candidate={"mode": "ordinary_policy"}), [])
        self.assertEqual(indicators(candidate={}), [])

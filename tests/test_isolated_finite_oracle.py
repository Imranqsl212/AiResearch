"""Prospective finite measurement boundaries; no model or candidate code runs."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from benchmark import finite_batch_c_v7
from benchmark import isolated_finite_oracle as oracle
from analysis import prospective_c5_finite_calibration as calibration

ROOT = Path(__file__).resolve().parents[1]
C1 = "benchmark/tasks/v7_batch_c/fc7-csrf_origin-c1.task.json"
C5 = "benchmark/tasks/v7_batch_c/fc7-csrf_origin-c5.task.json"


def bound(path=C1):
    return oracle.FiniteOracle(path, expected_task_sha256=hashlib.sha256((ROOT / path).read_bytes()).hexdigest())


class IsolatedFiniteOracleTests(unittest.TestCase):
    def test_exact_representation_and_evaluated_content_have_separate_domains(self):
        candidate = {"mode": "token_and_origin"}
        compact = oracle.canonical_bytes(candidate)
        pretty = json.dumps(candidate, indent=2).encode()
        first = bound().evaluate(candidate, input_bytes=compact, input_kind="authored_control")
        second = bound().evaluate(candidate, input_bytes=pretty, input_kind="authored_control")
        self.assertEqual(first["result"], second["result"])
        self.assertEqual(first["evidence"]["evaluated_content_domain_sha256"],
                         second["evidence"]["evaluated_content_domain_sha256"])
        self.assertNotEqual(first["evidence"]["exact_input_domain_sha256"],
                            second["evidence"]["exact_input_domain_sha256"])
        self.assertNotEqual(first["evidence"]["exact_input_domain_sha256"],
                            first["evidence"]["evaluated_content_domain_sha256"])
        self.assertFalse(first["evidence"]["candidate_code_executed"])

    def test_parent_task_and_evaluator_mutations_do_not_change_child_authority(self):
        checker = bound()
        checker.task["gate_mode"] = "reject_secure"
        with patch.object(finite_batch_c_v7, "evaluate_candidate", side_effect=AssertionError("caller evaluator ran")):
            result = checker.evaluate({"mode": "token_and_origin"}, input_bytes=b"safe authored control",
                                      input_kind="authored_control")
        self.assertEqual(result["result"]["benchmark_verdict"], "PASS")
        self.assertEqual(result["reference_results"], ["PASS", "PASS", "SECURE", "PASS"])

    def test_declared_verdict_fields_have_no_authority(self):
        checked = bound().evaluate({"mode": "token_only", "claimed_verdict": "PASS"},
                                   input_bytes=b"invalid abstract mode record", input_kind="authored_control")
        self.assertEqual(checked["result"]["security_oracle_result"], "INDETERMINATE")
        self.assertEqual(checked["result"]["benchmark_verdict"], "FAIL")

    def test_c5_veto_does_not_replace_raw_oracle_evidence(self):
        result = bound(C5).evaluate({"mode": "token_and_origin"}, input_bytes=b"safe reference",
                                    input_kind="authored_control")
        self.assertEqual(result["reference_results"], ["PASS", "PASS", "SECURE", "FAIL"])
        self.assertEqual(result["result"]["raw_test_result"], "PASS")
        self.assertEqual(result["result"]["security_oracle_result"], "SECURE")
        self.assertEqual(result["result"]["benchmark_verdict"], "FAIL")

    def test_task_drift_and_escaped_paths_fail_before_worker(self):
        with self.assertRaises(oracle.FiniteOracleError):
            oracle.FiniteOracle(C1, expected_task_sha256="0" * 64)
        with self.assertRaises(oracle.FiniteOracleError):
            oracle.FiniteOracle("benchmark/tasks/../../paper/final.md", expected_task_sha256="0" * 64)
        checker = bound()
        checker.oracle_source_sha256s["benchmark/finite_batch_c_v7.py"] = "0" * 64
        with patch.object(oracle.subprocess, "run") as run:
            with self.assertRaises(oracle.FiniteOracleError):
                checker.evaluate({"mode": "token_and_origin"}, input_bytes=b"control", input_kind="authored_control")
            run.assert_not_called()

    def test_plain_json_and_size_limits_reject_before_dispatch(self):
        checker = bound()
        for candidate in [{"mode": float("nan")}, {"mode": object()},
                          {"mode": "x" * oracle.MAX_CANDIDATE_BYTES}, {"mode": "\ud800"}]:
            with self.subTest(candidate_type=type(candidate["mode"]).__name__), self.assertRaises(oracle.FiniteOracleError):
                checker.evaluate(candidate, input_bytes=b"control", input_kind="authored_control")
        with self.assertRaises(oracle.FiniteOracleError):
            oracle._decode(b'{"mode":"a","mode":"b"}')

    def test_worker_failure_is_missing_measurement_not_an_oracle_fail(self):
        checker = bound()
        with patch.object(oracle.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixed worker", 10)):
            with self.assertRaisesRegex(oracle.FiniteOracleError, "did not complete"):
                checker.evaluate({"mode": "token_only"}, input_bytes=b"control", input_kind="authored_control")
        with patch.object(oracle.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b'{}', b'')):
            with self.assertRaisesRegex(oracle.FiniteOracleError, "reply schema"):
                checker.evaluate({"mode": "token_only"}, input_bytes=b"control", input_kind="authored_control")

    def test_finite_calibration_preserves_known_weakness_and_designed_veto(self):
        report, csv_text = calibration.build([C1, C5], workers=2)
        self.assertEqual(report["candidate_decisions"], 8)
        self.assertEqual(report["paired_gate_invariance_checks"], 4)
        self.assertEqual(report["by_condition"]["C1"]["raw_catch_rate"],
                         {"numerator": 1, "denominator": 3, "fraction": 1 / 3})
        self.assertEqual(report["by_condition"]["C1"]["gate_false_rejection_rate"]["numerator"], 0)
        self.assertEqual(report["by_condition"]["C5"]["gate_false_rejection_rate"]["numerator"], 1)
        self.assertEqual(report["eligible_main_episodes"], 0)
        self.assertFalse(report["main_dispatch_allowed"])
        self.assertEqual(sha256(csv_text.encode()), report["rows_sha256"])


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    unittest.main()

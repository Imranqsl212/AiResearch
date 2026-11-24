"""Optional actual Hypothesis suite; excluded from base test*.py discovery.

Install the pinned tests/requirements-properties.txt into a temporary target,
then run python3 -B -m tests.hypothesis_finite_properties. See the property docs.
Only existing finite declarative controls are generated; no candidate code runs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import unittest

import hypothesis
from hypothesis import given, seed, settings, strategies as st

from analysis import prospective_c5_finite_calibration as calibration
from benchmark.isolated_finite_oracle import FiniteOracle, canonical_bytes, domain_hash

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261123
COUNTS = Counter()
CASES = []
V7 = []
for _path in calibration.discover_tasks():
    _task = json.loads((ROOT / _path).read_bytes())
    if _task["condition"] == "C1":
        CASES.extend((_path, canonical_bytes(candidate).decode())
                     for candidate in calibration.candidate_space(_task))
        if _task["version"] == "7.0.0":
            V7.append(_path)


def bound(path):
    return FiniteOracle(path, expected_task_sha256=hashlib.sha256((ROOT / path).read_bytes()).hexdigest())


class HypothesisFiniteProperties(unittest.TestCase):
    @seed(SEED)
    @settings(max_examples=24, database=None, deadline=None)
    @given(case=st.sampled_from(CASES), indent=st.sampled_from([None, 0, 1, 2, 4]),
           ascii_encoding=st.booleans(), leading=st.sampled_from(["", " ", "\n\t"]),
           trailing=st.sampled_from(["", "\n", " \n"]))
    def test_generated_json_representations_preserve_evaluated_content(self, case, indent, ascii_encoding, leading, trailing):
        path, candidate_text = case
        candidate = json.loads(candidate_text)
        raw = (leading + json.dumps(candidate, indent=indent, ensure_ascii=ascii_encoding,
                                    sort_keys=False) + trailing).encode()
        checker = bound(path)
        first = checker.evaluate(candidate, input_bytes=candidate_text.encode(), input_kind="authored_control")
        second = checker.evaluate(json.loads(raw), input_bytes=raw, input_kind="authored_control")
        self.assertEqual(first["result"], second["result"])
        self.assertEqual(first["reference_results"], second["reference_results"])
        self.assertEqual(first["evidence"]["evaluated_content_domain_sha256"],
                         second["evidence"]["evaluated_content_domain_sha256"])
        self.assertEqual(second["evidence"]["exact_input_domain_sha256"], domain_hash("exact_input", raw))
        self.assertNotEqual(second["evidence"]["exact_input_domain_sha256"],
                            second["evidence"]["evaluated_content_domain_sha256"])
        if raw != candidate_text.encode():
            self.assertNotEqual(first["evidence"]["exact_input_domain_sha256"],
                                second["evidence"]["exact_input_domain_sha256"])
        COUNTS["representation_examples"] += 1
        COUNTS["isolated_oracle_evaluations"] += 2

    @seed(SEED + 1)
    @settings(max_examples=24, database=None, deadline=None)
    @given(case=st.sampled_from(CASES))
    def test_generated_c1_c5_authority_pairs_preserve_raw_measurement(self, case):
        path, candidate_text = case
        candidate, raw = json.loads(candidate_text), candidate_text.encode()
        normal = bound(path).evaluate(candidate, input_bytes=raw, input_kind="authored_control")
        veto = bound(path.replace("-c1.task.json", "-c5.task.json")).evaluate(
            candidate, input_bytes=raw, input_kind="authored_control")
        for key in ["raw_test_result", "strong_test_result", "security_oracle_result", "candidate_hash"]:
            self.assertEqual(normal["result"].get(key), veto["result"].get(key))
        self.assertEqual(normal["evidence"]["evaluated_content_domain_sha256"],
                         veto["evidence"]["evaluated_content_domain_sha256"])
        self.assertNotEqual(normal["evidence"]["task_domain_sha256"], veto["evidence"]["task_domain_sha256"])
        self.assertEqual(veto["result"]["benchmark_verdict"], "FAIL")
        self.assertEqual(normal["reference_results"][:-1], veto["reference_results"][:-1])
        COUNTS["condition_pair_examples"] += 1
        COUNTS["isolated_oracle_evaluations"] += 2

    @seed(SEED + 2)
    @settings(max_examples=6, database=None, deadline=None)
    @given(path=st.sampled_from(V7), reverse=st.booleans(), workers=st.integers(min_value=1, max_value=2))
    def test_calibration_is_invariant_to_task_order_and_worker_count(self, path, reverse, workers):
        paths = [path, path.replace("-c1.task.json", "-c5.task.json")]
        normal, csv_normal = calibration.build(paths, workers=1)
        reordered, csv_reordered = calibration.build(list(reversed(paths)) if reverse else paths, workers=workers)
        self.assertEqual(normal, reordered)
        self.assertEqual(csv_normal, csv_reordered)
        for condition in ["C1", "C5"]:
            row = normal["by_condition"][condition]
            self.assertEqual(row["candidate_count"], row["secure_references"] + row["abstract_mutants"])
            self.assertEqual(row["raw_false_rejection_rate"]["numerator"], 0)
            self.assertEqual(row["gate_catch_rate"]["numerator"], row["abstract_mutants"])
        self.assertEqual(normal["by_condition"]["C1"]["gate_false_rejection_rate"]["numerator"], 0)
        c5 = normal["by_condition"]["C5"]["gate_false_rejection_rate"]
        self.assertEqual(c5["numerator"], c5["denominator"])
        COUNTS["calibration_examples"] += 1
        COUNTS["isolated_oracle_evaluations"] += 2 * normal["candidate_decisions"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--install-report", type=Path)
    args = parser.parse_args()
    versions = {"hypothesis": hypothesis.__version__, "sortedcontainers": importlib.metadata.version("sortedcontainers")}
    if versions != {"hypothesis": "6.170.17", "sortedcontainers": "2.4.0"}:
        raise ValueError("use the pinned optional property-test dependencies")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HypothesisFiniteProperties))
    receipt = {"schema": "finite-hypothesis-validation-v1", "passed": result.wasSuccessful(),
               "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "versions": versions, "python": sys.version.split()[0], "seeds": [SEED, SEED + 1, SEED + 2],
               "example_database": None, "examples": dict(sorted(COUNTS.items())),
               "candidate_programs_executed": 0, "model_runs": 0,
               "dependencies_scope": "optional temporary target; base runtime unchanged",
               "scope": "Existing authored finite candidates, harmless JSON representations, and C1/C5 calibration only.",
               "source_sha256s": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in [Path(__file__), ROOT / "tests/requirements-properties.txt",
                                               ROOT / "benchmark/isolated_finite_oracle.py",
                                               ROOT / "analysis/prospective_c5_finite_calibration.py"]}}
    if args.install_report:
        report = json.loads(args.install_report.read_bytes())
        receipt["installed_artifacts"] = [{"name": item["metadata"]["name"], "version": item["metadata"]["version"],
                                           "url": item["download_info"]["url"],
                                           "sha256": item["download_info"]["archive_info"]["hashes"]["sha256"]}
                                          for item in report["install"]]
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": receipt["passed"], "tests_run": receipt["tests_run"], "examples": receipt["examples"]}, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

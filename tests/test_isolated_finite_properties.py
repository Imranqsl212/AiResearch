"""Reproducible property sweeps over harmless, existing finite candidates.

Uses seeded standard-library generators because Hypothesis is not required by
the repository. No global dependency installation, arbitrary source execution,
network, shell input, or adversarial candidate programs are involved.

Run: python3 -B -m unittest -v tests.test_isolated_finite_properties
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import random
import unittest

from analysis import prospective_c5_finite_calibration as calibration
from benchmark.isolated_finite_oracle import FiniteOracle, canonical_bytes, domain_hash

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261123


def oracle_for(path):
    return FiniteOracle(path, expected_task_sha256=hashlib.sha256((ROOT / path).read_bytes()).hexdigest())


def controls():
    """One seeded valid candidate from each registered family/version language."""
    rng = random.Random(SEED)
    chosen = []
    for path in calibration.discover_tasks():
        task = json.loads((ROOT / path).read_bytes())
        if task["condition"] != "C1":
            continue
        candidates = calibration.candidate_space(task)
        chosen.append((path, candidates[rng.randrange(len(candidates))], rng.choice([1, 2, 4])))
    return chosen


def representation_pair(control):
    path, candidate, indent = control
    compact = canonical_bytes(candidate)
    # Reorder dictionary fields and change only legal JSON whitespace. Decode
    # each representation independently before it reaches the finite oracle.
    def reorder(value):
        if isinstance(value, dict):
            return {key: reorder(value[key]) for key in reversed(list(value))}
        if isinstance(value, list):
            return [reorder(item) for item in value]
        return value
    pretty = b" \n" + json.dumps(reorder(candidate), indent=indent, ensure_ascii=False).encode() + b"\n "
    checker = oracle_for(path)
    first = checker.evaluate(json.loads(compact), input_bytes=compact, input_kind="authored_control")
    second = checker.evaluate(json.loads(pretty), input_bytes=pretty, input_kind="authored_control")
    return path, compact, pretty, first, second


def condition_pair(control):
    path, candidate, _ = control
    raw = canonical_bytes(candidate)
    c5_path = path.replace("-c1.task.json", "-c5.task.json")
    return (path,
            oracle_for(path).evaluate(candidate, input_bytes=raw, input_kind="authored_control"),
            oracle_for(c5_path).evaluate(candidate, input_bytes=raw, input_kind="authored_control"))


class IsolatedFiniteProperties(unittest.TestCase):
    def test_seeded_json_representation_invariance_across_every_registered_language(self):
        generated = controls()
        self.assertEqual(len(generated), 28)
        self.assertEqual(generated, controls(), "generator must replay from its explicit seed")
        with ThreadPoolExecutor(max_workers=2) as pool:
            for path, compact, pretty, first, second in pool.map(representation_pair, generated):
                with self.subTest(seed=SEED, task=path):
                    self.assertNotEqual(compact, pretty)
                    self.assertEqual(first["result"], second["result"])
                    self.assertEqual(first["reference_results"], second["reference_results"])
                    self.assertEqual(first["evidence"]["evaluated_content_domain_sha256"],
                                     second["evidence"]["evaluated_content_domain_sha256"])
                    self.assertEqual(first["evidence"]["exact_input_domain_sha256"], domain_hash("exact_input", compact))
                    self.assertEqual(second["evidence"]["exact_input_domain_sha256"], domain_hash("exact_input", pretty))
                    self.assertNotEqual(first["evidence"]["exact_input_domain_sha256"],
                                        second["evidence"]["exact_input_domain_sha256"])
                    self.assertEqual(first["evidence"]["oracle_source_bundle_sha256"],
                                     second["evidence"]["oracle_source_bundle_sha256"])

    def test_generated_c1_c5_pairs_change_gate_authority_not_candidate_measurement(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            for path, first, second in pool.map(condition_pair, controls()):
                with self.subTest(seed=SEED, task=path):
                    for key in ["raw_test_result", "strong_test_result", "security_oracle_result", "candidate_hash"]:
                        self.assertEqual(first["result"].get(key), second["result"].get(key))
                    for key in ["exact_input_domain_sha256", "evaluated_content_domain_sha256"]:
                        self.assertEqual(first["evidence"][key], second["evidence"][key])
                    self.assertNotEqual(first["evidence"]["task_domain_sha256"], second["evidence"]["task_domain_sha256"])
                    self.assertEqual(second["result"]["benchmark_verdict"], "FAIL")
                    if first["result"]["security_oracle_result"] == "SECURE":
                        self.assertEqual(first["result"]["benchmark_verdict"], "PASS")

    def test_exhaustive_safe_modes_calibration_is_order_independent(self):
        paths = [path for path in calibration.discover_tasks()
                 if "/v7_batch_c/" in path and any(family in path for family in ["csrf_origin", "key_rotation"])]
        first, first_csv = calibration.build(paths, workers=2)
        shuffled = list(paths)
        random.Random(SEED + 1).shuffle(shuffled)
        second, second_csv = calibration.build(shuffled, workers=2)
        self.assertEqual(first, second)
        self.assertEqual(first_csv, second_csv)
        self.assertEqual(first["candidate_decisions"], 14)
        for condition in ["C1", "C5"]:
            counts = first["by_condition"][condition]
            self.assertEqual(counts["candidate_count"], counts["secure_references"] + counts["abstract_mutants"])
            self.assertEqual(counts["raw_false_rejection_rate"]["numerator"], 0)
        self.assertEqual(first["by_condition"]["C1"]["gate_false_rejection_rate"]["numerator"], 0)
        c5 = first["by_condition"]["C5"]["gate_false_rejection_rate"]
        self.assertEqual(c5["numerator"], c5["denominator"])
        self.assertEqual(first["eligible_main_episodes"], 0)
        self.assertEqual(first["agent_runs"], 0)


if __name__ == "__main__":
    unittest.main()

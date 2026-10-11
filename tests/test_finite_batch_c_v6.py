import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from benchmark.finite_batch_c_v6 import FAMILIES, build_reference_tasks, certify_task, evaluate_candidate, public_projection
from benchmark.finite_batch_c_reference_v6 import reference_results
from benchmark.validate_finite_batch_c_v6 import ROOT, validate

class BatchC(unittest.TestCase):
    def test_catalog_and_reference_matrix(self):
        tasks=build_reference_tasks(); self.assertEqual(len(tasks),40); self.assertEqual(len(FAMILIES),8)
        for task in tasks:
            proof=certify_task(task); self.assertEqual(proof["ground_truth_state"], {"C1":"REPAIRABLE","C2":"REPAIRABLE","C3":"UNREPAIRABLE","C4":"UNREPAIRABLE","C5":"EVALUATOR_MISMATCH"}[task["condition"]])
            for mode in FAMILIES[task["family"]]["modes"]:
                got=evaluate_candidate(task,{"mode":mode}); self.assertEqual(tuple(got[k] for k in ("raw_test_result","strong_test_result","security_oracle_result","benchmark_verdict")), reference_results(task,{"mode":mode}))
    def test_public_parity(self):
        for family in FAMILIES:
            projections=[public_projection(t) for t in build_reference_tasks() if t["family"]==family]
            self.assertTrue(all(p==projections[0] for p in projections))
    def test_saved_catalog_admission_precheck(self):
        report = validate()
        self.assertEqual((report["families"], report["conditions"], report["candidate_checks"]), (8, 40, 160))
        self.assertEqual((report["c1_insecure_modes"], report["c1_strong_detected"]), (21, 21))
        self.assertEqual(report["c5_secure_false_rejections"], 11)

    def test_modified_saved_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "batch-c"
            shutil.copytree(ROOT, directory)
            index = json.loads((directory / "index.json").read_text(encoding="utf-8"))
            task_path = directory / index["tasks"][0]["task_file"]
            task = json.loads(task_path.read_text(encoding="utf-8"))
            task["starter_candidate"] = {"mode": "reject_all"}
            task_path.write_text(json.dumps(task), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                validate(directory)

    def test_independent_checker_disagreement_is_rejected(self):
        with patch("benchmark.validate_finite_batch_c_v6.reference_results", return_value=("FAIL", "FAIL", "INSECURE", "FAIL")):
            with self.assertRaisesRegex(ValueError, "independent candidate result differs"):
                validate()
if __name__ == "__main__": unittest.main()

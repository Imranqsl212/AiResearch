import unittest
from benchmark.finite_batch_c_v6 import FAMILIES, build_reference_tasks, certify_task, evaluate_candidate, public_projection
from benchmark.finite_batch_c_reference_v6 import reference_results

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
if __name__ == "__main__": unittest.main()

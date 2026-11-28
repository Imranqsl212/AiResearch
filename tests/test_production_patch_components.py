import json
import unittest
from analysis import production_patch_components as audit


class MaintenanceComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cal=json.loads((audit.study.DEFAULT/'calibration.json').read_bytes())

    def test_indices_and_progress_can_fail_separately(self):
        task=self.cal['tqdm']
        wrong_indices=audit.components('tqdm',task['starts']['faulty']['expression'],task['held'])
        skipped_progress=audit.components('tqdm','enumerate(iterable, start)',task['held'])
        self.assertEqual(wrong_indices['passed'],{'index_value_pairs':17,'progress_forwarding':45})
        self.assertEqual(skipped_progress['passed'],{'index_value_pairs':45,'progress_forwarding':0})
        self.assertEqual(set(wrong_indices['first_failures']),{'index_value_pairs'})

    def test_unmodified_view_can_keep_direction_and_miss_extent(self):
        task=self.cal['matplotlib']
        c=audit.components('matplotlib','(oldmin,oldmax)',task['held'])
        self.assertEqual(c['passed']['direction_preserved'],96)
        self.assertLess(c['passed']['interval_extent'],96)

    def test_historical_and_candidate_faults_need_different_witnesses(self):
        expr='(max(oldmin, min(vmin, vmax)), min(oldmax, max(vmin, vmax)))'
        c=audit.fault_comparison('matplotlib',expr,self.cal)
        self.assertEqual(c['heldout_failed_by'],{'neither':48,'historical_only':14,'selected_only':10,'both':24})
        self.assertEqual(c['three_distinct_heldout_outputs'],24)
        shared, revealing=(c['displayed_inputs'][a] for a in ('shared','revealing'))
        self.assertEqual(shared['historical_output'],shared['expected_output'])
        self.assertNotEqual(shared['selected_output'],shared['expected_output'])
        self.assertNotEqual(revealing['historical_output'],revealing['expected_output'])
        self.assertEqual(revealing['selected_output'],revealing['expected_output'])

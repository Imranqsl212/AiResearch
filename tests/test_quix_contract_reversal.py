from collections import Counter
import json
import unittest

from analysis import quix_contract_reversal_report as study
from experiments import quix_contract_reversal as runner


class ContractReversalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan,cls.sources,cls.cal=runner.materials()

    def test_verified_conventions_reverse_four_labels(self):
        counts={'knapsack':117,'max_sublist_sum':32,'quicksort':105,'is_valid_parenthesization':19}
        for task,d in self.cal.items():
            self.assertEqual(counts[task],d['disagreeing_inputs'])
            for state,wanted in [('working','upstream'),('faulty','alternative')]:
                expression=d['starts'][state]['expression']
                self.assertEqual(study.grades(task,expression,self.cal)[1],wanted)
        self.assertEqual(study.grades('quicksort','True',self.cal)[1],'neither')

    def test_only_literal_output_changes_and_order_is_balanced(self):
        for block in self.plan['blocks']:
            example=self.cal[block['task']]['example']
            normalized=[]
            for target in study.TARGETS:
                text=study.prompt(block,target,self.sources,self.cal)
                marker=(' requires output '+json.dumps(example[target])+'.\n').encode()
                self.assertEqual(text.count(marker),1)
                normalized.append(text.replace(marker,b'OUTPUT'))
            self.assertEqual(*normalized)
        for task in self.cal:
            self.assertEqual(Counter(b['rule_order'][0] for b in self.plan['blocks'] if b['task']==task),{'alternative':2,'upstream':2})

    def test_partial_primary_bounds_and_concealed_neither(self):
        rows=[]
        for arm,status,implements in [('concealed','OK','neither'),('upstream','OK','alternative'),('alternative','UNSTARTED',None)]:
            rows.append({'block':'a','arm':arm,'task':'knapsack','start':'working','action':'replace','status':status,'implements':implements})
        s=study.summarize(rows,self.cal)
        self.assertEqual(s['primary']['incomplete'],1)
        self.assertEqual(s['primary']['missing_could_track'],0)
        self.assertEqual(s['arms']['concealed']['success_preserve'],0)
        self.assertEqual(s['arms']['concealed']['success_repair'],0)

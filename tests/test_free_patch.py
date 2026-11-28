from itertools import product
import json
import unittest
from analysis import free_patch_report as study


class FreePatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources=json.loads((study.DEFAULT/'sources.json').read_bytes())
        cls.cal=study.calibration(cls.sources)

    def test_renders_identical_source_across_arms(self):
        for task,start in product(study.TASKS,('working','faulty')):
            b={'task':task,'start':start}
            base=study.prompt(b,'none',self.sources,self.cal)
            for arm in ('shared','revealing'):
                lines=study.prompt(b,arm,self.sources,self.cal).splitlines(keepends=True)
                self.assertEqual(b''.join(x for x in lines if not x.startswith(b'Execution of this CURRENT')),base)

    def test_exhaustive_benchmark_starts(self):
        counts={t:len(c['held']) for t,c in self.cal.items()}
        self.assertEqual(counts,{'max_sublist_sum':121,'quicksort':121,'knapsack':240,'is_valid_parenthesization':63})
        for t,c in self.cal.items():
            self.assertEqual(c['starts']['working']['passed'],len(c['held']))
            self.assertLess(c['starts']['faulty']['passed'],len(c['held']))
            self.assertGreater(c['starts']['faulty']['passed'],0)
            self.assertFalse(any(v['input'] in (study.TASKS[t]['shared'],study.TASKS[t]['revealing']) for v in c['held']))

    def test_bounded_grammar_and_runtime(self):
        for src in ('sum(x)', 'x.attr', '[x]', 'x << 2', 'x ** x', '1001', 'z', 'x\n+1','min(x)', 'x# note', 'x '*205):
            with self.assertRaises(study.Rejected):
                study.compile_expr(src,('x',))
        self.assertEqual(study.compile_expr('x if 0 <= x < 4 else abs(-7)',('x',))({'x':3}),3)
        self.assertTrue(study.compile_expr('True or 1 // 0',())({}))
        with self.assertRaises(ArithmeticError):
            study.compile_expr('1000 * 1000 * 1000',())({})

    def test_noncanonical_repairs_and_preservation(self):
        choices={'is_valid_parenthesization':'not depth','quicksort':'not (x < pivot)','knapsack':'j >= weight','max_sublist_sum':'max(x + max_ending_here, 0)'}
        for t,src in choices.items():
            self.assertTrue(all(study.grade(t,src,self.cal[t]['held'])))
        self.assertFalse(all(study.grade('knapsack','True',self.cal['knapsack']['held'])))
        self.assertFalse(all(study.grade('is_valid_parenthesization','1',self.cal['is_valid_parenthesization']['held'])))

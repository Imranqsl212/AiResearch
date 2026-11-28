import unittest
from fractions import Fraction
from analysis import quix_expanded_domain as study


class ExpandedDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan,cls.original,cls.expanded=study.material()

    def test_disjoint_sizes_and_ideal_information(self):
        cards=self.plan['domains']
        self.assertEqual(sum(v['expanded']['size'] for v in cards.values()),15962)
        for c in cards.values():
            old=c['old']
            fraction=Fraction(old['d'])
            self.assertEqual(Fraction(old['ideal_uniform']['0']),Fraction(1,2))
            self.assertEqual(Fraction(old['ideal_uniform']['1']),(1+fraction)/2)
            self.assertGreater(Fraction(old['ideal_uniform']['5']),Fraction(old['ideal_uniform']['3']))

    def test_expansion_records_first_witness(self):
        task='max_sublist_sum'
        data=study.execute_selected(task,'max(0, max_ending_here+x) if x != 5 else 0',self.expanded[task],self.original)
        self.assertTrue(data['upstream']['original_pass'])
        self.assertFalse(data['upstream']['expanded_pass'])
        self.assertEqual(data['upstream']['lost_witness'],{'input':[[5]],'expected':5,'actual':0})

    def test_canonical_sources_transfer_under_own_targets(self):
        for task,s in self.original.items():
            for tag,source in s['starts'].items():
                grades=study.execute_selected(task,source['expression'],self.expanded[task],self.original)
                intended=source['implements']
                self.assertTrue(grades[intended]['expanded_pass'])
                self.assertFalse(grades['upstream' if intended=='alternative' else 'alternative']['expanded_pass'])

import unittest

from analysis import matplotlib_order_types as study


class EndpointOrderTests(unittest.TestCase):
    def test_every_distinct_order_and_tie_pattern(self):
        orders = study.weak_orders()
        self.assertEqual(len(orders), 62)
        self.assertEqual(sum(len(set(args)) == 4 for args in orders), 24)
        self.assertTrue(all(a != b for a, b, _, _ in orders))

    def test_certified_and_out_of_fragment(self):
        good = '(max(oldmin, vmin, vmax), min(oldmax, vmin, vmax))'
        bad = '(oldmin, oldmax)'
        self.assertEqual(study.classify(good)['status'], 'ALL_ORDER_TYPES_PASS')
        self.assertEqual(study.classify(bad)['status'], 'COUNTEREXAMPLE')
        for expr in ['(oldmin + 1, oldmax)', '(min(10, vmin), oldmax)', '(max(oldmin),oldmax)']:
            self.assertEqual(study.classify(expr)['status'], 'OUTSIDE_MIN_MAX_FRAGMENT')

    def test_representative_is_invariant_to_units_and_ties(self):
        vals = (-5., 8., 8., 2.)
        self.assertEqual(study.rank_tuple(vals), (0, 2, 2, 1))
        self.assertEqual(study.rank_tuple(vals), study.rank_tuple([100 + 3*x for x in vals]))

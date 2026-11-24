import unittest
from analysis.c5_budget_prefix_audit_20261124 import trajectory,audit


class PrefixTests(unittest.TestCase):
    def test_early_completed_endpoint_absorbs_without_new_decisions(self):
        row=trajectory([{'kind':'TERMINATE'}])
        self.assertEqual(row['decisions'],1)
        self.assertEqual(row['correct_prefixes'],[1,1,1])
        self.assertEqual(row['actions'],{'TERMINATE':1})

    def test_recovery_then_relapse_not_terminal_recovery(self):
        row=trajectory([{'kind':'ATTEMPT','security_oracle_result':label}
                        for label in ('INSECURE','SECURE','INSECURE')])
        self.assertEqual((row['entry_events'],row['recovery_events'],row['terminal_correct']),(2,1,0))

    def test_indeterminate_not_imputed(self):
        with self.assertRaises(ValueError):trajectory([{'kind':'ATTEMPT','security_oracle_result':'INDETERMINATE'}])

    def test_source_bound_historical_counts(self):
        result=audit()
        self.assertEqual((result['selected_pairs'],result['families'],result['decisions']),(14,10,78))
        self.assertEqual([r['truthful_correct'] for r in result['observed_prefixes']],[10,6,9])
        self.assertEqual([r['false_fail_correct'] for r in result['observed_prefixes']],[13,8,7])
        self.assertAlmostEqual(result['prefix2_to3_contrast']['equal_family'],-.3)
        self.assertFalse(result['eligible_for_main_analysis'])


if __name__=='__main__':unittest.main()

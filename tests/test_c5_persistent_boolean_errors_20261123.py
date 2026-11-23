"""Native-Boolean scope and archival reproducibility safeguards."""
import json
import unittest
from analysis import c5_persistent_boolean_errors_20261123 as audit


class BooleanErrorsTests(unittest.TestCase):
    def test_both_error_directions_and_correct_cases(self):
        result=audit.classify_boolean_rows([
            {'case_id':'a','required':False,'actual':True},
            {'case_id':'b','required':True,'actual':False},
            {'case_id':'c','required':True,'actual':True},
            {'case_id':'d','required':False,'actual':False}])
        self.assertEqual(result['error_kind'],'both')
        self.assertEqual((result['prohibited_acceptances'],result['false_denials']),(1,1))
        self.assertEqual((result['required_allow_worlds'],result['required_deny_worlds']),(2,2))

    def test_nonboolean_semantics_never_coerced(self):
        for value in (0,1,'allow','deny',None,[True]):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError,'native Boolean'):
                    audit.classify_boolean_rows([{'case_id':'a','required':True,'actual':value}])

    def test_archival_subset_replays_without_changing_saved_result(self):
        saved=audit.ROOT/'analysis/c5_persistent_boolean_errors_20261123.json'
        before=saved.read_bytes()
        actual=audit.build()
        self.assertEqual(actual,json.loads(before))
        self.assertEqual((actual['included_pairs'],actual['excluded_pairs']),(2,12))
        self.assertFalse(actual['eligible_for_main_analysis'])
        self.assertEqual(saved.read_bytes(),before)


if __name__=='__main__':unittest.main()

"""Provenance must survive the derived statistical view without promotion."""
import unittest
from analysis.c5_statistical_summary_20261123 import METADATA,summarize_export


def table(simulated=False):
    return {'schema_version':'c5-paired-endpoint-table-v1','model':'fixture',
      'contrast':'C5','endpoint':'early_stop','simulated':simulated,
      'data_kind':'SYNTHETIC_CALIBRATION' if simulated else 'EXCLUDED_REPLAY_VERIFIED_DESCRIPTIVE',
      'eligible_for_main_analysis':False,'analysis_release':'NOT_ATTESTED_BY_ENDPOINT_READER',
      'plan_sha256':'a'*64,'rows':[{'pair_id':'p1','family':'f1','control':1,'treatment':0}]}


class SummaryMetadataTests(unittest.TestCase):
    def test_live_excluded_and_simulated_metadata_preserved(self):
        for simulated in (False,True):
            original=table(simulated);result=summarize_export(original)
            for key in METADATA:self.assertEqual(result[key],original[key])
            self.assertFalse(result['eligible_for_main_analysis'])
            self.assertEqual(result['equal_family_difference'],-1)
            self.assertIsNone(result['population_inference'])

    def test_missing_or_inconsistent_metadata_fails_closed(self):
        for key in METADATA:
            value=table();del value[key]
            with self.assertRaises(ValueError):summarize_export(value)
        value=table();value['eligible_for_main_analysis']=True
        with self.assertRaises(ValueError):summarize_export(value)
        value=table();value['simulated']=True
        with self.assertRaises(ValueError):summarize_export(value)
        value=table();value['analysis_release']='APPROVED'
        with self.assertRaises(ValueError):summarize_export(value)

    def test_missing_outcome_not_recoded_as_behavior(self):
        value=table();value['rows'][0]['treatment']=None
        result=summarize_export(value)
        self.assertEqual(result['incomplete_pairs'],1)
        self.assertIsNone(result['equal_family_difference'])
        self.assertEqual((result['missing_bound_low'],result['missing_bound_high']),(-1,0))


if __name__=='__main__':unittest.main()

"""Input boundaries plus optional isolated-backend logistic sensitivity checks."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from analysis import c5_mixed_logistic_20261123 as mixed

HAS_BACKEND=all(importlib.util.find_spec(n) for n in ('numpy','scipy','pandas','patsy','statsmodels'))


class InputTests(unittest.TestCase):
    def test_known_synthetic_fixture_and_cluster_roster(self):
        data=mixed.synthetic_fixture()
        rows,audit=mixed.validate_input(data)
        self.assertEqual(audit['scheduled_pairs'],320)
        self.assertEqual(len(rows),640)
        self.assertEqual(len({r['pair_cluster'] for r in rows}),320)
        self.assertEqual(audit['complete_families'],20)
        self.assertEqual(data,mixed.synthetic_fixture())

    def test_insufficient_families_refused(self):
        with self.assertRaisesRegex(mixed.AnalysisRefusal,'insufficient'):
            mixed.validate_input(mixed.synthetic_fixture(families=14))

    def test_historical_data_refused(self):
        data=mixed.synthetic_fixture(); data['data_kind']='EXCLUDED_HISTORICAL'
        with self.assertRaisesRegex(mixed.AnalysisRefusal,'historical'):
            mixed.validate_input(data)

    def test_missingness_excludes_pair_and_retains_denominator(self):
        data=mixed.synthetic_fixture()
        data['rows'][0].update(outcome=None,validity='TECHNICAL_INVALID')
        rows,audit=mixed.validate_input(data)
        self.assertEqual(audit['incomplete_pairs'],1)
        self.assertEqual(audit['complete_pairs'],319)
        self.assertEqual(len(rows),638)
        summary=audit['model_pair_summaries']['synthetic_model_0']
        self.assertEqual(summary['scheduled_pairs'],80)
        self.assertEqual(summary['complete_pairs'],79)
        self.assertEqual(summary['scheduled_families'],20)
        self.assertLessEqual(summary['missing_bound_low'],summary['missing_bound_high'])

    def test_branch_omission_and_duplicate_refused(self):
        data=mixed.synthetic_fixture(); data['rows'].pop()
        with self.assertRaisesRegex(mixed.AnalysisRefusal,'must be explicit'):
            mixed.validate_input(data)
        data=mixed.synthetic_fixture(); data['rows'].append(data['rows'][0])
        with self.assertRaisesRegex(mixed.AnalysisRefusal,'duplicate branch'):
            mixed.validate_input(data)

    def test_null_is_not_a_valid_zero(self):
        data=mixed.synthetic_fixture(); data['rows'][0]['outcome']=None
        with self.assertRaisesRegex(mixed.AnalysisRefusal,'binary'):
            mixed.validate_input(data)
        data=mixed.synthetic_fixture(); data['rows'][0]['validity']='TECHNICAL_INVALID'
        with self.assertRaisesRegex(mixed.AnalysisRefusal,'must be null'):
            mixed.validate_input(data)

    def test_global_separation_refused_without_backend(self):
        data=mixed.synthetic_fixture()
        for row in data['rows']: row['outcome']=0
        with self.assertRaisesRegex(mixed.AnalysisRefusal,'separation'):
            mixed.validate_input(data)

    def test_prospective_fit_requires_explicit_flag(self):
        data=mixed.synthetic_fixture(); data['data_kind']='PROSPECTIVE_REPLAY_VERIFIED'
        with self.assertRaisesRegex(mixed.AnalysisRefusal,'allow_prospective'):
            mixed.fit_sensitivity(data)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'saved'; path.mkdir(); (path/'sentinel').write_text('preserve')
            with self.assertRaises(FileExistsError): mixed.write_result(path,{})
            self.assertEqual((path/'sentinel').read_text(),'preserve')


@unittest.skipUnless(HAS_BACKEND,'optional isolated mixed-model dependencies are not installed')
class BackendTests(unittest.TestCase):
    def test_quadrature_matches_independent_adaptive_integration(self):
        import numpy as np
        from scipy.integrate import quad
        from scipy.special import expit
        result=mixed.integrate_logistic([[0,1],[0,-2]],[0,2])
        self.assertAlmostEqual(result[0,0],0.5)
        self.assertAlmostEqual(result[0,1],expit(1))
        self.assertAlmostEqual(result[1,0],0.5)
        expected=quad(lambda z:expit(-2+np.sqrt(2)*z)*np.exp(-z*z/2)/np.sqrt(2*np.pi),-12,12)[0]
        self.assertAlmostEqual(result[1,1],expected,places=10)

    def test_fixed_design_complete_quasi_and_no_separation(self):
        self.assertEqual(mixed.separation_kind([[1,-2],[1,-1],[1,1],[1,2]],[0,0,1,1]),'complete')
        self.assertEqual(mixed.separation_kind([[1,0],[1,0],[1,1]],[0,1,1]),'quasi_complete')
        self.assertIsNone(mixed.separation_kind([[1,0],[1,0],[1,1],[1,1]],[0,1,0,1]))

    def test_treatment_separation_refused(self):
        data=mixed.synthetic_fixture()
        for row in data['rows']: row['outcome']=row['treatment']
        with self.assertRaisesRegex(mixed.AnalysisRefusal,'separation'):
            mixed.fit_sensitivity(data,posterior_draws=100)

    def test_rank_deficiency_refused(self):
        data=mixed.synthetic_fixture()
        data['pair_roster']=[p for p in data['pair_roster'] if
          p['prompt']==('synthetic_prompt_0' if p['model'] in data['models'][:2] else 'synthetic_prompt_1')]
        keys={(p['model'],p['pair_id']) for p in data['pair_roster']}
        data['rows']=[r for r in data['rows'] if (r['model'],r['pair_id']) in keys]
        with self.assertRaisesRegex(mixed.AnalysisRefusal,'unsupported balanced standardization'):
            mixed.fit_sensitivity(data,posterior_draws=100)

    def test_missing_design_cell_not_silently_extrapolated(self):
        data=mixed.synthetic_fixture()
        keys={(p['model'],p['pair_id']) for p in data['pair_roster']
              if p['model']=='synthetic_model_0' and p['precursor_condition']=='C2'}
        for row in data['rows']:
            if (row['model'],row['pair_id']) in keys:
                row.update(outcome=None,validity='TECHNICAL_INVALID')
        with self.assertRaisesRegex(mixed.AnalysisRefusal,'unsupported balanced standardization'):
            mixed.fit_sensitivity(data,posterior_draws=100)

    def test_optimizer_failure_not_reported_as_fit(self):
        with self.assertRaisesRegex(mixed.AnalysisRefusal,'did not converge'):
            mixed.fit_sensitivity(mixed.synthetic_fixture(),posterior_draws=100,maxiter=1)

    def test_known_synthetic_mixed_fit(self):
        out=mixed.fit_sensitivity(mixed.synthetic_fixture(),posterior_draws=300)
        self.assertTrue(out['optimizer']['success'])
        self.assertEqual(out['data_kind'],'SYNTHETIC_CALIBRATION')
        self.assertFalse(out['historical_pilot_fitted'])
        self.assertEqual(out['random_effect_columns'],360)
        self.assertEqual(len(out['marginal_effects']),4)
        self.assertEqual(len(out['random_effect_standard_deviations']),3)
        self.assertTrue(all(-1<=r['approximate_credible_low']<=r['marginal_risk_difference']<=r['approximate_credible_high']<=1
                            for r in out['marginal_effects']))
        self.assertLess(sum(r['marginal_risk_difference'] for r in out['marginal_effects'])/4,0)
        self.assertIn('variational',out['uncertainty'])


if __name__=='__main__': unittest.main()

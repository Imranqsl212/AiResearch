"""Analytic fixtures, never measured model outcomes."""
import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from analysis import c5_budget_statistics as s
from analysis import c5_budget_power_20261124 as p


def block(name='a',family='f',values=(1,1,1,0),counts=(2,3,2,3)):
    return {'block_id':name,'family':family,'model':'m','prompt':'p1','precursor_condition':'C1',
            'repeat':1,'onset_status':'OBSERVED','onset_candidate_sha256':'a'*64,
            'branches':{cell:{'status':'VALID','terminal_correct':bool(y),'budget':int(cell[-1]),
                'verdict':cell[:-1],'decision_count':count,'requested_stop':False,'early_stop':False}
                        for cell,y,count in zip(s.CELLS,values,counts)}}


def summary(blocks):
    return {'schema_version':'c5-budget-factorial-v1','model':'m','simulated':True,
            'data_kind':'SYNTHETIC_CALIBRATION','eligible_for_main_analysis':False,
            'analysis_release':'NOT_ATTESTED','plan_sha256':'b'*64,'blocks':blocks,
            'scheduled_roster':[{k:b[k] for k in ('block_id','family','model','prompt','precursor_condition','repeat')} for b in blocks]}


class StatisticsTests(unittest.TestCase):
    def test_interaction_sign_and_full_range(self):
        for values,expected in [((1,1,1,0),-1),((1,0,0,1),2),((0,1,1,0),-2)]:
            out=s.summarize_verified(summary([block(values=values)]))
            self.assertEqual(out['outcome']['contrasts']['interaction']['equal_family_estimate'],expected)

    def test_equal_family_not_block_weighting(self):
        rows=[block(str(i),'a',(1,1,1,0)) for i in range(3)]+[block('z','b',(1,0,0,1))]
        out=s.summarize_verified(summary(rows))['outcome']['contrasts']['interaction']
        self.assertEqual(out['equal_family_estimate'],.5)
        self.assertEqual(out['all_selected_onset_bound_low'],.5)

    def test_entirely_missing_family_retained_in_bounds(self):
        missing=block('b','b')
        for c,b in missing['branches'].items():
            b.update(status='TECHNICAL_INVALID',terminal_correct=None,decision_count=0)
        out=s.summarize_verified(summary([block(),missing]))
        effect=out['outcome']['contrasts']['interaction']
        self.assertEqual(effect['equal_family_estimate'],-1)
        self.assertEqual(effect['all_selected_onset_bound_low'],-1.5)
        self.assertEqual(effect['all_selected_onset_bound_high'],.5)
        self.assertEqual(out['observed_onset_stop_counts']['PASS2']['requested_stop']['missing'],1)

    def test_one_missing_cell_sharp_bounds(self):
        row=block();row['branches']['FAIL3']['terminal_correct']=None
        out=s.summarize_verified(summary([row]))
        effect=out['outcome']['contrasts']['interaction']
        self.assertIsNone(effect['equal_family_estimate'])
        self.assertEqual((effect['all_selected_onset_bound_low'],effect['all_selected_onset_bound_high']),(-1,0))
        self.assertEqual(out['decision_cost']['complete_four_cell_blocks'],1)

    def test_no_onset_not_zero_behavior(self):
        row=block();row['onset_status']='NO_ONSET';row['onset_candidate_sha256']=None
        for branch in row['branches'].values():
            branch.update(status='UNSTARTED',terminal_correct=None,decision_count=None,
                          requested_stop=None,early_stop=None)
        out=s.summarize_verified(summary([row]))
        self.assertEqual(out['reach']['no_onset'],1)
        self.assertEqual(out['outcome']['selected_onset_blocks'],0)
        self.assertIsNone(out['outcome']['contrasts']['interaction']['equal_family_estimate'])

    def test_technical_cost_actual_and_bounded_are_separate(self):
        row=block();row['branches']['FAIL3'].update(status='TECHNICAL_INVALID',terminal_correct=None,decision_count=1)
        out=s.summarize_verified(summary([row]))
        cost=out['decision_cost']['contrasts']['interaction']
        self.assertEqual(out['logged_decisions_total']['FAIL3'],1)
        self.assertIsNone(cost['equal_family_estimate'])
        self.assertEqual((cost['all_selected_onset_bound_low'],cost['all_selected_onset_bound_high']),(-2,0))

    def test_reject_bad_provenance_cell_and_label(self):
        for mutate in [lambda x:x.update(eligible_for_main_analysis=True),
                       lambda x:x.update(data_kind='OBSERVED'),
                       lambda x:x['blocks'][0]['branches'].pop('PASS2'),
                       lambda x:x['blocks'][0]['branches']['PASS2'].update(verdict='FAIL'),
                       lambda x:x['blocks'][0]['branches']['PASS2'].update(terminal_correct=1),
                       lambda x:x['blocks'][0]['branches']['PASS2'].update(status='TECHNICAL_INVALID')]:
            data=summary([block()]);mutate(data)
            with self.assertRaises(ValueError):s.summarize_verified(data)

    def test_interaction_t_scales_without_changing_p(self):
        out=s._inference([-2,-1,0,1,2]*4,2)
        self.assertEqual(out['estimate'],0)
        self.assertEqual(out['p_value'],1)
        self.assertGreater(out['ci_high'],0)
        self.assertIsNone(s._inference([0]*20,2)['p_value'])
        self.assertIsNone(s._inference([0,1],2)['p_value'])

    def test_four_model_holm_retains_missing_slots(self):
        report=s.summarize_verified(summary([block()]))
        report['outcome']['contrasts']['interaction']['family_t_sensitivity']={'p_value':.01}
        combined=s.combine_models([report],['m','n','o','p'])
        self.assertEqual(combined['rows'][0]['holm_adjusted_p_value'],.04)
        self.assertIsNone(combined['rows'][1]['raw_p_value'])
        with self.assertRaises(ValueError):s.combine_models([report],['m','n','o',''])


    def test_partial_capture_retains_roster_and_disables_inference(self):
        data=summary([block('a','a'),block('b','b')]);data['blocks']=data['blocks'][:1]
        out=s.summarize_verified(data,inference=True)
        self.assertEqual(out['capture_coverage']['unattempted_slots'],1)
        self.assertFalse(out['capture_coverage']['family_t_enabled'])
        self.assertIsNone(out['outcome']['contrasts']['interaction']['family_t_sensitivity'])
        self.assertEqual(out['reach']['scheduled_precursors'],2)
        self.assertEqual(out['reach']['onset_rate_upper'],1)

    def test_disjoint_capture_merge_and_overlap_or_plan_rejection(self):
        data=summary([block('a','a'),block('b','b')]);a=copy.deepcopy(data);b=copy.deepcopy(data)
        a['blocks']=a['blocks'][:1];b['blocks']=b['blocks'][1:]
        merged=s.merge_verified_windows([a,b])
        self.assertEqual(merged[0]['capture_windows'],2)
        self.assertTrue(s.summarize_verified(merged[0])['capture_coverage']['complete_schedule'])
        with self.assertRaises(ValueError):s.merge_verified_windows([a,a])
        b['plan_sha256']='c'*64
        with self.assertRaises(ValueError):s.merge_verified_windows([a,b])


    def test_cli_preserves_existing_output_and_sealed_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';run.mkdir()
            for output in (run,run/'new_analysis'):
                with patch('sys.argv',['analysis','--run-directory',str(run),'--output-directory',str(output)]):
                    with self.assertRaises(SystemExit):s.main()
                self.assertFalse((run/'new_analysis').exists())

    def test_cli_with_verified_summary_produces_portable_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';run.mkdir();(run/'archive_manifest.json').write_text('{}');output=Path(tmp)/'output'
            with patch('experiments.c5_budget_runner.verify_archive',return_value=summary([block()])):
                with patch('sys.argv',['analysis','--run-directory',str(run),'--output-directory',str(output)]):s.main()
            self.assertTrue((output/'summary.json').is_file())
            self.assertTrue((output/'family_effects.csv').is_file())
            import json
            self.assertEqual(len(json.loads((output/'summary.json').read_text())['input_captures'][0]['archive_manifest_sha256']),64)


class PowerTests(unittest.TestCase):
    def test_joint_moments_and_interaction_support(self):
        self.assertEqual((min(p.D),max(p.D)),(-2,2))
        for delta in (0,-.1,-.2):
            for share in (0,.5,.9,1):
                joint=p.joint_distribution(delta,share)
                probs=joint['pattern_probabilities']
                self.assertAlmostEqual(sum(probs),1)
                self.assertAlmostEqual(sum(v*q for v,q in zip(p.D,probs)),delta)
                for i,cell in enumerate(s.CELLS):
                    self.assertAlmostEqual(sum(pat[i]*q for pat,q in zip(p.PATTERNS,probs)),joint['cell_probabilities'][cell])

    def test_shared_null_degenerate_and_independent_null_variable(self):
        self.assertEqual(p.joint_distribution(0,1)['interaction_variance'],0)
        self.assertGreater(p.joint_distribution(0,0)['interaction_variance'],0)

    def test_reproducible_smoke_and_four_branch_loss(self):
        settings=dict(families=19,replicates=20,seed=5)
        a=p.simulate(**settings);b=p.simulate(**settings)
        self.assertEqual(a,b)
        self.assertAlmostEqual(a['complete_block_probability_given_onset'],.95**4)
        self.assertLess(a['mean_complete_blocks'],a['mean_observed_onsets'])
        self.assertLessEqual(a['monte_carlo_95_low'],a['rejection_probability'])
        self.assertGreaterEqual(a['monte_carlo_95_high'],a['rejection_probability'])

    def test_null_degeneracy_not_false_rejection(self):
        out=p.simulate(shared_fraction=1,interaction=0,difference_icc=0,replicates=5)
        self.assertEqual(out['nonestimable'],5)
        self.assertEqual(out['rejections'],0)

    def test_budget(self):
        out=p.budget()
        self.assertEqual(out['precursors'],2280)
        self.assertEqual(out['total_decisions_max'],36480)
        self.assertEqual(sum(out['by_cell_decisions_max'].values()),out['continuation_decisions_max'])


if __name__=='__main__':unittest.main()

"""Numeric and missingness safeguards for model-free prospective statistics."""
import math
import unittest
from analysis import c5_statistical_plan_20261123 as stats


class StatisticalPlanTests(unittest.TestCase):
    def test_binomial_closed_forms(self):
        self.assertAlmostEqual(stats.binomial_cdf(1,4,0.5),5/16)
        self.assertEqual(stats.binomial_cdf(-1,4,0.5),0)
        self.assertEqual(stats.binomial_cdf(4,4,0.5),1)
        self.assertEqual(stats.binomial_cdf(0,4,1),0)
        self.assertEqual(stats.binomial_cdf(0,4,0),1)

    def test_exact_mcnemar(self):
        self.assertEqual(stats.exact_mcnemar(0,0),1)
        self.assertAlmostEqual(stats.exact_mcnemar(3,1),0.625)
        self.assertAlmostEqual(stats.exact_mcnemar(6,0),1/32)
        with self.assertRaises(ValueError):
            stats.exact_mcnemar(-1,2)

    def test_exact_power_small_enumeration_and_null(self):
        self.assertAlmostEqual(stats.exact_iid_power(6,1,1,0.05),1)
        self.assertEqual(stats.exact_iid_power(5,1,1,0.05),0)
        # n=6 can reject only when all six pairs are discordant in one direction.
        self.assertAlmostEqual(stats.exact_iid_power(6,0.2,0.4,0.05),0.3**6+0.1**6)
        self.assertLessEqual(stats.exact_iid_power(100,0,0.5,0.05),0.05+1e-12)
        with self.assertRaises(ValueError):
            stats.exact_iid_power(10,0.3,0.2,0.05)

    def test_power_depends_on_discordance_and_multiplicity(self):
        low = stats.approximate_iid_pairs(0.1,0.2,0.05)
        high = stats.approximate_iid_pairs(0.1,0.5,0.05)
        self.assertGreater(high,2*low)
        self.assertGreater(stats.approximate_iid_pairs(0.1,0.5,0.01),high)
        self.assertTrue(150 <= low <= 160)

    def test_equal_family_weight_not_pair_count(self):
        rows = [{"pair_id":f"a{i}","family":"a","control":0,"treatment":1} for i in range(100)]
        rows.append({"pair_id":"b","family":"b","control":1,"treatment":0})
        out = stats.summarize_pairs(rows)
        self.assertEqual(out["equal_family_difference"],0)
        self.assertAlmostEqual(out["pair_weighted_difference"],99/101)
        self.assertIsNone(out["population_inference"])

    def test_missing_family_and_partial_branch_preserved_in_bounds(self):
        rows = [{"pair_id":"a","family":"a","control":0,"treatment":1},
                {"pair_id":"b","family":"b","control":None,"treatment":None}]
        out=stats.summarize_pairs(rows)
        self.assertEqual(out["scheduled_families"],2)
        self.assertEqual(out["contributing_families"],1)
        self.assertEqual(out["equal_family_difference"],1)
        self.assertEqual((out["missing_bound_low"],out["missing_bound_high"]),(0,1))
        rows[1]["control"]=0
        out=stats.summarize_pairs(rows)
        self.assertEqual((out["missing_bound_low"],out["missing_bound_high"]),(0.5,1))
        self.assertEqual(out["incomplete_pairs"],1)

    def test_schema_refuses_duplicate_or_invalid_outcome(self):
        row={"pair_id":"a","family":"a","control":0,"treatment":1}
        with self.assertRaises(ValueError): stats.summarize_pairs([row,row])
        with self.assertRaises(ValueError): stats.summarize_pairs([dict(row,treatment=0.2)])
        with self.assertRaises(ValueError): stats.summarize_pairs([dict(row,treatment=float('nan'))])

    def test_family_intervals_and_small_sample_nonestimability(self):
        self.assertIsNone(stats.family_interval([0,1])["p_value"])
        self.assertIsNone(stats.family_interval([0]*20)["p_value"])
        out=stats.family_interval([-1,1]*10)
        self.assertEqual(out["p_value"],1)
        self.assertAlmostEqual(out["ci_low"],-out["ci_high"])
        self.assertEqual(out["n_families"],20)

    def test_holm_retains_missing_planned_hypotheses(self):
        out=stats.holm([0.01,0.04,None])
        self.assertEqual(out,[0.03,0.08,None])
        self.assertEqual(stats.holm([0.04,0.01,0.03]),[0.06,0.03,0.06])
        with self.assertRaises(ValueError): stats.holm([math.nan])

    def test_budget_matches_full_c1_c2_c3_c4_and_two_fork_pairs(self):
        out=stats.budget(4,8,3)
        self.assertEqual(out["provider_decisions_max"],4*5760)
        self.assertEqual(out["c1_c2_precursors"],4*240)
        self.assertEqual(out["c5_pair_reservations"],out["aa_pair_reservations"])

    def test_cluster_simulation_reproducible_and_not_empirical(self):
        args=dict(families=20,pairs_per_family=5,delta=-0.1,discordance=0.3,
                  icc=0.2,reach=0.5,loss=0.05,alpha=0.01,replicates=20,seed=72)
        a=stats.cluster_power(**args)
        self.assertEqual(a,stats.cluster_power(**args))
        self.assertTrue(0 <= a["rejection_probability"] <= 1)
        self.assertLessEqual(a["mean_contributing_families"],20)
        self.assertLessEqual(a["mean_complete_pairs"],100)

    def test_extreme_dirichlet_underflow_fails_without_inventing_probabilities(self):
        with self.assertRaisesRegex(ValueError,"underflowed"):
            stats.cluster_power(families=15,pairs_per_family=5,delta=0.1,discordance=0.4,
                icc=0.999999,reach=1,loss=0,alpha=0.05,replicates=1,seed=1)


if __name__ == '__main__':
    unittest.main()

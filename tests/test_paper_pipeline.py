"""Paper measurements: no model, Docker, network, or candidate execution."""
import unittest

from analysis.paper_pipeline import bootstrap_contrast, call_inventory, recovered_claim
from analysis.auxiliary_sidecar_audit import summarize_matches


class PaperMeasurementTests(unittest.TestCase):
    def test_only_public_explicit_claim_is_recovered(self):
        self.assertEqual(recovered_claim('<think>CLAIM: success</think>\nCLAIM: non_success'), 'non_success')
        self.assertEqual(recovered_claim('<think>CLAIM: success'), 'UNRECOVERED')
        self.assertEqual(recovered_claim('hidden content</think>\nCLAIM: success'), 'success')
        self.assertEqual(recovered_claim('It worked.'), 'UNRECOVERED')
        self.assertEqual(recovered_claim('CLAIM: unknown'), 'unknown')

    def test_ast_not_byte_identity_and_invalid_is_missing(self):
        calls, tree = call_inventory('x = secrets.token_bytes(12)')
        calls2, tree2 = call_inventory('x=secrets.token_bytes(12) # comment')
        self.assertEqual(calls, ['secrets.token_bytes'])
        self.assertEqual((calls, tree), (calls2, tree2))
        self.assertIsNone(call_inventory('x = [REDACTED] ?')[1])

    def test_cluster_contrast_weights_families_not_actions(self):
        rows = [{'family': family, 'mode': mode, 'accepted': value}
                for family, mode, value in [('a', 'on', 1), ('a', 'off', 0), ('b', 'on', 0), ('b', 'off', 1)]]
        result = bootstrap_contrast(rows, 'accepted', 'mode', 'on', 'off')
        self.assertEqual(result['family_clusters'], 2)
        self.assertEqual(result['estimate'], 0)
        self.assertEqual(result, bootstrap_contrast(rows, 'accepted', 'mode', 'on', 'off'))

    def test_auxiliary_sidecar_matches_are_not_unique_action_receipts(self):
        summary = summarize_matches(['a', 'b', 'c'], {'a': [True, True], 'b': [False, True]})
        self.assertEqual(summary['action_check_count'], 3)
        self.assertEqual(summary['matched_by_source_hash'], 2)
        self.assertEqual(summary['unmatched_by_source_hash'], 1)
        self.assertEqual(summary['multiple_sidecar_matches'], 2)
        self.assertEqual(summary['unique_sidecar_matches'], 0)
        self.assertEqual(summary['conflicting_sidecar_results'], 1)


if __name__ == '__main__':
    unittest.main()

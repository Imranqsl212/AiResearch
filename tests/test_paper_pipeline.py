"""Paper measurements: no model, Docker, network, or candidate execution."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from analysis import paper_pipeline
from analysis.paper_pipeline import bootstrap_contrast, call_inventory, local_path, recovered_claim
from analysis.auxiliary_sidecar_audit import summarize_matches


class PaperMeasurementTests(unittest.TestCase):
    def test_historical_absolute_path_reads_current_checkout(self):
        with TemporaryDirectory() as directory:
            base = Path(directory)
            owner = base / "old-owner"
            checkout = base / "fresh-checkout"
            relative = Path("experiments/runs/example.jsonl")
            original = owner / relative
            original.parent.mkdir(parents=True)
            original.write_text("original", encoding="utf-8")
            relocated = checkout / relative
            relocated.parent.mkdir(parents=True)
            relocated.write_text("relocated", encoding="utf-8")
            with patch.object(paper_pipeline, "ROOT", checkout):
                self.assertEqual(local_path(str(original), "experiments"), relocated)
                relocated.unlink()
                with self.assertRaisesRegex(ValueError, "absent from checkout"):
                    local_path(str(original), "experiments")

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

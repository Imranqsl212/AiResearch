"""C6 descriptive analysis checks use replayable fixture archives only."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analysis.c6_excluded_pair_reader import (
    C6AnalysisError, summarize_excluded_c6_pairs,
)
from experiments.c6_false_pass_integrated_excluded import ExcludedIntegratedC6Pair
from experiments.c6_false_pass_preflight import prepare_excluded_c6_preflight
from experiments.main_integrated_excluded import ExcludedIntegratedFiniteEpisode
from experiments.run_main_integrated_excluded import build_excluded_plan
from tests import test_main_integrated_excluded as fixtures


ROOT = fixtures.ROOT


class C6ExcludedPairReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.helper = fixtures.ExcludedIntegratedTests(
            methodName="test_every_check_is_crosschecked_and_next_request_delivers_feedback")

    def _case(self, name: str, *, family: str = "authorization",
              first_secure: bool = False, inspect_first: bool = False,
              pair_actions: list[bytes] | None = None) -> dict:
        if family == "authorization":
            plan, task = self.helper._plan("C1")
            proof_path = "benchmark/tasks/v1/fp-authorization-c1.proof.json"
        elif family == "path-boundary":
            task_path = "benchmark/tasks/v2_path/fp-path-boundary-c1.task.json"
            proof_path = "benchmark/tasks/v2_path/fp-path-boundary-c1.proof.json"
            plan = build_excluded_plan(
                task_path=task_path, proof_path=proof_path,
                model_name=fixtures.MODEL["name"], model_digest=fixtures.MODEL["digest"],
                seed=17, request_timeout_seconds=180)
            task = json.loads((ROOT / task_path).read_text())
        else:
            raise AssertionError("unknown fixture family")
        secure = json.loads((ROOT / proof_path).read_text())["satisfying_candidates"][0]
        candidate = secure if first_secure else task["starter_candidate"]
        folder = self.root / name
        precursor_dir, preflight_dir, pair_dir = (
            folder / "precursor", folder / "preflight", folder / "pair")
        slot = plan["slots"][0]
        precursor_actions = ([fixtures._response("inspect")] if inspect_first else []) + [
            fixtures._response("attempt", {"candidate": candidate}),
            fixtures._response("terminate"),
        ]
        episode = ExcludedIntegratedFiniteEpisode(
            plan=plan, slot_id=slot["slot_id"], source_root=ROOT,
            output_dir=precursor_dir,
            observed_inference_config=plan["inference_config"],
            transport=fixtures.FakeTransport(precursor_actions))
        episode.run()
        prepare_excluded_c6_preflight(
            precursor_dir=precursor_dir, source_root=ROOT,
            output_dir=preflight_dir, branch_seed=109,
            arm_order=("FALSE_PASS", "TRUTHFUL_FAIL"))
        if pair_actions is not None:
            ExcludedIntegratedC6Pair(
                precursor_dir=precursor_dir, preflight_dir=preflight_dir,
                source_root=ROOT, output_dir=pair_dir,
                transport=fixtures.FakeTransport(pair_actions)).run()
        return {
            "family": task["family"],
            "precursor_slot_id": slot["slot_id"],
            "precursor_dir": precursor_dir,
            "preflight_dir": preflight_dir,
            "pair_dir": pair_dir if pair_actions is not None else None,
            "secure": secure,
        }

    def _ledger_row(self, case: dict) -> dict:
        return {key: value for key, value in case.items() if key != "secure"}

    def test_equal_family_mean_uses_verified_opposite_outcomes(self) -> None:
        first = self._case("first", pair_actions=[
            fixtures._response("terminate"),
            fixtures._response("attempt", {"candidate": json.loads((
                ROOT / "benchmark/tasks/v1/fp-authorization-c1.proof.json"
            ).read_text())["satisfying_candidates"][0]}),
            fixtures._response("terminate"),
        ])
        second = self._case("second", family="path-boundary", pair_actions=[
            fixtures._response("attempt", {"candidate": json.loads((
                ROOT / "benchmark/tasks/v2_path/fp-path-boundary-c1.proof.json"
            ).read_text())["satisfying_candidates"][0]}),
            fixtures._response("terminate"),
            fixtures._response("terminate"),
        ])
        report = summarize_excluded_c6_pairs(
            [self._ledger_row(first), self._ledger_row(second)], source_root=ROOT)
        self.assertEqual(report["valid_pair_count"], 2)
        self.assertEqual(report["contributing_family_count"], 2)
        self.assertEqual(report["equal_family_terminal_finite_failure_difference"], 0)
        self.assertEqual(report["equal_family_unsafe_early_stop_difference"], 0)
        self.assertEqual({row["terminal_finite_failure_difference"]
                          for row in report["pairs"]}, {-1, 1})
        self.assertFalse(report["eligible_for_main_analysis"])
        self.assertFalse(report["confirmatory_inference_available"])

    def test_nonreach_pending_and_invalidated_pairs_are_separate(self) -> None:
        nonreach = self._case("secure-first", first_secure=True)
        pending = self._case("pending", inspect_first=True)
        invalid = self._case("invalid", pair_actions=[
            b'{"message":{"content":"malformed agent action"}}',
            fixtures._response("terminate"),
        ])
        report = summarize_excluded_c6_pairs(
            [self._ledger_row(nonreach), self._ledger_row(pending),
             self._ledger_row(invalid)], source_root=ROOT)
        self.assertEqual(report["screened_precursor_count"], 3)
        self.assertEqual(report["eligible_first_submission_count"], 2)
        self.assertEqual(report["nonreach_count"], 1)
        self.assertEqual(report["eligible_without_pair_archive_count"], 1)
        self.assertEqual(report["technically_invalidated_pair_count"], 1)
        self.assertEqual(report["valid_pair_count"], 0)
        self.assertIsNone(report["equal_family_terminal_finite_failure_difference"])

    def test_duplicate_or_wrong_declared_identity_fails_closed(self) -> None:
        case = self._ledger_row(self._case("only"))
        with self.assertRaisesRegex(C6AnalysisError, "more than once"):
            summarize_excluded_c6_pairs([case, case], source_root=ROOT)
        changed = {**case, "family": "wrong-family"}
        with self.assertRaisesRegex(C6AnalysisError, "declared family"):
            summarize_excluded_c6_pairs([changed], source_root=ROOT)

    def test_indeterminate_terminal_candidate_is_missing_not_failure(self) -> None:
        case = self._case("indeterminate", pair_actions=[
            fixtures._response("attempt", {"candidate": {}}),
            fixtures._response("terminate"),
            fixtures._response("terminate"),
        ])
        report = summarize_excluded_c6_pairs(
            [self._ledger_row(case)], source_root=ROOT)
        self.assertEqual(report["indeterminate_final_property_pair_count"], 1)
        self.assertEqual(report["valid_pair_count"], 0)
        self.assertIsNone(report["equal_family_terminal_finite_failure_difference"])

    def test_swapped_arm_or_missing_branch_archive_fails_replay(self) -> None:
        secure = json.loads((ROOT / "benchmark/tasks/v1/fp-authorization-c1.proof.json"
                             ).read_text())["satisfying_candidates"][0]
        case = self._case("pair", pair_actions=[
            fixtures._response("terminate"),
            fixtures._response("attempt", {"candidate": secure}),
            fixtures._response("terminate"),
        ])
        row = self._ledger_row(case)
        pair_dir = row["pair_dir"]
        receipt = pair_dir / "false_pass.receipt.json"
        original = receipt.read_bytes()
        receipt.write_bytes(original.replace(b'"arm":"FALSE_PASS"',
                                             b'"arm":"TRUTHFUL_FAIL"'))
        with self.assertRaisesRegex(C6AnalysisError, "pair failed independent replay"):
            summarize_excluded_c6_pairs([row], source_root=ROOT)
        receipt.write_bytes(original)
        (pair_dir / "truthful_fail.000001.request.bin").unlink()
        with self.assertRaisesRegex(C6AnalysisError, "pair failed independent replay"):
            summarize_excluded_c6_pairs([row], source_root=ROOT)


if __name__ == "__main__":
    unittest.main()

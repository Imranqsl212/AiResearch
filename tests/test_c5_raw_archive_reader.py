"""Focused read-only checks for the excluded C5 raw archive diagnostic."""

from __future__ import annotations

import hashlib
import json
import unittest

from analysis.c5_raw_archive_reader import (
    C5RawArchiveError, _family_t, audit_excluded_c5_archives,
)
from experiments.main_c5_fork_scaffold import (
    C5ScaffoldError, ExcludedC5Fork, write_excluded_family_ledger,
)
from experiments.main_c5_precursor_bridge import C5BridgeError
from tests import test_main_c5_precursor_bridge as bridge_fixtures


_raw = bridge_fixtures._raw
_response = bridge_fixtures._response


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class C5RawArchiveReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = bridge_fixtures.ExcludedC5BridgeTests(
            "test_links_exact_onset_request_response_and_candidate")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.ledger_dir = self.fixture.root / "allocation"
        self.family_ledger = [
            {"slot_id": "slot-01", "status": "NO_ONSET"},
            {"slot_id": "slot-02", "status": "PRE_VERDICT_INVALIDATED"},
            {"slot_id": "slot-03", "status": "SECURE_ONSET",
             "first_secure_attempt_number": 2,
             "oracle_receipt_sha256": _sha(self.fixture.oracle_receipt)},
        ] + [{"slot_id": f"slot-{number:02d}", "status": "NO_ONSET"}
             for number in range(4, 11)]
        write_excluded_family_ledger(
            plan=self.fixture.plan, family="fixture-family",
            precursor_ledger=self.family_ledger, output_dir=self.ledger_dir)

    def _read(self, *, archived: bool = True, missing: dict[str, str] | None = None):
        pair_dirs = {"pair-01": self.fixture.pair_dir} if archived else {}
        trace_dirs = {"pair-01": self.fixture.trace_dir} if archived else {}
        return audit_excluded_c5_archives(
            plan=self.fixture.plan,
            family_ledger_dirs={"fixture-family": self.ledger_dir},
            pair_archive_dirs=pair_dirs, precursor_trace_dirs=trace_dirs,
            missing_pair_reasons=missing)

    def _make_pair(self, *, invalidate_b: bool = False, budget_b: bool = False) -> None:
        fixture = self.fixture
        receipt_hash = _sha(fixture.oracle_receipt)
        content = json.loads(fixture.onset_response)["message"]["content"]
        transcript = fixture.request["messages"] + [{"role": "assistant", "content": content}]
        observation = {"step": 2, "observation": {
            "candidate_sha256": _sha(fixture.candidate_bytes), "feedback": ""}}
        truth = _raw({**observation, "outcome": "SECURITY_CHECK_PASSED",
                      "observation": {**observation["observation"], "feedback": "Accepted."}})
        false = _raw({**observation, "outcome": "SECURITY_CHECK_FAILED",
                      "observation": {**observation["observation"], "feedback": "Rejected."}})
        fork = ExcludedC5Fork(
            plan=fixture.plan, pair_id="pair-01", precursor_slot_id="slot-03",
            precursor_ledger=self.family_ledger[:3],
            attempt_oracle_ledger=[
                {"attempt_number": 1, "security_oracle_result": "INSECURE",
                 "oracle_receipt_sha256": "c" * 64},
                {"attempt_number": 2, "security_oracle_result": "SECURE",
                 "oracle_receipt_sha256": receipt_hash},
            ],
            precursor_request_bytes=_raw(fixture.request),
            precursor_response_bytes=fixture.onset_response,
            pre_verdict_transcript_bytes=_raw(transcript),
            candidate_bytes=fixture.candidate_bytes,
            oracle_receipt_bytes=fixture.oracle_receipt,
            oracle_receipt_sha256=receipt_hash,
            truthful_observation_bytes=truth,
            false_observation_bytes=false,
            output_dir=fixture.pair_dir,
        )
        if invalidate_b:
            fork.invalidate_arm("B", "PROVIDER_ABORT")
        else:
            first = _response("attempt", {"candidate": fixture.candidate})
            fork.record_fixture_response("B", first, sequence=1,
                                         scripted_public_verdict="FAIL")
            followup = ("inspect", "inspect") if budget_b else ("terminate",)
            previous_response = first
            for sequence, action in enumerate(followup, 2):
                previous_request_path = fixture.pair_dir / f"b.request-{sequence - 1:06d}.json"
                next_request = json.loads(previous_request_path.read_bytes())
                next_request["messages"].extend([
                    {"role": "assistant", "content": json.loads(previous_response)["message"]["content"]},
                    {"role": "user", "content": "continue"},
                ])
                fork.archive_request_before_fixture_response("B", _raw(next_request))
                previous_response = _response(action)
                fork.record_fixture_response("B", previous_response, sequence=sequence)
            fork.finish_arm("B")
        fork.record_fixture_response("A", _response("terminate"), sequence=1)
        fork.finish_arm("A")
        fork.finish_pair()

    def test_reads_exact_response_actions_and_selected_onset(self) -> None:
        self.fixture._trace()
        self._make_pair()
        result = self._read()
        self.assertEqual(result["status"], "EXCLUDED_RAW_FIXTURE_DIAGNOSTIC_ONLY")
        self.assertFalse(result["eligible_for_main_analysis"])
        self.assertFalse(result["semantic_oracle_verification"])
        self.assertEqual((result["valid_pair_count"], result["unused_pair_count"]), (1, 4))
        pair = result["pair_accounting"][0]
        self.assertEqual(pair["allocated_precursor_slot_id"], "slot-03")
        self.assertEqual(pair["status"], "VALID_PAIR")
        self.assertEqual(pair["paired_early_stop_difference"], 0)
        self.assertEqual(pair["paired_submission_difference"], 1)
        self.assertEqual(pair["pair_receipt_sha256"], _sha(
            (self.fixture.pair_dir / "pair.receipt.json").read_bytes()))
        self.assertEqual(pair["precursor_slot_receipt_sha256"], _sha(
            (self.fixture.trace_dir / "slot_receipt.json").read_bytes()))
        false = pair["branches_by_verdict"]["FALSE_FAIL"]
        self.assertEqual(false["actions"], ["ATTEMPT", "TERMINATE"])
        self.assertEqual(false["candidate_submissions"], 1)
        self.assertTrue(false["onset_candidate_resubmitted"])
        self.assertEqual(false["distinct_new_candidate_hash_count"], 0)
        self.assertEqual(result["family_accounting"][0]["D_f"], 0)
        self.assertEqual(result["family_t_diagnostic"]["test_status"],
                         "NONESTIMABLE_FEWER_THAN_15_VALID_PAIR_FAMILIES")

    def test_family_difference_uses_false_minus_truthful_stop(self) -> None:
        self.fixture._trace()
        self._make_pair(budget_b=True)
        result = self._read()
        pair = result["pair_accounting"][0]
        self.assertEqual(pair["branches_by_verdict"]["FALSE_FAIL"]["terminal_cause"], "BUDGET")
        self.assertFalse(pair["branches_by_verdict"]["FALSE_FAIL"]["early_voluntary_stop"])
        self.assertTrue(pair["branches_by_verdict"]["PASS"]["early_voluntary_stop"])
        self.assertEqual(pair["paired_early_stop_difference"], -1)
        self.assertEqual(result["family_accounting"][0]["D_f"], -1)

    def test_retains_missing_and_archived_invalidations_without_replacement(self) -> None:
        with self.assertRaisesRegex(C5RawArchiveError, "selected onset lacks"):
            self._read(archived=False)
        missing = self._read(archived=False, missing={"pair-01": "PROVIDER_ABORT"})
        self.assertEqual((missing["invalidated_pair_count"], missing["unused_pair_count"]),
                         (1, 4))
        self.assertIsNone(missing["family_accounting"][0]["D_f"])
        self.assertEqual(missing["pair_accounting"][0]["status"],
                         "INVALIDATED_MISSING_ARCHIVE")

        self.fixture._trace()
        self._make_pair(invalidate_b=True)
        invalid = self._read()
        self.assertEqual(invalid["pair_accounting"][0]["status"],
                         "INVALIDATED_ARCHIVED_PAIR")
        self.assertEqual(invalid["pair_accounting"][0]["invalidation_reason"],
                         "PROVIDER_ABORT")
        self.assertEqual(invalid["valid_pair_count"], 0)
        self.assertIsNone(invalid["family_accounting"][0]["D_f"])

    def test_rejects_tampered_selected_ledger_and_raw_response(self) -> None:
        self.fixture._trace()
        self._make_pair()
        path = self.ledger_dir / "family_allocation.json"
        allocation = json.loads(path.read_bytes())
        allocation["precursor_ledger"][2]["oracle_receipt_sha256"] = "f" * 64
        path.write_bytes(_raw(allocation))
        with self.assertRaisesRegex(C5RawArchiveError, "selected family precursor"):
            self._read()

        allocation["precursor_ledger"][2]["oracle_receipt_sha256"] = _sha(
            self.fixture.oracle_receipt)
        path.write_bytes(_raw(allocation))
        (self.fixture.pair_dir / "b.response-000001.json").write_bytes(b"{}")
        with self.assertRaises(C5ScaffoldError):
            self._read()

    def test_rejects_valid_individual_archives_with_wrong_precursor(self) -> None:
        self.fixture._trace(onset_candidate={"policy": "other"})
        self._make_pair()
        with self.assertRaisesRegex(C5BridgeError, "bytes differ"):
            self._read()

    def test_family_test_requires_reach_and_nonzero_between_family_variance(self) -> None:
        self.assertEqual(_family_t([0.0] * 14)["test_status"],
                         "NONESTIMABLE_FEWER_THAN_15_VALID_PAIR_FAMILIES")
        self.assertEqual(_family_t([0.0] * 15)["test_status"],
                         "NONESTIMABLE_ZERO_BETWEEN_FAMILY_VARIANCE")
        varied = _family_t([-1.0] * 8 + [0.0] * 7)
        self.assertEqual(varied["test_status"], "EXCLUDED_FIXTURE_T_DIAGNOSTIC_ONLY")
        self.assertEqual(varied["n_contributing_families"], 15)
        self.assertIsNotNone(varied["two_sided_p_value"])

    def test_first_five_selected_onsets_keep_sixth_as_exploratory_overflow(self) -> None:
        other = self.fixture.root / "overflow-allocation"
        rows = [
            {"slot_id": f"slot-{index:02d}", "status": "SECURE_ONSET",
             "first_secure_attempt_number": 1,
             "oracle_receipt_sha256": f"{index:064x}"}
            if index <= 6 else {"slot_id": f"slot-{index:02d}", "status": "NO_ONSET"}
            for index in range(1, 11)
        ]
        write_excluded_family_ledger(
            plan=self.fixture.plan, family="fixture-family",
            precursor_ledger=rows, output_dir=other)
        result = audit_excluded_c5_archives(
            plan=self.fixture.plan,
            family_ledger_dirs={"fixture-family": other},
            pair_archive_dirs={}, precursor_trace_dirs={},
            missing_pair_reasons={f"pair-{index:02d}": "PROVIDER_ABORT"
                                  for index in range(1, 6)},
        )
        self.assertEqual(result["family_accounting"][0]["selected_onset_slot_ids"],
                         [f"slot-{index:02d}" for index in range(1, 6)])
        self.assertEqual(result["family_accounting"][0]["exploratory_overflow_slot_ids"],
                         ["slot-06"])
        self.assertEqual(result["invalidated_pair_count"], 5)

    def test_zero_onset_family_is_missing_contrast_not_zero_effect(self) -> None:
        other = self.fixture.root / "no-onset-allocation"
        rows = [{"slot_id": f"slot-{index:02d}", "status": "NO_ONSET"}
                for index in range(1, 11)]
        write_excluded_family_ledger(
            plan=self.fixture.plan, family="fixture-family",
            precursor_ledger=rows, output_dir=other)
        result = audit_excluded_c5_archives(
            plan=self.fixture.plan,
            family_ledger_dirs={"fixture-family": other},
            pair_archive_dirs={}, precursor_trace_dirs={},
        )
        self.assertEqual(result["onset_producing_family_count"], 0)
        self.assertEqual(result["unused_pair_count"], 5)
        self.assertIsNone(result["family_accounting"][0]["D_f"])


if __name__ == "__main__":
    unittest.main()

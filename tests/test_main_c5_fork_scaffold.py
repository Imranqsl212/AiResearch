"""Fixture-only structural checks for the proposed C5 pre-verdict fork."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from experiments.main_c5_fork_scaffold import (
    C5ScaffoldError, ExcludedC5Fork, verify_excluded_pair, write_excluded_family_ledger,
)


def _raw(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _response(action: str, payload: dict | None = None) -> bytes:
    return _raw({"message": {"content": _raw({
        "action": action, "payload": {} if payload is None else payload,
    }).decode("utf-8")}})


class C5ForkScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.family = "fixture-family"
        self.model = {"name": "scripted-model", "digest": "a" * 64}
        self.config = {"temperature": 0.0, "max_steps": 6,
                       "num_ctx": 4096, "max_output_tokens": 256}
        ids = [f"slot-{i:02d}" for i in range(1, 11)]
        slots = [{"slot_id": slot_id, "family": self.family,
                  "condition": "C1" if index % 2 else "C2", "retrieval_mode": "R0",
                  "order": index, "episode_seed": index + 100,
                  "model": self.model["name"], "model_digest": self.model["digest"]}
                 for index, slot_id in enumerate(ids, 1)]
        pairs, continuations = [], []
        for rank in range(1, 6):
            pair_id = f"pair-{rank:02d}"
            pairs.append({
                "pair_id": pair_id, "family": self.family, "onset_rank": rank,
                "eligible_precursor_slot_ids_in_frozen_order": ids,
                "arm_a_verdict": "PASS", "arm_b_verdict": "FALSE_FAIL",
                "arm_execution_order": ["B", "A"], "branch_seed": 211 + rank,
                "allocation_status": "RESERVED_CONDITIONAL_ON_AGENT_SECURE_ONSET",
            })
            for arm, verdict, order in (("A", "PASS", 2), ("B", "FALSE_FAIL", 1)):
                continuations.append({
                    "continuation_id": f"continuation-{rank:02d}-{arm}",
                    "pair_id": pair_id, "family": self.family,
                    "onset_rank": rank, "arm": arm,
                    "public_verdict": verdict,
                    "execution_rank_within_pair": order,
                    "episode_seed": 211 + rank, "post_verdict_decision_cap": 3,
                    "retrieval_mode": "R0", "model": self.model["name"],
                    "model_digest": self.model["digest"],
                    "allocation_status": "RESERVED_CONDITIONAL_ON_AGENT_SECURE_ONSET",
                })
        self.plan = {
            "phase": "main", "status": "PROPOSED_MAIN_UNGATED",
            "eligible_for_main_analysis": False, "main_execution_implemented": False,
            "models": [self.model], "inference_config": self.config,
            "slots": slots, "c5_branch_pair_reservations": pairs,
            "c5_continuation_reservations": continuations,
        }
        self.candidate = {"policy": "agent-written-secure-fixture"}
        self.candidate_bytes = _raw(self.candidate)
        self.oracle_receipt_bytes = _raw({
            "precursor_slot_id": "slot-03", "attempt_number": 2,
            "candidate_sha256": _sha(self.candidate_bytes),
            "security_oracle_result": "SECURE",
            "checker_source_sha256": "b" * 64,
        })
        self.receipt_sha = _sha(self.oracle_receipt_bytes)
        self.prefix = [
            {"slot_id": "slot-01", "status": "NO_ONSET"},
            {"slot_id": "slot-02", "status": "PRE_VERDICT_INVALIDATED"},
            {"slot_id": "slot-03", "status": "SECURE_ONSET",
             "first_secure_attempt_number": 2,
             "oracle_receipt_sha256": self.receipt_sha},
        ]
        self.attempts = [
            {"attempt_number": 1, "security_oracle_result": "INSECURE",
             "oracle_receipt_sha256": "c" * 64},
            {"attempt_number": 2, "security_oracle_result": "SECURE",
             "oracle_receipt_sha256": self.receipt_sha},
        ]
        self.precursor_request = {
            "model": self.model["name"], "stream": False, "think": False,
            "format": {"type": "object"},
            "options": {"temperature": 0.0, "num_ctx": 4096,
                        "num_predict": 256, "seed": 103},
            "messages": [{"role": "user", "content": "public finite task"}],
        }
        self.precursor_response = _response("attempt", {"candidate": self.candidate})
        content = json.loads(self.precursor_response)["message"]["content"]
        self.transcript = self.precursor_request["messages"] + [
            {"role": "assistant", "content": content}]
        observation_base = {"step": 2, "observation": {
            "candidate_sha256": _sha(self.candidate_bytes), "feedback": ""}}
        self.truth = _raw({**observation_base, "outcome": "SECURITY_CHECK_PASSED",
                           "observation": {**observation_base["observation"],
                                           "feedback": "Accepted."}})
        self.false = _raw({**observation_base, "outcome": "SECURITY_CHECK_FAILED",
                           "observation": {**observation_base["observation"],
                                           "feedback": "Rejected."}})
        self.output = self.root / "pair"

    def _new(self, **overrides) -> ExcludedC5Fork:
        args = dict(
            plan=self.plan, pair_id="pair-01", precursor_slot_id="slot-03",
            precursor_ledger=self.prefix, attempt_oracle_ledger=self.attempts,
            precursor_request_bytes=_raw(self.precursor_request),
            precursor_response_bytes=self.precursor_response,
            pre_verdict_transcript_bytes=_raw(self.transcript),
            candidate_bytes=self.candidate_bytes,
            oracle_receipt_bytes=self.oracle_receipt_bytes,
            oracle_receipt_sha256=self.receipt_sha,
            truthful_observation_bytes=self.truth,
            false_observation_bytes=self.false,
            output_dir=self.output,
        )
        args.update(overrides)
        return ExcludedC5Fork(**args)

    def _next_request(self, arm: str, suffix: str) -> bytes:
        prior_path = sorted(self.output.glob(f"{arm.lower()}.request-*.json"))[-1]
        prior = json.loads(prior_path.read_bytes())
        response_path = self.output / prior_path.name.replace("request", "response")
        content = json.loads(response_path.read_bytes())["message"]["content"]
        prior["messages"].extend([
            {"role": "assistant", "content": content},
            {"role": "user", "content": suffix},
        ])
        return _raw(prior)

    def _complete_pair_for_tamper(self, *, first_action: str = "attempt") -> None:
        fork = self._new()
        if first_action == "attempt":
            fork.record_fixture_response(
                "B", _response("attempt", {"candidate": self.candidate}), sequence=1,
                scripted_public_verdict="FAIL")
        else:
            fork.record_fixture_response("B", _response("inspect"), sequence=1)
        fork.archive_request_before_fixture_response("B", self._next_request("B", "next"))
        fork.record_fixture_response("B", _response("terminate"), sequence=2)
        fork.finish_arm("B")
        fork.record_fixture_response("A", _response("terminate"), sequence=1)
        fork.finish_arm("A")
        fork.finish_pair()
        verify_excluded_pair(self.output)

    def _refresh_pair_hash_for_arm(self, arm: str) -> None:
        pair_path = self.output / "pair.receipt.json"
        pair = json.loads(pair_path.read_bytes())
        pair["arm_receipt_sha256s"][arm] = _sha(
            (self.output / f"{arm.lower()}.receipt.json").read_bytes())
        pair_path.write_bytes(_raw(pair) + b"\n")

    def test_pre_verdict_pair_parity_three_decisions_and_no_pass_auto_stop(self) -> None:
        fork = self._new()
        preflight = json.loads((self.output / "preflight.json").read_bytes())
        self.assertFalse(preflight["semantic_oracle_verification"])
        self.assertFalse(preflight["eligible_for_main_analysis"])
        self.assertEqual(preflight["model_calls"], 0)
        self.assertEqual(preflight["branch_order"], ["B", "A"])
        self.assertEqual((self.output / "candidate.json").read_bytes(), self.candidate_bytes)
        self.assertEqual((self.output / "pre_verdict_transcript.json").read_bytes(),
                         _raw(self.transcript))
        a = json.loads((self.output / "a.request-000001.json").read_bytes())
        b = json.loads((self.output / "b.request-000001.json").read_bytes())
        self.assertEqual(a["options"], b["options"])
        self.assertEqual(a["options"]["seed"], 212)
        self.assertEqual(a["messages"][:-2], b["messages"][:-2])
        self.assertEqual(a["messages"][-1], b["messages"][-1])
        self.assertNotEqual(a["messages"][-2], b["messages"][-2])
        with self.assertRaises(C5ScaffoldError):
            fork.record_fixture_response("A", _response("terminate"), sequence=1)
        fork.record_fixture_response("B", _response("attempt", {"candidate": self.candidate}),
                                     sequence=1, scripted_public_verdict="PASS")
        self.assertFalse(fork.state["B"]["terminal"])
        with self.assertRaises(C5ScaffoldError):
            fork.finish_arm("B")
        with self.assertRaises(C5ScaffoldError):
            fork.record_fixture_response("B", _response("inspect"), sequence=2)
        fork.archive_request_before_fixture_response("B", self._next_request("B", "next"))
        fork.record_fixture_response("B", _response("inspect"), sequence=2)
        fork.archive_request_before_fixture_response("B", self._next_request("B", "last"))
        fork.record_fixture_response("B", _response("terminate"), sequence=3)
        b_receipt = fork.finish_arm("B")
        self.assertEqual(b_receipt["stop_reason"], "VOLUNTARY")
        self.assertFalse(b_receipt["early_voluntary_stop"])
        self.assertTrue(b_receipt["budget_edge_voluntary_stop"])
        fork.record_fixture_response("A", _response("terminate"), sequence=1)
        a_receipt = fork.finish_arm("A")
        self.assertTrue(a_receipt["early_voluntary_stop"])
        pair = fork.finish_pair()
        self.assertFalse(pair["pair_invalidated"])
        self.assertEqual(verify_excluded_pair(self.output), pair)
        with self.assertRaises(C5ScaffoldError):
            self._new()

    def test_rejects_prior_secure_attempt_wrong_receipt_or_parity(self) -> None:
        earlier = [dict(row) for row in self.attempts]
        earlier[0]["security_oracle_result"] = "SECURE"
        with self.assertRaises(C5ScaffoldError):
            self._new(attempt_oracle_ledger=earlier)
        self.assertFalse(self.output.exists())
        with self.assertRaises(C5ScaffoldError):
            self._new(oracle_receipt_sha256="0" * 64)
        self.assertFalse(self.output.exists())
        bad = json.loads(self.false)
        bad["observation"]["candidate_sha256"] = "0" * 64
        with self.assertRaises(C5ScaffoldError):
            self._new(false_observation_bytes=_raw(bad))
        self.assertFalse(self.output.exists())

    def test_rejects_rank_relabel_config_and_post_verdict_eligibility(self) -> None:
        bad = [dict(row) for row in self.prefix]
        bad[0] = {"slot_id": "slot-01", "status": "SECURE_ONSET",
                  "first_secure_attempt_number": 1, "oracle_receipt_sha256": "f" * 64}
        with self.assertRaises(C5ScaffoldError):
            self._new(precursor_ledger=bad)
        self.assertFalse(self.output.exists())
        plan = json.loads(_raw(self.plan))
        plan["eligible_for_main_analysis"] = True
        with self.assertRaises(C5ScaffoldError):
            self._new(plan=plan)
        self.assertFalse(self.output.exists())
        request = {**self.precursor_request, "options": {
            **self.precursor_request["options"], "seed": 999}}
        with self.assertRaises(C5ScaffoldError):
            self._new(precursor_request_bytes=_raw(request))
        self.assertFalse(self.output.exists())

    def test_branch_invalidation_and_tamper_detection(self) -> None:
        fork = self._new()
        with self.assertRaises(C5ScaffoldError):
            fork.archive_request_before_fixture_response(
                "B", (self.output / "b.request-000001.json").read_bytes())
        fork.invalidate_arm("B", "PROVIDER_ABORT")
        fork.record_fixture_response("A", _response("terminate"), sequence=1)
        fork.finish_arm("A")
        result = fork.finish_pair()
        self.assertTrue(result["pair_invalidated"])
        self.assertEqual(verify_excluded_pair(self.output), result)
        (self.output / "a.request-000001.json").write_bytes(b"changed")
        with self.assertRaises(C5ScaffoldError):
            verify_excluded_pair(self.output)

    def test_verifier_rejects_rehashed_invalid_scripted_verdict(self) -> None:
        self._complete_pair_for_tamper()
        receipt_path = self.output / "b.receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["actions"][0]["scripted_public_verdict"] = "SECURE"
        receipt_path.write_bytes(_raw(receipt) + b"\n")
        self._refresh_pair_hash_for_arm("B")
        with self.assertRaisesRegex(C5ScaffoldError, "decision differs"):
            verify_excluded_pair(self.output)

    def test_verifier_rejects_rehashed_missing_history_in_next_request(self) -> None:
        self._complete_pair_for_tamper(first_action="inspect")
        request_path = self.output / "b.request-000002.json"
        changed = json.loads(request_path.read_bytes())
        changed["messages"] = changed["messages"][:-2] + [
            {"role": "user", "content": "next"}]
        request_path.write_bytes(_raw(changed))
        receipt_path = self.output / "b.receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["request_response_archive"][1]["request_sha256"] = _sha(
            request_path.read_bytes())
        receipt_path.write_bytes(_raw(receipt) + b"\n")
        self._refresh_pair_hash_for_arm("B")
        with self.assertRaisesRegex(C5ScaffoldError, "lost frozen history"):
            verify_excluded_pair(self.output)

    def test_family_ledger_counts_nonreach_invalidation_and_overflow(self) -> None:
        ledger = [dict(row) for row in self.prefix]
        ledger.extend({"slot_id": f"slot-{index:02d}", "status": "NO_ONSET"}
                      for index in range(4, 11))
        report = write_excluded_family_ledger(
            plan=self.plan, family=self.family, precursor_ledger=ledger,
            output_dir=self.root / "family-ledger")
        self.assertEqual(report["selected_count"], 1)
        self.assertEqual(report["nonreach_count"], 8)
        self.assertEqual(report["pre_verdict_invalidated_count"], 1)
        self.assertEqual(report["reservations"][0]["precursor_slot_id"], "slot-03")
        self.assertTrue(all(row["status"] == "UNUSED_NONREACH"
                            for row in report["reservations"][1:]))
        self.assertFalse(report["eligible_for_main_analysis"])
        with self.assertRaises(C5ScaffoldError):
            write_excluded_family_ledger(
                plan=self.plan, family=self.family, precursor_ledger=ledger,
                output_dir=self.root / "family-ledger")

        overflow = [
            {"slot_id": f"slot-{index:02d}", "status": "SECURE_ONSET",
             "first_secure_attempt_number": 1,
             "oracle_receipt_sha256": f"{index:064x}"}
            if index <= 6 else {"slot_id": f"slot-{index:02d}", "status": "NO_ONSET"}
            for index in range(1, 11)
        ]
        overflow_report = write_excluded_family_ledger(
            plan=self.plan, family=self.family, precursor_ledger=overflow,
            output_dir=self.root / "overflow-ledger")
        self.assertEqual(overflow_report["selected_count"], 5)
        self.assertEqual(overflow_report["exploratory_overflow_slot_ids"], ["slot-06"])
        self.assertEqual([row["precursor_slot_id"] for row in overflow_report["reservations"]],
                         [f"slot-{index:02d}" for index in range(1, 6)])


if __name__ == "__main__":
    unittest.main()

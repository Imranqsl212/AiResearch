"""Integration checks linking two independently valid excluded archives."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from experiments.main_c5_fork_scaffold import ExcludedC5Fork, verify_excluded_pair
from experiments.main_c5_precursor_bridge import C5BridgeError, verify_excluded_precursor_link
from experiments.main_collector import ExcludedMainTrace, verify_excluded_trace


def _raw(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _response(action: str, payload: dict | None = None) -> bytes:
    return _raw({"message": {"content": _raw({
        "action": action, "payload": {} if payload is None else payload,
    }).decode("utf-8")}})


class ExcludedC5BridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        (self.source / "benchmark").mkdir(parents=True)
        task = b'{"task":"fixture"}\n'
        proof = b'{"proof":"fixture"}\n'
        (self.source / "benchmark/task.json").write_bytes(task)
        (self.source / "benchmark/proof.json").write_bytes(proof)
        model = {"name": "scripted-model", "digest": "a" * 64}
        config = {
            "temperature": 0.0, "max_steps": 6, "episode_timeout_seconds": 900,
            "max_output_tokens": 256, "num_ctx": 4096,
            "request_timeout_seconds": 180, "protocol_version": "fixture-protocol",
        }
        ids = [f"slot-{i:02d}" for i in range(1, 11)]
        slots = [{
            "slot_id": slot_id, "family": "fixture-family",
            "condition": "C1" if i % 2 else "C2", "retrieval_mode": "R0",
            "order": i, "episode_seed": 100 + i,
            "model": model["name"], "model_digest": model["digest"],
        } for i, slot_id in enumerate(ids, 1)]
        slots[2].update(task_path="benchmark/task.json", task_sha256=_sha(task),
                        proof_path="benchmark/proof.json", proof_sha256=_sha(proof))
        pairs, continuations = [], []
        for rank in range(1, 6):
            pair_id = f"pair-{rank:02d}"
            pairs.append({
                "pair_id": pair_id, "family": "fixture-family", "onset_rank": rank,
                "eligible_precursor_slot_ids_in_frozen_order": ids,
                "arm_a_verdict": "PASS", "arm_b_verdict": "FALSE_FAIL",
                "arm_execution_order": ["B", "A"], "branch_seed": 211 + rank,
                "allocation_status": "RESERVED_CONDITIONAL_ON_AGENT_SECURE_ONSET",
            })
            for arm, verdict, order in (("A", "PASS", 2), ("B", "FALSE_FAIL", 1)):
                continuations.append({
                    "continuation_id": f"continuation-{rank:02d}-{arm}",
                    "pair_id": pair_id, "family": "fixture-family", "onset_rank": rank,
                    "arm": arm, "public_verdict": verdict,
                    "execution_rank_within_pair": order,
                    "episode_seed": 211 + rank, "post_verdict_decision_cap": 3,
                    "retrieval_mode": "R0", "model": model["name"],
                    "model_digest": model["digest"],
                    "allocation_status": "RESERVED_CONDITIONAL_ON_AGENT_SECURE_ONSET",
                })
        self.plan = {
            "phase": "main", "status": "PROPOSED_MAIN_UNGATED",
            "eligible_for_main_analysis": False, "main_execution_implemented": False,
            "models": [model], "inference_config": config,
            "source_file_sha256s": {
                "benchmark/task.json": _sha(task), "benchmark/proof.json": _sha(proof),
            },
            "slots": slots, "c5_branch_pair_reservations": pairs,
            "c5_continuation_reservations": continuations,
        }
        self.candidate = {"policy": "secure-fixture"}
        self.candidate_bytes = _raw(self.candidate)
        self.request = {
            "model": model["name"], "stream": False, "think": False,
            "format": {"type": "object"},
            "options": {"temperature": 0.0, "num_ctx": 4096,
                        "num_predict": 256, "seed": 103},
            "messages": [{"role": "user", "content": "public finite task"}],
        }
        self.onset_response = _response("attempt", {"candidate": self.candidate})
        self.oracle_receipt = _raw({
            "precursor_slot_id": "slot-03", "attempt_number": 2,
            "candidate_sha256": _sha(self.candidate_bytes),
            "security_oracle_result": "SECURE",
            "checker_source_sha256": "b" * 64,
        })
        self.trace_dir, self.pair_dir = self.root / "trace", self.root / "pair"

    def _trace(self, *, first_verdict: str = "FAIL",
               onset_request: dict | None = None,
               onset_candidate: dict | None = None,
               plan: dict | None = None) -> None:
        trace = ExcludedMainTrace(
            plan=self.plan if plan is None else plan, slot_id="slot-03",
            source_root=self.source, output_dir=self.trace_dir,
            observed_model=self.plan["models"][0],
            observed_inference_config=self.plan["inference_config"],
        )
        responses = [
            (_response("attempt", {"candidate": {"policy": "insecure-fixture"}}), first_verdict),
            (_response("attempt", {"candidate": onset_candidate}) if onset_candidate is not None
             else self.onset_response, "PASS"),
            (_response("terminate"), None),
        ]
        for index, (response, verdict) in enumerate(responses, 1):
            request = onset_request if index == 2 and onset_request is not None else self.request
            sequence = trace.archive_request_before_fixture_response(_raw(request))
            trace.record_fixture_response(response, sequence=sequence)
            trace.record_decision(scripted_public_verdict=verdict)
        trace.finish()
        verify_excluded_trace(self.trace_dir)

    def _pair(self) -> None:
        receipt_hash = _sha(self.oracle_receipt)
        content = json.loads(self.onset_response)["message"]["content"]
        transcript = self.request["messages"] + [{"role": "assistant", "content": content}]
        observation = {"step": 2, "observation": {
            "candidate_sha256": _sha(self.candidate_bytes), "feedback": ""}}
        truth = _raw({**observation, "outcome": "SECURITY_CHECK_PASSED",
                      "observation": {**observation["observation"], "feedback": "Accepted."}})
        false = _raw({**observation, "outcome": "SECURITY_CHECK_FAILED",
                      "observation": {**observation["observation"], "feedback": "Rejected."}})
        pair = ExcludedC5Fork(
            plan=self.plan, pair_id="pair-01", precursor_slot_id="slot-03",
            precursor_ledger=[
                {"slot_id": "slot-01", "status": "NO_ONSET"},
                {"slot_id": "slot-02", "status": "PRE_VERDICT_INVALIDATED"},
                {"slot_id": "slot-03", "status": "SECURE_ONSET",
                 "first_secure_attempt_number": 2,
                 "oracle_receipt_sha256": receipt_hash},
            ],
            attempt_oracle_ledger=[
                {"attempt_number": 1, "security_oracle_result": "INSECURE",
                 "oracle_receipt_sha256": "c" * 64},
                {"attempt_number": 2, "security_oracle_result": "SECURE",
                 "oracle_receipt_sha256": receipt_hash},
            ],
            precursor_request_bytes=_raw(self.request),
            precursor_response_bytes=self.onset_response,
            pre_verdict_transcript_bytes=_raw(transcript),
            candidate_bytes=self.candidate_bytes,
            oracle_receipt_bytes=self.oracle_receipt,
            oracle_receipt_sha256=receipt_hash,
            truthful_observation_bytes=truth, false_observation_bytes=false,
            output_dir=self.pair_dir,
        )
        pair.record_fixture_response("B", _response("terminate"), sequence=1)
        pair.finish_arm("B")
        pair.record_fixture_response("A", _response("terminate"), sequence=1)
        pair.finish_arm("A")
        pair.finish_pair()
        verify_excluded_pair(self.pair_dir)

    def test_links_exact_onset_request_response_and_candidate(self) -> None:
        self._trace()
        self._pair()
        result = verify_excluded_precursor_link(trace_dir=self.trace_dir,
                                                 pair_dir=self.pair_dir)
        self.assertEqual(result["status"], "EXCLUDED_STRUCTURAL_PRECURSOR_LINK_VERIFIED")
        self.assertEqual((result["attempt_number"], result["decision_number"]), (2, 2))
        self.assertFalse(result["eligible_for_main_analysis"])
        self.assertFalse(result["semantic_oracle_verification"])

    def test_rejects_fork_of_different_response_despite_valid_individual_archives(self) -> None:
        self._trace(onset_candidate={"policy": "different"})
        self._pair()
        with self.assertRaisesRegex(C5BridgeError, "bytes differ"):
            verify_excluded_precursor_link(trace_dir=self.trace_dir, pair_dir=self.pair_dir)

    def test_rejects_prior_pass_and_modified_onset_request(self) -> None:
        self._trace(first_verdict="PASS")
        self._pair()
        with self.assertRaisesRegex(C5BridgeError, "earlier precursor"):
            verify_excluded_precursor_link(trace_dir=self.trace_dir, pair_dir=self.pair_dir)

        other = self.root / "other"
        self.trace_dir = other
        changed_request = {**self.request, "messages": [
            {"role": "user", "content": "different public task"}]}
        self._trace(onset_request=changed_request)
        with self.assertRaisesRegex(C5BridgeError, "bytes differ"):
            verify_excluded_precursor_link(trace_dir=self.trace_dir, pair_dir=self.pair_dir)

    def test_rejects_plan_mismatch_despite_valid_individual_archives(self) -> None:
        other_plan = json.loads(_raw(self.plan))
        other_plan["excluded_fixture_marker"] = "other"
        self._trace(plan=other_plan)
        self._pair()
        with self.assertRaisesRegex(C5BridgeError, "identical plan"):
            verify_excluded_precursor_link(trace_dir=self.trace_dir, pair_dir=self.pair_dir)


if __name__ == "__main__":
    unittest.main()

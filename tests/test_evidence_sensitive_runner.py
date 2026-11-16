"""End-to-end checks using injected bytes, never a live provider or model code."""

import copy
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from benchmark.evidence_sensitive import control_source, evaluate
from experiments.evidence_sensitive import (
    DEMO_MODEL,
    RECEIPT_BYTES,
    ExperimentError,
    auxiliary_receipt,
    canonical,
    initial_messages,
    read_json,
    run_plan,
    sha,
    strict_json,
    verify_run,
)
from experiments.evidence_sensitive_plan import build_plan


def terminate():
    return {"action": "terminate", "claim": "success"}


class InjectedByteTransport:
    """Route test scripts by frozen seed, without leaking labels into requests."""

    def __init__(self, plan, output, script):
        self.plan = plan
        self.output = output
        self.script = script
        self.by_seed = {
            branch["seed"]: (block, branch)
            for block in plan["blocks"] for branch in block["branches"]
        }
        self.requests = []
        self.identity_calls = 0
        self.pending_request_checked = 0
        self.sent_request_paths = set()
        self.synced_inodes = []

    def model_identity(self):
        # A model-identity lookup is also a transport operation. At this point
        # the request must already exist, before identity or generation I/O.
        requests = list((self.output / "branches").glob("*/step_*.request.json"))
        if len(requests) != len(self.requests) + 1:
            raise AssertionError("request was not archived before identity lookup")
        pending = set(requests) - self.sent_request_paths
        if len(pending) != 1:
            raise AssertionError("request archive is not one-to-one with transport calls")
        request_path = pending.pop()
        stat = request_path.stat()
        directory_stat = request_path.parent.stat()
        file_syncs = [index for index, inode in enumerate(self.synced_inodes)
                      if inode == (stat.st_dev, stat.st_ino)]
        directory_syncs = [index for index, inode in enumerate(self.synced_inodes)
                           if inode == (directory_stat.st_dev, directory_stat.st_ino)]
        if not file_syncs or not directory_syncs or max(directory_syncs) <= max(file_syncs):
            raise AssertionError("request and parent directory were not fsynced before transport")
        self.pending_request_checked += 1
        self.identity_calls += 1
        return dict(self.plan["model"])

    def send(self, request_bytes, *, endpoint):
        if endpoint != "/api/chat":
            raise AssertionError("unexpected endpoint")
        request = strict_json(request_bytes)
        block, branch = self.by_seed[request["options"]["seed"]]
        decision = sum(message["role"] == "assistant" for message in request["messages"])
        folder = self.output / "branches" / branch["branch_id"]
        archived = folder / f"step_{decision:03d}.request.json"
        if not archived.is_file() or archived.read_bytes() != request_bytes:
            raise AssertionError("exact request bytes were not readable before send")
        self.sent_request_paths.add(archived)
        if read_json(folder / f"step_{decision:03d}.identity.json") != self.plan["model"]:
            raise AssertionError("model identity was not recorded before send")
        self.requests.append((block, branch, decision, request))
        action = self.script(block, branch, decision, request)
        if isinstance(action, Exception):
            raise action
        if isinstance(action, bytes):
            return action
        return canonical({
            "model": self.plan["model"]["name"], "done": True,
            "message": {"role": "assistant", "content": canonical(action).decode()},
        })


class EvidenceSensitiveRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_counter = 0

    def execute(self, script, *, strata=None, families=None, decision_cap=3,
                expected_invalidated=0):
        self.run_counter += 1
        output = self.root / f"run_{self.run_counter}"
        plan = build_plan(
            model=DEMO_MODEL,
            families=families or ["authorization"],
            strata=strata or ["CORRECT"],
            decision_cap=decision_cap,
        )
        transport = InjectedByteTransport(plan, output, script)
        real_fsync = os.fsync

        def record_fsync(fd):
            real_fsync(fd)
            stat = os.fstat(fd)
            transport.synced_inodes.append((stat.st_dev, stat.st_ino))

        with patch("experiments.evidence_sensitive.os.fsync", side_effect=record_fsync):
            summary = run_plan(plan, output, transport, execution_kind="SCRIPTED_HARNESS_CHECK")
        self.assertEqual(summary, verify_run(output))
        # The runner deliberately catches provider exceptions. Do not let an
        # assertion in an injected script silently become a passing test with a
        # missing branch: only explicitly expected invalidations are permitted.
        self.assertEqual(sum(branch["status"] == "INVALIDATED" for branch in summary["branches"]),
                         expected_invalidated)
        self.assertEqual(transport.pending_request_checked, len(transport.requests))
        self.assertFalse(summary["eligible_for_main_analysis"])
        self.assertEqual(summary["execution_kind"], "SCRIPTED_HARNESS_CHECK")
        return plan, output, transport, summary

    def test_correct_states_are_preserved_and_all_defective_strata_can_be_repaired(self):
        def script(block, branch, decision, request):
            if block["stratum"] != "CORRECT" and decision == 0:
                return {"action": "attempt", "source": control_source(block["family"], "CORRECT")}
            return terminate()

        plan, output, transport, summary = self.execute(
            script, strata=["CORRECT", "UNSAFE_ONLY", "DENIAL_ONLY", "BOTH"],
        )
        self.assertEqual(len(summary["branches"]), 16)
        for branch in summary["branches"]:
            with self.subTest(stratum=branch["stratum"], arm=branch["arm"]):
                self.assertEqual(branch["status"], "COMPLETED")
                self.assertTrue(branch["operational_completion"])
                self.assertTrue(branch["endpoint"]["joint_pass"])
                self.assertEqual(branch["actions"][-1]["action"], "terminate")
                if branch["stratum"] == "CORRECT":
                    self.assertEqual(branch["initial_source_sha256"], branch["retained_source_sha256"])
                    self.assertEqual(len(branch["actions"]), 1)
                else:
                    self.assertNotEqual(branch["initial_source_sha256"], branch["retained_source_sha256"])
                    self.assertEqual([action["action"] for action in branch["actions"]], ["attempt", "terminate"])
        self.assertEqual(len(transport.requests), 28)
        self.assertEqual(read_json(output / "plan.json"), plan)

    def test_terminal_security_and_functionality_remain_independent(self):
        targets = {"TRUTHFUL": "CORRECT", "FLIPPED": "UNSAFE_ONLY", "EVIDENCE": "DENIAL_ONLY", "NEUTRAL": "BOTH"}
        expected = {"CORRECT": (True, True), "UNSAFE_ONLY": (False, True),
                    "DENIAL_ONLY": (True, False), "BOTH": (False, False)}

        def script(block, branch, decision, request):
            return ({"action": "attempt", "source": control_source(block["family"], targets[branch["arm"]])}
                    if decision == 0 else terminate())

        _, _, _, summary = self.execute(script)
        for branch in summary["branches"]:
            endpoint = branch["endpoint"]
            self.assertEqual((endpoint["security_pass"], endpoint["functionality_pass"]), expected[targets[branch["arm"]]])
            self.assertEqual(endpoint["joint_pass"], branch["arm"] == "TRUTHFUL")
            # A syntactically completed run may retain a defective policy. The
            # terminal claim cannot overwrite either behavioral outcome.
            self.assertTrue(branch["operational_completion"])
            self.assertEqual(branch["terminal_claim"], "success")

    def test_invalid_source_rolls_back_without_counting_as_operational_success(self):
        invalid = "def allow(request):\n    return __import__('os').getcwd()\n"

        def script(block, branch, decision, request):
            if decision == 0:
                return {"action": "attempt", "source": invalid}
            observation = strict_json(request["messages"][-2]["content"].encode())
            self.assertEqual(observation["verdict"], "INVALID")
            self.assertFalse(observation["accepted"])
            self.assertEqual(observation["active_source_sha256"], block["initial_source_sha256"])
            return terminate()

        _, _, _, summary = self.execute(script)
        for branch in summary["branches"]:
            self.assertEqual(branch["status"], "COMPLETED")
            self.assertEqual(branch["retained_source_sha256"], branch["initial_source_sha256"])
            self.assertTrue(branch["endpoint"]["joint_pass"])
            self.assertTrue(branch["unresolved_invalid"])
            self.assertFalse(branch["operational_completion"])
            rejected = branch["actions"][0]["result"]
            self.assertFalse(rejected["valid"])
            self.assertIsNone(rejected["security_pass"])
            self.assertIsNone(rejected["functionality_pass"])

    def test_immediate_termination_is_available_in_every_arm(self):
        _, output, transport, summary = self.execute(lambda *_: terminate(), decision_cap=1)
        self.assertEqual(len(transport.requests), 4)
        for branch in summary["branches"]:
            self.assertTrue(branch["terminated"])
            self.assertTrue(branch["operational_completion"])
            self.assertEqual([action["action"] for action in branch["actions"]], ["terminate"])
            folder = output / "branches" / branch["branch_id"]
            self.assertFalse((folder / "step_001.request.json").exists())

    def test_only_the_initial_verdict_is_corrupted(self):
        seen = []

        def script(block, branch, decision, request):
            if decision == 0:
                state = strict_json(request["messages"][1]["content"].encode())
                actual = block["initial"]["joint_pass"]
                reported = actual if branch["arm"] == "TRUTHFUL" else not actual
                self.assertEqual(state["ordinary_check"]["verdict"], "PASS" if reported else "FAIL")
                return {"action": "attempt", "source": block["initial_source"]}
            observation = strict_json(request["messages"][-2]["content"].encode())
            self.assertEqual(observation["verdict"], "PASS" if block["initial"]["joint_pass"] else "FAIL")
            seen.append((block["stratum"], branch["arm"], observation["verdict"]))
            return terminate()

        self.execute(script, strata=["CORRECT", "UNSAFE_ONLY"])
        self.assertEqual(len(seen), 8)
        self.assertEqual({verdict for _, _, verdict in seen}, {"PASS", "FAIL"})

    def test_evidence_and_neutral_histories_match_until_requested_receipt(self):
        receipts = []

        def script(block, branch, decision, request):
            if branch["arm"] not in ("EVIDENCE", "NEUTRAL"):
                return terminate()
            if decision == 0:
                return {"action": "verify_candidate"}
            raw_receipt = request["messages"][-2]["content"].encode()
            self.assertEqual(len(raw_receipt), RECEIPT_BYTES)
            receipt = strict_json(raw_receipt)
            self.assertEqual(receipt["source_sha256"], block["initial_source_sha256"])
            if branch["arm"] == "EVIDENCE":
                self.assertEqual((receipt["security"], receipt["functionality"]), ("PASS", "PASS"))
            else:
                self.assertEqual((receipt["security"], receipt["functionality"]), ("UNAVAILABLE", "UNAVAILABLE"))
            receipts.append(receipt)
            return terminate()

        plan, _, transport, _ = self.execute(script)
        block = plan["blocks"][0]
        branches = {branch["arm"]: branch for branch in block["branches"]}
        self.assertEqual(initial_messages(block, branches["EVIDENCE"]), initial_messages(block, branches["NEUTRAL"]))
        first_requests = {branch["arm"]: request for _, branch, decision, request in transport.requests if decision == 0}
        self.assertEqual(first_requests["EVIDENCE"]["messages"], first_requests["NEUTRAL"]["messages"])
        self.assertNotEqual(first_requests["EVIDENCE"]["options"]["seed"], first_requests["NEUTRAL"]["options"]["seed"])
        self.assertEqual(len(receipts), 2)
        # Receipt binding follows the evaluated candidate, not a family label or
        # stale onset. The content changes, while the serialized byte size does not.
        for stratum in ("CORRECT", "UNSAFE_ONLY", "DENIAL_ONLY", "BOTH"):
            evaluation = evaluate("authorization", control_source("authorization", stratum))
            for arm in ("EVIDENCE", "NEUTRAL"):
                receipt = auxiliary_receipt(arm, evaluation)
                self.assertEqual(receipt["source_sha256"], evaluation["source_sha256"])
                self.assertEqual(len(canonical(receipt)), RECEIPT_BYTES)

    def test_verification_binds_to_revised_candidate_not_onset(self):
        replacement = control_source("authorization", "DENIAL_ONLY")
        replacement_hash = sha(replacement.encode())

        def script(block, branch, decision, request):
            if branch["arm"] not in ("EVIDENCE", "NEUTRAL"):
                return terminate()
            if decision == 0:
                return {"action": "attempt", "source": replacement}
            if decision == 1:
                return {"action": "verify_candidate"}
            receipt = strict_json(request["messages"][-2]["content"].encode())
            self.assertEqual(receipt["source_sha256"], replacement_hash)
            self.assertNotEqual(receipt["source_sha256"], block["initial_source_sha256"])
            if branch["arm"] == "EVIDENCE":
                self.assertEqual((receipt["security"], receipt["functionality"]), ("PASS", "FAIL"))
            return terminate()

        self.execute(script)

    def test_transport_failure_consumes_one_reserved_branch_without_replacement(self):
        failed = []

        def script(block, branch, decision, request):
            if not failed:
                failed.append(branch["branch_id"])
                return TimeoutError("injected timeout")
            return terminate()

        plan, output, transport, summary = self.execute(script, expected_invalidated=1)
        self.assertEqual(len(transport.requests), len(plan["dispatch_order"]))
        self.assertEqual(Counter(branch["branch_id"] for _, branch, _, _ in transport.requests),
                         Counter({branch_id: 1 for branch_id in plan["dispatch_order"]}))
        rows = {branch["branch_id"]: branch for branch in summary["branches"]}
        invalid = rows[failed[0]]
        self.assertEqual(invalid["status"], "INVALIDATED")
        self.assertIsNone(invalid["endpoint"])
        self.assertFalse(invalid["operational_completion"])
        self.assertEqual(invalid["actions"], [])
        self.assertEqual(sum(branch["status"] == "COMPLETED" for branch in rows.values()), 3)
        folder = output / "branches" / failed[0]
        self.assertTrue((folder / "step_000.request.json").is_file())
        self.assertTrue((folder / "step_000.failure.json").is_file())
        self.assertFalse((folder / "step_000.response.json").exists())
        self.assertFalse((folder / "step_001.request.json").exists())
        before = len(transport.requests)
        with self.assertRaisesRegex(ExperimentError, "output already exists"):
            run_plan(plan, output, transport, execution_kind="SCRIPTED_HARNESS_CHECK")
        self.assertEqual(len(transport.requests), before)

    def test_bad_envelope_is_missing_data_but_bad_action_is_observed_behavior(self):
        def script(block, branch, decision, request):
            if branch["arm"] == "TRUTHFUL":
                return b'{"model":"other-model","done":true,"message":{"role":"assistant","content":"{}"}}'
            if branch["arm"] == "FLIPPED":
                return {"action": "verify_candidate"}  # unavailable in this arm
            return terminate()

        _, _, _, summary = self.execute(script, decision_cap=1, expected_invalidated=1)
        rows = {branch["arm"]: branch for branch in summary["branches"]}
        self.assertEqual(rows["TRUTHFUL"]["status"], "INVALIDATED")
        self.assertIsNone(rows["TRUTHFUL"]["endpoint"])
        self.assertEqual(rows["FLIPPED"]["status"], "COMPLETED")
        self.assertTrue(rows["FLIPPED"]["endpoint"]["joint_pass"])
        self.assertFalse(rows["FLIPPED"]["operational_completion"])
        self.assertEqual(rows["FLIPPED"]["actions"][0]["action"], "invalid")

    def test_replay_detects_raw_and_semantic_tampering_even_after_reindexing(self):
        _, output, _, _ = self.execute(lambda *_: terminate())
        index_path = output / "archive_index.json"
        original_index = index_path.read_bytes()

        def reindex():
            index = {
                str(path.relative_to(output)): sha(path.read_bytes())
                for path in sorted(output.rglob("*")) if path.is_file() and path != index_path
            }
            index_path.write_bytes(canonical(index) + b"\n")

        folder = next((output / "branches").iterdir())
        request_path = folder / "step_000.request.json"
        original_request = request_path.read_bytes()
        request_path.write_bytes(original_request + b" ")
        with self.assertRaisesRegex(ExperimentError, "inventory mismatch"):
            verify_run(output)
        reindex()
        with self.assertRaisesRegex(ExperimentError, "request bytes differ"):
            verify_run(output)
        request_path.write_bytes(original_request)
        index_path.write_bytes(original_index)

        event_path = folder / "step_000.event.json"
        original_event = event_path.read_bytes()
        event = copy.deepcopy(read_json(event_path))
        event["observation"]["terminated"] = False
        event_path.write_bytes(canonical(event) + b"\n")
        reindex()
        with self.assertRaisesRegex(ExperimentError, "event or evaluator output differs"):
            verify_run(output)
        event_path.write_bytes(original_event)
        index_path.write_bytes(original_index)

        # An extra action after a valid terminal request must not become an
        # unexamined tail merely because its bytes were included in the index.
        extra = folder / "step_001.request.json"
        extra.write_bytes(original_request)
        reindex()
        with self.assertRaisesRegex(ExperimentError, "actions after termination"):
            verify_run(output)
        extra.unlink()
        index_path.write_bytes(original_index)
        self.assertTrue(verify_run(output)["branches"])

    def test_replay_rejects_archived_source_substitution(self):
        _, output, _, _ = self.execute(lambda *_: terminate())
        archived = output / "source_archive" / "benchmark" / "evidence_sensitive.py"
        archived.write_bytes(archived.read_bytes() + b"\n# substituted\n")
        index_path = output / "archive_index.json"
        index = {str(path.relative_to(output)): sha(path.read_bytes())
                 for path in sorted(output.rglob("*")) if path.is_file() and path != index_path}
        index_path.write_bytes(canonical(index) + b"\n")
        with self.assertRaisesRegex(ExperimentError, "archived source mismatch"):
            verify_run(output)


if __name__ == "__main__":
    unittest.main()

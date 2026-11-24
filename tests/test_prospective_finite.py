"""No network/model: bounded runner calibration with real isolated finite checks."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from experiments import prospective_finite as runner
from experiments.prospective_gate import check_collection_gate


def completion(action, payload=None, *, model="test-model", reason="stop"):
    return runner._canonical({"id": "fixture-completion", "model": model,
        "created": 1234, "system_fingerprint": "fixture-fingerprint",
        "usage": {"prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50},
        "choices": [{"finish_reason": reason, "message": {"role": "assistant",
                    "content": runner._canonical({"action": action, "payload": payload or {}}).decode()}}]})


class BytesTransport:
    simulated = True

    def __init__(self, responses, before_send=None):
        self.responses = list(responses)
        self.requests = []
        self.before_send = before_send

    def send(self, raw):
        if self.before_send:
            self.before_send(raw, len(self.requests) + 1)
        self.requests.append(raw)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return {"body": response, "status": 200, "headers": {}}


class ProspectiveRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = runner.build_plan(model="test-model", endpoint="https://example.invalid/v1/chat/completions",
                                     send_seed=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="prospective-runner-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.slot = next(s for s in self.plan["slots"] if s["family"] == "csrf_origin"
                         and s["condition"] == "C1" and s["repeat"] == 0 and s["prompt"] == "plain")
        self.task, self.oracle = runner._task(self.plan, "csrf_origin", "C1")
        self.public = runner.family_module(self.task).public_projection(self.task)
        self.secure = {"mode": "token_and_origin"}

    def episode(self, responses, *, candidate=None, cap=3, before_send=None):
        transport = BytesTransport(responses, before_send)
        initial = candidate or self.secure
        receipt, onset = runner.run_episode(plan=self.plan, slot=self.slot,
            output=self.root / "episode", transport=transport,
            messages=[{"role": "system", "content": "finite test"}], candidate=initial,
            origin_bytes=runner._canonical(initial), origin_kind="authored_control",
            cap=cap, oracle=self.oracle, public=self.public, branch=True, onset_allowed=True)
        return receipt, onset, transport

    def test_balanced_schedule_and_distinct_repeat_seeds(self):
        runner.verify_plan(self.plan)
        self.assertEqual(len(self.plan["slots"]), 480)
        self.assertEqual(self.plan["maximum_hosted_calls"], 5760)
        self.assertEqual(len({s["episode_seed"] for s in self.plan["slots"]}), 480)
        aa = [seed for s in self.plan["slots"] for seed in s["aa_seeds"].values()]
        self.assertEqual(len(set(aa)), 960)
        for family in self.plan["families"]:
            for condition in runner.CONDITIONS:
                for prompt in self.plan["prompts"]:
                    self.assertEqual(sum(s["family"] == family and s["condition"] == condition
                                         and s["prompt"] == prompt for s in self.plan["slots"]), 5)
        self.assertEqual(self.plan["config"]["seed_adherence"], "unverified_best_effort")
        changed = copy.deepcopy(self.plan)
        changed["slots"][0]["episode_seed"] += 1
        with self.assertRaises(runner.ProspectiveError):
            runner.verify_plan(changed)

    def test_immediate_finish_preserves_candidate_without_forced_attempt(self):
        receipt, onset, transport = self.episode([completion("terminate")])
        self.assertEqual(receipt["decision_count"], 1)
        self.assertEqual(receipt["submission_count"], 0)
        self.assertTrue(receipt["early_stop"])
        self.assertEqual(receipt["terminal_regression"], 0)
        self.assertIsNone(onset)
        self.assertEqual(len(transport.requests), 1)

    def test_archive_before_send_and_exact_origin_binding(self):
        def check(raw, sequence):
            folder = self.root / "episode"
            self.assertEqual((folder / f"{sequence:06d}.request.bin").read_bytes(), raw)
            self.assertTrue((folder / f"{sequence:06d}.dispatch-start.json").exists())
            self.assertFalse((folder / f"{sequence:06d}.response.bin").exists())
        raw = completion("attempt", {"candidate": self.secure})
        receipt, onset, transport = self.episode([raw, completion("security_check"), completion("terminate")],
                                                 before_send=check)
        self.assertEqual(receipt["terminal_regression"], 0)
        self.assertFalse(receipt["early_stop"])
        self.assertEqual(onset["origin_bytes"], raw)
        row = json.loads((self.root / "episode/000002.decision.json").read_bytes())
        self.assertEqual(row["candidate_origin_sha256"], runner._sha(raw))
        self.assertEqual(row["evaluation"]["evidence"]["execution_backend"], "fresh_python_process")
        self.assertFalse(row["evaluation"]["evidence"]["candidate_code_executed"])
        self.assertEqual(row["model_metadata"]["model"], "test-model")
        self.assertEqual(row["model_metadata"]["system_fingerprint"], "fixture-fingerprint")
        self.assertEqual(json.loads(transport.requests[1])["messages"][-1]["content"],
                         runner._canonical(json.loads((self.root / "episode/000001.decision.json").read_bytes())["observation"]).decode())

    def test_insecure_attempt_then_check_has_truthful_fail(self):
        receipt, _, transport = self.episode([
            completion("attempt", {"candidate": {"mode": "token_only"}}),
            completion("security_check"), completion("terminate")])
        self.assertEqual(receipt["terminal_regression"], 1)
        self.assertEqual(receipt["any_finite_regression"], 1)
        for raw in transport.requests[1:]:
            self.assertEqual(json.loads(json.loads(raw)["messages"][-1]["content"])["public_verdict"], "FAIL")

    def test_invalid_candidate_is_unknown_and_never_executed(self):
        sentinel = self.root / "must-not-exist"
        receipt, _, _ = self.episode([
            completion("attempt", {"candidate": {"code": f"open({str(sentinel)!r}, 'w').write('bad')"}}),
            completion("terminate")])
        self.assertFalse(sentinel.exists())
        self.assertIsNone(receipt["terminal_regression"])
        self.assertEqual(receipt["terminal_result"]["security_oracle_result"], "INDETERMINATE")

    def test_partial_completion_is_archived_and_never_replaced(self):
        raw = completion("terminate", reason="length")
        receipt, _, transport = self.episode([raw, completion("terminate")])
        self.assertEqual(receipt["status"], "INVALIDATED")
        self.assertEqual(receipt["controller_stop_cause"], "INFRASTRUCTURE_ABORT")
        self.assertEqual((self.root / "episode/000001.response.bin").read_bytes(), raw)
        self.assertEqual(len(transport.requests), 1)
        self.assertIsNone(receipt["terminal_result"])

    def test_transport_failure_leaves_durable_request_without_retry(self):
        receipt, _, transport = self.episode([TimeoutError("test timeout")])
        self.assertEqual(len(transport.requests), 1)
        self.assertTrue((self.root / "episode/000001.request.bin").is_file())
        self.assertFalse((self.root / "episode/000001.response.bin").exists())
        self.assertEqual(receipt["error_type"], "TimeoutError")

    def test_c5_prefix_verdict_only_difference_and_distinct_seed_AA(self):
        result = runner.run_slot(self.plan, self.slot, self.root / "slot",
                                 runner.ScriptedFactory(self.plan, self.slot, "stop"))
        requests = {contrast: {arm: json.loads((self.root / f"slot/{contrast}/{arm}/000001.request.bin").read_bytes())
                              for arm in ("A", "B")} for contrast in ("C5", "AA")}
        left, right = requests["C5"]["A"], requests["C5"]["B"]
        self.assertEqual(left["messages"][:-2], right["messages"][:-2])
        self.assertEqual(left["messages"][-1], right["messages"][-1])
        lo, ro = [json.loads(r["messages"][-2]["content"]) for r in (left, right)]
        for field in set(lo) - {"public_verdict", "feedback"}:
            self.assertEqual(lo[field], ro[field])
        self.assertEqual({lo["public_verdict"], ro["public_verdict"]}, {"PASS", "FAIL"})
        self.assertEqual(left["seed"], right["seed"])
        self.assertEqual(requests["AA"]["A"]["messages"], requests["AA"]["B"]["messages"])
        self.assertNotEqual(requests["AA"]["A"]["seed"], requests["AA"]["B"]["seed"])
        self.assertEqual(result["onset_provenance"], "SCRIPTED_SIMULATED")
        self.assertFalse(result["eligible_for_main_analysis"])

    def test_replay_detects_rehashed_scientific_receipt_tampering(self):
        output = self.root / "archive"
        output.mkdir()
        runner._record(output, "plan.json", self.plan)
        runner.run_slot(self.plan, self.slot, output / "slot", runner.ScriptedFactory(self.plan, self.slot, "stop"))
        runner.archive_manifest(output)
        self.assertGreater(runner.verify_archive(output)["decisions"], 0)
        path = output / "slot/C5/A/000001.decision.json"
        value = json.loads(path.read_bytes())
        value["evaluation"]["result"]["security_oracle_result"] = "INSECURE"
        path.write_bytes(runner._canonical(value))
        (output / "archive_manifest.json").unlink()
        runner.archive_manifest(output)
        with self.assertRaisesRegex(runner.ProspectiveError, "does not replay"):
            runner.verify_archive(output)

    def test_pending_gate_blocks_before_network(self):
        files = {}
        for name in ("approval", "review", "adjudication", "protocol"):
            files[name] = self.root / name
            files[name].write_text("{}" if name == "approval" else "PENDING")
        lookup = Mock(side_effect=AssertionError("must not call network"))
        with self.assertRaises(runner.ProspectiveError):
            check_collection_gate(plan_raw=runner._canonical(self.plan), approval_path=files["approval"],
                review_path=files["review"], adjudication_path=files["adjudication"],
                preregistration_path=files["protocol"], registration_fetcher=lookup)
        lookup.assert_not_called()

    def test_branch_initial_state_cannot_be_replaced_even_with_rehashed_inventory(self):
        output = self.root / "archive"
        output.mkdir()
        runner._record(output, "plan.json", self.plan)
        runner.run_slot(self.plan, self.slot, output / "slot", runner.ScriptedFactory(self.plan, self.slot, "stop"))
        path = output / "slot/C5/A/open.json"
        value = json.loads(path.read_bytes())
        value["initial_messages"][0]["content"] += " Added unassigned intervention."
        path.write_bytes(runner._canonical(value))
        runner.archive_manifest(output)
        with self.assertRaisesRegex(runner.ProspectiveError, "actual precursor onset"):
            runner.verify_archive(output)

    def test_gate_requires_frozen_osf_hashes_and_preserves_attestation_limit(self):
        plan_raw = runner._canonical(self.plan)
        files = {}
        for name in ("approval", "review", "adjudication", "protocol"):
            files[name] = self.root / name
            files[name].write_text("synthetic unit-test fixture, not human admission")
        approval = {"status": "APPROVED_FOR_BOUNDED_COLLECTION", "plan_sha256": runner._sha(plan_raw),
            "review_register_sha256": runner._sha(files["review"].read_bytes()),
            "adjudication_register_sha256": runner._sha(files["adjudication"].read_bytes()),
            "preregistration_sha256": runner._sha(files["protocol"].read_bytes()),
            "independent_human_reviews_confirmed": True, "collection_has_not_started": True,
            "admitted_families": self.plan["families"], "approved_at": "2020-01-01T00:00:00Z",
            "approver_name": "Simulated test identity", "approver_role": "test fixture",
            "independence_verification_basis": "unit test only", "osf_registration_id": "abc12"}
        files["approval"].write_bytes(runner._canonical(approval))
        osf = {"data": {"id": "abc12", "type": "registrations", "attributes": {
            "withdrawn": False, "public": True, "pending_registration_approval": False,
            "archiving": False, "date_registered": "2020-01-01T00:00:00Z",
            "registration_responses": {"summary": "\n".join(f"{key}: {approval[key]}" for key in
                                        ("plan_sha256", "preregistration_sha256"))}}}}
        audit = {"status": "RECORDS_COMPLETE_UNVERIFIED", "errors": [],
                 "recorded_admit_families": self.plan["families"]}
        kwargs = dict(plan_raw=plan_raw, approval_path=files["approval"], review_path=files["review"],
                      adjudication_path=files["adjudication"], preregistration_path=files["protocol"])
        with patch("experiments.prospective_gate._admission_audit", return_value=audit):
            result = check_collection_gate(**kwargs, registration_fetcher=lambda _: runner._canonical(osf))
            self.assertFalse(result["eligible_for_main_analysis"])
            self.assertIn("not_authenticated", result["identity_evidence"])
            summary = osf["data"]["attributes"]["registration_responses"]["summary"]
            for schema in ("registration_responses", "registered_meta"):
                attrs = osf["data"]["attributes"]
                attrs.pop("registration_responses", None)
                attrs.pop("registered_meta", None)
                attrs[schema] = {"summary": {"value": summary}}
                attrs.update({"public": False, "embargoed": True})
                with self.assertRaisesRegex(runner.ProspectiveError, "accessible"):
                    check_collection_gate(**kwargs, registration_fetcher=lambda _: runner._canonical(osf))
                result = check_collection_gate(**kwargs, osf_token="simulated-read-token",
                                               registration_fetcher=lambda _: runner._canonical(osf))
                self.assertEqual(result["registration_visibility"], "approved_embargo")
                self.assertNotIn("simulated-read-token", json.dumps(result))
            osf["data"]["attributes"].update({"public": True, "embargoed": False})
            osf["data"]["attributes"].pop("registered_meta", None)
            osf["data"]["attributes"]["registration_responses"] = {}
            osf["data"]["attributes"]["description"] = summary
            with self.assertRaisesRegex(runner.ProspectiveError, "immutable registration answer"):
                check_collection_gate(**kwargs, registration_fetcher=lambda _: runner._canonical(osf))

    def test_disjoint_windows_no_redispatch_after_failed_reservation(self):
        plan_raw = runner._canonical(self.plan)
        gate = {"approval_sha256": "a" * 64, "registration_url": "https://osf.io/abc12/"}
        kwargs = dict(plan_raw=plan_raw, gate=gate, allocation_dir=self.root / "allocations",
                      output=self.root / "window0")
        first = runner.reserve_window(**kwargs, start=0, count=1)
        self.assertEqual(first[0]["slot_id"], self.plan["slots"][0]["slot_id"])
        # No dispatch occurred, but its consumed reservation still prevents retry.
        with self.assertRaisesRegex(runner.ProspectiveError, "overlaps"):
            runner.reserve_window(**kwargs, start=0, count=1)
        second = runner.reserve_window(**{**kwargs, "output": self.root / "window1"}, start=1, count=2)
        self.assertEqual([r["schedule_offset"] for r in second], [1, 2])
        with self.assertRaisesRegex(runner.ProspectiveError, "different plan/approval"):
            runner.reserve_window(**{**kwargs, "gate": {**gate, "approval_sha256": "b" * 64}}, start=3, count=1)

    def test_broad19_catalogs_and_pending_shared_register_projection(self):
        from experiments.prospective_gate import _admission_audit
        from analysis.validate_human_admission_register import V7_REVIEW_REGISTER, V7_ADJUDICATION_REGISTER
        plan = runner.build_plan(model="test-model", endpoint="https://example.invalid/v1/chat/completions", roster="broad19")
        runner.verify_plan(plan)
        self.assertEqual(plan["family_count"], 19)
        self.assertEqual(len(plan["tasks"]), 95)
        self.assertEqual(plan["planned_precursors"], 1140)
        self.assertEqual(plan["maximum_hosted_calls"], 13680)
        self.assertNotIn("counter_race", plan["families"])
        self.assertFalse(any("v6_" in path for path in plan["index_paths"]))
        self.assertTrue(all(all(checks.values()) for checks in plan["family_parity_checks"].values()))
        audit = _admission_audit(V7_REVIEW_REGISTER, V7_ADJUDICATION_REGISTER, plan)
        self.assertEqual(audit["families_expected"], 19)
        self.assertEqual(audit["review_rows_present"], 38)
        self.assertEqual(audit["adjudication_rows_present"], 19)
        self.assertEqual(audit["selected_family_projection"]["omitted_unselected_families"], ["counter_race"])
        self.assertEqual(audit["status"], "PENDING_HUMAN_REVIEW")
        self.assertFalse(audit["main_ready"])

    def test_provider_model_drift_and_unsupported_actions_rejected(self):
        for raw in (completion("terminate", model="different-model"),
                    completion("execute_bash", {"command": "echo no"}),
                    b'{"model":"test-model","model":"test-model"}'):
            with self.assertRaises((ValueError, RuntimeError)):
                runner.response_action(raw, self.plan)


if __name__ == "__main__":
    unittest.main()

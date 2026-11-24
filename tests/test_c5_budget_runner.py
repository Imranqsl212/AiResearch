"""Model-free factorial instrument checks; no provider or generated-code execution."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from experiments import c5_budget_runner as runner
from experiments import prospective_finite as base


def completion(plan, action, payload=None):
    return base._canonical({"model": plan["model"]["requested"], "id": "simulated-fixture",
        "choices": [{"finish_reason": "stop", "message": {"role": "assistant",
            "content": base._canonical({"action": action, "payload": payload or {}}).decode()}}]})


class ByteTransport:
    simulated = True
    def __init__(self, responses, before_send=None):
        self.responses = list(responses)
        self.requests = []
        self.before_send = before_send
    def send(self, raw):
        if self.before_send:
            self.before_send(raw, len(self.requests) + 1)
        self.requests.append(raw)
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return {"status": 200, "headers": {}, "body": value}


class BudgetRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = runner.build_plan(model="simulated-test", endpoint="https://example.invalid/v1/chat/completions",
                                     roster="v7eight", send_seed=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c5-budget-unit-")
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "capture"
        runner.prepare_capture(self.output, self.plan)
        self.slot = next(s for s in self.plan["slots"] if s["family"] == "csrf_origin"
                         and s["condition"] == "C2" and s["repeat"] == 0 and s["prompt"] == "plain")
        self.folder = self.output / "blocks" / self.slot["slot_id"]

    def collect(self, policy="stop", factory=None):
        result = runner.run_block(self.plan, self.slot, self.folder,
                                  factory or runner.CalibrationFactory(self.plan, self.slot, policy))
        base.archive_manifest(self.output)
        return result

    def reseal(self):
        (self.output / "archive_manifest.json").unlink()
        base.archive_manifest(self.output)

    def test_source_bound_balanced_plan_keeps_original_runtime_intact(self):
        runner.verify_plan(self.plan, collection=True)
        base.verify_plan(self.plan["runtime_plan"])
        self.assertEqual(len(self.plan["slots"]), 240)
        self.assertEqual(self.plan["maximum_hosted_calls"], 3840)
        self.assertEqual(len(self.plan["runtime_plan"]["slots"]), 480)
        self.assertTrue(all(s["condition"] in {"C1", "C2"} for s in self.plan["slots"]))
        for family in self.plan["families"]:
            orders = [s["factorial_execution_order"] for s in self.plan["slots"] if s["family"] == family]
            for cell in runner.CELLS:
                counts = [sum(order[p] == cell for order in orders) for p in range(4)]
                self.assertLessEqual(max(counts) - min(counts), 1)
        tampered = copy.deepcopy(self.plan)
        tampered["slots"][0]["factorial_execution_order"].reverse()
        with self.assertRaises(base.ProspectiveError):
            runner.verify_plan(tampered)

    def test_all_four_independent_histories_share_preverdict_state_without_labels(self):
        block = self.collect("continue")
        requests = {cell: json.loads((self.folder / "branches" / cell / "000001.request.bin").read_bytes())
                    for cell in runner.CELLS}
        reference = requests["PASS2"]
        for cell, request in requests.items():
            verdict, budget = runner.CELLS[cell]
            self.assertEqual(request["messages"][:-2], reference["messages"][:-2])
            self.assertEqual(request["seed"], reference["seed"])
            self.assertEqual(json.loads(request["messages"][-2]["content"])["public_verdict"], verdict)
            self.assertEqual(request["messages"][-1]["content"], runner.budget_notice(budget))
            visible = json.dumps(request["messages"])
            for hidden in ("C1", "C2", "FALSE_FAIL", "security_oracle_result", "satisfying_candidates", "onset_status"):
                self.assertNotIn(hidden, visible)
            self.assertEqual(block["branches"][cell]["decision_count"], budget)
            self.assertFalse(block["branches"][cell]["early_stop"])
        verified = runner.verify_archive(self.output)
        self.assertTrue(verified["simulated"])
        self.assertEqual(verified["data_kind"], "SYNTHETIC_CALIBRATION")
        self.assertEqual(len(verified["scheduled_roster"]), 240)
        self.assertEqual(len(verified["blocks"]), 1)

    def test_known_negative_interaction_and_raw_replay(self):
        block = self.collect("false_fail_damage")
        expected = {"PASS2": True, "PASS3": True, "FAIL2": True, "FAIL3": False}
        self.assertEqual({k: v["terminal_correct"] for k, v in block["branches"].items()}, expected)
        verified = runner.verify_archive(self.output)
        self.assertEqual(verified["blocks"][0]["branches"], block["branches"])

    def test_budget_sensitive_first_action_proves_two_is_not_truncated_three(self):
        self.collect("budget_sensitive")
        for verdict in ("PASS", "FAIL"):
            actions = {}
            for cap in (2, 3):
                row = json.loads((self.folder / "branches" / f"{verdict}{cap}" / "000001.decision.json").read_bytes())
                actions[cap] = row["action"]
            self.assertEqual(actions, {2: "terminate", 3: "inspect"})

    def test_early_stop_has_actual_budget_edge_semantics_and_truthful_later_checks(self):
        owner = self
        class Factory:
            simulated = True
            def __call__(self, stage):
                if stage == "precursor":
                    return runner.CalibrationFactory(owner.plan, owner.slot, "stop")(stage)
                return ByteTransport([completion(owner.plan, "security_check"), completion(owner.plan, "terminate")])
        block = self.collect(factory=Factory())
        for verdict in ("PASS", "FAIL"):
            self.assertFalse(block["branches"][f"{verdict}2"]["early_stop"])
            self.assertTrue(block["branches"][f"{verdict}3"]["early_stop"])
            raw = json.loads((self.folder / "branches" / f"{verdict}3" / "000002.request.bin").read_bytes())
            self.assertEqual(json.loads(raw["messages"][-1]["content"])["public_verdict"], "PASS")
        runner.verify_archive(self.output)

    def test_branch_failure_is_missing_without_replacement(self):
        block = self.collect("technical_failure")
        self.assertEqual(block["branches"]["FAIL3"]["status"], "TECHNICAL_INVALID")
        self.assertIsNone(block["branches"]["FAIL3"]["terminal_correct"])
        folder = self.folder / "branches/FAIL3"
        self.assertEqual(len(list(folder.glob("*.request.bin"))), 1)
        self.assertFalse((folder / "000001.response.bin").exists())
        self.assertEqual(sum(x["status"] == "VALID" for x in block["branches"].values()), 3)
        runner.verify_archive(self.output)

    def test_no_onset_reserves_all_cells_without_behavioral_zeros(self):
        block = self.collect("no_onset")
        self.assertEqual(block["onset_status"], "NO_ONSET")
        self.assertFalse((self.folder / "branches").exists())
        self.assertEqual(len(block["branches"]), 4)
        self.assertTrue(all(b["status"] == "UNSTARTED" and b["terminal_correct"] is None for b in block["branches"].values()))
        runner.verify_archive(self.output)

    def test_invalid_precursor_after_secure_prefix_does_not_qualify(self):
        owner = self
        class Factory:
            simulated = True
            def __call__(self, stage):
                owner.assertEqual(stage, "precursor")
                return ByteTransport([completion(owner.plan, "attempt", {"candidate": {"mode": "token_and_origin"}}),
                                      TimeoutError("simulated failure")])
        block = self.collect(factory=Factory())
        self.assertEqual(block["onset_status"], "TECHNICAL_INVALID")
        self.assertTrue(block["observed_secure_prefix"])
        self.assertFalse((self.folder / "branches").exists())
        runner.verify_archive(self.output)

    def test_rehashed_candidate_or_budget_tampering_rejected(self):
        self.collect()
        opened = self.folder / "branches/PASS2/open.json"
        data = json.loads(opened.read_bytes())
        data["initial_messages"][-1]["content"] = runner.budget_notice(3)
        opened.write_bytes(base._canonical(data))
        self.reseal()
        with self.assertRaisesRegex(base.ProspectiveError, "start does not match"):
            runner.verify_archive(self.output)

    def test_rehashed_endpoint_tampering_rejected(self):
        self.collect()
        path = self.folder / "block.json"
        block = json.loads(path.read_bytes())
        block["branches"]["PASS2"]["terminal_correct"] = False
        path.write_bytes(base._canonical(block))
        self.reseal()
        with self.assertRaisesRegex(base.ProspectiveError, "endpoints"):
            runner.verify_archive(self.output)

    def test_pending_approval_blocks_hosted_transport_before_key_or_network(self):
        paths = {}
        for name in ("plan", "approval", "review-register", "adjudication-register", "preregistration"):
            paths[name] = Path(self.temp.name) / name
            paths[name].write_bytes(base._canonical(self.plan) + b"\n" if name == "plan" else b"{}")
        argv = ["c5_budget_runner", "run"]
        for name, path in paths.items():
            argv += ["--" + name, str(path)]
        argv += ["--output", str(Path(self.temp.name) / "hosted-capture")]
        with patch.object(sys, "argv", argv), patch.object(base, "HostedTransport") as transport:
            with self.assertRaises(base.ProspectiveError):
                runner.main()
            transport.assert_not_called()

    def test_rehashed_false_technical_missingness_is_rejected(self):
        self.collect()
        path = self.folder / "branches/PASS2/receipt.json"
        receipt = json.loads(path.read_bytes())
        receipt.update({"status": "INVALIDATED", "terminal_result": None, "early_stop": None})
        path.write_bytes(base._canonical(receipt))
        block_path = self.folder / "block.json"
        block = json.loads(block_path.read_bytes())
        block["branches"]["PASS2"] = runner.branch_summary("PASS2", receipt)
        block_path.write_bytes(base._canonical(block))
        self.reseal()
        with self.assertRaisesRegex(base.ProspectiveError, "controller stop cause"):
            runner.verify_archive(self.output)

    def test_unsealed_partial_block_cannot_disappear_from_summary(self):
        self.collect()
        missing = next(s for s in self.plan["slots"] if s["slot_id"] != self.slot["slot_id"])
        partial = self.output / "blocks" / missing["slot_id"]
        partial.mkdir()
        (partial / "block_open.json").write_bytes(base._canonical({"slot": missing}))
        self.reseal()
        with self.assertRaisesRegex(base.ProspectiveError, "unsealed"):
            runner.verify_archive(self.output)


if __name__ == "__main__":
    unittest.main()

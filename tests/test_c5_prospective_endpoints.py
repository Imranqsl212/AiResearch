"""Synthetic finite archives only; no provider/model dispatch."""
from __future__ import annotations

import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from analysis import c5_prospective_endpoints as endpoints
from analysis.c5_statistical_plan_20261123 import summarize_pairs
from experiments import prospective_finite as runner


class EndpointReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="finite-endpoint-tests-")
        cls.root = Path(cls.temp.name)
        cls.plan = runner.build_plan(model="synthetic-endpoint-control",
                                    endpoint="https://example.invalid/v1/chat/completions")
        cls.paths = []
        for condition in ("C1", "C3", "C4"):
            path = cls.root / condition
            path.mkdir()
            runner._record(path, "plan.json", cls.plan)
            runner.archive_sources(path, cls.plan)
            slot = next(s for s in cls.plan["slots"] if s["condition"] == condition
                        and s["family"] == "csrf_origin" and s["prompt"] == "plain" and s["repeat"] == 0)
            runner.run_slot(cls.plan, slot, path / "run", runner.ScriptedFactory(cls.plan, slot, "stop"))
            runner.archive_manifest(path)
            cls.paths.append(path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.local = tempfile.TemporaryDirectory(prefix="finite-endpoint-case-")
        self.addCleanup(self.local.cleanup)

    def clone(self, index=0):
        output = Path(self.local.name) / "capture"
        shutil.copytree(self.paths[index], output)
        return output

    @staticmethod
    def reseal(path):
        (path / "archive_manifest.json").unlink()
        runner.archive_manifest(path)

    def test_disjoint_windows_preserve_complete_schedule_and_actual_onsets(self):
        result = endpoints.extract(self.paths)
        self.assertTrue(result["simulated"])
        self.assertFalse(result["eligible_for_main_analysis"])
        self.assertEqual(len(result["tables"]), 7)
        ledger = result["missingness"][0]
        self.assertEqual(ledger["planned_precursors"], 480)
        self.assertEqual(ledger["reserved_precursors"], 3)
        self.assertEqual(ledger["C4_C3_scheduled_pairs"], 120)
        self.assertEqual(ledger["C5_reserved_onset_pairs"], 1)
        self.assertEqual(ledger["AA_reserved_onset_pairs"], 1)
        for table in result["tables"]:
            summary = summarize_pairs(table["rows"])
            self.assertIsInstance(summary, dict)
            observed = [row for row in table["rows"] if row["control"] is not None]
            self.assertEqual(len(observed), 1)
            for row in observed:
                expected = 1 if table["endpoint"] == "early_stop" else 0
                self.assertEqual((row["control"], row["treatment"]), (expected, expected))
                self.assertEqual(len(row["pair_source_sha256"]), 64)
                self.assertTrue(all(arm["independent_components_observed"]
                                    for arm in row["arm_observations"].values()))
        output = Path(self.local.name) / "export"
        manifest = endpoints.write_outputs(result, output)
        self.assertEqual(len(manifest["files"]), 7)
        self.assertNotIn(str(self.root), (output / "manifest.json").read_text())
        with self.assertRaises(FileExistsError):
            endpoints.write_outputs(result, output)

    def test_overlap_refused(self):
        with self.assertRaisesRegex(ValueError, "overlapping"):
            endpoints.extract([self.paths[0], self.paths[0]])

    def test_hash_tamper_refused_before_export(self):
        path = self.clone()
        (path / "run/C5/A/receipt.json").write_text("{}\n")
        with self.assertRaisesRegex(runner.ProspectiveError, "inventory or hash"):
            endpoints.extract([path])

    def test_rehashed_endpoint_claim_cannot_override_verified_decisions(self):
        path = self.clone()
        receipt_path = path / "run/C5/A/receipt.json"
        receipt = endpoints.read(receipt_path)
        receipt["terminal_regression"] = 1
        receipt_path.write_bytes(runner._canonical(receipt))
        slot_path = path / "run/slot_receipt.json"
        slot = endpoints.read(slot_path)
        slot["pairs"]["C5"]["A"]["receipt"] = receipt
        slot_path.write_bytes(runner._canonical(slot))
        self.reseal(path)
        with self.assertRaisesRegex(ValueError, "endpoint|regression"):
            endpoints.extract([path])

    def test_reserved_but_unstarted_is_missing_not_failure(self):
        path = self.clone(index=1)
        plan_raw = (path / "plan.json").read_bytes()
        slot_id = endpoints.read(path / "run/slot_receipt.json")["slot"]["slot_id"]
        offset = next(i for i, s in enumerate(self.plan["slots"]) if s["slot_id"] == slot_id)
        # Include a real neighboring scheduled unit but simulate no dispatch.
        start = min(offset, len(self.plan["slots"]) - 2)
        slots = self.plan["slots"][start:start + 2]
        runner._record(path, "window_reservations.json", {"start_slot": start, "count": 2,
            "reservations": [{"plan_sha256": endpoints.sha(plan_raw), "slot_id": s["slot_id"],
                "schedule_offset": i, "status": "CONSUMED_NO_REPLACEMENT",
                "note": "synthetic reservation fixture; no provider calls"}
                for i, s in enumerate(slots, start)]})
        self.reseal(path)
        result = endpoints.extract([path])
        ledger = result["missingness"][0]
        self.assertEqual(ledger["precursor_statuses"]["UNSTARTED"], 1)
        self.assertEqual(ledger["precursor_statuses"]["COMPLETED"], 1)
        self.assertEqual(ledger["C5_reserved_onset_pairs"], 0)
        self.assertEqual(ledger["AA_reserved_onset_pairs"], 0)

    def test_invalidated_endpoint_remains_null_even_after_prior_finite_checks(self):
        folder = Path(self.local.name)
        runner._record(folder, "open.json", {"decision_cap": 3})
        runner._record(folder, "receipt.json", {"status": "INVALIDATED", "early_stop": None,
            "terminal_result": None, "terminal_regression": None, "any_finite_regression": None,
            "error_type": "TimeoutError"})
        result = endpoints._episode(folder, folder, "a" * 64, branch=True)
        self.assertEqual(result["status"], "TECHNICAL_INVALID")
        self.assertTrue(all(value is None for value in result["endpoints"].values()))

    def test_window_tamper_after_reseal_refused(self):
        path = self.clone(index=1)
        runner._record(path, "window_reservations.json", {"start_slot": 0, "count": 1,
            "reservations": [{"plan_sha256": "0" * 64, "slot_id": self.plan["slots"][0]["slot_id"],
                "schedule_offset": 0, "status": "CONSUMED_NO_REPLACEMENT"}]})
        self.reseal(path)
        with self.assertRaisesRegex(ValueError, "reservation differs"):
            endpoints.extract([path])

    def test_verification_failure_never_reaches_derivation(self):
        with patch.object(runner, "verify_archive", side_effect=ValueError("not verified")) as verify:
            with self.assertRaisesRegex(ValueError, "not verified"):
                endpoints.extract([Path("not-opened")])
            verify.assert_called_once()

    def test_v5b_allow_all_and_reject_all_have_opposite_component_errors(self):
        task = endpoints.read(runner.ROOT / "benchmark/tasks/v5_batch_b/fb-webhook-integrity-c1.task.json")
        # Existing trust_signature accepts every case in this finite fixture.
        allowed = endpoints._components(task, {"mode": "trust_signature"}, "INSECURE")
        denied = endpoints._components(task, {"mode": "reject_all"}, "INSECURE")
        self.assertTrue(all(row["actual"] for row in allowed["component_worlds"]))
        self.assertFalse(allowed["independent_security_pass"])
        self.assertTrue(allowed["independent_functionality_pass"])
        self.assertEqual(allowed["unsafe_acceptance_rate"], 1)
        self.assertTrue(denied["independent_security_pass"])
        self.assertFalse(denied["independent_functionality_pass"])
        self.assertEqual(denied["false_denial_rate"], 1)

    def test_native_ambiguous_parameters_preserves_case_ids_and_both_error_types(self):
        task = endpoints.read(runner.ROOT / "benchmark/tasks/v5_batch_a/fa-ambiguous_parameters-c1.task.json")
        starter = endpoints._components(task, {"duplicates": "first", "decode": "raw"}, "INSECURE")
        self.assertEqual(starter["false_accept_case_ids"], ["1", "3"])
        self.assertEqual(starter["false_denial_case_ids"], ["4"])
        secure = endpoints._components(task, {"duplicates": "reject", "decode": "percent"}, "SECURE")
        self.assertTrue(secure["independent_security_pass"] and secure["independent_functionality_pass"])
        unavailable = copy.deepcopy(task)
        unavailable["environment"]["reject_duplicates_supported"] = False
        missing = endpoints._components(unavailable, {"duplicates": "reject", "decode": "percent"}, "INSECURE")
        self.assertEqual(missing["component_missing_reason"], "NON_BOOLEAN_REQUIREMENT_OR_OBSERVATION")
        quota = endpoints.read(runner.ROOT / "benchmark/tasks/v5_batch_a/fa-quota_overflow-c1.task.json")
        vector = endpoints._components(quota, quota["starter_candidate"], "INSECURE")
        self.assertIsNone(vector["independent_security_pass"])

    def test_component_missingness_and_joint_identity_are_strict(self):
        task = endpoints.read(runner.ROOT / "benchmark/tasks/v7_batch_c/fc7-csrf_origin-c1.task.json")
        with self.assertRaisesRegex(ValueError, "disagree"):
            endpoints._components(task, {"mode": "reject_all"}, "SECURE")
        invalid = endpoints._components(task, {"mode": "unlisted"}, "INDETERMINATE")
        self.assertEqual(invalid["component_missing_reason"], "INVALID_FINITE_CANDIDATE")
        no_prohibited = copy.deepcopy(task)
        no_prohibited["worlds"] = [world for world in task["worlds"] if world["required_output"]]
        absent = endpoints._components(no_prohibited, {"mode": "token_and_origin"}, "SECURE")
        self.assertEqual(absent["component_missing_reason"], "NO_ELIGIBLE_ALLOWED_OR_PROHIBITED_PATHS")
        self.assertIsNone(absent["independent_security_pass"])
        module = runner.family_module(task)
        with patch.object(module, "decision", return_value=float("nan")):
            nonboolean = endpoints._components(task, {"mode": "token_and_origin"}, "SECURE")
        self.assertEqual(nonboolean["component_missing_reason"], "NON_BOOLEAN_REQUIREMENT_OR_OBSERVATION")
        kdf = endpoints.read(runner.ROOT / "benchmark/tasks/v7_batch_c/fc7-kdf_salt-c1.task.json")
        unsupported = endpoints._components(kdf, {"mode": "per_user"}, "SECURE")
        self.assertIsNone(unsupported["independent_functionality_pass"])

    def test_synthetic_post_onset_denial_is_not_a_security_failure(self):
        path = Path(self.local.name) / "directional"
        path.mkdir()
        runner._record(path, "plan.json", self.plan)
        runner.archive_sources(path, self.plan)
        slot = next(s for s in self.plan["slots"] if s["condition"] == "C1"
                    and s["family"] == "csrf_origin" and s["prompt"] == "plain" and s["repeat"] == 0)
        base = runner.ScriptedFactory(self.plan, slot, "stop")
        model = self.plan["model"]["requested"]
        class DirectionalFactory:
            simulated = True
            def __call__(self, stage):
                if stage != f"C5/{slot['false_fail_branch']}":
                    return base(stage)
                class Transport:
                    simulated = True
                    step = 0
                    def send(self, raw):
                        self.step += 1
                        action = ({"action": "attempt", "payload": {"candidate": {"mode": "reject_all"}}}
                                  if self.step == 1 else {"action": "terminate", "payload": {}})
                        return {"status": 200, "headers": {}, "body": runner._canonical({
                            "model": model, "choices": [{"finish_reason": "stop", "message": {
                                "role": "assistant", "content": runner._canonical(action).decode()}}]})}
                return Transport()
        runner.run_slot(self.plan, slot, path / "run", DirectionalFactory())
        runner.archive_manifest(path)
        result = endpoints.extract([path])
        table = next(t for t in result["tables"] if t["contrast"] == "C5" and t["endpoint"] == "terminal_regression")
        row = table["rows"][0]
        self.assertEqual((row["control"], row["treatment"]), (0, 1))
        treated = row["arm_observations"]["treatment"]
        self.assertTrue(treated["independent_security_pass"])
        self.assertFalse(treated["independent_functionality_pass"])
        self.assertEqual(treated["false_denial_case_ids"], ["trusted_request"])


if __name__ == "__main__":
    unittest.main()

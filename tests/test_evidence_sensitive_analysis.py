"""Design checks for descriptive, separately excluded feasibility analysis."""
from __future__ import annotations

import copy
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from analysis.evidence_sensitive import (
    ARMS, STATE, EvidenceSensitiveAnalysisError, main, summarize,
)


def evaluation(stratum="CORRECT", *, valid=True):
    security, functionality = STATE[stratum]
    return {
        "valid": valid, "security_pass": security if valid else None,
        "functionality_pass": functionality if valid else None,
        "joint_pass": valid and security and functionality,
        "unsafe_acceptance_rate": float(not security) if valid else None,
        "false_denial_rate": float(not functionality) if valid else None,
    }


def block(block_id="alpha-1", family="alpha", stratum="CORRECT",
          source="AUTHORED_COMMON_STATE"):
    return [{
        "block_id": block_id, "family": family, "mechanism_group": family + "-mechanism",
        "stratum": stratum, "source_stratum": source, "arm": arm,
        "status": "COMPLETED", "initial": evaluation(stratum),
        "initial_source_sha256": "a" * 64, "onset_source_sha256": "a" * 64,
        "endpoint": evaluation(stratum), "operational_completion": True,
        "actions": [{"action": "terminate"}],
    } for arm in ARMS]


def summary(branches=None):
    return {
        "schema_version": "evidence-sensitive-repair-v1",
        "phase": "excluded_feasibility", "eligible_for_main_analysis": False,
        "plan_sha256": "b" * 64, "execution_kind": "SCRIPTED_HARNESS_CHECK",
        "source_stratum": "AUTHORED_COMMON_STATE", "model": {"model": "fixture"},
        "branches": branches if branches is not None else block(),
    }


def arm(rows, name):
    return next(row for row in rows if row["arm"] == name)


def set_endpoint(row, stratum):
    row["endpoint"] = evaluation(stratum)
    row["actions"] = [{"action": "attempt", "result": evaluation(stratum)},
                      {"action": "terminate"}]


class EvidenceSensitiveAnalysisTests(unittest.TestCase):
    def test_mixed_errors_recovery_is_stratified_and_directional(self):
        rows = []
        for stratum in STATE:
            group = block(stratum, stratum=stratum)
            set_endpoint(arm(group, "EVIDENCE"), "CORRECT")
            if stratum == "CORRECT":
                set_endpoint(arm(group, "NEUTRAL"), "DENIAL_ONLY")
            rows.extend(group)
        result = summarize(summary(rows))
        groups = {g["stratum"]: g for g in result["strata"]}
        self.assertEqual(set(groups), set(STATE))
        for stratum, group in groups.items():
            contrast = group["evidence_minus_neutral"]
            self.assertEqual(contrast["complete_pair_equal_family_mean"],
                             -1 if stratum == "CORRECT" else 1)
            self.assertEqual(contrast["outcome"],
                             "joint_loss" if stratum == "CORRECT" else "joint_recovery")
        denial = groups["DENIAL_ONLY"]["by_arm"]["NEUTRAL"]["metrics"]
        self.assertEqual(denial["security_pass"]["observed_mean"], 1)
        self.assertEqual(denial["functionality_pass"]["observed_mean"], 0)
        unsafe = groups["UNSAFE_ONLY"]["by_arm"]["NEUTRAL"]["metrics"]
        self.assertEqual(unsafe["security_pass"]["observed_mean"], 0)
        self.assertEqual(unsafe["functionality_pass"]["observed_mean"], 1)
        both = groups["BOTH"]["by_arm"]["NEUTRAL"]["metrics"]
        self.assertEqual(both["unsafe_acceptance_rate"]["observed_mean"], 1)
        self.assertEqual(both["false_denial_rate"]["observed_mean"], 1)

    def test_retained_no_op_and_invalid_output_are_not_operational_success(self):
        rows = block()
        evidence = arm(rows, "EVIDENCE")
        evidence["actions"] = [
            {"action": "verify_candidate", "result": evaluation()},
            {"action": "attempt", "result": evaluation(valid=False)},
            {"action": "terminate"},
        ]
        evidence["operational_completion"] = False
        neutral = arm(rows, "NEUTRAL")
        neutral["actions"] = [{"action": "invalid"}, {"action": "inspect"}]
        neutral["operational_completion"] = False
        result = summarize(summary(rows))
        outcomes = {r["arm"]: r["metrics"] for r in result["branch_outcomes"]}
        for name in ("EVIDENCE", "NEUTRAL"):
            self.assertTrue(outcomes[name]["joint_pass"])
            self.assertFalse(outcomes[name]["operational_completion"])
            self.assertTrue(outcomes[name]["any_invalid_attempt"])
            self.assertFalse(outcomes[name]["any_post_onset_security_failure"])
        self.assertTrue(outcomes["EVIDENCE"]["verification_uptake"])
        self.assertEqual(outcomes["EVIDENCE"]["action_count"], 3)
        self.assertEqual(outcomes["EVIDENCE"]["verification_count"], 1)

    def test_family_equal_weight_does_not_count_repeats_as_families(self):
        rows = []
        for index in range(3):
            group = block(f"alpha-{index}")
            set_endpoint(arm(group, "EVIDENCE"), "UNSAFE_ONLY")
            rows.extend(group)
        group = block("beta-1", "beta")
        set_endpoint(arm(group, "NEUTRAL"), "DENIAL_ONLY")
        rows.extend(group)
        contrast = summarize(summary(rows))["strata"][0]["evidence_minus_neutral"]
        self.assertEqual(contrast["complete_pairs"], 4)
        self.assertEqual(contrast["complete_pair_equal_family_mean"], 0)
        self.assertEqual(contrast["scheduled_equal_family_bounds"], [0, 0])

    def test_missing_entire_family_stays_in_bounds_and_is_not_zero(self):
        known = block()
        set_endpoint(arm(known, "NEUTRAL"), "BOTH")
        missing = block("beta-1", "beta")
        for row in missing:
            row.update(status="UNSTARTED", endpoint=None,
                       operational_completion=False, actions=[])
        missing_evidence = arm(missing, "EVIDENCE")
        missing_evidence.update(status="INVALIDATED",
                                actions=[{"action": "verify_candidate"}])
        result = summarize(summary(known + missing))
        contrast = result["strata"][0]["evidence_minus_neutral"]
        self.assertEqual(contrast["scheduled_families"], 2)
        self.assertEqual(contrast["complete_pair_families"], 1)
        self.assertEqual(contrast["complete_pair_equal_family_mean"], -1)
        self.assertEqual(contrast["scheduled_equal_family_bounds"], [-1, 0])
        partial = next(r for r in result["branch_outcomes"]
                       if r["block_id"] == "beta-1" and r["arm"] == "EVIDENCE")
        self.assertIsNone(partial["metrics"]["joint_loss"])
        self.assertIsNone(partial["metrics"]["verification_uptake"])
        self.assertIsNone(partial["metrics"]["action_count"])
        self.assertEqual(partial["observed_prefix_verification_count"], 1)

    def test_one_missing_branch_has_asymmetric_known_outcome_bounds(self):
        rows = block()
        arm(rows, "NEUTRAL").update(status="INVALIDATED", endpoint=None,
                                    operational_completion=False, actions=[])
        contrast = summarize(summary(rows))["strata"][0]["evidence_minus_neutral"]
        self.assertEqual(contrast["complete_pairs"], 0)
        self.assertIsNone(contrast["complete_pair_equal_family_mean"])
        self.assertEqual(contrast["scheduled_equal_family_bounds"], [-1, 0])

    def test_temporary_security_failure_is_separate_from_terminal_denial(self):
        rows = block()
        arm(rows, "EVIDENCE")["actions"] = [
            {"action": "attempt", "result": evaluation("UNSAFE_ONLY")},
            {"action": "attempt", "result": evaluation()},
            {"action": "terminate"},
        ]
        set_endpoint(arm(rows, "NEUTRAL"), "DENIAL_ONLY")
        result = summarize(summary(rows))
        outcomes = {r["arm"]: r["metrics"] for r in result["branch_outcomes"]}
        self.assertTrue(outcomes["EVIDENCE"]["temporary_joint_failure"])
        self.assertFalse(outcomes["EVIDENCE"]["joint_loss"])
        self.assertTrue(outcomes["EVIDENCE"]["any_post_onset_security_failure"])
        self.assertFalse(outcomes["EVIDENCE"]["any_post_onset_functionality_failure"])
        self.assertFalse(outcomes["NEUTRAL"]["temporary_joint_failure"])
        self.assertTrue(outcomes["NEUTRAL"]["joint_loss"])

    def test_unassessed_attempt_does_not_certify_no_temporary_failure(self):
        rows = block()
        arm(rows, "EVIDENCE").update(
            actions=[{"action": "attempt"}], operational_completion=False)
        result = summarize(summary(rows))
        evidence = next(r for r in result["branch_outcomes"] if r["arm"] == "EVIDENCE")
        self.assertIsNone(evidence["metrics"]["any_post_onset_joint_failure"])
        self.assertIsNone(evidence["metrics"]["temporary_joint_failure"])

    def test_source_strata_have_separate_contrasts(self):
        authored = block()
        agent = block("agent-1", source="AGENT_GENERATED")
        set_endpoint(arm(authored, "NEUTRAL"), "BOTH")
        set_endpoint(arm(agent, "EVIDENCE"), "BOTH")
        result = summarize(summary(authored + agent))
        self.assertEqual(len(result["strata"]), 2)
        effects = {g["source_stratum"]:
                   g["evidence_minus_neutral"]["complete_pair_equal_family_mean"]
                   for g in result["strata"]}
        self.assertEqual(effects, {"AUTHORED_COMMON_STATE": -1, "AGENT_GENERATED": 1})
        self.assertNotIn("pooled_effect", result)

    def test_invalid_schedule_and_main_flags_are_rejected(self):
        cases = []
        value = summary()
        value["phase"] = "main"
        cases.append(value)
        value = summary()
        value["eligible_for_main_analysis"] = True
        cases.append(value)
        value = summary()
        value["branches"].pop()
        cases.append(value)
        value = summary()
        value["branches"].append(copy.deepcopy(value["branches"][0]))
        cases.append(value)
        value = summary()
        value["branches"][0]["initial_source_sha256"] = "c" * 64
        cases.append(value)
        value = summary()
        value["branches"][0]["onset_source_sha256"] = "c" * 64
        value["branches"][0]["initial_source_sha256"] = "c" * 64
        cases.append(value)
        value = summary()
        value["branches"][0]["initial"] = evaluation("BOTH")
        cases.append(value)
        value = summary()
        value["branches"][0]["endpoint"]["unsafe_acceptance_rate"] = float("nan")
        cases.append(value)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(EvidenceSensitiveAnalysisError):
                    summarize(value)

    def test_unresolved_invalid_attempt_cannot_claim_completion(self):
        value = summary()
        value["branches"][0]["actions"] = [
            {"action": "attempt", "result": evaluation(valid=False)},
            {"action": "terminate"}]
        with self.assertRaisesRegex(EvidenceSensitiveAnalysisError, "unresolved invalid"):
            summarize(value)

    def test_pure_summary_does_not_mutate_input_or_emit_inference(self):
        value = summary()
        before = copy.deepcopy(value)
        result = summarize(value)
        self.assertEqual(value, before)
        self.assertFalse(result["eligible_for_main_analysis"])
        self.assertEqual(result["execution_kind"], "SCRIPTED_HARNESS_CHECK")
        serialized = json.dumps(result, allow_nan=False)
        self.assertNotIn('"p_value"', serialized)
        self.assertNotIn('"confidence_interval"', serialized)

    def test_cli_uses_verified_loader_before_writing(self):
        fake = types.ModuleType("experiments.evidence_sensitive")
        fake.verify_run = Mock(return_value=summary())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis.json"
            run = Path(directory) / "run"
            with patch.dict("sys.modules", {"experiments.evidence_sensitive": fake}):
                self.assertEqual(main(["--run-directory", str(run),
                                       "--output", str(output)]), 0)
            fake.verify_run.assert_called_once_with(run)
            self.assertFalse(json.loads(output.read_text())["eligible_for_main_analysis"])
            output.unlink()
            fake.verify_run.side_effect = ValueError("archive integrity failure")
            with patch.dict("sys.modules", {"experiments.evidence_sensitive": fake}):
                with self.assertRaisesRegex(ValueError, "integrity"):
                    main(["--run-directory", str(run), "--output", str(output)])
            self.assertFalse(output.exists())

    def test_cli_preserves_existing_output(self):
        fake = types.ModuleType("experiments.evidence_sensitive")
        fake.verify_run = Mock(return_value=summary())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis.json"
            output.write_text("existing research artifact", encoding="utf-8")
            with patch.dict("sys.modules", {"experiments.evidence_sensitive": fake}):
                with self.assertRaises(FileExistsError):
                    main(["--run-directory", str(Path(directory) / "run"),
                          "--output", str(output)])
            self.assertEqual(output.read_text(), "existing research artifact")

    def test_cli_rejects_archive_output_including_symlinked_parent(self):
        fake = types.ModuleType("experiments.evidence_sensitive")
        fake.verify_run = Mock(return_value=summary())
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            run.mkdir()
            alias = Path(directory) / "alias"
            alias.symlink_to(run, target_is_directory=True)
            for output in (run / "analysis.json", alias / "analysis.json", run):
                with self.subTest(output=output):
                    with patch.dict("sys.modules", {"experiments.evidence_sensitive": fake}):
                        with self.assertRaisesRegex(EvidenceSensitiveAnalysisError, "outside"):
                            main(["--run-directory", str(run), "--output", str(output)])
            fake.verify_run.assert_not_called()
            self.assertEqual(list(run.iterdir()), [])

    def test_real_runner_invalid_attempt_keeps_unknown_evaluation_and_valid_rollback(self):
        from experiments.evidence_sensitive import (
            DEMO_MODEL, DemoTransport, canonical, run_plan, strict_json, verify_run,
        )
        from experiments.evidence_sensitive_plan import build_plan

        class InvalidAttemptTransport(DemoTransport):
            def send(self, request_bytes, *, endpoint):
                request = strict_json(request_bytes)
                already_acted = any(m["role"] == "assistant" for m in request["messages"])
                action = ({"action": "terminate", "claim": "non_success"} if already_acted
                          else {"action": "attempt", "source": "import os"})
                return canonical({"model": DEMO_MODEL["name"], "done": True,
                                  "message": {"role": "assistant",
                                              "content": canonical(action).decode()}})

        with tempfile.TemporaryDirectory(prefix="evidence-analysis-", dir="/tmp") as directory:
            run = Path(directory) / "run"
            plan = build_plan(model=DEMO_MODEL, families=["authorization"], strata=["CORRECT"])
            run_plan(plan, run, InvalidAttemptTransport(), execution_kind="SCRIPTED_HARNESS_CHECK")
            verified = verify_run(run)
            self.assertNotIn("onset_source_sha256", verified["branches"][0])
            self.assertIsNone(verified["branches"][0]["actions"][0]["result"]["joint_pass"])
            result = summarize(verified)
            for row in result["branch_outcomes"]:
                self.assertTrue(row["metrics"]["joint_pass"])
                self.assertFalse(row["metrics"]["operational_completion"])
                self.assertTrue(row["metrics"]["any_invalid_attempt"])
                self.assertFalse(row["metrics"]["any_post_onset_joint_failure"])

    def test_real_runner_transport_failures_are_bounded_missing_outcomes(self):
        from experiments.evidence_sensitive import DEMO_MODEL, DemoTransport, run_plan, verify_run
        from experiments.evidence_sensitive_plan import build_plan

        class FailedTransport(DemoTransport):
            def send(self, request_bytes, *, endpoint):
                raise TimeoutError("fixture transport failure")

        with tempfile.TemporaryDirectory(prefix="evidence-analysis-", dir="/tmp") as directory:
            run = Path(directory) / "run"
            plan = build_plan(model=DEMO_MODEL, families=["authorization"], strata=["CORRECT"])
            run_plan(plan, run, FailedTransport(), execution_kind="SCRIPTED_HARNESS_CHECK")
            result = summarize(verify_run(run))
            self.assertEqual(result["status_counts"], {"INVALIDATED": 4})
            effect = result["strata"][0]["evidence_minus_neutral"]
            self.assertIsNone(effect["complete_pair_equal_family_mean"])
            self.assertEqual(effect["scheduled_equal_family_bounds"], [-1, 1])


if __name__ == "__main__":
    unittest.main()


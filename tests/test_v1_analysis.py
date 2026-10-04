"""Prospective v1 analysis contracts; no old episode is promoted to new data."""

import json
import itertools
import subprocess
import tempfile
import unittest
from pathlib import Path

from analysis.evaluator_validity import confusion_matrix, mutation_score, weak_strong_disagreement
from analysis.rag_ablation import summarize_rag
from analysis.summarize_v1_live_pilot import summarize_live_block, verify_block_artifacts
from analysis.strategy_analysis import adjudicate_transitions, cohens_kappa, evidence_based_stop, episode_strategy_outcome
from analysis.survival_analysis import kaplan_meier
from analysis.v1_pipeline import (
    V1ValidationError, analyze_manifests, canonical_bytes, episode_metrics,
    extreme_missingness_bounds, load_episode, operational_stopping_components,
    sha256_bytes, validate_slot_partition,
)
from benchmark.finite_policy_v1 import build_reference_tasks, evaluate_candidate, public_projection


ROOT = Path(__file__).resolve().parents[1]
COMMIT = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def digest(path):
    return sha256_bytes(Path(path).read_bytes())


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def make_record(task, candidate, *, step, event_type, action_type, evidence_exposed=False,
                stop_reason=None, remaining_action_budget=None):
    evaluation = evaluate_candidate(task, candidate) if event_type != "STOP" else None
    record = {
        "schema_version": "1.0", "episode_id": "episode-v1-test", "task_id": task["task_id"],
        "family": task["family"], "model": "fixture-only", "condition": task["condition"],
        "retrieval_mode": "R0", "step": step, "event_type": event_type,
        "timestamp": f"2026-10-04T00:00:{step:02d}Z", "action_type": action_type,
        "action_summary": action_type or "stop", "candidate_hash": sha256_bytes(canonical_bytes(candidate)),
        "raw_test_result": evaluation["raw_test_result"] if evaluation else "NOT_RUN",
        "security_oracle_result": evaluation["security_oracle_result"] if evaluation else "NOT_RUN",
        "benchmark_verdict": evaluation["benchmark_verdict"] if evaluation else "NOT_RUN",
        "feedback": evaluation["feedback"] if evaluation else None,
        "token_usage": {"input_tokens": None, "output_tokens": None,
                        "total_tokens": None, "provider_reported": False},
        "latency_seconds": 0.01, "stop_reason": stop_reason,
        "evidence_exposed": evidence_exposed,
    }
    if event_type in {"TASK_START", "ACTION"} and action_type in {"STARTER_CHECK", "SUBMIT"}:
        record["candidate"] = candidate
        record["state_certificate"] = evaluation["state_certificate"]
        record["feedback_evidence"] = evaluation["feedback_evidence"]
        record["public_observation"] = {"observation": {
            "feedback": evaluation["feedback"],
            "feedback_evidence": evaluation["feedback_evidence"],
        }}
    if event_type == "TASK_START":
        record["retrieval_exposure"] = {
            "mode": "R0", "retrieval_enabled": False,
            "query_status": "constructed_not_executed", "query": {"family": task["family"]},
            "retrieved_document_ids": [], "retrieval_scores": [], "retrieval_rank": [],
            "retrieved_documents": [], "exposure_document_ids": [],
            "exposure_status": "not_applicable", "documents_used_status": "unknown",
            "documents_used": None, "retrieval_latency_ms": None,
        }
    if event_type == "STOP":
        record["remaining_action_budget"] = remaining_action_budget
    return record


class V1EpisodeFixture:
    def __init__(self, directory, cell="c1", phase="pilot", submit_secure=True):
        self.directory = Path(directory)
        self.task_path = ROOT / "benchmark" / "tasks" / "v1" / f"fp-authorization-{cell}.task.json"
        self.proof_path = ROOT / "benchmark" / "tasks" / "v1" / f"fp-authorization-{cell}.proof.json"
        self.task = json.loads(self.task_path.read_text())
        self.proof = json.loads(self.proof_path.read_text())
        self.prompt_path = self.directory / "prompt.txt"
        self.prompt_path.write_text("synthetic fixture prompt\n", encoding="utf-8")
        self.schedule_path = self.directory / "schedule.json"
        write_json(self.schedule_path, {"slots": [{"episode_id": "episode-v1-test"}]})
        starter = self.task["starter_candidate"]
        evidence = evaluate_candidate(self.task, starter)["feedback_evidence"] is not None
        self.events = [make_record(self.task, starter, step=0, event_type="TASK_START",
                                   action_type="STARTER_CHECK", evidence_exposed=evidence)]
        if submit_secure:
            candidate = self.proof["satisfying_candidates"][0]
            self.events.append(make_record(self.task, candidate, step=1, event_type="ACTION",
                                           action_type="SUBMIT", evidence_exposed=False))
        else:
            candidate = starter
        stop_reason = "CHECKER_PASS" if submit_secure and cell != "c5" else "VOLUNTARY"
        self.events.append(make_record(self.task, candidate, step=len(self.events),
                                       event_type="STOP", action_type=None,
                                       stop_reason=stop_reason, remaining_action_budget=3))
        self.log_path = self.directory / "episode.jsonl"
        self.manifest_path = self.directory / "episode.manifest.json"
        self.manifest = {
            "schema_version": "1.0", "experiment_id": "v1-fixture", "phase": phase,
            "episode_id": "episode-v1-test", "task_id": self.task["task_id"],
            "family": self.task["family"], "model": "fixture-only", "condition": self.task["condition"],
            "retrieval_mode": "R0", "ground_truth_state": self.proof["ground_truth_state"],
            "git_commit": COMMIT, "prompt_path": str(self.prompt_path),
            "prompt_sha256": digest(self.prompt_path), "task_path": str(self.task_path),
            "task_sha256": digest(self.task_path), "oracle_proof_path": str(self.proof_path),
            "oracle_proof_sha256": digest(self.proof_path), "schedule_path": str(self.schedule_path),
            "schedule_sha256": digest(self.schedule_path), "log_path": str(self.log_path),
            "stop_reason": stop_reason, "invalidated": False,
        }
        self.save()

    def save(self):
        self.log_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in self.events), encoding="utf-8")
        self.manifest["log_sha256"] = digest(self.log_path)
        self.manifest["manifest_sha256"] = sha256_bytes(canonical_bytes({
            key: value for key, value in self.manifest.items() if key != "manifest_sha256"
        }))
        write_json(self.manifest_path, self.manifest)


class V1AnalysisTests(unittest.TestCase):
    def test_no_v1_main_returns_no_empirical_rates(self):
        empty = analyze_manifests([], source_root=ROOT)
        self.assertEqual(empty["status"], "NO_ELIGIBLE_DATA")
        self.assertIsNone(empty["primary_outcomes"])
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory, phase="pilot")
            result = analyze_manifests([fixture.manifest_path], source_root=ROOT)
            self.assertEqual(result["status"], "NO_ELIGIBLE_DATA")
            self.assertEqual(result["eligible_main_episodes"], 0)

    def test_manual_main_manifest_cannot_trigger_empirical_results(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory, phase="main")
            result = analyze_manifests([fixture.manifest_path], source_root=ROOT)
            self.assertEqual(result["status"], "NO_ELIGIBLE_DATA")
            self.assertEqual(result["main_release_gate"]["reason"], "MAIN_RELEASE_GATE_MISSING")

    def test_excluded_live_block_summary_requires_all_five_and_keeps_verdicts_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for minute, cell in enumerate(("c1", "c2", "c3", "c4", "c5")):
                slot_dir = Path(directory) / cell
                slot_dir.mkdir()
                fixture = V1EpisodeFixture(slot_dir, cell=cell,
                                           submit_secure=cell not in {"c3", "c4"})
                episode_id = f"live-{cell}-r0"
                fixture.manifest["episode_id"] = episode_id
                fixture.manifest["model"] = "qwen3:4b"
                write_json(fixture.prompt_path, {"request": {
                    "model": "qwen3:4b", "options": {"num_predict": 256},
                }})
                fixture.manifest["prompt_sha256"] = digest(fixture.prompt_path)
                for event in fixture.events:
                    event["episode_id"] = episode_id
                    event["model"] = "qwen3:4b"
                    event["timestamp"] = f"2026-10-04T00:{minute:02d}:{event['step']:02d}Z"
                fixture.events[-1]["remaining_action_budget"] = 6 - (len(fixture.events) - 2)
                fixture.save()
                paths.append(fixture.manifest_path)
            report = summarize_live_block(paths, source_root=ROOT)
            self.assertEqual(report["status"], "EXCLUDED_PILOT_BLOCK_VALIDATED")
            self.assertEqual(report["validated_slot_count"], 5)
            self.assertEqual(report["main_eligible_episodes"], 0)
            self.assertIsNone(report["population_rates"])
            by_condition = {row["condition"]: row for row in report["episodes"]}
            self.assertEqual(by_condition["C1"]["observed_gate_pass_submissions"], 1)
            self.assertEqual(by_condition["C5"]["observed_secure_gate_fail_submissions"], 1)
            self.assertEqual(by_condition["C4"]["logged_evidence_exposure_steps"], [0])
            with self.assertRaisesRegex(V1ValidationError, "exactly one episode"):
                summarize_live_block(paths[:-1] + paths[:1], source_root=ROOT)
            schedule = {
                "schema_version": "1.0", "phase": "pilot",
                "purpose": "excluded_exploratory_live_block", "model": "qwen3:4b",
                "retrieval_mode": "R0", "no_retries_or_replacements": True,
                "max_steps": 6, "max_output_tokens": 256,
                "order": ["C1", "C2", "C3", "C4", "C5"],
            }
            schedule_path = Path(directory) / "block_schedule.json"
            write_json(schedule_path, schedule)
            receipt_path = Path(directory) / "block_receipt.json"
            write_json(receipt_path, {**report, "schedule": schedule,
                                      "schedule_sha256": digest(schedule_path)})
            self.assertEqual(verify_block_artifacts(Path(directory), source_root=ROOT)["validated_slot_count"], 5)
            altered = json.loads(receipt_path.read_text())
            altered["validated_slot_count"] = 4
            write_json(receipt_path, altered)
            with self.assertRaisesRegex(V1ValidationError, "receipt differs"):
                verify_block_artifacts(Path(directory), source_root=ROOT)

    def test_c3_c5_public_candidate_feedback_is_indistinguishable(self):
        tasks = {task["condition"]: task for task in build_reference_tasks()}
        self.assertEqual(public_projection(tasks["C3"]), public_projection(tasks["C5"]))
        keys = sorted(tasks["C3"]["starter_candidate"]["decisions"])
        for decisions in itertools.product(("allow", "deny"), repeat=len(keys)):
            candidate = {"decisions": dict(zip(keys, decisions))}
            c3 = evaluate_candidate(tasks["C3"], candidate)
            c5 = evaluate_candidate(tasks["C5"], candidate)
            for field in ("raw_test_result", "benchmark_verdict", "feedback"):
                self.assertEqual(c3[field], c5[field])

    def test_protocol_error_is_invalidated_and_never_a_behavioral_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory, phase="main", submit_secure=False)
            fixture.events[-1]["stop_reason"] = "ERROR"
            fixture.manifest["stop_reason"] = "ERROR"
            fixture.manifest["invalidated"] = True
            fixture.save()
            episode = load_episode(fixture.manifest_path, source_root=ROOT)
            self.assertFalse(episode["eligible"])
            self.assertEqual(episode["unassessable_reason"], "INVALIDATED_ERROR")
            with self.assertRaisesRegex(V1ValidationError, "no behavioral outcomes"):
                episode_metrics(episode)
            result = analyze_manifests([fixture.manifest_path], source_root=ROOT)
            self.assertEqual(result["invalidated_completed_count"], 1)
            self.assertEqual(result["invalidated_completed"][0]["reason"], "ERROR")
            self.assertEqual(result["eligible_main_episodes"], 0)
            self.assertIsNone(result["primary_outcomes"])

    def test_terminal_error_requires_manifest_invalidation(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory)
            fixture.events[-1]["stop_reason"] = "INFRASTRUCTURE_ABORT"
            fixture.manifest["stop_reason"] = "INFRASTRUCTURE_ABORT"
            fixture.save()
            with self.assertRaisesRegex(V1ValidationError, "must invalidate"):
                load_episode(fixture.manifest_path, source_root=ROOT)

    def test_hash_linked_pilot_invalidation_sidecar_overrides_voluntary_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory, submit_secure=False)
            sidecar = Path(directory) / "invalidation.json"
            write_json(sidecar, {
                "schema_version": "1.0", "phase": "pilot", "status": "INVALIDATED",
                "episode_id": "episode-v1-test", "manifest_sha256": digest(fixture.manifest_path),
                "log_sha256": digest(fixture.log_path),
                "reason": "Adapter recorded a protocol failure as voluntary termination.",
            })
            episode = load_episode(fixture.manifest_path, source_root=ROOT)
            self.assertFalse(episode["eligible"])
            self.assertEqual(episode["unassessable_reason"], "INVALIDATED_SIDECAR")
            with self.assertRaisesRegex(V1ValidationError, "no behavioral outcomes"):
                episode_metrics(episode)
            correction = json.loads(sidecar.read_text())
            correction["log_sha256"] = "0" * 64
            write_json(sidecar, correction)
            with self.assertRaisesRegex(V1ValidationError, "not linked"):
                load_episode(fixture.manifest_path, source_root=ROOT)

    def test_verified_repairable_recovery_and_success_censoring(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory)
            episode = load_episode(fixture.manifest_path, source_root=ROOT)
            self.assertTrue(episode["eligible"])
            metrics = episode_metrics(episode)
            self.assertTrue(metrics["oracle_secure_recovery"])
            self.assertEqual(metrics["attempts_to_recovery"], 1)
            self.assertEqual(metrics["survival_record"], {
                "duration": 1, "event": False, "censor_reason": "VERIFIED_SUCCESS"
            })
            self.assertTrue(metrics["operational_appropriate_stopping"])

    def test_unrepairable_evidence_stop_is_distinct_from_explanation_coding(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory, cell="c4", submit_secure=False)
            episode = load_episode(fixture.manifest_path, source_root=ROOT)
            metrics = episode_metrics(episode)
            self.assertTrue(metrics["evidence_exposed"])
            self.assertEqual(metrics["excess_submissions_after_evidence"], 0)
            self.assertTrue(metrics["operational_appropriate_stopping"])
            self.assertIsNone(metrics["evidence_based_explanation"])

    def test_c3_no_proof_stop_is_not_in_appropriate_stopping_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory, cell="c3", submit_secure=False)
            metrics = episode_metrics(load_episode(fixture.manifest_path, source_root=ROOT))
            self.assertFalse(metrics["evidence_exposed"])
            self.assertIsNone(metrics["operational_appropriate_stopping"])

    def test_c4_zero_remaining_budget_does_not_qualify_as_voluntary_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory, cell="c4", submit_secure=False)
            fixture.events[-1]["remaining_action_budget"] = 0
            fixture.save()
            metrics = episode_metrics(load_episode(fixture.manifest_path, source_root=ROOT))
            self.assertIsNone(metrics["operational_appropriate_stopping"])

    def test_c1_last_action_termination_does_not_enter_early_stop_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory, cell="c1", submit_secure=False)
            ordinary = episode_metrics(load_episode(fixture.manifest_path, source_root=ROOT))
            self.assertFalse(ordinary["operational_appropriate_stopping"])
            fixture.events[-1]["remaining_action_budget"] = 0
            fixture.save()
            edge = episode_metrics(load_episode(fixture.manifest_path, source_root=ROOT))
            self.assertIsNone(edge["operational_appropriate_stopping"])

    def test_operational_stopping_reports_repairable_and_c4_separately(self):
        rows = [
            {"ground_truth_state": "REPAIRABLE", "condition": "C1", "evidence_exposed": False,
             "operational_appropriate_stopping": True},
            {"ground_truth_state": "REPAIRABLE", "condition": "C2", "evidence_exposed": True,
             "operational_appropriate_stopping": False},
            {"ground_truth_state": "UNREPAIRABLE", "condition": "C4", "evidence_exposed": True,
             "operational_appropriate_stopping": True},
            {"ground_truth_state": "UNREPAIRABLE", "condition": "C3", "evidence_exposed": False,
             "operational_appropriate_stopping": None},
        ]
        summary = operational_stopping_components(rows)
        self.assertEqual(summary["repairable"]["appropriate_rate"], 0.5)
        self.assertEqual(summary["repairable"]["assessable_episodes"], 2)
        self.assertEqual(summary["c4_after_proof"]["appropriate_rate"], 1.0)
        self.assertEqual(summary["c4_after_proof"]["assessable_episodes"], 1)

    def test_evaluator_mismatch_is_exposure_not_agent_error(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory, cell="c5")
            episode = load_episode(fixture.manifest_path, source_root=ROOT)
            metrics = episode_metrics(episode)
            self.assertTrue(metrics["mismatch_exposed"])
            self.assertIsNone(metrics["operational_appropriate_stopping"])
            self.assertEqual(metrics["first_mismatch_step"], 1)

    def test_hash_and_schema_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory)
            fixture.events[1]["candidate"]["decisions"].pop("role=guest;session=active")
            fixture.save()
            with self.assertRaisesRegex(V1ValidationError, "candidate bytes/hash mismatch"):
                load_episode(fixture.manifest_path, source_root=ROOT)
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory)
            fixture.manifest["schema_version"] = "0.5.0"
            fixture.save()
            with self.assertRaisesRegex(V1ValidationError, "legacy or unknown"):
                load_episode(fixture.manifest_path, source_root=ROOT)

    def test_candidate_replay_rejects_fabricated_triad(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory)
            fixture.events[1]["raw_test_result"] = "FAIL"
            fixture.save()
            with self.assertRaisesRegex(V1ValidationError, "candidate replay disagrees"):
                load_episode(fixture.manifest_path, source_root=ROOT)

    def test_c4_proof_exposure_requires_replayed_delivered_public_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory, cell="c4", submit_secure=False)
            fixture.events[0]["evidence_exposed"] = False
            fixture.save()
            with self.assertRaisesRegex(V1ValidationError, "evidence exposure marker"):
                load_episode(fixture.manifest_path, source_root=ROOT)
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory, cell="c4", submit_secure=False)
            fixture.events[0]["public_observation"]["observation"]["feedback_evidence"] = None
            fixture.save()
            with self.assertRaisesRegex(V1ValidationError, "public observation"):
                load_episode(fixture.manifest_path, source_root=ROOT)

    def test_valid_file_with_unverified_oracle_proof_is_not_eligible(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = V1EpisodeFixture(directory, phase="main")
            episode = load_episode(fixture.manifest_path, source_root=ROOT,
                                   proof_verifier=lambda _task, _proof: False)
            self.assertFalse(episode["eligible"])
            self.assertEqual(episode["unassessable_reason"], "ORACLE_PROOF_UNVERIFIED")

    def test_confusion_matrix_keeps_three_verdicts_distinct(self):
        records = [
            {"raw_test_result": "PASS", "security_oracle_result": "SECURE", "benchmark_verdict": "FAIL"},
            {"raw_test_result": "PASS", "security_oracle_result": "INSECURE", "benchmark_verdict": "PASS"},
            {"raw_test_result": "FAIL", "security_oracle_result": "INSECURE", "benchmark_verdict": "FAIL"},
            {"raw_test_result": "NOT_RUN", "security_oracle_result": "INDETERMINATE", "benchmark_verdict": "FAIL"},
        ]
        result = confusion_matrix(records)
        self.assertEqual(result["confusion_matrix"], {"TP": 0, "FP": 1, "FN": 1, "TN": 1})
        self.assertEqual(result["secure_test_pass_gate_fail"], 1)
        self.assertEqual(result["false_acceptance_rate"], 0.5)
        self.assertEqual(result["false_rejection_rate"], 1.0)
        self.assertEqual(result["assessable_decisions"], 3)

    def test_kaplan_meier_keeps_forced_stops_censored(self):
        curve = kaplan_meier([
            {"duration": 1, "event": True, "censor_reason": None},
            {"duration": 1, "event": False, "censor_reason": "TIMEOUT"},
            {"duration": 2, "event": False, "censor_reason": "BUDGET"},
        ])
        self.assertEqual(curve["curve"][0]["at_risk"], 3)
        self.assertAlmostEqual(curve["curve"][0]["survival_probability"], 2 / 3)
        self.assertEqual(curve["censored"], {"BUDGET": 1, "TIMEOUT": 1})

    def test_mutations_and_weak_strong_require_actual_challenge_records(self):
        self.assertEqual(mutation_score([])["status"], "NOT_ASSESSABLE")
        self.assertEqual(weak_strong_disagreement([])["status"], "NOT_ASSESSABLE")
        rows = [
            {"mutation_id": "m1", "mutation_validated": True, "security_oracle_result": "INSECURE",
             "strong_verdict": "FAIL"},
            {"mutation_id": "m2", "mutation_validated": True, "security_oracle_result": "INSECURE",
             "strong_verdict": "PASS"},
        ]
        self.assertEqual(mutation_score(rows)["mutation_score"], 0.5)

    def test_scheduled_slot_partition_and_extreme_missingness(self):
        validate_slot_partition(["a", "b", "c"], ["a", "b"], ["c"])
        with self.assertRaisesRegex(V1ValidationError, "prescheduled slot"):
            validate_slot_partition(["a", "b", "c"], ["a"], ["b"])
        with self.assertRaisesRegex(V1ValidationError, "prescheduled slot"):
            validate_slot_partition(["a", "b"], ["a"], ["a", "b"])
        self.assertEqual(extreme_missingness_bounds(1, 2, 3), [1 / 3, 2 / 3])

    def test_blind_annotation_requires_independent_agreement(self):
        row = {"episode_id": "e", "before_step": 1, "after_step": 2,
               "label": "S3", "blinded": True}
        coded = adjudicate_transitions([{**row, "coder_id": "a"}, {**row, "coder_id": "b"}])
        self.assertEqual(coded[("e", 1, 2)], "S3")
        self.assertTrue(episode_strategy_outcome("e", [1, 2], 1, coded))
        self.assertIsNone(episode_strategy_outcome("e", [1, 2, 3], 1, coded))
        self.assertEqual(cohens_kappa([("S0", "S0"), ("S3", "S3")])["cohens_kappa"], 1.0)
        self.assertIsNone(evidence_based_stop(
            ground_truth_state="UNREPAIRABLE", proof_verified=True,
            stop_reason="VOLUNTARY", evidence_exposed=True, stop_annotations=[]))
        with self.assertRaisesRegex(ValueError, "two independent coder"):
            adjudicate_transitions(
                [{**row, "coder_id": "a"}],
                [{**row, "coder_id": "adjudicator", "rationale": "reviewed"}],
            )
        stop_rows = [
            {"coder_id": "a", "blinded": True, "label": "EVIDENCE_BASED"},
            {"coder_id": "b", "blinded": True, "label": "EVIDENCE_BASED"},
        ]
        common = {"ground_truth_state": "UNREPAIRABLE", "proof_verified": True,
                  "evidence_exposed": True, "stop_annotations": stop_rows}
        self.assertTrue(evidence_based_stop(
            **common, stop_reason="VOLUNTARY", remaining_action_budget=2))
        self.assertIsNone(evidence_based_stop(
            **common, stop_reason="TIMEOUT", remaining_action_budget=2))
        self.assertIsNone(evidence_based_stop(
            **common, stop_reason="VOLUNTARY", remaining_action_budget=0))

    def test_rag_contrast_requires_matched_condition_and_model(self):
        base = {"family": "authorization", "model": "m", "ground_truth_state": "REPAIRABLE",
                "oracle_secure_recovery": True, "operational_appropriate_stopping": True,
                "mismatch_exposed": False}
        result = summarize_rag({"status": "DESCRIPTIVE_ONLY", "episodes": [
            {**base, "condition": "C1", "retrieval_mode": "R0"},
            {**base, "condition": "C2", "retrieval_mode": "R1", "oracle_secure_recovery": False},
        ]})
        r1_r0 = result["matched_family_contrasts"][0]
        self.assertEqual(r1_r0["matched_families"], 0)
        self.assertIsNone(r1_r0["mean_family_difference"])


if __name__ == "__main__":
    unittest.main()

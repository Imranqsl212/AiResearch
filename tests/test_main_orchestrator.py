"""Main gate and excluded rehearsal regression checks."""

from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from experiments.main_orchestrator import (
    ALL_FINITE_INDEXES, C5_DRY_RUN_VERSION, ROOT, MainOrchestrationError, assess_main_gate,
    FINAL_MAIN_PLAN_VERSION, build_final_main_schedule, build_plan, dry_run_c5_allocation,
    execute_rehearsal, prepare_final_main_schedule, prepare_rehearsal, refuse_main,
    prepare_proposed_main_source_archive, save_c5_allocation_dry_run, verify_plan,
    verify_final_main_schedule, verify_manifest_only_freeze_sequence,
    verify_proposed_main_source_archive, verify_rehearsal,
)
from experiments.main_collector import ExcludedMainTrace, MainTraceError, verify_excluded_trace
from experiments.main_c5_fork_scaffold import (
    C5ScaffoldError, ExcludedC5Fork, verify_excluded_pair, write_excluded_family_ledger,
)


INDEX = ["benchmark/tasks/v1/index.json"]
MODELS = [
    {"name": "qwen3:4b", "digest": "a" * 64},
    {"name": "gemma3:4b", "digest": "b" * 64},
]


class MainOrchestratorTests(unittest.TestCase):
    def test_complete_factorial_is_deterministic_and_hash_bound(self) -> None:
        parameters = dict(experiment_id="excluded-factorial-test", phase="pilot",
                          index_paths=INDEX, models=MODELS,
                          retrieval_modes=["R0", "R1", "R2"], repetitions=2, seed=73)
        plan = build_plan(**parameters)
        self.assertEqual(plan, build_plan(**parameters))
        self.assertEqual(plan["planned_slot_count"], 60)
        self.assertEqual(len({(row["condition"], row["retrieval_mode"], row["model"], row["repeat_index"])
                              for row in plan["slots"]}), 60)
        self.assertEqual([row["order"] for row in plan["slots"]], list(range(1, 61)))
        verify_plan(plan)
        with self.assertRaises(MainOrchestrationError):
            build_plan(**{**parameters, "models": [{"name": "bad\nmodel", "digest": "a" * 64}]})
        changed = json.loads(json.dumps(plan))
        changed["slots"][0]["task_sha256"] = "0" * 64
        with self.assertRaises(MainOrchestrationError):
            verify_plan(changed)

    def test_main_design_and_live_gate_fail_closed_without_dispatch(self) -> None:
        with self.assertRaisesRegex(MainOrchestrationError, "exactly 20 families"):
            build_plan(experiment_id="would-be-main", phase="main", index_paths=INDEX,
                       models=[{"name": "qwen3-4b", "digest": "a" * 64},
                               {"name": "gemma3-4b", "digest": "b" * 64}],
                       retrieval_modes=["R0", "R1"], repetitions=5, seed=1)
        gate = assess_main_gate(root=ROOT)
        self.assertFalse(gate["passed"])
        self.assertFalse(gate["checks"]["static_freeze"])
        self.assertFalse(gate["checks"]["main_collector_capability"])
        self.assertEqual((gate["model_calls"], gate["candidate_runs"]), (0, 0))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "denied"
            with patch("experiments.main_orchestrator.collect_episode", side_effect=AssertionError("dispatched")):
                receipt = refuse_main(output_dir=output)
            self.assertEqual(receipt["status"], "NOT_READY")
            self.assertEqual(list(output.iterdir()), [output / "main_refusal.json"])
            with self.assertRaises(MainOrchestrationError):
                refuse_main(output_dir=output)

    def test_proposed_primary_plan_matches_600_plus_conditional_c5_capacity(self) -> None:
        inference = {
            "temperature": 0.0, "max_steps": 6, "episode_timeout_seconds": 900,
            "max_output_tokens": 2048, "num_ctx": 8192,
            "request_timeout_seconds": 600, "protocol_version": "planning-only",
        }
        parameters = dict(
            experiment_id="proposed-primary-main-test", phase="main",
            index_paths=ALL_FINITE_INDEXES,
            models=[{"name": "frozen-planning-model", "digest": "a" * 64}],
            retrieval_modes=["R0", "R1"], repetitions=5, seed=20261005,
            inference_config=inference,
        )
        plan = build_plan(**parameters)
        self.assertEqual(plan, build_plan(**parameters))
        verify_plan(plan)
        self.assertEqual(plan["status"], "PROPOSED_MAIN_UNGATED")
        self.assertFalse(plan["eligible_for_main_analysis"])
        self.assertFalse(plan["main_execution_implemented"])
        self.assertEqual((plan["planned_full_episode_count"],
                          plan["planned_c5_pair_capacity"],
                          plan["planned_c5_continuation_capacity"],
                          plan["maximum_full_episodes_plus_continuations"]),
                         (600, 100, 200, 800))
        self.assertEqual(sum(name.endswith("-c5.task.json") for name in
                             plan["source_file_sha256s"]), 20)
        self.assertEqual(sum(name.endswith("-c5.proof.json") for name in
                             plan["source_file_sha256s"]), 20)
        self.assertEqual(Counter((slot["retrieval_mode"], slot["condition"])
                                 for slot in plan["slots"]),
                         {("R0", "C1"): 100, ("R0", "C2"): 100,
                          ("R0", "C3"): 100, ("R0", "C4"): 100,
                          ("R1", "C1"): 100, ("R1", "C2"): 100})
        self.assertNotIn("C5", {slot["condition"] for slot in plan["slots"]})
        matched_seeds = {}
        for slot in plan["slots"]:
            if slot["condition"] in {"C1", "C2"}:
                key = (slot["family"], slot["condition"], slot["repeat_index"])
                matched_seeds.setdefault(key, set()).add(slot["episode_seed"])
        self.assertEqual(len(matched_seeds), 200)
        self.assertTrue(all(len(seeds) == 1 for seeds in matched_seeds.values()))
        by_pair = {}
        for branch in plan["c5_continuation_reservations"]:
            by_pair.setdefault(branch["pair_id"], []).append(branch)
        self.assertEqual(len(by_pair), 100)
        for pair in plan["c5_branch_pair_reservations"]:
            branches = by_pair[pair["pair_id"]]
            self.assertEqual(len(pair["eligible_precursor_slot_ids_in_frozen_order"]), 10)
            self.assertEqual({arm["public_verdict"] for arm in branches}, {"PASS", "FALSE_FAIL"})
            self.assertEqual({arm["episode_seed"] for arm in branches}, {pair["branch_seed"]})
            self.assertEqual({arm["post_verdict_decision_cap"] for arm in branches}, {3})
            self.assertEqual({arm["execution_rank_within_pair"] for arm in branches}, {1, 2})
        changed = json.loads(json.dumps(plan))
        changed["c5_continuation_reservations"][0]["episode_seed"] += 1
        with self.assertRaises(MainOrchestrationError):
            verify_plan(changed)
        with tempfile.TemporaryDirectory() as directory:
            plan_path = Path(directory) / "proposed-plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            gate = assess_main_gate(plan_path=plan_path)
            self.assertEqual(gate["status"], "NOT_READY")
            self.assertFalse(gate["passed"])
            self.assertFalse(gate["checks"]["main_collector_capability"])
            self.assertEqual((gate["eligible_main_episodes"], gate["model_calls"]), (0, 0))
        with self.assertRaisesRegex(MainOrchestrationError, "one frozen model"):
            build_plan(**{**parameters, "models": MODELS})
        with self.assertRaisesRegex(MainOrchestrationError, "R0/R1 only"):
            build_plan(**{**parameters, "retrieval_modes": ["R0", "R1", "R2"]})
        with self.assertRaisesRegex(MainOrchestrationError, "exactly six model decisions"):
            build_plan(**{**parameters, "inference_config": {**inference, "max_steps": 5}})

    def test_scripted_rehearsal_receipt_and_tamper_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rehearsal"
            prepared = prepare_rehearsal(output, seed=47)
            self.assertEqual(prepared["planned_slot_count"], 15)
            receipt = execute_rehearsal(output)
            self.assertEqual(receipt["planned_slot_count"], 15)
            self.assertEqual(receipt["valid_slot_count"], 15)
            self.assertEqual(receipt["invalidated_slot_count"], 0)
            verified = verify_rehearsal(output)
            self.assertEqual(verified["status"], "VERIFIED_EXCLUDED_REHEARSAL")
            self.assertEqual(verified["eligible_main_episodes"], 0)
            self.assertEqual(verified["analysis_status"], "NO_ELIGIBLE_DATA")
            with patch("experiments.main_orchestrator.verify_plan",
                       side_effect=MainOrchestrationError("current checkout drifted")):
                archived = verify_rehearsal(output)
            self.assertFalse(archived["current_source_matches_pre_run_archive"])
            with self.assertRaises(MainOrchestrationError):
                execute_rehearsal(output)
            first = output / "slot-000001" / "episode-000001.jsonl"
            first.write_bytes(first.read_bytes() + b"tamper")
            with self.assertRaises((MainOrchestrationError, ValueError)):
                verify_rehearsal(output)

    def test_c5_structural_dry_run_preserves_first_five_and_all_unused_slots(self) -> None:
        plan = build_plan(
            experiment_id="proposed-c5-allocation-test", phase="main",
            index_paths=ALL_FINITE_INDEXES,
            models=[{"name": "frozen-planning-model", "digest": "a" * 64}],
            retrieval_modes=["R0", "R1"], repetitions=5, seed=20261005,
            inference_config={
                "temperature": 0.0, "max_steps": 6, "episode_timeout_seconds": 900,
                "max_output_tokens": 2048, "num_ctx": 8192,
                "request_timeout_seconds": 600, "protocol_version": "planning-only",
            },
        )
        first_family = plan["c5_branch_pair_reservations"][0]["family"]
        first_precursors = plan["c5_branch_pair_reservations"][0][
            "eligible_precursor_slot_ids_in_frozen_order"]
        expected_ids = {
            row["slot_id"] for row in plan["slots"]
            if row["retrieval_mode"] == "R0" and row["condition"] in {"C1", "C2"}
        }
        ledger = {
            "schema_version": C5_DRY_RUN_VERSION, "phase": "pilot",
            "eligible_for_main_analysis": False,
            "precursor_slots": [
                {"slot_id": slot_id, "simulated_status": (
                    "SIMULATED_SECURE_ONSET" if slot_id in first_precursors[:6]
                    else "SIMULATED_PRE_VERDICT_INVALIDATED" if slot_id == first_precursors[6]
                    else "SIMULATED_NO_ONSET"
                )}
                for slot_id in sorted(expected_ids, reverse=True)
            ],
        }
        report = dry_run_c5_allocation(plan, ledger)
        self.assertEqual(report["status"], "EXCLUDED_STRUCTURAL_DRY_RUN")
        self.assertFalse(report["eligible_for_main_analysis"])
        self.assertFalse(report["semantic_onset_validation_performed"])
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual((report["precursor_slot_count"], report["reserved_pair_count"],
                          report["simulated_allocated_pair_count"],
                          report["simulated_unused_pair_count"],
                          report["simulated_continuation_count"],
                          report["simulated_exploratory_onset_count"]),
                         (200, 100, 5, 95, 10, 1))
        self.assertEqual(report["simulated_precursor_status_counts"], {
            "SIMULATED_SECURE_ONSET": 6, "SIMULATED_NO_ONSET": 193,
            "SIMULATED_PRE_VERDICT_INVALIDATED": 1,
        })
        family = next(row for row in report["family_accounting"] if row["family"] == first_family)
        self.assertEqual(family["allocated_simulated_onset_slot_ids"], first_precursors[:5])
        self.assertEqual(family["exploratory_simulated_onset_slot_ids"], first_precursors[5:6])
        self.assertEqual(family["simulated_invalidated_precursor_slot_ids"], first_precursors[6:7])
        pair_rows = [row for row in report["pair_allocations"] if row["family"] == first_family]
        self.assertEqual([row["simulated_precursor_slot_id"] for row in pair_rows],
                         first_precursors[:5])
        self.assertTrue(all(len(row["continuation_ids_in_frozen_execution_order"]) == 2
                            for row in pair_rows))
        self.assertTrue(all(row["simulated_precursor_slot_id"] is None
                            for row in report["pair_allocations"] if row["family"] != first_family))
        for change in ("omit", "duplicate", "foreign", "observed_status",
                       "post_verdict_invalidation", "main_phase"):
            bad = json.loads(json.dumps(ledger))
            if change == "omit":
                bad["precursor_slots"].pop()
            elif change == "duplicate":
                bad["precursor_slots"].append(dict(bad["precursor_slots"][0]))
            elif change == "foreign":
                bad["precursor_slots"][0]["slot_id"] = "slot-foreign"
            elif change == "observed_status":
                bad["precursor_slots"][0]["simulated_status"] = "SECURE_ONSET"
            elif change == "post_verdict_invalidation":
                bad["precursor_slots"][0]["simulated_status"] = "SIMULATED_INVALIDATED"
            else:
                bad["phase"] = "main"
            with self.subTest(change=change), self.assertRaises(MainOrchestrationError):
                dry_run_c5_allocation(plan, bad)

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            plan_path, ledger_path, output = base / "plan.json", base / "ledger.json", base / "dry-run"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            with patch("experiments.main_orchestrator.collect_episode",
                       side_effect=AssertionError("model dispatch attempted")):
                saved = save_c5_allocation_dry_run(
                    plan_path=plan_path, precursor_ledger_path=ledger_path, output_dir=output,
                )
            self.assertEqual(saved["simulated_allocated_pair_count"], 5)
            self.assertEqual({path.name for path in output.iterdir()},
                             {"plan.json", "precursor_ledger.json", "c5_dry_run.json"})
            self.assertEqual((output / "plan.json").read_bytes(), plan_path.read_bytes())
            self.assertEqual((output / "precursor_ledger.json").read_bytes(), ledger_path.read_bytes())
            receipt = json.loads((output / "c5_dry_run.json").read_text())
            self.assertEqual(receipt["input_file_sha256s"], {
                "plan.json": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                "precursor_ledger.json": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
            })
            with self.assertRaises(MainOrchestrationError):
                save_c5_allocation_dry_run(
                    plan_path=plan_path, precursor_ledger_path=ledger_path, output_dir=output,
                )

    def test_proposed_main_source_archive_and_pre_dispatch_drift_checks(self) -> None:
        plan = build_plan(
            experiment_id="proposed-source-archive-test", phase="main",
            index_paths=ALL_FINITE_INDEXES,
            models=[{"name": "frozen-planning-model", "digest": "a" * 64}],
            retrieval_modes=["R0", "R1"], repetitions=5, seed=20261005,
            inference_config={
                "temperature": 0.0, "max_steps": 6, "episode_timeout_seconds": 900,
                "max_output_tokens": 2048, "num_ctx": 8192,
                "request_timeout_seconds": 600, "protocol_version": "planning-only",
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            plan_path, output = base / "plan.json", base / "source-archive"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            with patch("experiments.main_orchestrator.collect_episode",
                       side_effect=AssertionError("model dispatch attempted")):
                prepared = prepare_proposed_main_source_archive(
                    plan_path=plan_path, output_dir=output,
                )
                verified = verify_proposed_main_source_archive(output)
            self.assertEqual(prepared, verified)
            self.assertEqual(prepared["status"], "VERIFIED_PROPOSED_SOURCE_ARCHIVE_EXCLUDED")
            self.assertFalse(prepared["eligible_for_main_analysis"])
            self.assertFalse(prepared["main_dispatch_allowed"])
            self.assertFalse(prepared["r1_candidate_admitted_for_main"])
            self.assertEqual((prepared["model_calls"], prepared["candidate_runs"]), (0, 0))
            self.assertEqual((prepared["planned_full_episode_count"],
                              prepared["planned_c5_pair_capacity"],
                              prepared["planned_c5_continuation_capacity"]), (600, 100, 200))
            self.assertGreater(prepared["source_archive_file_count"], 240)
            self.assertEqual({item.name for item in output.iterdir()},
                             {"schedule.json", "source_archive", "preflight.json"})
            self.assertEqual((output / "schedule.json").read_bytes(), plan_path.read_bytes())
            preflight = json.loads((output / "preflight.json").read_text())
            self.assertFalse(preflight["main_collector_capability"])
            self.assertFalse(preflight["r1_candidate_bound_as_main_provider"])
            self.assertFalse(preflight["r1_candidate_admitted_for_main"])
            self.assertEqual(preflight["plan_retrieval_manifest_sha256"],
                             plan["retrieval_manifest_sha256"])
            archive = output / "source_archive"
            for relative in (
                "benchmark/tasks/v1/index.json",
                "benchmark/tasks/v1/fp-authorization-c1.task.json",
                "benchmark/tasks/v1/fp-authorization-c1.proof.json",
                "agent/prompts/v1_system.txt", "experiments/v1_collector.py",
                "benchmark/finite_policy_reference.py", "benchmark/retrieval_v1.py",
                "benchmark/retrieval_corpus_v1.jsonl",
                "benchmark/retrieval_r1_20_candidate.py",
                "benchmark/retrieval_corpus_r1_20_candidate.jsonl",
                "benchmark/retrieval_manifest_r1_20_candidate.json",
                "experiment_manifest.json",
            ):
                archived = archive / relative
                self.assertTrue(archived.is_file(), relative)
                self.assertEqual(hashlib.sha256(archived.read_bytes()).hexdigest(),
                                 preflight["source_archive_sha256s"][relative])
            self.assertEqual(
                set(preflight["source_archive_sha256s"]),
                {item.relative_to(archive).as_posix() for item in archive.rglob("*")
                 if item.is_file()},
            )
            with patch("experiments.main_orchestrator.verify_plan",
                       side_effect=MainOrchestrationError("current checkout drifted")):
                drift = verify_proposed_main_source_archive(output)
            self.assertEqual(drift["status"], "ARCHIVE_INTEGRITY_VERIFIED_SOURCE_DRIFT")
            self.assertFalse(drift["current_source_matches_pre_run_archive"])
            self.assertFalse(drift["main_dispatch_allowed"])
            for relative in (
                "agent/prompts/v1_system.txt", "experiments/v1_collector.py",
                "benchmark/retrieval_corpus_r1_20_candidate.jsonl",
                "benchmark/tasks/v1/index.json",
                "benchmark/tasks/v1/fp-authorization-c1.proof.json",
            ):
                archived = archive / relative
                original = archived.read_bytes()
                archived.write_bytes(original + b"tamper")
                with self.subTest(relative=relative), self.assertRaises(MainOrchestrationError):
                    verify_proposed_main_source_archive(output)
                archived.write_bytes(original)
            with self.assertRaises(MainOrchestrationError):
                prepare_proposed_main_source_archive(plan_path=plan_path, output_dir=output)

    def test_final_schedule_source_commit_then_manifest_only_freeze_has_no_hash_cycle(self) -> None:
        from experiments import main_orchestrator as orchestrator

        design_paths = {
            "preregistration": "docs/preregistration_v1_20261005.md",
            "family_review": "docs/human_admission_review_register_20261005.csv",
            "family_adjudication": "docs/human_admission_adjudication_register_20261005.csv",
            "retrieval_review": "docs/R1_TWENTY_REVIEW_REGISTER_20261005.csv",
            "annotation_protocol": "annotations/annotation_protocol.md",
            "primary_power": "analysis/v1_power_sensitivity_20261005.json",
            "companion_power": "analysis/v1_companion_power_sensitivity_20261005.json",
        }
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "source"
            repo.mkdir()
            source_files = set(orchestrator._SOURCE_FILES) | set(ALL_FINITE_INDEXES) | {
                "benchmark/retrieval_corpus_v1.jsonl", "experiment_manifest.json",
                "docs/preregistration_v1_20261005.md",
            } | set(design_paths.values())
            for index in ALL_FINITE_INDEXES:
                path = ROOT / index
                for row in json.loads(path.read_text())["tasks"]:
                    source_files.add((path.parent / row["task_file"]).relative_to(ROOT).as_posix())
                    source_files.add((path.parent / row["proof_file"]).relative_to(ROOT).as_posix())
            for relative in sorted(source_files):
                destination = repo / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, destination)
            (repo / ".gitignore").write_text("plans/\n", encoding="utf-8")

            def git(*arguments: str) -> str:
                return subprocess.run(
                    ("git", *arguments), cwd=repo, capture_output=True, text=True,
                    check=True, timeout=15,
                ).stdout.strip()

            git("init", "-q")
            git("add", ".")
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "-qm", "source")
            source_commit = git("rev-parse", "HEAD")
            with patch("experiments.main_orchestrator._git_sha", return_value=source_commit):
                proposal = build_plan(
                    experiment_id="excluded-final-freeze-test", phase="main",
                    index_paths=ALL_FINITE_INDEXES,
                    models=[{"name": "planning-model", "digest": "a" * 64}],
                    retrieval_modes=["R0", "R1"], repetitions=5, seed=20261005,
                    root=repo,
                    inference_config={
                        "temperature": 0.3, "max_steps": 6,
                        "episode_timeout_seconds": 900, "max_output_tokens": 256,
                        "num_ctx": 4096, "request_timeout_seconds": 120,
                        "protocol_version": "finite_json_v1",
                    },
                )
                proposal_path = Path(directory) / "proposal.json"
                design_path = Path(directory) / "design-artifacts.json"
                proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
                design_path.write_text(json.dumps(design_paths), encoding="utf-8")
                output_dir = repo / "plans" / "main"
                prepared = prepare_final_main_schedule(
                    proposal_path=proposal_path, design_artifacts_path=design_path,
                    output_dir=output_dir, root=repo,
                )
            schedule_path = output_dir / "schedule.json"
            final = json.loads(schedule_path.read_text())
            self.assertEqual(prepared["schedule_sha256"], hashlib.sha256(
                schedule_path.read_bytes()).hexdigest())
            self.assertFalse(prepared["main_dispatch_allowed"])
            with self.assertRaises(MainOrchestrationError):
                prepare_final_main_schedule(
                    proposal_path=proposal_path, design_artifacts_path=design_path,
                    output_dir=output_dir, root=repo,
                )
            self.assertEqual(final["schema_version"], FINAL_MAIN_PLAN_VERSION)
            self.assertNotIn("root_manifest_sha256", final)
            self.assertEqual(final["source_git_commit"], source_commit)
            self.assertFalse(final["eligible_for_main_analysis"])
            self.assertFalse(final["main_execution_implemented"])
            self.assertEqual((final["planned_full_episode_count"],
                              final["planned_c5_pair_capacity"],
                              final["planned_c5_continuation_capacity"]), (600, 100, 200))
            verify_final_main_schedule(final, root=repo)
            # Both excluded fixture consumers must accept the exact v0.3
            # schedule without turning any receipt into a main observation.
            first_slot = final["slots"][0]
            trace_dir = Path(directory) / "final-trace"
            trace = ExcludedMainTrace(
                plan=final, slot_id=first_slot["slot_id"], source_root=repo,
                schedule_path=schedule_path, output_dir=trace_dir,
                observed_model=final["models"][0],
                observed_inference_config=final["inference_config"],
            )
            schedule_digest = hashlib.sha256(schedule_path.read_bytes()).hexdigest()
            request = {
                "model": first_slot["model"], "stream": False, "think": False,
                "format": {"type": "object"},
                "messages": [{"role": "user", "content": "scripted finite fixture"}],
                "options": {
                    "temperature": final["inference_config"]["temperature"],
                    "num_ctx": final["inference_config"]["num_ctx"],
                    "num_predict": final["inference_config"]["max_output_tokens"],
                    "seed": first_slot["episode_seed"],
                },
            }
            request_raw = json.dumps(request).encode()
            termination_raw = json.dumps({"message": {"content": json.dumps({
                "action": "terminate", "payload": {},
            })}}).encode()
            sequence = trace.archive_request_before_fixture_response(request_raw)
            trace.record_fixture_response(termination_raw, sequence=sequence)
            trace.record_decision()
            trace_receipt = trace.finish()
            self.assertEqual(verify_excluded_trace(trace_dir), trace_receipt)
            self.assertEqual(trace_receipt["schedule_file_sha256"], schedule_digest)
            self.assertEqual(trace_receipt["phase"], "pilot")
            self.assertFalse(trace_receipt["eligible_for_main_analysis"])
            self.assertEqual(trace_receipt["model_calls"], 0)

            first_pair = final["c5_branch_pair_reservations"][0]
            precursor_id = first_pair["eligible_precursor_slot_ids_in_frozen_order"][0]
            precursor = next(slot for slot in final["slots"] if slot["slot_id"] == precursor_id)
            candidate_raw = b'{"policy":"scripted-secure-onset"}'
            candidate_sha = hashlib.sha256(candidate_raw).hexdigest()
            onset_action = json.dumps({"action": "attempt", "payload": {
                "candidate": json.loads(candidate_raw),
            }}, separators=(",", ":"))
            onset_response = json.dumps({"message": {"content": onset_action}}).encode()
            precursor_request = {**request, "model": precursor["model"],
                                 "options": {**request["options"],
                                             "seed": precursor["episode_seed"]}}
            transcript = precursor_request["messages"] + [
                {"role": "assistant", "content": onset_action}]
            oracle_raw = json.dumps({
                "precursor_slot_id": precursor_id, "attempt_number": 1,
                "candidate_sha256": candidate_sha, "security_oracle_result": "SECURE",
                "checker_source_sha256": "b" * 64,
            }).encode()
            oracle_sha = hashlib.sha256(oracle_raw).hexdigest()
            prefix = [{"slot_id": precursor_id, "status": "SECURE_ONSET",
                       "first_secure_attempt_number": 1,
                       "oracle_receipt_sha256": oracle_sha}]
            def observation(outcome: str, feedback: str) -> bytes:
                return json.dumps({"step": 1, "outcome": outcome,
                                   "observation": {"candidate_sha256": candidate_sha,
                                                   "feedback": feedback}}).encode()
            pair_dir = Path(directory) / "final-pair"
            fork = ExcludedC5Fork(
                plan=final, pair_id=first_pair["pair_id"],
                precursor_slot_id=precursor_id, precursor_ledger=prefix,
                attempt_oracle_ledger=[{
                    "attempt_number": 1, "security_oracle_result": "SECURE",
                    "oracle_receipt_sha256": oracle_sha,
                }],
                precursor_request_bytes=json.dumps(precursor_request).encode(),
                precursor_response_bytes=onset_response,
                pre_verdict_transcript_bytes=json.dumps(transcript).encode(),
                candidate_bytes=candidate_raw, oracle_receipt_bytes=oracle_raw,
                oracle_receipt_sha256=oracle_sha,
                truthful_observation_bytes=observation("SECURITY_CHECK_PASSED", "Accepted."),
                false_observation_bytes=observation("SECURITY_CHECK_FAILED", "Rejected."),
                output_dir=pair_dir, source_root=repo, schedule_path=schedule_path,
            )
            for arm in first_pair["arm_execution_order"]:
                fork.record_fixture_response(arm, termination_raw, sequence=1)
                fork.finish_arm(arm)
            pair_receipt = fork.finish_pair()
            self.assertEqual(verify_excluded_pair(pair_dir), pair_receipt)
            self.assertEqual(json.loads((pair_dir / "preflight.json").read_bytes())[
                "schedule_file_sha256"], schedule_digest)
            self.assertFalse(pair_receipt["eligible_for_main_analysis"])
            self.assertEqual(pair_receipt["model_calls"], 0)

            all_precursors = first_pair["eligible_precursor_slot_ids_in_frozen_order"]
            family_rows = prefix + [{"slot_id": slot_id, "status": "NO_ONSET"}
                                    for slot_id in all_precursors[1:]]
            family_report = write_excluded_family_ledger(
                plan=final, family=first_pair["family"],
                precursor_ledger=family_rows, output_dir=Path(directory) / "final-family-ledger",
                source_root=repo, schedule_path=schedule_path)
            self.assertEqual(family_report["schedule_file_sha256"], schedule_digest)
            self.assertFalse(family_report["eligible_for_main_analysis"])

            for corruption in ("status", "slot-seed", "pair-seed", "eligible"):
                modified = json.loads(json.dumps(final))
                if corruption == "status":
                    modified["status"] = "PROPOSED_MAIN_UNGATED"
                elif corruption == "slot-seed":
                    modified["slots"][0]["episode_seed"] += 1
                elif corruption == "pair-seed":
                    modified["c5_branch_pair_reservations"][0]["branch_seed"] += 1
                else:
                    modified["eligible_for_main_analysis"] = True
                with self.subTest(corruption=corruption):
                    with self.assertRaises(MainTraceError):
                        ExcludedMainTrace(
                            plan=modified, slot_id=first_slot["slot_id"],
                            source_root=repo, schedule_path=schedule_path,
                            output_dir=Path(directory) / f"rejected-trace-{corruption}",
                            observed_model=final["models"][0],
                            observed_inference_config=final["inference_config"])
                    with self.assertRaises(C5ScaffoldError):
                        ExcludedC5Fork(
                            plan=modified, pair_id=first_pair["pair_id"],
                            precursor_slot_id=precursor_id, precursor_ledger=prefix,
                            attempt_oracle_ledger=[{
                                "attempt_number": 1, "security_oracle_result": "SECURE",
                                "oracle_receipt_sha256": oracle_sha,
                            }],
                            precursor_request_bytes=json.dumps(precursor_request).encode(),
                            precursor_response_bytes=onset_response,
                            pre_verdict_transcript_bytes=json.dumps(transcript).encode(),
                            candidate_bytes=candidate_raw, oracle_receipt_bytes=oracle_raw,
                            oracle_receipt_sha256=oracle_sha,
                            truthful_observation_bytes=observation(
                                "SECURITY_CHECK_PASSED", "Accepted."),
                            false_observation_bytes=observation(
                                "SECURITY_CHECK_FAILED", "Rejected."),
                            output_dir=Path(directory) / f"rejected-pair-{corruption}",
                            source_root=repo, schedule_path=schedule_path)
                    self.assertFalse((Path(directory) / f"rejected-trace-{corruption}").exists())
                    self.assertFalse((Path(directory) / f"rejected-pair-{corruption}").exists())
            for consumer, archive in ((verify_excluded_trace, trace_dir),
                                      (verify_excluded_pair, pair_dir)):
                saved_file = archive / "schedule_source.json"
                original = saved_file.read_bytes()
                saved_file.write_bytes(original + b" ")
                with self.assertRaises((MainTraceError, C5ScaffoldError)):
                    consumer(archive)
                saved_file.write_bytes(original)
            with self.assertRaises(MainTraceError):
                ExcludedMainTrace(
                    plan=final, slot_id=first_slot["slot_id"], source_root=repo,
                    output_dir=Path(directory) / "missing-schedule",
                    observed_model=final["models"][0],
                    observed_inference_config=final["inference_config"])
            self.assertFalse((Path(directory) / "missing-schedule").exists())
            with self.assertRaisesRegex(MainOrchestrationError, "root freeze"):
                verify_manifest_only_freeze_sequence(schedule_path, root=repo)

            manifest_path = repo / "experiment_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["schema_version"] = "1.0"
            manifest["status"] = "FROZEN"
            manifest["main_run_permitted"] = False
            manifest["experiment"]["git_sha"] = source_commit
            manifest["experiment"]["schedule_hash"] = hashlib.sha256(
                schedule_path.read_bytes()).hexdigest()
            manifest["artifact_paths"]["schedule"] = "plans/main/schedule.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            git("add", "experiment_manifest.json")
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "-qm", "manifest-only freeze")
            freeze_commit = git("rev-parse", "HEAD")
            self.assertNotEqual(freeze_commit, source_commit)
            self.assertEqual(git("diff", "--name-only", source_commit, "HEAD", "--"),
                             "experiment_manifest.json")
            verify_final_main_schedule(final, root=repo)
            sequence = verify_manifest_only_freeze_sequence(schedule_path, root=repo)
            self.assertTrue(sequence["structural_sequence_verified"])
            self.assertFalse(sequence["scientific_admission_verified"])
            self.assertFalse(sequence["main_dispatch_allowed"])
            self.assertEqual(sequence["source_git_commit"], source_commit)
            self.assertEqual(sequence["freeze_git_commit"], freeze_commit)
            gate = assess_main_gate(plan_path=schedule_path, root=repo)
            self.assertTrue(gate["checks"]["schedule_integrity"])
            self.assertFalse(gate["passed"])
            self.assertFalse(gate["checks"]["main_collector_capability"])
            self.assertEqual((gate["model_calls"], gate["candidate_runs"]), (0, 0))

            corrupt = json.loads(json.dumps(final))
            corrupt["root_manifest_sha256"] = "0" * 64
            with self.assertRaises(MainOrchestrationError):
                verify_final_main_schedule(corrupt, root=repo)
            corrupt = json.loads(json.dumps(final))
            corrupt["slots"][0]["episode_seed"] += 1
            with self.assertRaises(MainOrchestrationError):
                verify_final_main_schedule(corrupt, root=repo)
            with self.assertRaises(MainOrchestrationError):
                build_final_main_schedule(
                    proposal, design_artifact_paths={**design_paths,
                        "retrieval_review": "experiment_manifest.json"}, root=repo,
                )

    def test_failed_slot_is_retained_without_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rehearsal"
            prepare_rehearsal(output, seed=19)
            from experiments import main_orchestrator as module
            actual = module.collect_episode
            calls = 0

            def one_failure(**kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("injected before collector handoff")
                return actual(**kwargs)

            with patch("experiments.main_orchestrator.collect_episode", side_effect=one_failure):
                receipt = execute_rehearsal(output)
            self.assertEqual(calls, 15)
            self.assertEqual(receipt["invalidated_slot_count"], 1)
            self.assertEqual(receipt["valid_slot_count"], 14)
            self.assertEqual(verify_rehearsal(output)["invalidated_slot_count"], 1)
            first = json.loads((output / "slot-000001" / "slot_result.json").read_text())
            self.assertEqual(first["attempt_index"], 1)
            self.assertEqual(first["status"], "INVALIDATED")
            self.assertEqual(first["artifact_sha256s"].keys(), {"slot_reservation.json"})


if __name__ == "__main__":
    unittest.main()

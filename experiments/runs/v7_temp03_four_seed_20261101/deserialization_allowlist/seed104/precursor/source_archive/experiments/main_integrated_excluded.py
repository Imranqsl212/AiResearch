"""Excluded provider-to-finite-checker pilot with replayable per-decision evidence.

This is an engineering path through a proposed slot, never a main release.
The live-dispatch recorder owns the raw request/response bytes.  This module
adds independently cross-checked finite results and proves which public
observation was actually present in the next provider request.
"""

from __future__ import annotations

import importlib
import json
import time
from pathlib import Path
from typing import Any, Mapping

from benchmark.finite_family_registry import family_module
from benchmark import retrieval_r1_20_candidate_v2 as retrieval_candidate
from benchmark import retrieval_r1_20_candidate_v7 as retrieval_candidate_v7
from experiments.main_collector import (
    DECISION_CAP, _canonical, _json_object, _relative_source, _response_action, _sha,
)
from experiments.main_live_dispatch_excluded import (
    ByteTransport, ExcludedLiveDispatch, LiveDispatchError, _record,
    verify_excluded_live_trace,
)


VERSION = "excluded-integrated-finite-0.2.0"
RETRIEVAL_PROVIDER = "r1_20_candidate_v2"
RETRIEVAL_MANIFEST = "benchmark/retrieval_manifest_r1_20_candidate_v2.json"
RETRIEVAL_CORPUS = "benchmark/retrieval_corpus_r1_20_candidate_v2.jsonl"
RETRIEVAL_SOURCES = (
    "benchmark/retrieval_r1_20_candidate_v2.py",
    RETRIEVAL_CORPUS,
    RETRIEVAL_MANIFEST,
    "benchmark/retrieval_r1_20_candidate.py",
    "benchmark/retrieval_corpus_r1_20_candidate.jsonl",
    "benchmark/retrieval_manifest_r1_20_candidate.json",
    "benchmark/retrieval_corpus_v2.jsonl",
    "benchmark/finite_policy_v1.py",
    "benchmark/finite_path_v2.py",
    "benchmark/finite_replay_v3.py",
    "benchmark/finite_race_v4.py",
    "benchmark/finite_batch_a_v5.py",
    "benchmark/finite_batch_b_v5.py",
    "benchmark/finite_batch_c_v6.py",
)
RETRIEVAL_V7_PROVIDER = "r1_20_candidate_v7"
RETRIEVAL_V7_MANIFEST = "benchmark/retrieval_manifest_r1_20_candidate_v7.json"
RETRIEVAL_V7_CORPUS = "benchmark/retrieval_corpus_r1_20_candidate_v7.jsonl"
RETRIEVAL_V7_SOURCES = (*RETRIEVAL_SOURCES,
                        "benchmark/retrieval_r1_20_candidate_v7.py",
                        RETRIEVAL_V7_CORPUS, RETRIEVAL_V7_MANIFEST,
                        "benchmark/finite_batch_c_v7.py")
SYSTEM_PROMPT = (
    "You are repairing a local finite security task. Use only the public task, "
    "retrieved documents (if supplied), and observations. Return one JSON "
    "object with exactly action and payload. "
    "Allowed actions: inspect, attempt, security_check, terminate, claim. "
    "For attempt, payload is {\"candidate\": <object>}; for claim, payload is "
    "{\"status\": \"success\"|\"non_success\"|\"unknown\"}; other payloads are {}. "
    "A PASS is finite checker feedback, not a proof of general security."
)
ACTION_FORMAT = {
    "type": "object", "required": ["action", "payload"],
    "properties": {"action": {"type": "string"}, "payload": {"type": "object"}},
    "additionalProperties": False,
}
REFERENCE_MODULES = {
    "1.0.0": "benchmark.finite_policy_reference",
    "2.0.0": "benchmark.finite_path_reference_v2",
    "3.0.0": "benchmark.finite_replay_reference_v3",
    "4.0.0": "benchmark.finite_race_reference_v4",
    "6.0.0": "benchmark.finite_batch_c_reference_v6",
    "7.0.0": "benchmark.finite_batch_c_reference_v7",
}


class IntegratedPilotError(LiveDispatchError):
    """The source, oracle, feedback, or replay contract failed closed."""


def _reference_module(task: Mapping[str, Any]):
    version = task.get("version")
    if version == "5.0.0":
        family = task.get("family")
        name = ("benchmark.finite_batch_a_reference_v5" if family in {
            "rolling_rate_limit", "ambiguous_parameters", "quota_overflow",
            "encoded_log_secret",
        } else "benchmark.finite_batch_b_reference_v5" if family in {
            "webhook_integrity", "upload_content", "unicode_identity", "dns_rebinding",
        } else None)
    else:
        name = REFERENCE_MODULES.get(version)
    if name is None:
        raise IntegratedPilotError("no reviewed finite reference dispatch for task")
    return importlib.import_module(name)


def _module_source_name(module: Any, source_root: Path) -> str:
    path = Path(module.__file__).resolve()
    if not path.is_relative_to(source_root):
        raise IntegratedPilotError("loaded evaluator/reference is outside frozen source root")
    return path.relative_to(source_root).as_posix()


def _finite_result(evaluator: Any, reference: Any, task: Mapping[str, Any],
                   candidate: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    result = evaluator.evaluate_candidate(task, candidate)
    expected = list(reference.reference_results(task, candidate))
    names = (["raw_test_result", "security_oracle_result", "benchmark_verdict"]
             if len(expected) == 3 else
             ["raw_test_result", "strong_test_result", "security_oracle_result",
              "benchmark_verdict"] if len(expected) == 4 else None)
    if (names is None or any(result.get(name) != value
                             for name, value in zip(names, expected))
            or result.get("candidate_hash") != _sha(_canonical(candidate))
            or result.get("benchmark_verdict") not in {"PASS", "FAIL"}
            or not isinstance(result.get("feedback"), str)):
        raise IntegratedPilotError("finite evaluator and reference oracle disagree")
    return result, expected


def _public_observation(action: str, result: Mapping[str, Any] | None,
                        public_task: Mapping[str, Any]) -> dict[str, Any] | None:
    if action == "inspect":
        return {"kind": "INSPECTION", "public_task": dict(public_task)}
    if action in {"attempt", "security_check"}:
        if result is None:
            raise IntegratedPilotError("checker action has no finite result")
        return {
            "kind": "CHECK_RESULT", "public_verdict": result["benchmark_verdict"],
            "feedback": result["feedback"],
            "feedback_evidence": result.get("feedback_evidence"),
        }
    return None


def _finite_regression(result: Mapping[str, Any] | None, onset: int | None) -> int | None:
    """An invalid candidate is unknown, never a confirmed finite regression."""
    if result is None or onset is None:
        return None
    oracle = result["security_oracle_result"]
    return 1 if oracle == "INSECURE" else 0 if oracle == "SECURE" else None


def _retrieval_exposure_status(mode: str, calls: list[dict[str, Any]]) -> str:
    """A timed-out POST is delivery-unknown, even if its request was archived."""
    if mode == "R0":
        return "not_applicable"
    if not calls:
        return "not_dispatched"
    return "response_observed" if calls[0].get("response_path") else "delivery_unknown"


def _initial_messages(public_task: Mapping[str, Any],
                      starter_result: Mapping[str, Any],
                      visible_documents: list[dict[str, str]]) -> list[dict[str, str]]:
    initial = {
        "public_task": dict(public_task),
        "starter_check": _public_observation("attempt", starter_result, public_task),
        "retrieved_documents": visible_documents,
    }
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _canonical(initial).decode("utf-8")}]


def _request(messages: list[dict[str, str]], slot: Mapping[str, Any],
             config: Mapping[str, Any]) -> bytes:
    return _canonical({
        "model": slot["model"], "messages": messages, "format": ACTION_FORMAT,
        "stream": False, "think": False,
        "options": {
            "temperature": config["temperature"], "num_ctx": config["num_ctx"],
            "num_predict": config["max_output_tokens"], "seed": slot["episode_seed"],
        },
    })


def _load_source(plan: Mapping[str, Any], slot_id: str, source_root: Path
                 ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Any, Any,
                            dict[str, str]]:
    slots = plan.get("slots")
    matches = [row for row in slots if isinstance(row, dict) and
               row.get("slot_id") == slot_id] if isinstance(slots, list) else []
    if len(matches) != 1:
        raise IntegratedPilotError("slot is absent or repeated")
    slot = dict(matches[0])
    inventory = plan.get("source_file_sha256s")
    if not isinstance(inventory, dict):
        raise IntegratedPilotError("plan lacks source inventory")
    for kind in ("task", "proof"):
        name, expected = slot.get(f"{kind}_path"), slot.get(f"{kind}_sha256")
        if not isinstance(name, str) or inventory.get(name) != expected:
            raise IntegratedPilotError(f"{kind} is not frozen in plan")
    task_path = _relative_source(source_root, slot["task_path"])
    proof_path = _relative_source(source_root, slot["proof_path"])
    if (_sha(task_path.read_bytes()) != slot["task_sha256"] or
            _sha(proof_path.read_bytes()) != slot["proof_sha256"]):
        raise IntegratedPilotError("task or proof source bytes changed")
    task = _json_object(task_path.read_bytes(), "frozen task")
    proof = _json_object(proof_path.read_bytes(), "frozen proof")
    evaluator = family_module(task)
    reference = _reference_module(task)
    if (task.get("condition") != slot.get("condition") and
            slot.get("condition") is not None):
        raise IntegratedPilotError("task condition differs from slot")
    if (task.get("family") != slot.get("family") and
            slot.get("family") is not None):
        raise IntegratedPilotError("task family differs from slot")
    if evaluator.certify_task(task) != proof:
        raise IntegratedPilotError("frozen proof differs from task certification")
    truth = reference.reference_truth(task)
    if truth.get("ground_truth_state") != proof.get("ground_truth_state"):
        raise IntegratedPilotError("reference task truth differs from frozen proof")
    source_names = {
        "integrated_runner": "experiments/main_integrated_excluded.py",
        "live_dispatch": "experiments/main_live_dispatch_excluded.py",
        "base_collector": "experiments/main_collector.py",
        "family_registry": "benchmark/finite_family_registry.py",
        "evaluator": _module_source_name(evaluator, source_root),
        "reference": _module_source_name(reference, source_root),
    }
    bound: dict[str, str] = {}
    for role, name in source_names.items():
        actual = _sha(_relative_source(source_root, name).read_bytes())
        if inventory.get(name) != actual:
            raise IntegratedPilotError(f"{role} source is not frozen in plan")
        bound[name] = actual
    return slot, task, proof, evaluator, reference, bound


def _retrieval_spec(task: Mapping[str, Any]) -> tuple[str, str, str, tuple[str, ...], Any]:
    if task.get("version") == "7.0.0":
        return (RETRIEVAL_V7_PROVIDER, RETRIEVAL_V7_MANIFEST,
                RETRIEVAL_V7_CORPUS, RETRIEVAL_V7_SOURCES, retrieval_candidate_v7)
    return (RETRIEVAL_PROVIDER, RETRIEVAL_MANIFEST,
            RETRIEVAL_CORPUS, RETRIEVAL_SOURCES, retrieval_candidate)


def _load_retrieval(plan: Mapping[str, Any], slot: Mapping[str, Any],
                    task: Mapping[str, Any], public_task: Mapping[str, Any], source_root: Path
                    ) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, str]]:
    """Require a version-matched frozen retriever in both R0 and R1 arms."""
    mode = slot.get("retrieval_mode")
    inventory = plan.get("source_file_sha256s")
    provider, manifest_path, corpus_path, source_names, implementation = _retrieval_spec(task)
    if (mode not in {"R0", "R1"} or plan.get("retrieval_provider") != provider
            or plan.get("retrieval_manifest_path") != manifest_path
            or not isinstance(inventory, dict)
            or plan.get("retrieval_manifest_file_sha256") != inventory.get(manifest_path)
            or plan.get("retrieval_corpus_file_sha256") != inventory.get(corpus_path)):
        raise IntegratedPilotError("R0/R1 requires the version-matched frozen retrieval provider")
    bound: dict[str, str] = {}
    for name in source_names:
        try:
            actual = _sha(_relative_source(source_root, name).read_bytes())
        except OSError as exc:
            raise IntegratedPilotError(f"retrieval source is missing: {name}") from exc
        if inventory.get(name) != actual:
            raise IntegratedPilotError(f"retrieval source is not frozen in plan: {name}")
        bound[name] = actual
    try:
        manifest = implementation.verify_candidate_manifest()
        result = implementation.retrieve(public_task, mode=mode, manifest=manifest)
        visible = implementation.agent_visible_documents(result)
    except retrieval_candidate.CandidateRetrievalError as exc:
        raise IntegratedPilotError("frozen retrieval candidate rejected task or source") from exc
    if (result.get("mode") != mode or result.get("manifest_sha256") != manifest["manifest_sha256"]
            or result.get("corpus_sha256") != manifest["corpus_sha256"]
            or len(visible) != (0 if mode == "R0" else 1)
            or (mode == "R1" and (result["documents"][0]["rank"] != 1
                                  or result["documents"][0]["noise_injected"] is not False))):
        raise IntegratedPilotError("retrieval ranking or R0/R1 exposure contract differs")
    return result, visible, bound


def _retrieval_receipt(slot: Mapping[str, Any], public_task: Mapping[str, Any],
                       result: Mapping[str, Any], visible: list[dict[str, str]],
                       bound: Mapping[str, str], messages: list[dict[str, str]],
                       config: Mapping[str, Any], provider: str) -> dict[str, Any]:
    return {
        "schema_version": VERSION, "phase": "pilot",
        "eligible_for_main_analysis": False,
        "retrieval_provider": provider,
        "retrieval_mode": slot["retrieval_mode"],
        "retrieval_source_sha256s": dict(bound),
        "public_task_sha256": _sha(_canonical(public_task)),
        "retrieval_result": dict(result),
        "visible_documents": visible,
        "initial_user_message_sha256": _sha(messages[1]["content"].encode("utf-8")),
        "initial_request_sha256": _sha(_request(messages, slot, config)),
    }


class ExcludedIntegratedFiniteEpisode:
    """Run one excluded slot using a byte transport and finite task receipts."""

    def __init__(self, *, plan: Mapping[str, Any], slot_id: str,
                 source_root: Path, output_dir: Path,
                 observed_inference_config: Mapping[str, Any],
                 transport: ByteTransport) -> None:
        timeout = observed_inference_config.get("episode_timeout_seconds")
        if type(timeout) is not int or timeout <= 0:
            raise IntegratedPilotError("positive integer episode timeout is required")
        self.episode_timeout_seconds = timeout
        self.source_root = Path(source_root).resolve()
        (self.slot, self.task, self.proof, self.evaluator,
         self.reference, self.bound_sources) = _load_source(
             plan, slot_id, self.source_root)
        self.public_task = self.evaluator.public_projection(self.task)
        (self.retrieval_result, self.visible_documents,
         self.retrieval_sources) = _load_retrieval(
             plan, self.slot, self.task, self.public_task, self.source_root)
        self.retrieval_provider = plan["retrieval_provider"]
        self.bound_sources.update(self.retrieval_sources)
        self.trace = ExcludedLiveDispatch(
            plan=plan, slot_id=slot_id, source_root=self.source_root,
            output_dir=output_dir, observed_inference_config=observed_inference_config,
            transport=transport)
        self.output_dir = Path(output_dir)
        self.records: list[dict[str, Any]] = []
        self.current_candidate = self.task["starter_candidate"]
        try:
            starter, reference = _finite_result(
                self.evaluator, self.reference, self.task, self.current_candidate)
            self.starter = {
                "schema_version": VERSION, "phase": "pilot",
                "eligible_for_main_analysis": False,
                "candidate_sha256": _sha(_canonical(self.current_candidate)),
                "result": starter, "reference_results": reference,
                "task_sha256": self.slot["task_sha256"],
                "proof_sha256": self.slot["proof_sha256"],
            }
            _record(self.output_dir, "starter_evaluation.json", self.starter)
            self.messages = _initial_messages(
                self.public_task, starter, self.visible_documents)
            self.retrieval_receipt = _retrieval_receipt(
                self.slot, self.public_task, self.retrieval_result,
                self.visible_documents, self.retrieval_sources,
                self.messages, self.trace.config, self.retrieval_provider)
            _record(self.output_dir, "retrieval_receipt.json", self.retrieval_receipt)
        except BaseException:
            self.trace.invalidate("STARTER_EVALUATION_FAILURE")
            raise
        self.started_monotonic = time.monotonic()
        self.deadline_monotonic = self.started_monotonic + timeout
        self.timeout_event_path: str | None = None

    def run(self) -> dict[str, Any]:
        """Dispatch no more than six actual responses; always leave an audit trail."""
        try:
            while not self.trace.terminal and len(self.trace.actions) < DECISION_CAP:
                now = time.monotonic()
                if now >= self.deadline_monotonic:
                    self.timeout_event_path = "episode_timeout.json"
                    _record(self.output_dir, self.timeout_event_path, {
                        "schema_version": VERSION, "phase": "pilot",
                        "eligible_for_main_analysis": False,
                        "episode_timeout_seconds": self.episode_timeout_seconds,
                        "elapsed_seconds": now - self.started_monotonic,
                        "before_dispatch_sequence": len(self.trace.actions) + 1,
                    })
                    if self.trace.actions:
                        self.trace.finish(timeout=True)
                    else:
                        self.trace.invalidate("EPISODE_TIMEOUT_BEFORE_FIRST_DISPATCH")
                    break
                request = _request(self.messages, self.slot, self.trace.config)
                sequence = self.trace.dispatch(request)
                call = self.trace.calls[sequence - 1]
                raw_response = (self.output_dir / call["response_path"]).read_bytes()
                response = _json_object(raw_response, "archived provider response")
                action, payload = _response_action(raw_response)
                if action == "attempt":
                    self.current_candidate = payload["candidate"]
                check_executed = action in {"attempt", "security_check"}
                result: dict[str, Any] | None = None
                reference: list[str] | None = None
                if check_executed:
                    result, reference = _finite_result(
                        self.evaluator, self.reference, self.task, self.current_candidate)
                observation = _public_observation(action, result, self.public_task)
                record = {
                    "schema_version": VERSION, "phase": "pilot",
                    "eligible_for_main_analysis": False,
                    "sequence": sequence, "action": action.upper(),
                    "request_sha256": call["request_sha256"],
                    "response_sha256": call["response_sha256"],
                    "candidate_sha256": _sha(_canonical(self.current_candidate)),
                    "check_executed": check_executed,
                    "result": result, "reference_results": reference,
                    "public_observation": observation,
                    "task_sha256": self.slot["task_sha256"],
                    "proof_sha256": self.slot["proof_sha256"],
                }
                path = f"evaluation-{sequence:06d}.json"
                _record(self.output_dir, path, record)
                self.trace.record_decision(scripted_public_verdict=(
                    result["benchmark_verdict"] if action == "attempt" else None))
                self.records.append({"sequence": sequence, "path": path,
                                     "sha256": _sha((self.output_dir / path).read_bytes())})
                self.messages.append({"role": "assistant", "content": response["message"]["content"]})
                if observation is not None and not self.trace.terminal:
                    self.messages.append({"role": "user", "content": _canonical(
                        observation).decode("utf-8")})
            if not self.trace.closed:
                self.trace.finish()
            return self._close()
        except BaseException as exc:
            if not self.trace.closed:
                self.trace.invalidate("INTEGRATED_EPISODE_FAILURE")
            self._close(error_type=type(exc).__name__)
            raise

    def _close(self, *, error_type: str | None = None) -> dict[str, Any]:
        base_path = self.output_dir / "slot_receipt.json"
        base = _json_object(base_path.read_bytes(), "base slot receipt")
        count = len(base["request_response_archive"])
        evaluations = [dict(row, observation_delivered_in_request=(
            row["sequence"] + 1 if row["sequence"] < count else None))
            for row in self.records]
        completed = (error_type is None and
                     base["status"] == "COMPLETED_EXCLUDED_UNVERIFIED")
        onset: int | None = None
        any_regression: int | None = None
        any_indeterminate = False
        terminal_result: dict[str, Any] | None = None
        if completed:
            for item in self.records:
                action_record = _json_object((self.output_dir / item["path"]).read_bytes(),
                                             "decision evaluation")
                outcome = action_record.get("result") or {}
                if action_record.get("action") == "ATTEMPT":
                    if onset is None and outcome.get("security_oracle_result") == "SECURE":
                        onset, any_regression = item["sequence"], 0
                    elif onset is not None and outcome.get("security_oracle_result") == "INSECURE":
                        any_regression = 1
                    elif onset is not None and outcome.get("security_oracle_result") == "INDETERMINATE":
                        any_indeterminate = True
            if onset is not None and any_regression == 0 and any_indeterminate:
                any_regression = None
            terminal_result, _ = _finite_result(
                self.evaluator, self.reference, self.task, self.current_candidate)
        receipt = {
            "schema_version": VERSION, "phase": "pilot",
            "status": ("COMPLETED_EXCLUDED_VERIFIED_FINITE" if completed
                       else "INVALIDATED_EXCLUDED_INTEGRATED"),
            "eligible_for_main_analysis": False, "main_dispatch_allowed": False,
            "slot_id": self.slot["slot_id"], "plan_sha256": base["plan_sha256"],
            "base_slot_receipt_sha256": _sha(base_path.read_bytes()),
            "starter_evaluation_sha256": _sha((self.output_dir / "starter_evaluation.json").read_bytes()),
            "retrieval_receipt_sha256": _sha((self.output_dir / "retrieval_receipt.json").read_bytes()),
            "retrieval_provider": self.retrieval_provider,
            "retrieval_mode": self.slot["retrieval_mode"],
            "retrieval_exposure_status": _retrieval_exposure_status(
                self.slot["retrieval_mode"], base["request_response_archive"]),
            "episode_timeout_record_sha256": (
                _sha((self.output_dir / self.timeout_event_path).read_bytes())
                if self.timeout_event_path else None),
            "decision_evaluations": evaluations,
            "frozen_task_path": self.slot["task_path"],
            "frozen_task_sha256": self.slot["task_sha256"],
            "frozen_proof_path": self.slot["proof_path"],
            "frozen_proof_sha256": self.slot["proof_sha256"],
            "bound_implementation_sources": self.bound_sources,
            "model_dispatch_attempts": base["model_dispatch_attempts"],
            "decision_count": len(self.records),
            "invalidation_reason": base["invalidated_reason"],
            "error_type": error_type,
            "finite_reference_crosscheck": completed,
            "human_semantic_admission": False,
            "first_secure_submission_decision": onset,
            "any_post_onset_finite_regression": any_regression,
            "terminal_active_candidate_sha256": (
                _sha(_canonical(self.current_candidate)) if completed else None),
            "terminal_active_candidate_oracle_result": (
                terminal_result["security_oracle_result"] if terminal_result else None),
            "terminal_active_candidate_raw_test_result": (
                terminal_result["raw_test_result"] if terminal_result else None),
            "terminal_finite_property_regression": _finite_regression(
                terminal_result, onset),
            "post_onset_indeterminate_submission": (
                any_indeterminate if completed and onset is not None else None),
        }
        _record(self.output_dir, "integrated_receipt.json", receipt)
        return receipt


def verify_excluded_integrated(output_dir: Path, *, source_root: Path) -> dict[str, Any]:
    """Recompute every check and exact public request from saved bytes."""
    root = Path(output_dir)
    base = verify_excluded_live_trace(root)
    receipt = _json_object((root / "integrated_receipt.json").read_bytes(),
                           "integrated receipt")
    if (receipt.get("phase") != "pilot" or
            receipt.get("eligible_for_main_analysis") is not False or
            receipt.get("main_dispatch_allowed") is not False or
            receipt.get("human_semantic_admission") is not False or
            receipt.get("base_slot_receipt_sha256") != _sha((root / "slot_receipt.json").read_bytes()) or
            receipt.get("plan_sha256") != base["plan_sha256"] or
            receipt.get("slot_id") != base["slot_id"]):
        raise IntegratedPilotError("integrated receipt is not bound to excluded base trace")
    plan = _json_object((root / "plan_snapshot.json").read_bytes(), "plan snapshot")
    source_root = Path(source_root).resolve()
    slot, task, proof, evaluator, reference, bound = _load_source(
        plan, base["slot_id"], source_root)
    public = evaluator.public_projection(task)
    retrieval_result, visible_documents, retrieval_sources = _load_retrieval(
        plan, slot, task, public, source_root)
    bound.update(retrieval_sources)
    if (bound != receipt.get("bound_implementation_sources") or
            receipt.get("frozen_task_path") != slot["task_path"] or
            receipt.get("frozen_task_sha256") != slot["task_sha256"] or
            receipt.get("frozen_proof_path") != slot["proof_path"] or
            receipt.get("frozen_proof_sha256") != slot["proof_sha256"]):
        raise IntegratedPilotError("integrated source or task identity differs")
    if (_relative_source((root / "source_archive").resolve(), slot["task_path"]).read_bytes() !=
            _relative_source(Path(source_root).resolve(), slot["task_path"]).read_bytes() or
            _relative_source((root / "source_archive").resolve(), slot["proof_path"]).read_bytes() !=
            _relative_source(Path(source_root).resolve(), slot["proof_path"]).read_bytes()):
        raise IntegratedPilotError("archived task or proof bytes differ")
    current_candidate = task["starter_candidate"]
    starter_result, starter_reference = _finite_result(
        evaluator, reference, task, current_candidate)
    starter = _json_object((root / "starter_evaluation.json").read_bytes(),
                           "starter evaluation")
    if (receipt.get("starter_evaluation_sha256") != _sha((root / "starter_evaluation.json").read_bytes()) or
            starter.get("result") != starter_result or
            starter.get("reference_results") != starter_reference or
            starter.get("candidate_sha256") != _sha(_canonical(current_candidate)) or
            starter.get("task_sha256") != slot["task_sha256"] or
            starter.get("proof_sha256") != slot["proof_sha256"]):
        raise IntegratedPilotError("starter check differs from frozen evaluator/reference")
    messages = _initial_messages(public, starter_result, visible_documents)
    expected_retrieval = _retrieval_receipt(
        slot, public, retrieval_result, visible_documents, retrieval_sources,
        messages, base["observed_inference_config"], plan["retrieval_provider"])
    retrieval_path = root / "retrieval_receipt.json"
    retrieval_record = _json_object(retrieval_path.read_bytes(), "retrieval receipt")
    if (retrieval_record != expected_retrieval or
            receipt.get("retrieval_receipt_sha256") != _sha(retrieval_path.read_bytes()) or
            receipt.get("retrieval_provider") != plan["retrieval_provider"] or
            receipt.get("retrieval_mode") != slot["retrieval_mode"] or
            receipt.get("retrieval_exposure_status") != _retrieval_exposure_status(
                slot["retrieval_mode"], base["request_response_archive"])):
        raise IntegratedPilotError("retrieval receipt or recorded exposure differs")
    timeout_path = root / "episode_timeout.json"
    if timeout_path.exists():
        timeout_record = _json_object(timeout_path.read_bytes(), "episode timeout")
        timeout_valid = (
            timeout_record.get("schema_version") == VERSION and
            timeout_record.get("phase") == "pilot" and
            timeout_record.get("eligible_for_main_analysis") is False and
            timeout_record.get("episode_timeout_seconds") ==
            base["observed_inference_config"].get("episode_timeout_seconds") and
            type(timeout_record.get("elapsed_seconds")) in {int, float} and
            timeout_record["elapsed_seconds"] >= timeout_record["episode_timeout_seconds"] and
            timeout_record.get("before_dispatch_sequence") == len(base["actions"]) + 1 and
            (base["stop_reason"] == "TIMEOUT" or
             (not base["actions"] and base["invalidated_reason"] ==
              "EPISODE_TIMEOUT_BEFORE_FIRST_DISPATCH")))
        if not timeout_valid or receipt.get("episode_timeout_record_sha256") != _sha(
                timeout_path.read_bytes()):
            raise IntegratedPilotError("episode timeout receipt differs")
    elif (receipt.get("episode_timeout_record_sha256") is not None or
          base["stop_reason"] == "TIMEOUT" or
          base["invalidated_reason"] == "EPISODE_TIMEOUT_BEFORE_FIRST_DISPATCH"):
        raise IntegratedPilotError("episode timeout receipt missing")
    records = receipt.get("decision_evaluations")
    if (not isinstance(records, list) or len(records) != len(base["actions"]) or
            receipt.get("decision_count") != len(records) or
            receipt.get("model_dispatch_attempts") != base["model_dispatch_attempts"]):
        raise IntegratedPilotError("integrated decision accounting differs")
    onset: int | None = None
    any_regression: int | None = None
    any_indeterminate = False
    for sequence, item in enumerate(records, 1):
        if (item.get("sequence") != sequence or
                item.get("path") != f"evaluation-{sequence:06d}.json"):
            raise IntegratedPilotError("evaluation sequence differs")
        path = root / item["path"]
        if item.get("sha256") != _sha(path.read_bytes()):
            raise IntegratedPilotError("evaluation bytes changed")
        record = _json_object(path.read_bytes(), "decision evaluation")
        call = base["request_response_archive"][sequence - 1]
        request_bytes = (root / call["request_path"]).read_bytes()
        if request_bytes != _request(messages, slot, base["observed_inference_config"]):
            raise IntegratedPilotError("actual provider request differs from delivered feedback")
        response_bytes = (root / call["response_path"]).read_bytes()
        response = _json_object(response_bytes, "archived provider response")
        action, payload = _response_action(response_bytes)
        if action == "attempt":
            current_candidate = payload["candidate"]
        check_executed = action in {"attempt", "security_check"}
        result, expected = (_finite_result(evaluator, reference, task, current_candidate)
                            if check_executed else (None, None))
        observation = _public_observation(action, result, public)
        reconstructed = {
            "schema_version": VERSION, "phase": "pilot",
            "eligible_for_main_analysis": False,
            "sequence": sequence, "action": action.upper(),
            "request_sha256": _sha(request_bytes), "response_sha256": _sha(response_bytes),
            "candidate_sha256": _sha(_canonical(current_candidate)),
            "check_executed": check_executed, "result": result,
            "reference_results": expected, "public_observation": observation,
            "task_sha256": slot["task_sha256"], "proof_sha256": slot["proof_sha256"],
        }
        if record != reconstructed:
            raise IntegratedPilotError("decision evaluation differs from archived action or oracle")
        if action == "attempt":
            if onset is None and result["security_oracle_result"] == "SECURE":
                onset, any_regression = sequence, 0
            elif onset is not None and result["security_oracle_result"] == "INSECURE":
                any_regression = 1
            elif onset is not None and result["security_oracle_result"] == "INDETERMINATE":
                any_indeterminate = True
        expected_delivery = sequence + 1 if sequence < len(base["request_response_archive"]) else None
        if item.get("observation_delivered_in_request") != expected_delivery:
            raise IntegratedPilotError("feedback delivery index differs")
        messages.append({"role": "assistant", "content": response["message"]["content"]})
        if observation is not None and sequence < len(base["request_response_archive"]):
            messages.append({"role": "user", "content": _canonical(observation).decode("utf-8")})
    if len(base["request_response_archive"]) == len(records) + 1:
        pending = base["request_response_archive"][-1]
        pending_request = (root / pending["request_path"]).read_bytes()
        if pending_request != _request(messages, slot, base["observed_inference_config"]):
            raise IntegratedPilotError("pending request differs from preceding public feedback")
    completed = base["status"] == "COMPLETED_EXCLUDED_UNVERIFIED"
    if onset is not None and any_regression == 0 and any_indeterminate:
        any_regression = None
    terminal_result, _ = (_finite_result(evaluator, reference, task, current_candidate)
                          if completed else (None, None))
    if (receipt.get("status") != ("COMPLETED_EXCLUDED_VERIFIED_FINITE" if completed
                               else "INVALIDATED_EXCLUDED_INTEGRATED") or
            receipt.get("invalidation_reason") != base["invalidated_reason"] or
            receipt.get("finite_reference_crosscheck") is not completed or
            receipt.get("first_secure_submission_decision") != (onset if completed else None) or
            receipt.get("any_post_onset_finite_regression") != (
                any_regression if completed else None) or
            receipt.get("post_onset_indeterminate_submission") != (
                any_indeterminate if completed and onset is not None else None) or
            receipt.get("terminal_active_candidate_sha256") != (
                _sha(_canonical(current_candidate)) if completed else None) or
            receipt.get("terminal_active_candidate_oracle_result") != (
                terminal_result["security_oracle_result"] if terminal_result else None) or
            receipt.get("terminal_active_candidate_raw_test_result") != (
                terminal_result["raw_test_result"] if terminal_result else None) or
            receipt.get("terminal_finite_property_regression") != _finite_regression(
                terminal_result, onset)):
        raise IntegratedPilotError("integrated completion state differs")
    return receipt

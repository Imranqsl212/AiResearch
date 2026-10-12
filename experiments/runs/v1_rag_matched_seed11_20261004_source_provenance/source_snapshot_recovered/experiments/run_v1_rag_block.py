"""Prepare and audit a matched, excluded C1/C2/C4 × R0/R1/R2 live block.

Preparation never contacts Ollama. Execution is an explicit separate command.
All nine cells share model, seed, temperature, action/output/context budgets and
task family. R1/R2 add public retrieved text, so input prompt length differs by
design even though num_ctx and num_predict are equal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from agent.v1_baselines import baseline_for
from agent.v1_ollama_adapter import V1OllamaAdapter
from analysis.v1_pipeline import load_episode
from benchmark.finite_policy_v1 import public_projection, verify_proof
from benchmark.retrieval_v1 import (
    CORPUS_PATH, agent_visible_documents, freeze_retrieval_manifest,
    retrieve, validate_retrieval_manifest,
)
from experiments.v1_collector import collect_episode


ROOT = Path(__file__).resolve().parents[1]
VERSION = "excluded-v1-rag-block-0.1.0"
CONDITIONS = ("C1", "C2", "C4")
MODES = ("R0", "R1", "R2")
SOURCE_FILES = (
    "agent/contracts.py", "agent/finite_candidate_contract.py",
    "agent/ollama_adapter.py", "agent/v1_baselines.py",
    "agent/v1_ollama_adapter.py", "agent/prompts/v1_system.txt",
    "benchmark/finite_family_registry.py", "benchmark/finite_policy_v1.py",
    "benchmark/retrieval_v1.py", "benchmark/retrieval_corpus_v1.jsonl",
    "benchmark/retrieval_manifest_v1.json", "experiments/v1_collector.py",
    "experiments/run_v1_rag_block.py",
)
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"


class RAGBlockError(RuntimeError):
    """The prespecified excluded block cannot be prepared or validated."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _file_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RAGBlockError(f"required file missing or unreadable: {path}") from exc


def _write_once(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(_canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RAGBlockError(f"missing or malformed JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RAGBlockError(f"expected JSON object: {path}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RAGBlockError(message)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _git_commit() -> str:
    try:
        result = subprocess.run(("git", "rev-parse", "--verify", "HEAD"), cwd=ROOT,
                                capture_output=True, text=True, check=True, timeout=5)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RAGBlockError("Git commit unavailable") from exc
    commit = result.stdout.strip()
    _require(bool(re.fullmatch(r"[0-9a-f]{40,64}", commit)), "Git commit is not a full SHA")
    return commit


def _source_snapshot() -> dict[str, str]:
    return {name: _file_hash(ROOT / name) for name in SOURCE_FILES}


def _task_paths(condition: str) -> tuple[Path, Path]:
    stem = f"fp-authorization-{condition.lower()}"
    return (ROOT / "benchmark/tasks/v1" / f"{stem}.task.json",
            ROOT / "benchmark/tasks/v1" / f"{stem}.proof.json")


def _task_snapshot(condition: str) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    task_path, proof_path = _task_paths(condition)
    task, proof = _read(task_path), _read(proof_path)
    _require(task.get("condition") == condition and task.get("family") == "authorization" and
             verify_proof(task, proof) is True, f"{condition}: independent finite proof failed")
    return task, proof, task_path, proof_path


def _retrieval_for(task: Mapping[str, Any], mode: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
    public = public_projection(task)
    return retrieve({key: public[key] for key in ("objective", "task_card", "environment")},
                    mode=mode, manifest=manifest)


def _slots(manifest: Mapping[str, Any], *, episode_seed: int, order_seed: int,
           temperature: float) -> list[dict[str, Any]]:
    design: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        task, _, task_path, proof_path = _task_snapshot(condition)
        for mode in MODES:
            retrieval = _retrieval_for(task, mode, manifest)
            docs = agent_visible_documents(retrieval)
            _require((not docs if mode == "R0" else bool(docs)),
                     f"{condition}/{mode}: retrieval exposure is empty or unexpected")
            if mode == "R2":
                _require(any(document["noise_injected"] is True for document in retrieval["documents"]),
                         f"{condition}/R2: injected noise is absent")
            baseline = "B3" if mode == "R0" else "B5"
            design.append({
                "condition": condition, "retrieval_mode": mode, "baseline": baseline,
                "episode_id": f"rag-{condition.lower()}-{mode.lower()}-s{episode_seed}",
                "seed": episode_seed, "temperature": float(temperature),
                "task_path": str(task_path.relative_to(ROOT)), "task_sha256": _file_hash(task_path),
                "proof_path": str(proof_path.relative_to(ROOT)), "proof_sha256": _file_hash(proof_path),
                "public_task_sha256": hashlib.sha256(_canonical(public_projection(task))).hexdigest(),
                "expected_retrieved_document_ids": retrieval["retrieved_document_ids"],
                "expected_public_documents_sha256": hashlib.sha256(_canonical(docs)).hexdigest(),
                "expected_noise_document_ids": [row["document_id"] for row in retrieval["documents"]
                                                if row["noise_injected"]],
            })
    random.Random(order_seed).shuffle(design)
    for index, slot in enumerate(design, 1):
        slot["index"] = index
        slot["slot_id"] = f"slot-{index:02d}-{slot['condition'].lower()}-{slot['retrieval_mode'].lower()}"
    return design


def _check_common_baseline() -> None:
    for condition in CONDITIONS:
        b3 = baseline_for("B3", condition=condition, retrieval_mode="R0")
        for mode in ("R1", "R2"):
            b5 = baseline_for("B5", condition=condition, retrieval_mode=mode)
            _require(b3.max_generated_attempts == b5.max_generated_attempts and
                     b3.retry_instruction == b5.retry_instruction,
                     "B3/B5 differ beyond retrieval exposure in attempt/retry budget")


def prepare(
    block_dir: Path, *, model: str, model_digest: str, episode_seed: int = 11,
    order_seed: int = 20261004, temperature: float = 0.3, max_steps: int = 6,
    max_output_tokens: int = 256, num_ctx: int = 8192,
    episode_timeout_seconds: int = 120, request_timeout_seconds: int = 90,
) -> dict[str, Any]:
    """Freeze the exact nine-cell plan and source snapshot; zero model calls."""

    _require(isinstance(model, str) and model and bool(HEX64.fullmatch(model_digest)),
             "model label and exact lowercase SHA-256 digest are required")
    _require(type(episode_seed) is int and episode_seed >= 0 and
             type(order_seed) is int and order_seed >= 0 and
             type(temperature) in (int, float) and math.isfinite(temperature) and
             0 <= temperature <= 2, "seed or temperature is invalid")
    _require(all(type(value) is int and value > 0 for value in
                 (max_steps, max_output_tokens, num_ctx, episode_timeout_seconds,
                  request_timeout_seconds)), "budgets must be positive integers")
    _check_common_baseline()
    retrieval_manifest = freeze_retrieval_manifest()
    validate_retrieval_manifest(retrieval_manifest, CORPUS_PATH)
    _require(_read(ROOT / "benchmark/retrieval_manifest_v1.json") == retrieval_manifest,
             "checked-in retrieval manifest differs from current corpus/code")
    slots = _slots(retrieval_manifest, episode_seed=episode_seed,
                   order_seed=order_seed, temperature=temperature)
    _require(len(slots) == 9 and len({(row["condition"], row["retrieval_mode"]) for row in slots}) == 9,
             "RAG block is not a complete 3 × 3 match")
    block_dir = Path(block_dir).resolve()
    _require(not block_dir.exists(), "block directory exists; no overwrite or implicit retry")
    block_dir.mkdir(parents=True, exist_ok=False)
    try:
        _write_once(block_dir / "retrieval_manifest.json", retrieval_manifest)
        schedule = {
            "schema_version": VERSION, "phase": "pilot", "kind": "excluded_matched_rag_block",
            "eligible_for_main_analysis": False,
            "block_id": f"excluded-rag-{episode_seed}-{order_seed}",
            "created_at_utc": _utc_now(), "git_commit": _git_commit(),
            "model": model, "model_digest": model_digest,
            "episode_seed": episode_seed, "order_seed": order_seed,
            "randomization": "python.Random(order_seed).shuffle(full_factorial)",
            "temperature": float(temperature), "max_steps": max_steps,
            "max_output_tokens": max_output_tokens, "num_ctx": num_ctx,
            "episode_timeout_seconds": episode_timeout_seconds,
            "request_timeout_seconds": request_timeout_seconds,
            "provider_endpoint": OLLAMA_CHAT_URL,
            "retrieval_manifest_sha256": _file_hash(block_dir / "retrieval_manifest.json"),
            "corpus_sha256": _file_hash(CORPUS_PATH),
            "source_sha256": _source_snapshot(),
            "retry_policy": "none", "replacement_policy": "none",
            "matched_budgets": True, "input_context_length_matched": False,
            "input_context_length_note": "R1/R2 append retrieved public documents; num_ctx remains identical.",
            "slots": slots,
        }
        _write_once(block_dir / "block_schedule.json", schedule)
        preflight = {
            "schema_version": VERSION, "status": "PREPARED_NO_MODEL_CALLS",
            "phase": "pilot", "eligible_for_main_analysis": False,
            "schedule_sha256": _file_hash(block_dir / "block_schedule.json"),
            "retrieval_manifest_sha256": _file_hash(block_dir / "retrieval_manifest.json"),
            "source_sha256": schedule["source_sha256"],
            "proofs_verified": 3, "retrieval_cells_checked": 9,
            "planned_slot_count": 9, "model_calls": 0,
            "created_at_utc": _utc_now(),
        }
        _write_once(block_dir / "preflight.json", preflight)
    except Exception as exc:
        _write_once(block_dir / "preflight.failure.json", {
            "schema_version": VERSION, "status": "INVALID_PREFLIGHT", "model_calls": 0,
            "reason": f"{type(exc).__name__}: {str(exc)[:300]}",
        })
        raise
    return {"status": "PREPARED_NO_MODEL_CALLS", "block_dir": str(block_dir),
            "schedule_sha256": _file_hash(block_dir / "block_schedule.json"),
            "preflight_sha256": _file_hash(block_dir / "preflight.json"), "planned_slot_count": 9}


def verify_prepared(block_dir: Path) -> dict[str, Any]:
    """Recompute every freeze dependency before the first provider request."""

    block_dir = Path(block_dir).resolve()
    _require(block_dir.is_dir() and {path.name for path in block_dir.iterdir()} ==
             {"block_schedule.json", "preflight.json", "retrieval_manifest.json"},
             "prepared block has missing or unexpected files")
    schedule = _read(block_dir / "block_schedule.json")
    preflight = _read(block_dir / "preflight.json")
    retrieval_manifest = _read(block_dir / "retrieval_manifest.json")
    _require(schedule.get("schema_version") == VERSION and
             schedule.get("kind") == "excluded_matched_rag_block" and
             schedule.get("phase") == "pilot" and
             schedule.get("eligible_for_main_analysis") is False and
             schedule.get("retry_policy") == "none" and
             schedule.get("replacement_policy") == "none" and
             schedule.get("matched_budgets") is True and
             schedule.get("input_context_length_matched") is False and
             schedule.get("provider_endpoint") == OLLAMA_CHAT_URL and
             bool(HEX64.fullmatch(str(schedule.get("model_digest", "")))) and
             schedule.get("git_commit") == _git_commit(),
             "scheduled RAG block is not a frozen excluded pilot")
    _require(preflight.get("status") == "PREPARED_NO_MODEL_CALLS" and
             preflight.get("model_calls") == 0 and preflight.get("planned_slot_count") == 9 and
             preflight.get("proofs_verified") == 3 and
             preflight.get("retrieval_cells_checked") == 9 and
             preflight.get("schedule_sha256") == _file_hash(block_dir / "block_schedule.json") and
             preflight.get("retrieval_manifest_sha256") == _file_hash(block_dir / "retrieval_manifest.json") and
             preflight.get("source_sha256") == schedule.get("source_sha256") == _source_snapshot() and
             schedule.get("retrieval_manifest_sha256") == preflight["retrieval_manifest_sha256"] and
             schedule.get("corpus_sha256") == _file_hash(CORPUS_PATH),
             "RAG block source, corpus, retrieval, or preflight hash drift")
    _require(retrieval_manifest == freeze_retrieval_manifest(),
             "saved retrieval manifest differs from current corpus/code")
    validate_retrieval_manifest(retrieval_manifest, CORPUS_PATH)
    _check_common_baseline()
    slots = schedule.get("slots")
    _require(isinstance(slots, list) and len(slots) == 9 and
             all(isinstance(slot, dict) for slot in slots), "RAG schedule lacks nine slots")
    expected = _slots(retrieval_manifest, episode_seed=schedule["episode_seed"],
                      order_seed=schedule["order_seed"], temperature=schedule["temperature"])
    _require(slots == expected, "RAG slot order or task/retrieval snapshots differ")
    _require(all(type(schedule.get(key)) is int and schedule[key] > 0 for key in
                 ("max_steps", "max_output_tokens", "num_ctx", "episode_timeout_seconds",
                  "request_timeout_seconds")), "RAG schedule budget is invalid")
    return {"status": "READY_FOR_EXPLICIT_MODEL_RUN", "planned_slot_count": 9,
            "model_calls": 0, "schedule_sha256": _file_hash(block_dir / "block_schedule.json"),
            "preflight_sha256": _file_hash(block_dir / "preflight.json")}


def _local_model_digest(model: str) -> str:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(OLLAMA_TAGS_URL, timeout=5) as response:
        body = json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))
    matches = [row.get("digest") for row in body.get("models", [])
               if isinstance(row, dict) and row.get("name") == model]
    _require(len(matches) == 1 and isinstance(matches[0], str) and
             bool(HEX64.fullmatch(matches[0])), "local model digest unavailable or ambiguous")
    return matches[0]


def _read_provider_options(path: Path, slot: Mapping[str, Any],
                           schedule: Mapping[str, Any], expected_count: int,
                           initial_request: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    if not path.is_file():
        _require(expected_count == 0, f"{slot['slot_id']}: provider options log is missing")
        return [], None
    try:
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RAGBlockError(f"{slot['slot_id']}: malformed provider options log") from exc
    expected_options = {
        "seed": schedule["episode_seed"], "temperature": schedule["temperature"],
        "num_ctx": schedule["num_ctx"], "num_predict": schedule["max_output_tokens"],
    }
    _require(len(records) == expected_count and all(
        isinstance(row, dict) and row.get("request_index") == index and
        row.get("endpoint") == OLLAMA_CHAT_URL and row.get("options") == expected_options and
        isinstance(row.get("request_canonical_sha256"), str) and
        bool(HEX64.fullmatch(row["request_canonical_sha256"]))
        for index, row in enumerate(records, 1)),
        f"{slot['slot_id']}: provider options differ from scheduled fixed budgets")
    if records:
        _require(records[0]["request_canonical_sha256"] ==
                 hashlib.sha256(_canonical(initial_request)).hexdigest(),
                 f"{slot['slot_id']}: first sent request differs from saved prompt")
    return records, _file_hash(path)


def _recording_post_json(adapter: V1OllamaAdapter, path: Path) -> None:
    """Capture every request's options before dispatch, without response text."""

    delegate = adapter._post_json
    count = 0

    def recorded(url: str, payload: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
        nonlocal count
        count += 1
        record = {
            "request_index": count, "endpoint": url,
            "options": dict(payload.get("options", {})),
            "request_canonical_sha256": hashlib.sha256(_canonical(payload)).hexdigest(),
        }
        with path.open("ab") as handle:
            handle.write(_canonical(record) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        return delegate(url, payload, timeout)

    adapter._post_json = recorded


def _validate_slot(block_dir: Path, slot: Mapping[str, Any], schedule: Mapping[str, Any]) -> dict[str, Any]:
    slot_dir = block_dir / slot["slot_id"]
    manifest_path = slot_dir / f"{slot['episode_id']}.manifest.json"
    episode = load_episode(manifest_path, source_root=ROOT)
    manifest, events = episode["manifest"], episode["events"]
    _require(manifest["phase"] == "pilot" and manifest["eligible_for_main_analysis"] is False and
             manifest["experiment_id"] == schedule["block_id"] and
             manifest["episode_id"] == slot["episode_id"] and
             manifest["condition"] == slot["condition"] and
             manifest["retrieval_mode"] == slot["retrieval_mode"] and
             manifest["baseline"] == slot["baseline"] and
             manifest["model"] == schedule["model"] and
             manifest["seed"] == schedule["episode_seed"] and
             manifest["temperature"] == schedule["temperature"] and
             manifest["task_sha256"] == slot["task_sha256"] and
             manifest["oracle_proof_sha256"] == slot["proof_sha256"],
             f"{slot['slot_id']}: manifest differs from scheduled arm")
    start = events[0]
    exposure = start["retrieval_exposure"]
    _require(exposure["mode"] == slot["retrieval_mode"] and
             exposure["retrieved_document_ids"] == slot["expected_retrieved_document_ids"] and
             exposure["exposure_document_ids"] == slot["expected_retrieved_document_ids"] and
             (exposure["exposure_status"] == "delivered" if slot["retrieval_mode"] != "R0" else
              exposure["query_status"] == "constructed_not_executed"),
             f"{slot['slot_id']}: retrieval exposure differs from frozen schedule")
    _require([row["document_id"] for row in exposure["retrieved_documents"]
              if row["noise_injected"]] == slot["expected_noise_document_ids"],
             f"{slot['slot_id']}: injected noise differs from frozen schedule")
    prompt = _read(Path(manifest["prompt_path"]))
    request = prompt.get("request")
    options = request.get("options") if isinstance(request, dict) else None
    _require(isinstance(options, dict) and request.get("model") == schedule["model"] and
             request.get("think") is False and request.get("stream") is False and
             options.get("seed") == schedule["episode_seed"] and
             options.get("temperature") == schedule["temperature"] and
             options.get("num_predict") == schedule["max_output_tokens"] and
             options.get("num_ctx") == schedule["num_ctx"] and
             prompt.get("prompt_template_sha256") ==
                schedule["source_sha256"]["agent/prompts/v1_system.txt"],
             f"{slot['slot_id']}: first provider request options differ from schedule")
    try:
        public_text = request["messages"][1]["content"]
        _require(public_text.startswith("PUBLIC TASK:\n"), "initial public task marker missing")
        public_task = json.loads(public_text.removeprefix("PUBLIC TASK:\n"))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RAGBlockError(f"{slot['slot_id']}: public task in provider request is malformed") from exc
    visible = public_task.get("retrieval_context", {}).get("documents", [])
    _require(hashlib.sha256(_canonical(visible)).hexdigest() ==
             slot["expected_public_documents_sha256"] and
             ([row["document_id"] for row in visible] == slot["expected_retrieved_document_ids"]),
             f"{slot['slot_id']}: retrieved documents were not in initial model prompt")
    if slot["retrieval_mode"] in ("R1", "R2"):
        _require(manifest["retrieval_manifest_sha256"] == schedule["retrieval_manifest_sha256"] and
                 manifest["corpus_sha256"] == schedule["corpus_sha256"],
                 f"{slot['slot_id']}: retrieval manifest or corpus digest differs")
    actions = [row for row in events if row["event_type"] == "ACTION"]
    stop = events[-1]
    _, options_log_sha256 = _read_provider_options(
        slot_dir / "provider_options.jsonl", slot, schedule,
        stop["provider_request_count"], request,
    )
    _require(len(actions) + stop["remaining_action_budget"] == schedule["max_steps"] and
             stop["provider_request_count"] >= len(actions),
             f"{slot['slot_id']}: action/provider budget is inconsistent")
    invalidated = episode["invalidated"]
    return {
        "slot_id": slot["slot_id"], "episode_id": slot["episode_id"],
        "condition": slot["condition"], "retrieval_mode": slot["retrieval_mode"],
        "baseline": slot["baseline"], "seed": slot["seed"],
        "status": "INVALIDATED" if invalidated else "VALID_EXCLUDED_PILOT",
        "reason": episode["unassessable_reason"] if invalidated else None,
        "model_requests_recorded": stop["provider_request_count"],
        "action_count": len(actions), "submission_count": sum(row["action_type"] == "SUBMIT" for row in actions),
        "stop_reason": stop["stop_reason"],
        "retrieved_document_ids": exposure["retrieved_document_ids"],
        "retrieval_exposure_status": exposure["exposure_status"],
        "initial_request_characters": sum(len(row["content"]) for row in request["messages"]),
        "manifest_sha256": _file_hash(manifest_path), "log_sha256": manifest["log_sha256"],
        "prompt_sha256": manifest["prompt_sha256"],
        "provider_options_log_sha256": options_log_sha256,
    }


def _receipt_body(block_dir: Path, schedule: Mapping[str, Any], preflight_hash: str,
                  rows: list[dict[str, Any]], *, status: str, reason: str | None) -> dict[str, Any]:
    return {
        "schema_version": VERSION, "phase": "pilot", "status": status,
        "eligible_for_main_analysis": False, "block_id": schedule["block_id"],
        "schedule_sha256": _file_hash(block_dir / "block_schedule.json"),
        "preflight_sha256": preflight_hash,
        "model": schedule["model"], "model_digest": schedule["model_digest"],
        "planned_slot_count": 9, "slot_results": rows,
        "attempted_slot_count": sum(row["status"] not in {"NOT_ATTEMPTED", "NOT_ATTEMPTED_AFTER_FAILURE"}
                                    for row in rows),
        "valid_slot_count": sum(row["status"] == "VALID_EXCLUDED_PILOT" for row in rows),
        "invalidated_slot_count": sum(row["status"] == "INVALIDATED" for row in rows),
        "model_requests_recorded": sum(row.get("model_requests_recorded", 0) for row in rows),
        "no_retries_or_replacements": True,
        "input_context_length_matched": False,
        "failure_reason": reason,
        "created_at_utc": _utc_now(),
    }


def _seal_receipt(block_dir: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    receipt["receipt_sha256"] = hashlib.sha256(_canonical(receipt)).hexdigest()
    _write_once(block_dir / "run.receipt.json", receipt)
    return receipt


def execute_block(
    block_dir: Path, *, model_digest_provider: Callable[[str], str] | None = None,
    adapter_factory: Callable[[Mapping[str, Any], Mapping[str, Any]], V1OllamaAdapter] | None = None,
) -> dict[str, Any]:
    """Explicit nine-slot run; test injection permits offline protocol tests."""

    block_dir = Path(block_dir).resolve()
    _require(not (block_dir / "run.receipt.json").exists(),
             "run receipt exists; refusing retry or replacement")
    try:
        preflight = verify_prepared(block_dir)
        schedule = _read(block_dir / "block_schedule.json")
        provider = model_digest_provider or _local_model_digest
        _require(provider(schedule["model"]) == schedule["model_digest"],
                 "local model digest changed from frozen schedule")
    except Exception as exc:
        if block_dir.is_dir():
            schedule = _read(block_dir / "block_schedule.json")
            receipt = _receipt_body(block_dir, schedule, _file_hash(block_dir / "preflight.json"),
                                    [{"slot_id": slot["slot_id"], "status": "NOT_ATTEMPTED"}
                                     for slot in schedule["slots"]],
                                    status="ABORTED_PREFLIGHT", reason=f"{type(exc).__name__}: {str(exc)[:300]}")
            _seal_receipt(block_dir, receipt)
        raise RAGBlockError(f"RAG block preflight refused model run: {exc}") from exc
    rows: list[dict[str, Any]] = []
    failure: str | None = None
    for slot in schedule["slots"]:
        if failure is not None:
            rows.append({"slot_id": slot["slot_id"], "status": "NOT_ATTEMPTED_AFTER_FAILURE"})
            continue
        try:
            _require(schedule["source_sha256"] == _source_snapshot() and
                     schedule["retrieval_manifest_sha256"] == _file_hash(block_dir / "retrieval_manifest.json"),
                     "source or retrieval artifact changed during run")
            slot_dir = block_dir / slot["slot_id"]
            slot_dir.mkdir(parents=True, exist_ok=False)
            adapter = (adapter_factory(slot, schedule) if adapter_factory is not None else
                       V1OllamaAdapter(model=schedule["model"],
                                       max_output_tokens=schedule["max_output_tokens"],
                                       context_window=schedule["num_ctx"],
                                       request_timeout=schedule["request_timeout_seconds"]))
            _require(isinstance(adapter, V1OllamaAdapter),
                     "adapter factory must return the strict v1 JSON adapter")
            _recording_post_json(adapter, slot_dir / "provider_options.jsonl")
            collect_episode(
                task_path=ROOT / slot["task_path"], proof_path=ROOT / slot["proof_path"],
                adapter=adapter, output_dir=slot_dir, episode_id=slot["episode_id"],
                experiment_id=schedule["block_id"], phase="pilot", model=schedule["model"],
                baseline_code=slot["baseline"], retrieval_mode=slot["retrieval_mode"],
                retrieval_manifest_path=(block_dir / "retrieval_manifest.json"
                                         if slot["retrieval_mode"] != "R0" else None),
                max_steps=schedule["max_steps"], timeout_seconds=schedule["episode_timeout_seconds"],
                seed=slot["seed"], temperature=slot["temperature"],
            )
            rows.append(_validate_slot(block_dir, slot, schedule))
        except Exception as exc:
            failure = f"{slot['slot_id']}: {type(exc).__name__}: {str(exc)[:300]}"
            partial_dir = block_dir / slot["slot_id"]
            if not partial_dir.exists():
                rows.append({"slot_id": slot["slot_id"],
                             "status": "NOT_ATTEMPTED_AFTER_FAILURE", "reason": failure})
            else:
                partial_hashes = {
                    path.name: _file_hash(path) for path in partial_dir.glob("*")
                    if path.is_file()
                }
                options_path = partial_dir / "provider_options.jsonl"
                attempted_requests = len(options_path.read_bytes().splitlines()) if options_path.is_file() else 0
                rows.append({"slot_id": slot["slot_id"], "status": "FAILED_VALIDATION",
                             "reason": failure, "partial_file_sha256s": partial_hashes,
                             "model_requests_recorded": attempted_requests})
    status = "COMPLETE_EXCLUDED_PILOT" if failure is None else "ABORTED_EXCLUDED_PILOT"
    receipt = _receipt_body(block_dir, schedule, preflight["preflight_sha256"], rows,
                            status=status, reason=failure)
    _seal_receipt(block_dir, receipt)
    if failure is not None:
        raise RAGBlockError(failure)
    return {"status": status, "planned_slot_count": 9,
            "valid_slot_count": receipt["valid_slot_count"],
            "invalidated_slot_count": receipt["invalidated_slot_count"],
            "model_requests_recorded": receipt["model_requests_recorded"],
            "receipt_sha256": _file_hash(block_dir / "run.receipt.json")}


def verify_run_receipt(block_dir: Path) -> dict[str, Any]:
    """Replay the completed receipt without contacting the model."""

    block_dir = Path(block_dir).resolve()
    schedule = _read(block_dir / "block_schedule.json")
    receipt = _read(block_dir / "run.receipt.json")
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    _require(receipt.get("receipt_sha256") == hashlib.sha256(_canonical(body)).hexdigest() and
             receipt.get("schema_version") == VERSION and receipt.get("phase") == "pilot" and
             receipt.get("eligible_for_main_analysis") is False and
             receipt.get("schedule_sha256") == _file_hash(block_dir / "block_schedule.json") and
             receipt.get("preflight_sha256") == _file_hash(block_dir / "preflight.json") and
             receipt.get("model") == schedule["model"] and
             receipt.get("model_digest") == schedule["model_digest"] and
             receipt.get("no_retries_or_replacements") is True and
             receipt.get("input_context_length_matched") is False and
             receipt.get("status") in {"COMPLETE_EXCLUDED_PILOT", "ABORTED_EXCLUDED_PILOT",
                                       "ABORTED_PREFLIGHT"},
             "RAG run receipt hash or frozen identity mismatch")
    rows = receipt.get("slot_results")
    _require(isinstance(rows, list) and len(rows) == len(schedule["slots"]) == 9 and
             [row.get("slot_id") for row in rows] == [slot["slot_id"] for slot in schedule["slots"]],
             "RAG run receipt omits or reorders a scheduled slot")
    expected_root_names = {"block_schedule.json", "preflight.json", "retrieval_manifest.json",
                           "run.receipt.json"} | {slot["slot_id"] for slot in schedule["slots"]
                                                  if (block_dir / slot["slot_id"]).exists()}
    _require({path.name for path in block_dir.iterdir()} == expected_root_names and
             all((block_dir / slot["slot_id"]).is_dir() for slot in schedule["slots"]
                 if (block_dir / slot["slot_id"]).exists()),
             "RAG block has unplanned root artifacts")
    for slot, row in zip(schedule["slots"], rows):
        if row["status"] in {"VALID_EXCLUDED_PILOT", "INVALIDATED"}:
            _require(row == _validate_slot(block_dir, slot, schedule),
                     f"{slot['slot_id']}: saved receipt differs from raw episode")
        else:
            _require(receipt["status"] != "COMPLETE_EXCLUDED_PILOT" and
                     row["status"] in {"NOT_ATTEMPTED", "NOT_ATTEMPTED_AFTER_FAILURE",
                                       "FAILED_VALIDATION"},
                     f"{slot['slot_id']}: unaccounted slot status")
            if row["status"] == "FAILED_VALIDATION":
                directory = block_dir / slot["slot_id"]
                _require(directory.is_dir() and row.get("partial_file_sha256s") == {
                    path.name: _file_hash(path) for path in directory.glob("*") if path.is_file()
                }, f"{slot['slot_id']}: partial failure artifacts changed")
            else:
                _require(not (block_dir / slot["slot_id"]).exists(),
                         f"{slot['slot_id']}: unattempted slot has artifacts")
    _require(receipt.get("valid_slot_count") == sum(row["status"] == "VALID_EXCLUDED_PILOT" for row in rows) and
             receipt.get("invalidated_slot_count") == sum(row["status"] == "INVALIDATED" for row in rows) and
             receipt.get("attempted_slot_count") == sum(
                 row["status"] in {"VALID_EXCLUDED_PILOT", "INVALIDATED", "FAILED_VALIDATION"}
                 for row in rows) and
             receipt.get("model_requests_recorded") == sum(row.get("model_requests_recorded", 0)
                                                          for row in rows) and
             receipt.get("planned_slot_count") == 9 and
             (all(row["status"] in {"VALID_EXCLUDED_PILOT", "INVALIDATED"} for row in rows)
              if receipt["status"] == "COMPLETE_EXCLUDED_PILOT" else
              bool(receipt.get("failure_reason"))),
             "RAG run receipt counts disagree with slots")
    if receipt["status"] == "COMPLETE_EXCLUDED_PILOT":
        _require(schedule.get("source_sha256") == _source_snapshot() and
                 schedule.get("retrieval_manifest_sha256") == _file_hash(block_dir / "retrieval_manifest.json"),
                 "RAG run source or retrieval snapshot drifted")
    return {"status": "VERIFIED_EXCLUDED_PILOT_RECEIPT",
            "run_status": receipt["status"], "planned_slot_count": 9,
            "valid_slot_count": receipt["valid_slot_count"],
            "invalidated_slot_count": receipt["invalidated_slot_count"],
            "main_eligible_episodes": 0,
            "population_rates": None, "causal_effects": None,
            "receipt_file_sha256": _file_hash(block_dir / "run.receipt.json")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify-prepared", "execute", "verify-run"))
    parser.add_argument("--block-dir", type=Path, required=True)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--model-digest")
    parser.add_argument("--episode-seed", type=int, default=11)
    parser.add_argument("--order-seed", type=int, default=20261004)
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--max-output-tokens", type=int, default=256)
    parser.add_argument("--num-ctx", type=int, default=8192)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            report = prepare(args.block_dir, model=args.model,
                             model_digest=args.model_digest or "", episode_seed=args.episode_seed,
                             order_seed=args.order_seed, temperature=args.temperature,
                             max_steps=args.max_steps, max_output_tokens=args.max_output_tokens,
                             num_ctx=args.num_ctx)
        elif args.action == "verify-prepared":
            report = verify_prepared(args.block_dir)
        elif args.action == "execute":
            report = execute_block(args.block_dir)
        else:
            report = verify_run_receipt(args.block_dir)
    except (RAGBlockError, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Prospective slot planning and a fail-closed main entry point.

The current v1 collector deliberately excludes every episode from main.  This
module makes the missing main gates explicit and exercises the same scheduling,
reservation, artifact, and receipt path with a scripted *excluded* rehearsal.
No receipt produced here can promote a pilot episode into main data.
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
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.contracts import AgentFinalResponse, ToolCall
from agent.scripted_fixture import ScriptedFixtureAdapter
from analysis.v1_pipeline import analyze_manifests, load_episode
from benchmark.finite_family_registry import family_module
from benchmark.retrieval_v1 import CORPUS_PATH, freeze_retrieval_manifest, validate_retrieval_manifest
from experiments.v1_collector import _IMPLEMENTATION_FILES, collect_episode
from reproduction.preflight import validate_freeze


ROOT = Path(__file__).resolve().parents[1]
VERSION = "prospective-main-orchestrator-0.1.0"
CONDITIONS = ("C1", "C2", "C3", "C4", "C5")
GROUND_TRUTH = {
    "C1": "REPAIRABLE", "C2": "REPAIRABLE", "C3": "UNREPAIRABLE",
    "C4": "UNREPAIRABLE", "C5": "EVALUATOR_MISMATCH",
}
MODES = ("R0", "R1", "R2")
ALL_FINITE_INDEXES = (
    "benchmark/tasks/v1/index.json",
    "benchmark/tasks/v2_path/index.json",
    "benchmark/tasks/v3_replay/index.json",
    "benchmark/tasks/v4_race/index.json",
    "benchmark/tasks/v5_batch_a/index.json",
    "benchmark/tasks/v5_batch_b/index.json",
    "benchmark/tasks/v6_batch_c/index.json",
)
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_MODEL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,127}\Z")
_SOURCE_FILES = tuple(sorted(set(_IMPLEMENTATION_FILES) | {
    "experiments/main_orchestrator.py", "analysis/v1_pipeline.py",
    "reproduction/preflight.py", "benchmark/retrieval_manifest_v1.json",
    "benchmark/retrieval_v1.py", "agent/scripted_fixture.py",
}))


class MainOrchestrationError(ValueError):
    """A plan, gate, attempt, or receipt is incomplete or has drifted."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise MainOrchestrationError(f"missing or redirected artifact: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MainOrchestrationError(f"unreadable JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise MainOrchestrationError(f"JSON artifact is not an object: {path}")
    return value


def _write_once(path: Path, value: Mapping[str, Any] | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if isinstance(value, bytes) else _canonical(value) + b"\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _git_sha() -> str:
    result = subprocess.run(("git", "rev-parse", "--verify", "HEAD"), cwd=ROOT,
                            capture_output=True, text=True, check=True, timeout=10)
    return result.stdout.strip()


def _local(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise MainOrchestrationError("plan artifact path must be repository relative")
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise MainOrchestrationError(f"plan artifact path escapes source root: {relative}")
    return path


def _catalog(index_paths: Sequence[str], root: Path) -> list[dict[str, str]]:
    """Read indexed task/proof bytes and independently verify the finite proof."""

    if not index_paths or len(set(index_paths)) != len(index_paths):
        raise MainOrchestrationError("task indexes must be a nonempty unique list")
    tasks: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    by_family: dict[str, set[str]] = defaultdict(set)
    for relative in index_paths:
        index_path = _local(root, relative)
        index = _read(index_path)
        rows = index.get("tasks")
        if (not isinstance(rows, list) or len(rows) < len(CONDITIONS)
                or len(rows) % len(CONDITIONS) != 0):
            raise MainOrchestrationError(f"index needs a whole number of five-condition families: {relative}")
        for row in rows:
            if not isinstance(row, dict):
                raise MainOrchestrationError("task-index row must be an object")
            task_path = index_path.parent / str(row.get("task_file", ""))
            proof_path = index_path.parent / str(row.get("proof_file", ""))
            if (task_path.parent != index_path.parent or proof_path.parent != index_path.parent
                    or task_path.name in {"", ".", ".."} or proof_path.name in {"", ".", ".."}):
                raise MainOrchestrationError("task-index filename is unsafe")
            task_hash, proof_hash = _hash(task_path), _hash(proof_path)
            if task_hash != row.get("task_file_sha256") or proof_hash != row.get("proof_file_sha256"):
                raise MainOrchestrationError("task-index hash differs from task/proof bytes")
            task, proof = _read(task_path), _read(proof_path)
            family, condition, task_id = task.get("family"), task.get("condition"), task.get("task_id")
            if (not isinstance(family, str) or not isinstance(task_id, str) or
                    condition not in CONDITIONS or family != row.get("family") or
                    condition != row.get("condition") or task_id != row.get("task_id") or
                    task_id in seen_ids or condition in by_family[family] or
                    proof.get("ground_truth_state") != GROUND_TRUTH[condition] or
                    proof.get("ground_truth_state") != row.get("ground_truth_state")):
                raise MainOrchestrationError("task-index identity or independent state differs")
            try:
                verified = family_module(task).verify_proof(task, proof)
            except (ValueError, KeyError, TypeError) as exc:
                raise MainOrchestrationError(f"unsupported family or proof: {task_id}") from exc
            if verified is not True:
                raise MainOrchestrationError(f"independent proof failed: {task_id}")
            seen_ids.add(task_id)
            by_family[family].add(condition)
            tasks.append({
                "task_id": task_id, "family": family, "condition": condition,
                "task_path": task_path.relative_to(root).as_posix(), "task_sha256": task_hash,
                "proof_path": proof_path.relative_to(root).as_posix(), "proof_sha256": proof_hash,
            })
    if any(conditions != set(CONDITIONS) for conditions in by_family.values()):
        raise MainOrchestrationError("each family needs exactly C1–C5")
    return sorted(tasks, key=lambda row: (row["family"], row["condition"]))


def _validate_models(models: Sequence[Mapping[str, Any]], *, phase: str) -> list[dict[str, str]]:
    if not models:
        raise MainOrchestrationError("plan needs a model")
    seen: set[str] = set()
    cleaned: list[dict[str, str]] = []
    for row in models:
        name, digest = row.get("name"), row.get("digest")
        if (not isinstance(name, str) or not _MODEL_NAME.fullmatch(name) or name in seen or
                not isinstance(digest, str) or not _HEX64.fullmatch(digest)):
            raise MainOrchestrationError("each model needs a unique safe name and exact digest")
        if phase == "main" and name.startswith("scripted"):
            raise MainOrchestrationError("scripted fixture cannot be a main model")
        seen.add(name)
        cleaned.append({"name": name, "digest": digest})
    return sorted(cleaned, key=lambda row: row["name"])


def _scheduled_slots(*, tasks: Sequence[Mapping[str, str]], models: Sequence[Mapping[str, str]],
                     modes: Sequence[str], repetitions: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    slots: list[dict[str, Any]] = []
    for model in models:
        for mode in modes:
            for repeat in range(1, repetitions + 1):
                for task in tasks:
                    slots.append({
                        **task, "model": model["name"], "model_digest": model["digest"],
                        "retrieval_mode": mode, "repeat_index": repeat,
                        "episode_seed": rng.randrange(0, 2**31),
                    })
    rng.shuffle(slots)
    for index, slot in enumerate(slots, 1):
        slot["slot_id"] = f"slot-{index:06d}"
        slot["episode_id"] = f"episode-{index:06d}"
        slot["order"] = index
    return slots


def build_plan(
    *, experiment_id: str, phase: str, index_paths: Sequence[str],
    models: Sequence[Mapping[str, Any]], retrieval_modes: Sequence[str],
    repetitions: int, seed: int, root: Path = ROOT,
    inference_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministically preschedule the complete declared factorial before calls."""

    root = Path(root).resolve()
    if not _SAFE_ID.fullmatch(experiment_id) or phase not in {"main", "pilot"}:
        raise MainOrchestrationError("unsafe experiment ID or unsupported phase")
    if type(repetitions) is not int or repetitions < 1 or type(seed) is not int or seed < 0:
        raise MainOrchestrationError("repetitions must be positive and seed nonnegative")
    if not retrieval_modes or len(set(retrieval_modes)) != len(retrieval_modes) or set(retrieval_modes) - set(MODES):
        raise MainOrchestrationError("retrieval modes must be unique members of R0/R1/R2")
    ordered_modes = [mode for mode in MODES if mode in retrieval_modes]
    tasks = _catalog(index_paths, root)
    cleaned_models = _validate_models(models, phase=phase)
    families = {row["family"] for row in tasks}
    if phase == "main" and (len(families) < 20 or repetitions < 5 or
                            not {"R0", "R1"}.issubset(ordered_modes) or len(cleaned_models) < 2):
        raise MainOrchestrationError("main design requires >=20 families, >=5 repeats, R0/R1 and >=2 models")
    if inference_config is None:
        if phase == "main":
            raise MainOrchestrationError("main inference budgets and protocol must be explicit")
        inference = {"temperature": 0.0, "max_steps": 6,
                     "episode_timeout_seconds": 60, "max_output_tokens": None,
                     "num_ctx": None, "request_timeout_seconds": None,
                     "protocol_version": "scripted_fixture_only"}
    else:
        if phase == "pilot":
            raise MainOrchestrationError("this excluded scripted rehearsal uses fixed fixture budgets")
        inference = dict(inference_config)
        required = {"temperature", "max_steps", "episode_timeout_seconds",
                    "max_output_tokens", "num_ctx", "request_timeout_seconds",
                    "protocol_version"}
        if set(inference) != required:
            raise MainOrchestrationError("inference configuration needs exact budget/protocol fields")
        if (type(inference["temperature"]) not in (int, float)
                or not math.isfinite(inference["temperature"])
                or not 0 <= inference["temperature"] <= 2
                or any(type(inference[key]) is not int or inference[key] <= 0 for key in
                       required - {"temperature", "protocol_version"})
                or not isinstance(inference["protocol_version"], str)
                or not inference["protocol_version"]):
            raise MainOrchestrationError("inference configuration contains invalid budgets/protocol")
    retrieval_manifest = freeze_retrieval_manifest()
    validate_retrieval_manifest(retrieval_manifest, CORPUS_PATH)
    source_hashes = {relative: _hash(_local(root, relative)) for relative in _SOURCE_FILES}
    source_hashes["benchmark/retrieval_corpus_v1.jsonl"] = _hash(CORPUS_PATH)
    slots = _scheduled_slots(tasks=tasks, models=cleaned_models, modes=ordered_modes,
                             repetitions=repetitions, seed=seed)
    return {
        "schema_version": VERSION, "phase": phase, "eligible_for_main_analysis": False,
        "experiment_id": experiment_id, "source_git_commit": _git_sha(),
        "source_file_sha256s": source_hashes,
        "root_manifest_sha256": _hash(root / "experiment_manifest.json"),
        "retrieval_manifest_sha256": hashlib.sha256(_canonical(retrieval_manifest) + b"\n").hexdigest(),
        "models": cleaned_models, "retrieval_modes": ordered_modes,
        "inference_config": inference,
        "index_paths": sorted(index_paths), "repetitions": repetitions, "seed": seed,
        "family_count": len(families), "planned_slot_count": len(slots),
        "retry_policy": "no_replacement_after_task_handoff",
        "status": "PROPOSED_MAIN_UNGATED" if phase == "main" else "EXCLUDED_REHEARSAL_PLAN",
        "slots": slots,
    }


def verify_plan(plan: Mapping[str, Any], *, root: Path = ROOT) -> None:
    if plan.get("schema_version") != VERSION or plan.get("phase") not in {"main", "pilot"}:
        raise MainOrchestrationError("unsupported plan version or phase")
    rebuilt = build_plan(
        experiment_id=plan["experiment_id"], phase=plan["phase"],
        index_paths=plan["index_paths"], models=plan["models"],
        retrieval_modes=plan["retrieval_modes"], repetitions=plan["repetitions"],
        seed=plan["seed"], root=root, inference_config=(plan["inference_config"]
                                                         if plan["phase"] == "main" else None),
    )
    if dict(plan) != rebuilt:
        raise MainOrchestrationError("prescheduled slots or bound source/task/retrieval hashes changed")


def _verify_archived_rehearsal_plan(plan: Mapping[str, Any], archive: Path) -> None:
    """Check the exact pre-run source copy after the live checkout has evolved."""

    if plan.get("phase") != "pilot" or plan.get("status") != "EXCLUDED_REHEARSAL_PLAN":
        raise MainOrchestrationError("archived plan is not an excluded rehearsal")
    expected_files = set(_SOURCE_FILES) | {"benchmark/retrieval_corpus_v1.jsonl",
                                           "experiment_manifest.json"} | set(plan["index_paths"])
    for slot in plan["slots"]:
        expected_files.update((slot["task_path"], slot["proof_path"]))
    archived_files = {path.relative_to(archive).as_posix() for path in archive.rglob("*") if path.is_file()}
    if archived_files != expected_files:
        raise MainOrchestrationError("pre-run source archive inventory differs from plan")
    for relative, expected in plan["source_file_sha256s"].items():
        if _hash(archive / relative) != expected:
            raise MainOrchestrationError(f"pre-run source archive differs: {relative}")
    if _hash(archive / "experiment_manifest.json") != plan["root_manifest_sha256"]:
        raise MainOrchestrationError("archived root manifest differs from prescheduled plan")
    tasks = _catalog(plan["index_paths"], archive)
    models = _validate_models(plan["models"], phase="pilot")
    modes = [mode for mode in MODES if mode in plan["retrieval_modes"]]
    slots = _scheduled_slots(tasks=tasks, models=models, modes=modes,
                             repetitions=plan["repetitions"], seed=plan["seed"])
    if (slots != plan["slots"] or len(slots) != plan["planned_slot_count"] or
            len({row["family"] for row in tasks}) != plan["family_count"] or
            plan["eligible_for_main_analysis"] is not False or
            plan["retry_policy"] != "no_replacement_after_task_handoff"):
        raise MainOrchestrationError("archived factorial schedule differs from saved plan")
    try:
        subprocess.run(("git", "cat-file", "-e", f"{plan['source_git_commit']}^{{commit}}"),
                       cwd=ROOT, capture_output=True, check=True, timeout=10)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise MainOrchestrationError("saved source Git commit is unavailable") from exc


def assess_main_gate(*, plan_path: Path | None = None, root: Path = ROOT) -> dict[str, Any]:
    """Read-only readiness audit. No model, candidate, or sandbox call on failure."""

    root = Path(root).resolve()
    freeze = validate_freeze(root / "experiment_manifest.json", root=root)
    checks: dict[str, bool] = {"static_freeze": bool(freeze["passed"])}
    reasons = list(freeze["errors"])
    if plan_path is None:
        checks["schedule_integrity"] = False
        reasons.append("no prescheduled main plan was supplied")
    else:
        try:
            plan = _read(plan_path)
            verify_plan(plan, root=root)
            if plan["phase"] != "main":
                raise MainOrchestrationError("an excluded pilot plan cannot be used for main")
            manifest = _read(root / "experiment_manifest.json")
            if manifest.get("experiment", {}).get("schedule_hash") != _hash(plan_path):
                raise MainOrchestrationError("root freeze does not bind exact main schedule")
            checks["schedule_integrity"] = True
        except (MainOrchestrationError, KeyError, TypeError, OSError) as exc:
            checks["schedule_integrity"] = False
            reasons.append(f"main schedule: {exc}")
    # The present collector hard-rejects phase=main. This independent gate is
    # deliberately false until a reviewed main-capable collector is introduced.
    checks["main_collector_capability"] = False
    reasons.append("v1 collector currently rejects phase=main and marks episodes ineligible")
    # These checks require released evidence and actual live execution. Never
    # infer them from a draft flag or today's saved safety receipt.
    for name in ("fresh_safety", "oracle_validation", "mutation_validation",
                 "model_freeze", "pilot_replay", "logging_integrity",
                 "request_archive", "blind_annotation_plan", "statistical_plan"):
        checks[name] = False
    reasons.append("live main gates and independently reviewed release evidence are absent")
    return {
        "schema_version": VERSION, "status": "NOT_READY", "phase": "main",
        "eligible_main_episodes": 0, "passed": False, "checks": checks,
        "reasons": sorted(set(reasons)), "model_calls": 0, "candidate_runs": 0,
    }


def refuse_main(*, output_dir: Path, plan_path: Path | None = None, root: Path = ROOT) -> dict[str, Any]:
    """Persist a one-time denial; never dispatch an episode with a missing gate."""

    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise MainOrchestrationError("main output exists; refusing overwrite or implicit retry")
    assessment = assess_main_gate(plan_path=plan_path, root=root)
    output_dir.mkdir(parents=True, exist_ok=False)
    receipt = {**assessment, "created_at_utc": _utc_now(),
               "plan_sha256": _hash(plan_path) if plan_path is not None and plan_path.is_file() else None}
    receipt["receipt_sha256"] = hashlib.sha256(_canonical(receipt)).hexdigest()
    _write_once(output_dir / "main_refusal.json", receipt)
    return receipt


def prepare_rehearsal(
    output_dir: Path, *, seed: int = 20261004, full_catalog_r0: bool = False,
) -> dict[str, Any]:
    """Freeze an excluded scripted plan, optionally covering every finite family."""

    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise MainOrchestrationError("rehearsal output exists; refusing overwrite")
    plan = build_plan(
        experiment_id="excluded-main-path-rehearsal", phase="pilot",
        index_paths=(ALL_FINITE_INDEXES if full_catalog_r0 else ["benchmark/tasks/v1/index.json"]),
        models=[{"name": "scripted-observable-fixture", "digest": "0" * 64}],
        retrieval_modes=(("R0",) if full_catalog_r0 else MODES), repetitions=1, seed=seed,
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_once(output_dir / "schedule.json", plan)
    _write_once(output_dir / "retrieval_manifest.json", freeze_retrieval_manifest())
    archive = output_dir / "source_archive"
    files = set(plan["source_file_sha256s"])
    files.add("experiment_manifest.json")
    files.update(plan["index_paths"])
    for slot in plan["slots"]:
        files.add(slot["task_path"])
        files.add(slot["proof_path"])
    for relative in sorted(files):
        _write_once(archive / relative, _local(ROOT, relative).read_bytes())
    archive_hashes = {relative: _hash(archive / relative) for relative in sorted(files)}
    preflight = {
        "schema_version": VERSION, "phase": "pilot", "status": "EXCLUDED_ONLY",
        "eligible_for_main_analysis": False, "model_calls": 0,
        "schedule_sha256": _hash(output_dir / "schedule.json"),
        "retrieval_manifest_sha256": _hash(output_dir / "retrieval_manifest.json"),
        "source_archive_sha256s": archive_hashes,
        "planned_slot_count": plan["planned_slot_count"], "created_at_utc": _utc_now(),
    }
    _write_once(output_dir / "preflight.json", preflight)
    return {"status": "PREPARED_EXCLUDED", "planned_slot_count": plan["planned_slot_count"],
            "schedule_sha256": preflight["schedule_sha256"], "output_dir": str(output_dir)}


def _verify_prepared(output_dir: Path, *, archived: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = _read(output_dir / "schedule.json")
    preflight = _read(output_dir / "preflight.json")
    if plan.get("phase") != "pilot" or plan.get("eligible_for_main_analysis") is not False:
        raise MainOrchestrationError("rehearsal plan is not excluded")
    if archived:
        _verify_archived_rehearsal_plan(plan, output_dir / "source_archive")
    else:
        verify_plan(plan)
    if (preflight.get("status") != "EXCLUDED_ONLY" or
            preflight.get("eligible_for_main_analysis") is not False or
            preflight.get("schedule_sha256") != _hash(output_dir / "schedule.json") or
            preflight.get("retrieval_manifest_sha256") != _hash(output_dir / "retrieval_manifest.json") or
            plan["retrieval_manifest_sha256"] != preflight["retrieval_manifest_sha256"]):
        raise MainOrchestrationError("rehearsal preflight or retrieval bytes drifted")
    for relative, expected in preflight["source_archive_sha256s"].items():
        if _hash(output_dir / "source_archive" / relative) != expected:
            raise MainOrchestrationError(f"pre-run source archive drifted: {relative}")
    return plan, preflight


def _assert_root_entries(output_dir: Path, *, slot_ids: set[str] | None = None) -> None:
    expected = {"schedule.json", "retrieval_manifest.json", "source_archive", "preflight.json"}
    if slot_ids is not None:
        expected.update({"run.started.json", "run.receipt.json"})
        expected.update(slot_ids)
    observed = {path.name for path in output_dir.iterdir()}
    if observed != expected:
        raise MainOrchestrationError(f"rehearsal has missing or unplanned root artifacts: {sorted(observed ^ expected)}")


def _slot_file_hashes(directory: Path) -> dict[str, str]:
    return {path.name: _hash(path) for path in sorted(directory.iterdir()) if path.is_file()
            and path.name != "slot_result.json"}


def _rehearsal_adapter(slot: Mapping[str, Any]) -> ScriptedFixtureAdapter:
    proof = _read(ROOT / slot["proof_path"])
    candidates = proof.get("satisfying_candidates")
    calls = ([ToolCall("attempt", {"candidate": candidates[0]})]
             if isinstance(candidates, list) and candidates else [])
    calls.append(ToolCall("terminate", {}))
    return ScriptedFixtureAdapter(calls, AgentFinalResponse("unknown", "Scripted rehearsal stop."))


def execute_rehearsal(output_dir: Path) -> dict[str, Any]:
    """One attempt per frozen slot, retaining every partial failure in place."""

    output_dir = Path(output_dir).resolve()
    if (output_dir / "run.receipt.json").exists() or (output_dir / "run.started.json").exists():
        raise MainOrchestrationError("rehearsal was already started; no retry or replacement")
    plan, preflight = _verify_prepared(output_dir)
    _assert_root_entries(output_dir)
    _write_once(output_dir / "run.started.json", {
        "schema_version": VERSION, "phase": "pilot", "status": "STARTED_ONCE",
        "schedule_sha256": preflight["schedule_sha256"],
        "preflight_sha256": _hash(output_dir / "preflight.json"),
        "created_at_utc": _utc_now(),
    })
    rows: list[dict[str, Any]] = []
    for slot in plan["slots"]:
        directory = output_dir / slot["slot_id"]
        if directory.exists():
            raise MainOrchestrationError(f"reserved slot already exists: {slot['slot_id']}")
        directory.mkdir(parents=True, exist_ok=False)
        _write_once(directory / "slot_reservation.json", {
            "schema_version": VERSION, "phase": "pilot", "slot_id": slot["slot_id"],
            "episode_id": slot["episode_id"], "schedule_sha256": preflight["schedule_sha256"],
            "attempt_index": 1, "created_at_utc": _utc_now(),
        })
        try:
            verify_plan(plan)
            result = collect_episode(
                task_path=ROOT / slot["task_path"], proof_path=ROOT / slot["proof_path"],
                adapter=_rehearsal_adapter(slot), output_dir=directory,
                episode_id=slot["episode_id"], experiment_id=plan["experiment_id"],
                phase="pilot", model=slot["model"],
                baseline_code="B3" if slot["retrieval_mode"] == "R0" else "B5",
                retrieval_mode=slot["retrieval_mode"],
                retrieval_manifest_path=(output_dir / "retrieval_manifest.json"
                                         if slot["retrieval_mode"] != "R0" else None),
                max_steps=plan["inference_config"]["max_steps"],
                timeout_seconds=plan["inference_config"]["episode_timeout_seconds"],
                seed=slot["episode_seed"],
                temperature=plan["inference_config"]["temperature"],
            )
            loaded = load_episode(Path(result["manifest"]), source_root=ROOT)
            manifest = loaded["manifest"]
            if (manifest["phase"] != "pilot" or manifest["eligible_for_main_analysis"] is not False
                    or manifest["task_sha256"] != slot["task_sha256"]
                    or manifest["oracle_proof_sha256"] != slot["proof_sha256"]
                    or manifest["episode_id"] != slot["episode_id"]
                    or manifest["model"] != slot["model"]
                    or manifest["retrieval_mode"] != slot["retrieval_mode"]):
                raise MainOrchestrationError("raw episode differs from frozen slot")
            status = "VALID_EXCLUDED" if not loaded["invalidated"] else "INVALIDATED"
            reason = None if status == "VALID_EXCLUDED" else manifest["stop_reason"]
        except Exception as exc:
            status, reason = "INVALIDATED", f"{type(exc).__name__}: {str(exc)[:300]}"
        row = {
            "schema_version": VERSION, "slot_id": slot["slot_id"],
            "episode_id": slot["episode_id"], "phase": "pilot",
            "status": status, "reason": reason,
            "attempt_index": 1, "artifact_sha256s": _slot_file_hashes(directory),
        }
        row["result_sha256"] = hashlib.sha256(_canonical(row)).hexdigest()
        _write_once(directory / "slot_result.json", row)
        rows.append({"slot_id": slot["slot_id"], "status": status,
                     "result_sha256": _hash(directory / "slot_result.json")})
    receipt = {
        "schema_version": VERSION, "phase": "pilot", "eligible_for_main_analysis": False,
        "status": "COMPLETE_EXCLUDED_REHEARSAL",
        "schedule_sha256": preflight["schedule_sha256"],
        "preflight_sha256": _hash(output_dir / "preflight.json"),
        "run_started_sha256": _hash(output_dir / "run.started.json"),
        "planned_slot_count": len(plan["slots"]), "slot_results": rows,
        "valid_slot_count": sum(row["status"] == "VALID_EXCLUDED" for row in rows),
        "invalidated_slot_count": sum(row["status"] == "INVALIDATED" for row in rows),
        "replacement_count": 0, "eligible_main_episodes": 0,
        "created_at_utc": _utc_now(),
    }
    receipt["receipt_sha256"] = hashlib.sha256(_canonical(receipt)).hexdigest()
    _write_once(output_dir / "run.receipt.json", receipt)
    return receipt


def verify_rehearsal(output_dir: Path) -> dict[str, Any]:
    """Recompute receipt and raw hashes; reject omitted or changed slots."""

    output_dir = Path(output_dir).resolve()
    plan, preflight = _verify_prepared(output_dir, archived=True)
    _assert_root_entries(output_dir, slot_ids={slot["slot_id"] for slot in plan["slots"]})
    receipt = _read(output_dir / "run.receipt.json")
    started = _read(output_dir / "run.started.json")
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    rows = receipt.get("slot_results")
    if (receipt.get("receipt_sha256") != hashlib.sha256(_canonical(body)).hexdigest()
            or receipt.get("phase") != "pilot" or receipt.get("eligible_for_main_analysis") is not False
            or receipt.get("status") != "COMPLETE_EXCLUDED_REHEARSAL"
            or receipt.get("schedule_sha256") != preflight["schedule_sha256"]
            or receipt.get("preflight_sha256") != _hash(output_dir / "preflight.json")
            or receipt.get("run_started_sha256") != _hash(output_dir / "run.started.json")
            or started.get("phase") != "pilot" or started.get("status") != "STARTED_ONCE"
            or started.get("schedule_sha256") != preflight["schedule_sha256"]
            or receipt.get("replacement_count") != 0 or receipt.get("eligible_main_episodes") != 0
            or not isinstance(rows, list) or len(rows) != len(plan["slots"])
            or receipt.get("planned_slot_count") != len(rows)):
        raise MainOrchestrationError("rehearsal receipt identity or counts differ")
    manifests: list[Path] = []
    for slot, summary in zip(plan["slots"], rows):
        directory = output_dir / slot["slot_id"]
        reservation = _read(directory / "slot_reservation.json")
        row = _read(directory / "slot_result.json")
        unsigned = {key: value for key, value in row.items() if key != "result_sha256"}
        if (summary.get("slot_id") != slot["slot_id"] or row.get("slot_id") != slot["slot_id"]
                or summary.get("status") != row.get("status")
                or summary.get("result_sha256") != _hash(directory / "slot_result.json")
                or row.get("result_sha256") != hashlib.sha256(_canonical(unsigned)).hexdigest()
                or row.get("artifact_sha256s") != _slot_file_hashes(directory)
                or reservation.get("slot_id") != slot["slot_id"]
                or reservation.get("schedule_sha256") != preflight["schedule_sha256"]
                or reservation.get("attempt_index") != 1 or row.get("attempt_index") != 1):
            raise MainOrchestrationError(f"slot reservation, result or artifact drift: {slot['slot_id']}")
        if row["status"] == "VALID_EXCLUDED":
            manifest_path = directory / f"{slot['episode_id']}.manifest.json"
            loaded = load_episode(manifest_path, source_root=ROOT)
            if loaded["manifest"]["phase"] != "pilot" or loaded["manifest"]["eligible_for_main_analysis"] is not False:
                raise MainOrchestrationError("pilot episode was promoted to main")
            manifests.append(manifest_path)
        elif row["status"] != "INVALIDATED" or not row.get("reason"):
            raise MainOrchestrationError(f"unaccounted slot outcome: {slot['slot_id']}")
    if (receipt.get("valid_slot_count") != len(manifests) or
            receipt.get("invalidated_slot_count") != len(rows) - len(manifests)):
        raise MainOrchestrationError("receipt omits completed or invalidated slots")
    analysis = analyze_manifests(manifests, source_root=ROOT)
    if analysis["status"] != "NO_ELIGIBLE_DATA" or analysis["eligible_main_episodes"] != 0:
        raise MainOrchestrationError("excluded rehearsal entered main analysis")
    try:
        verify_plan(plan)
        current_source_matches = True
    except MainOrchestrationError:
        current_source_matches = False
    status = ("VERIFIED_EXCLUDED_REHEARSAL" if current_source_matches else
              "ARCHIVE_INTEGRITY_VERIFIED_SOURCE_DRIFT")
    return {"status": status, "planned_slot_count": len(rows),
            "valid_slot_count": len(manifests), "invalidated_slot_count": len(rows) - len(manifests),
            "eligible_main_episodes": 0, "analysis_status": analysis["status"],
            "current_source_matches_pre_run_archive": current_source_matches,
            "receipt_sha256": _hash(output_dir / "run.receipt.json")}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("main-gate", "refuse-main", "prepare-rehearsal",
                                           "run-rehearsal", "verify-rehearsal"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--seed", type=int, default=20261004)
    parser.add_argument("--all-families-r0", action="store_true",
                        help="prepare a 100-slot excluded R0 rehearsal over all 20 finite families")
    args = parser.parse_args(argv)
    try:
        if args.action == "main-gate":
            result = assess_main_gate(plan_path=args.plan)
            code = 2
        else:
            if args.output_dir is None:
                parser.error("--output-dir is required for this action")
            if args.action == "refuse-main":
                result, code = refuse_main(output_dir=args.output_dir, plan_path=args.plan), 2
            elif args.action == "prepare-rehearsal":
                result, code = prepare_rehearsal(
                    args.output_dir, seed=args.seed, full_catalog_r0=args.all_families_r0
                ), 0
            elif args.action == "run-rehearsal":
                result, code = execute_rehearsal(args.output_dir), 0
            else:
                result, code = verify_rehearsal(args.output_dir), 0
    except (MainOrchestrationError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "INVALID", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

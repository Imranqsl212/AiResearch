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
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.contracts import AgentFinalResponse, ToolCall
from agent.scripted_fixture import ScriptedFixtureAdapter
from analysis.v1_pipeline import analyze_manifests, load_episode
from benchmark import retrieval_r1_20_candidate as candidate_r1_20
from benchmark.finite_family_registry import family_module
from benchmark.retrieval_v1 import CORPUS_PATH, freeze_retrieval_manifest, validate_retrieval_manifest
from experiments.v1_collector import _IMPLEMENTATION_FILES, collect_episode
from reproduction.preflight import validate_freeze


ROOT = Path(__file__).resolve().parents[1]
VERSION = "prospective-main-orchestrator-0.1.0"
MAIN_PLAN_VERSION = "prospective-primary-main-plan-0.2.0"
FINAL_MAIN_PLAN_VERSION = "prospective-primary-main-schedule-0.3.0"
FINAL_MAIN_PLAN_STATUS = "SOURCE_COMMIT_BOUND_SCHEDULE_UNGATED"
FINAL_DESIGN_ROLES = frozenset({
    "preregistration", "family_review", "family_adjudication",
    "retrieval_review", "annotation_protocol", "primary_power",
    "companion_power",
})
MAIN_FAMILIES = 20
MAIN_REPETITIONS = 5
MAIN_FULL_DECISIONS = 6
C5_ONSET_CAP_PER_FAMILY = 5
C5_POST_VERDICT_DECISIONS = 3
C5_DRY_RUN_VERSION = "prospective-c5-structural-dry-run-0.1.0"
MAIN_SOURCE_ARCHIVE_VERSION = "proposed-main-source-archive-0.1.0"
C5_SIMULATED_STATUSES = (
    "SIMULATED_SECURE_ONSET", "SIMULATED_NO_ONSET", "SIMULATED_PRE_VERDICT_INVALIDATED",
)
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
    "experiments/main_collector.py", "experiments/main_c5_fork_scaffold.py",
    "experiments/main_schedule_consumer.py",
    "reproduction/preflight.py", "benchmark/retrieval_manifest_v1.json",
    "benchmark/retrieval_v1.py", "agent/scripted_fixture.py",
}))
# Preserve the 20-family R1 prototype for review without claiming that the
# proposed plan has selected or admitted it as its main retrieval provider.
_MAIN_ARCHIVE_EXTRA_FILES = (
    "agent/adapter.py",
    "benchmark/retrieval_r1_20_candidate.py",
    "benchmark/retrieval_corpus_r1_20_candidate.jsonl",
    "benchmark/retrieval_manifest_r1_20_candidate.json",
    "benchmark/retrieval_corpus_v2.jsonl",
)


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


def _git_bytes(root: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(("git", *arguments), cwd=root, capture_output=True,
                                check=True, timeout=15)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise MainOrchestrationError(f"Git source identity unavailable: {' '.join(arguments)}") from exc
    return result.stdout


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


def _scheduled_primary_main_slots(*, tasks: Sequence[Mapping[str, str]],
                                  model: Mapping[str, str], seed: int) -> list[dict[str, Any]]:
    """Preschedule C1–C4 R0 and matched C1/C2 R1 for one primary model."""

    by_family: dict[str, dict[str, Mapping[str, str]]] = defaultdict(dict)
    for task in tasks:
        by_family[task["family"]][task["condition"]] = task
    rng = random.Random(seed)
    blocks: list[list[dict[str, Any]]] = []
    for family in sorted(by_family):
        for repeat in range(1, MAIN_REPETITIONS + 1):
            condition_seeds = {condition: rng.randrange(0, 2**31)
                               for condition in ("C1", "C2", "C3", "C4")}
            block: list[dict[str, Any]] = []
            for mode, conditions in (("R0", ("C1", "C2", "C3", "C4")),
                                     ("R1", ("C1", "C2"))):
                for condition in conditions:
                    block.append({
                        **by_family[family][condition],
                        "model": model["name"], "model_digest": model["digest"],
                        "retrieval_mode": mode, "repeat_index": repeat,
                        "episode_seed": condition_seeds[condition],
                    })
            rng.shuffle(block)
            blocks.append(block)
    rng.shuffle(blocks)
    slots = [slot for block in blocks for slot in block]
    for index, slot in enumerate(slots, 1):
        slot["slot_id"] = f"slot-{index:06d}"
        slot["episode_id"] = f"episode-{index:06d}"
        slot["order"] = index
    return slots


def _scheduled_c5_reservations(*, slots: Sequence[Mapping[str, Any]],
                               model: Mapping[str, str], seed: int
                               ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Freeze conditional onset-pair capacity, orientation, and execution order."""

    rng = random.Random(seed ^ 0xC5C5)
    families = sorted({slot["family"] for slot in slots})
    pairs: list[dict[str, Any]] = []
    continuations: list[dict[str, Any]] = []
    for family in families:
        precursors = [slot["slot_id"] for slot in slots
                      if slot["family"] == family and slot["condition"] in {"C1", "C2"}
                      and slot["retrieval_mode"] == "R0"]
        if len(precursors) != 2 * MAIN_REPETITIONS:
            raise MainOrchestrationError("C5 needs ten R0 C1/C2 precursor slots per family")
        # Concealed A/B-to-verdict orientation is fixed within a family. This
        # source plan remains inaccessible to the agent at execution time.
        a_verdict = "PASS" if rng.getrandbits(1) == 0 else "FALSE_FAIL"
        for onset_rank in range(1, C5_ONSET_CAP_PER_FAMILY + 1):
            pair_id = f"c5-pair-{len(pairs) + 1:06d}"
            branch_seed = rng.randrange(0, 2**31)
            execution_order = ["A", "B"] if rng.getrandbits(1) == 0 else ["B", "A"]
            pairs.append({
                "pair_id": pair_id, "family": family, "onset_rank": onset_rank,
                "eligible_precursor_slot_ids_in_frozen_order": precursors,
                "arm_a_verdict": a_verdict,
                "arm_b_verdict": "FALSE_FAIL" if a_verdict == "PASS" else "PASS",
                "arm_execution_order": execution_order,
                "branch_seed": branch_seed,
                "allocation_status": "RESERVED_CONDITIONAL_ON_AGENT_SECURE_ONSET",
            })
            for arm in ("A", "B"):
                continuations.append({
                    "continuation_id": f"continuation-{len(continuations) + 1:06d}",
                    "pair_id": pair_id, "family": family, "onset_rank": onset_rank,
                    "arm": arm,
                    "public_verdict": (a_verdict if arm == "A" else pairs[-1]["arm_b_verdict"]),
                    "execution_rank_within_pair": execution_order.index(arm) + 1,
                    "model": model["name"], "model_digest": model["digest"],
                    "retrieval_mode": "R0", "episode_seed": branch_seed,
                    "post_verdict_decision_cap": C5_POST_VERDICT_DECISIONS,
                    "allocation_status": "RESERVED_CONDITIONAL_ON_AGENT_SECURE_ONSET",
                })
    dispatch_ids = [pair["pair_id"] for pair in pairs]
    rng.shuffle(dispatch_ids)
    dispatch_rank = {pair_id: rank for rank, pair_id in enumerate(dispatch_ids, 1)}
    for pair in pairs:
        pair["dispatch_priority_when_ready"] = dispatch_rank[pair["pair_id"]]
    return pairs, continuations


def build_plan(
    *, experiment_id: str, phase: str, index_paths: Sequence[str],
    models: Sequence[Mapping[str, Any]], retrieval_modes: Sequence[str],
    repetitions: int, seed: int, root: Path = ROOT,
    inference_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Preschedule an excluded rehearsal or proposed primary-model main design."""

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
    if phase == "main" and (len(families) != MAIN_FAMILIES or repetitions != MAIN_REPETITIONS
                            or ordered_modes != ["R0", "R1"] or len(cleaned_models) != 1):
        raise MainOrchestrationError(
            "primary main design requires exactly 20 families, 5 repeats, R0/R1 only and one frozen model"
        )
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
        if inference["max_steps"] != MAIN_FULL_DECISIONS:
            raise MainOrchestrationError("primary main full episodes require exactly six model decisions")
    retrieval_manifest = freeze_retrieval_manifest()
    validate_retrieval_manifest(retrieval_manifest, CORPUS_PATH)
    source_hashes = {relative: _hash(_local(root, relative)) for relative in _SOURCE_FILES}
    source_hashes["benchmark/retrieval_corpus_v1.jsonl"] = _hash(CORPUS_PATH)
    # Bind the exact index bytes as well as each referenced task/proof. Index
    # metadata could otherwise drift between planning and source archiving.
    for relative in index_paths:
        source_hashes[relative] = _hash(_local(root, relative))
    if phase == "main":
        source_hashes["docs/preregistration_v1_20261005.md"] = _hash(
            _local(root, "docs/preregistration_v1_20261005.md"))
        for task in tasks:
            source_hashes[task["task_path"]] = task["task_sha256"]
            source_hashes[task["proof_path"]] = task["proof_sha256"]
        slots = _scheduled_primary_main_slots(tasks=tasks, model=cleaned_models[0], seed=seed)
        branch_pairs, continuations = _scheduled_c5_reservations(
            slots=slots, model=cleaned_models[0], seed=seed)
    else:
        slots = _scheduled_slots(tasks=tasks, models=cleaned_models, modes=ordered_modes,
                                 repetitions=repetitions, seed=seed)
    plan = {
        "schema_version": MAIN_PLAN_VERSION if phase == "main" else VERSION,
        "phase": phase, "eligible_for_main_analysis": False,
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
    if phase == "main":
        plan.update({
            "primary_model": cleaned_models[0]["name"],
            "design": "20-family primary C1-C4 R0 plus C1/C2 R1; C5 paired onset reservations",
            "planned_full_episode_count": len(slots),
            "planned_c5_pair_capacity": len(branch_pairs),
            "planned_c5_continuation_capacity": len(continuations),
            "maximum_full_episodes_plus_continuations": len(slots) + len(continuations),
            "c5_onset_allocation_policy": (
                "first five agent-generated oracle-secure onsets per family in frozen R0 C1/C2 "
                "precursor slot order; retain nonreach and invalidation without replacement"
            ),
            "c5_branch_pair_reservations": branch_pairs,
            "c5_continuation_reservations": continuations,
            "main_execution_implemented": False,
        })
    return plan


def verify_plan(plan: Mapping[str, Any], *, root: Path = ROOT) -> None:
    phase = plan.get("phase")
    expected_version = MAIN_PLAN_VERSION if phase == "main" else VERSION
    if plan.get("schema_version") != expected_version or phase not in {"main", "pilot"}:
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


def _final_design_artifacts(paths: Mapping[str, str], root: Path) -> dict[str, dict[str, str]]:
    if not isinstance(paths, Mapping) or set(paths) != FINAL_DESIGN_ROLES:
        raise MainOrchestrationError("final schedule needs every named design artifact")
    rows: dict[str, dict[str, str]] = {}
    for role in sorted(FINAL_DESIGN_ROLES):
        relative = paths[role]
        if (not isinstance(relative, str) or relative == "experiment_manifest.json"
                or ":" in relative or ".." in Path(relative).parts):
            raise MainOrchestrationError(f"unsafe or circular final design path: {role}")
        rows[role] = {"path": relative, "sha256": _hash(_local(root, relative))}
    return rows


def _as_final_main_schedule(
    proposal: Mapping[str, Any], *, source_commit: str,
    design_artifacts: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    """Derive an ungated schedule whose identity never includes the root lock."""

    final = dict(proposal)
    final.pop("root_manifest_sha256")
    final["schema_version"] = FINAL_MAIN_PLAN_VERSION
    final["status"] = FINAL_MAIN_PLAN_STATUS
    final["source_git_commit"] = source_commit
    final["root_manifest_binding"] = "SCHEDULE_FIRST_THEN_MANIFEST_ONLY_FREEZE"
    final["design_artifact_sha256s"] = dict(design_artifacts)
    source_hashes = dict(proposal["source_file_sha256s"])
    for record in design_artifacts.values():
        relative, digest = record["path"], record["sha256"]
        if relative in source_hashes and source_hashes[relative] != digest:
            raise MainOrchestrationError(f"design artifact differs from source inventory: {relative}")
        source_hashes[relative] = digest
    final["source_file_sha256s"] = source_hashes
    return final


def _verify_final_source_commit(plan: Mapping[str, Any], root: Path) -> None:
    commit = plan["source_git_commit"]
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise MainOrchestrationError("final schedule lacks a full source Git commit")
    resolved = _git_bytes(root, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    if resolved != commit:
        raise MainOrchestrationError("final schedule source commit is not canonical")
    _git_bytes(root, "merge-base", "--is-ancestor", commit, "HEAD")
    changed = _git_bytes(root, "diff", "--name-only", commit, "HEAD", "--").decode().splitlines()
    if changed not in ([], ["experiment_manifest.json"]):
        raise MainOrchestrationError("source commit to current HEAD changed more than the root manifest")
    if _git_bytes(root, "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise MainOrchestrationError("final schedule requires a clean source checkout")
    for relative, digest in sorted(plan["source_file_sha256s"].items()):
        if _hash(_local(root, relative)) != digest:
            raise MainOrchestrationError(f"final schedule current source drift: {relative}")
        committed = _git_bytes(root, "show", f"{commit}:{relative}")
        if hashlib.sha256(committed).hexdigest() != digest:
            raise MainOrchestrationError(f"final schedule source is not in the source commit: {relative}")


def build_final_main_schedule(
    proposal: Mapping[str, Any], *, design_artifact_paths: Mapping[str, str],
    root: Path = ROOT,
) -> dict[str, Any]:
    """Build a source-commit-bound schedule, still ineligible for main dispatch.

    Call this after committing implementation/design bytes and before the sole
    root-manifest freeze commit. A SHA of the draft root manifest is deliberately
    removed: the future frozen root manifest will hash this schedule instead.
    Hash identity does not certify human admission, R1, runtime, or safety gates.
    """

    root = Path(root).resolve()
    if proposal.get("phase") != "main" or proposal.get("schema_version") != MAIN_PLAN_VERSION:
        raise MainOrchestrationError("final schedule input must be a proposed v0.2 main plan")
    verify_plan(proposal, root=root)
    design = _final_design_artifacts(design_artifact_paths, root)
    final = _as_final_main_schedule(
        proposal, source_commit=proposal["source_git_commit"], design_artifacts=design,
    )
    verify_final_main_schedule(final, root=root)
    return final


def prepare_final_main_schedule(
    *, proposal_path: Path, design_artifacts_path: Path, output_dir: Path,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Write one ungated schedule after the source commit, before root freeze."""

    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise MainOrchestrationError("final schedule output exists; refusing overwrite")
    proposal_path, design_artifacts_path = Path(proposal_path), Path(design_artifacts_path)
    _hash(proposal_path)
    _hash(design_artifacts_path)
    plan = build_final_main_schedule(
        _read(proposal_path), design_artifact_paths=_read(design_artifacts_path), root=root,
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    schedule_path = output_dir / "schedule.json"
    _write_once(schedule_path, plan)
    return {
        "status": plan["status"], "eligible_for_main_analysis": False,
        "main_dispatch_allowed": False,
        "planned_full_episode_count": plan["planned_full_episode_count"],
        "planned_c5_pair_capacity": plan["planned_c5_pair_capacity"],
        "planned_c5_continuation_capacity": plan["planned_c5_continuation_capacity"],
        "source_git_commit": plan["source_git_commit"],
        "schedule_path": str(schedule_path), "schedule_sha256": _hash(schedule_path),
    }


def verify_final_main_schedule(plan: Mapping[str, Any], *, root: Path = ROOT) -> None:
    """Rebuild the schedule after either source or manifest-only freeze commit."""

    root = Path(root).resolve()
    if (plan.get("schema_version") != FINAL_MAIN_PLAN_VERSION
            or plan.get("status") != FINAL_MAIN_PLAN_STATUS
            or plan.get("phase") != "main"
            or plan.get("eligible_for_main_analysis") is not False
            or plan.get("main_execution_implemented") is not False
            or plan.get("root_manifest_binding") != "SCHEDULE_FIRST_THEN_MANIFEST_ONLY_FREEZE"
            or "root_manifest_sha256" in plan):
        raise MainOrchestrationError("final schedule version, status, or non-circular binding differs")
    design = plan.get("design_artifact_sha256s")
    if (not isinstance(design, dict) or set(design) != FINAL_DESIGN_ROLES
            or any(not isinstance(row, dict) or set(row) != {"path", "sha256"}
                   for row in design.values())):
        raise MainOrchestrationError("final schedule design artifact inventory is incomplete")
    paths = {role: row["path"] for role, row in design.items()}
    current_design = _final_design_artifacts(paths, root)
    if design != current_design:
        raise MainOrchestrationError("final schedule design artifact bytes drifted")
    try:
        rebuilt = build_plan(
            experiment_id=plan["experiment_id"], phase="main", index_paths=plan["index_paths"],
            models=plan["models"], retrieval_modes=plan["retrieval_modes"],
            repetitions=plan["repetitions"], seed=plan["seed"], root=root,
            inference_config=plan["inference_config"],
        )
    except (KeyError, TypeError) as exc:
        raise MainOrchestrationError("final schedule is incomplete") from exc
    expected = _as_final_main_schedule(
        rebuilt, source_commit=plan["source_git_commit"], design_artifacts=current_design,
    )
    if dict(plan) != expected:
        raise MainOrchestrationError("final schedule differs from deterministic 600/100/200 design")
    _verify_final_source_commit(plan, root)


def verify_manifest_only_freeze_sequence(
    schedule_path: Path, *, root: Path = ROOT,
) -> dict[str, Any]:
    """Check source commit → schedule → root-only commit, not scientific readiness."""

    requested_schedule = Path(schedule_path)
    if requested_schedule.is_symlink():
        raise MainOrchestrationError("final schedule path is redirected")
    root, schedule_path = Path(root).resolve(), requested_schedule.resolve()
    if not schedule_path.is_relative_to(root):
        raise MainOrchestrationError("final schedule path must stay inside the source checkout")
    schedule = _read(schedule_path)
    verify_final_main_schedule(schedule, root=root)
    manifest_path = root / "experiment_manifest.json"
    manifest = _read(manifest_path)
    experiment, paths = manifest.get("experiment"), manifest.get("artifact_paths")
    if (manifest.get("schema_version") != "1.0" or manifest.get("status") != "FROZEN"
            or not isinstance(experiment, dict) or not isinstance(paths, dict)
            or experiment.get("git_sha") != schedule["source_git_commit"]
            or experiment.get("schedule_hash") != _hash(schedule_path)
            or paths.get("schedule") != schedule_path.relative_to(root).as_posix()):
        raise MainOrchestrationError("root freeze does not bind the source commit and exact final schedule")
    freeze_commit = _git_bytes(root, "rev-parse", "--verify", "HEAD").decode().strip()
    if freeze_commit == schedule["source_git_commit"]:
        raise MainOrchestrationError("root manifest-only freeze commit has not occurred")
    changed = _git_bytes(root, "diff", "--name-only", schedule["source_git_commit"],
                         freeze_commit, "--").decode().splitlines()
    if changed != ["experiment_manifest.json"]:
        raise MainOrchestrationError("freeze commit changed files other than root manifest")
    if _git_bytes(root, "show", "HEAD:experiment_manifest.json") != manifest_path.read_bytes():
        raise MainOrchestrationError("working root manifest differs from freeze commit")
    return {
        "status": "EXCLUDED_STRUCTURAL_FREEZE_SEQUENCE_VERIFIED",
        "structural_sequence_verified": True,
        "scientific_admission_verified": False,
        "main_dispatch_allowed": False,
        "source_git_commit": schedule["source_git_commit"],
        "freeze_git_commit": freeze_commit,
        "schedule_sha256": _hash(schedule_path),
        "root_manifest_sha256": _hash(manifest_path),
    }


def dry_run_c5_allocation(
    plan: Mapping[str, Any], precursor_ledger: Mapping[str, Any], *, root: Path = ROOT,
) -> dict[str, Any]:
    """Audit C5 reservation accounting with synthetic statuses; collect no data.

    The input deliberately cannot contain observed outcomes. Each status is
    captured *before* delivery of a C5 verdict: later branch failure cannot
    erase an already observed secure onset. This checks that the frozen
    precursor order consumes only the first five simulated secure onsets in
    each family, while every other precursor and unused reservation remains
    visible. It does not validate an agent-generated candidate or authorize
    any main branch.
    """

    if (plan.get("phase") != "main" or plan.get("status") != "PROPOSED_MAIN_UNGATED"
            or plan.get("eligible_for_main_analysis") is not False
            or plan.get("main_execution_implemented") is not False):
        raise MainOrchestrationError("C5 structural dry-run needs an ungated proposed main plan")
    try:
        verify_plan(plan, root=root)
    except (KeyError, TypeError) as exc:
        raise MainOrchestrationError("proposed main plan is incomplete") from exc
    if (not isinstance(precursor_ledger, Mapping)
            or set(precursor_ledger) != {"schema_version", "phase", "eligible_for_main_analysis",
                                          "precursor_slots"}
            or precursor_ledger["schema_version"] != C5_DRY_RUN_VERSION
            or precursor_ledger["phase"] != "pilot"
            or precursor_ledger["eligible_for_main_analysis"] is not False
            or not isinstance(precursor_ledger["precursor_slots"], list)):
        raise MainOrchestrationError("C5 input must be a complete excluded synthetic precursor ledger")

    expected_ids = {
        slot["slot_id"] for slot in plan["slots"]
        if slot["retrieval_mode"] == "R0" and slot["condition"] in {"C1", "C2"}
    }
    statuses: dict[str, str] = {}
    for row in precursor_ledger["precursor_slots"]:
        if (not isinstance(row, dict) or set(row) != {"slot_id", "simulated_status"}
                or not isinstance(row["slot_id"], str)
                or row["simulated_status"] not in C5_SIMULATED_STATUSES
                or row["slot_id"] in statuses):
            raise MainOrchestrationError("C5 synthetic precursor row is duplicate or malformed")
        statuses[row["slot_id"]] = row["simulated_status"]
    if set(statuses) != expected_ids or len(expected_ids) != MAIN_FAMILIES * 2 * MAIN_REPETITIONS:
        raise MainOrchestrationError("C5 synthetic ledger must account for exactly every R0 C1/C2 precursor")

    branches_by_pair: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for branch in plan["c5_continuation_reservations"]:
        branches_by_pair[branch["pair_id"]].append(branch)
    pairs_by_family: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for pair in plan["c5_branch_pair_reservations"]:
        pairs_by_family[pair["family"]].append(pair)

    pair_allocations: list[dict[str, Any]] = []
    family_accounting: list[dict[str, Any]] = []
    for family in sorted(pairs_by_family):
        reservations = sorted(pairs_by_family[family], key=lambda row: row["onset_rank"])
        if len(reservations) != C5_ONSET_CAP_PER_FAMILY:
            raise MainOrchestrationError("C5 family reservation count differs")
        precursor_ids = reservations[0]["eligible_precursor_slot_ids_in_frozen_order"]
        if (len(precursor_ids) != 2 * MAIN_REPETITIONS or len(set(precursor_ids)) != len(precursor_ids)
                or any(pair["eligible_precursor_slot_ids_in_frozen_order"] != precursor_ids
                       for pair in reservations)):
            raise MainOrchestrationError("C5 family precursor order differs across reservations")
        secure_ids = [slot_id for slot_id in precursor_ids
                      if statuses[slot_id] == "SIMULATED_SECURE_ONSET"]
        selected = secure_ids[:C5_ONSET_CAP_PER_FAMILY]
        family_accounting.append({
            "family": family,
            "precursor_slots_in_frozen_order": [
                {"slot_id": slot_id, "simulated_status": statuses[slot_id]}
                for slot_id in precursor_ids
            ],
            "allocated_simulated_onset_slot_ids": selected,
            "exploratory_simulated_onset_slot_ids": secure_ids[C5_ONSET_CAP_PER_FAMILY:],
            "simulated_invalidated_precursor_slot_ids": [
                slot_id for slot_id in precursor_ids
                if statuses[slot_id] == "SIMULATED_PRE_VERDICT_INVALIDATED"
            ],
        })
        for rank, pair in enumerate(reservations, 1):
            branches = sorted(branches_by_pair[pair["pair_id"]],
                              key=lambda row: row["execution_rank_within_pair"])
            if len(branches) != 2:
                raise MainOrchestrationError("C5 pair does not have exactly two frozen continuations")
            allocated = rank <= len(selected)
            pair_allocations.append({
                "pair_id": pair["pair_id"], "family": family, "onset_rank": rank,
                "simulated_precursor_slot_id": selected[rank - 1] if allocated else None,
                "allocation_status": "SIMULATED_ALLOCATED" if allocated else "SIMULATED_UNUSED_NO_ONSET",
                "continuation_ids_in_frozen_execution_order": [
                    branch["continuation_id"] for branch in branches
                ] if allocated else [],
            })
    if (len(family_accounting) != MAIN_FAMILIES
            or len(pair_allocations) != MAIN_FAMILIES * C5_ONSET_CAP_PER_FAMILY):
        raise MainOrchestrationError("C5 dry-run did not account for every family and pair")
    counts = Counter(statuses.values())
    allocated_count = sum(row["allocation_status"] == "SIMULATED_ALLOCATED"
                          for row in pair_allocations)
    return {
        "schema_version": C5_DRY_RUN_VERSION, "phase": "pilot",
        "status": "EXCLUDED_STRUCTURAL_DRY_RUN", "eligible_for_main_analysis": False,
        "semantic_onset_validation_performed": False, "model_calls": 0,
        "plan_content_sha256": hashlib.sha256(_canonical(plan)).hexdigest(),
        "precursor_ledger_content_sha256": hashlib.sha256(_canonical(precursor_ledger)).hexdigest(),
        "precursor_slot_count": len(statuses),
        "simulated_precursor_status_counts": {key: counts[key] for key in C5_SIMULATED_STATUSES},
        "reserved_pair_count": len(pair_allocations),
        "simulated_allocated_pair_count": allocated_count,
        "simulated_unused_pair_count": len(pair_allocations) - allocated_count,
        "simulated_exploratory_onset_count": sum(
            len(row["exploratory_simulated_onset_slot_ids"]) for row in family_accounting
        ),
        "simulated_continuation_count": 2 * allocated_count,
        "family_accounting": family_accounting,
        "pair_allocations": pair_allocations,
    }


def save_c5_allocation_dry_run(
    *, plan_path: Path, precursor_ledger_path: Path, output_dir: Path, root: Path = ROOT,
) -> dict[str, Any]:
    """Preserve the exact dry-run inputs and a write-once structural report."""

    plan_path, precursor_ledger_path = Path(plan_path), Path(precursor_ledger_path)
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise MainOrchestrationError("C5 dry-run output exists; refusing overwrite")
    plan_hash, ledger_hash = _hash(plan_path), _hash(precursor_ledger_path)
    plan, ledger = _read(plan_path), _read(precursor_ledger_path)
    report = dry_run_c5_allocation(plan, ledger, root=root)
    plan_bytes, ledger_bytes = plan_path.read_bytes(), precursor_ledger_path.read_bytes()
    try:
        same_content = json.loads(plan_bytes) == plan and json.loads(ledger_bytes) == ledger
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MainOrchestrationError("C5 dry-run input changed during validation") from exc
    if (hashlib.sha256(plan_bytes).hexdigest() != plan_hash
            or hashlib.sha256(ledger_bytes).hexdigest() != ledger_hash or not same_content):
        raise MainOrchestrationError("C5 dry-run input changed during validation")
    report["input_file_sha256s"] = {
        "plan.json": plan_hash, "precursor_ledger.json": ledger_hash,
    }
    report["created_at_utc"] = _utc_now()
    report["report_sha256"] = hashlib.sha256(_canonical(report)).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_once(output_dir / "plan.json", plan_bytes)
    _write_once(output_dir / "precursor_ledger.json", ledger_bytes)
    _write_once(output_dir / "c5_dry_run.json", report)
    return {
        "status": report["status"], "precursor_slot_count": report["precursor_slot_count"],
        "simulated_allocated_pair_count": report["simulated_allocated_pair_count"],
        "simulated_unused_pair_count": report["simulated_unused_pair_count"],
        "simulated_continuation_count": report["simulated_continuation_count"],
        "report_sha256": _hash(output_dir / "c5_dry_run.json"),
        "output_dir": str(output_dir),
    }


def _proposed_main_source_files(plan: Mapping[str, Any]) -> set[str]:
    if (plan.get("phase") != "main" or plan.get("status") != "PROPOSED_MAIN_UNGATED"
            or plan.get("eligible_for_main_analysis") is not False
            or plan.get("main_execution_implemented") is not False
            or plan.get("planned_full_episode_count") != 600
            or plan.get("planned_c5_pair_capacity") != 100
            or plan.get("planned_c5_continuation_capacity") != 200):
        raise MainOrchestrationError("source archive requires the exact ungated 600/100/200 proposal")
    source_hashes = plan.get("source_file_sha256s")
    if (not isinstance(source_hashes, dict) or not source_hashes
            or any(not isinstance(name, str) or not isinstance(digest, str)
                   or not _HEX64.fullmatch(digest) for name, digest in source_hashes.items())):
        raise MainOrchestrationError("proposed plan lacks exact source file hashes")
    task_files = {slot["task_path"] for slot in plan["slots"]}
    proof_files = {slot["proof_path"] for slot in plan["slots"]}
    if not (set(plan["index_paths"]) | task_files | proof_files).issubset(source_hashes):
        raise MainOrchestrationError("proposed plan does not bind every index, task, and oracle proof")
    if not {
        "experiments/v1_collector.py", "benchmark/retrieval_v1.py",
        "benchmark/retrieval_corpus_v1.jsonl", "benchmark/retrieval_manifest_v1.json",
        "agent/v1_ollama_adapter.py", "agent/v1_baselines.py",
        "benchmark/finite_family_registry.py", "analysis/v1_pipeline.py",
        "docs/preregistration_v1_20261005.md",
    }.issubset(source_hashes):
        raise MainOrchestrationError("proposed plan omits collector, retrieval, prompt, or oracle code")
    if not any(name.startswith("agent/prompts/") for name in source_hashes):
        raise MainOrchestrationError("proposed plan omits prompt templates")
    return set(source_hashes) | {"experiment_manifest.json"} | set(_MAIN_ARCHIVE_EXTRA_FILES)


def prepare_proposed_main_source_archive(
    *, plan_path: Path, output_dir: Path, root: Path = ROOT,
) -> dict[str, Any]:
    """Save exact proposal/source bytes before dispatch; never grant main access."""

    root, plan_path, output_dir = Path(root).resolve(), Path(plan_path), Path(output_dir).resolve()
    if output_dir.exists():
        raise MainOrchestrationError("proposed main archive exists; refusing overwrite")
    plan_sha256 = _hash(plan_path)
    plan_bytes = plan_path.read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != plan_sha256:
        raise MainOrchestrationError("proposed plan changed during archive preparation")
    try:
        plan = json.loads(plan_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MainOrchestrationError("proposed plan is unreadable") from exc
    if not isinstance(plan, dict):
        raise MainOrchestrationError("proposed plan must be a JSON object")
    source_files = _proposed_main_source_files(plan)
    verify_plan(plan, root=root)
    candidate_manifest = _read(root / "benchmark/retrieval_manifest_r1_20_candidate.json")
    if (candidate_manifest != candidate_r1_20.freeze_candidate_manifest()
            or candidate_manifest.get("status") != "EXCLUDED_PROTOTYPE_UNREVIEWED"):
        raise MainOrchestrationError("R1 candidate manifest or corpus differs from exact candidate source")
    source_bytes: dict[str, bytes] = {}
    source_hashes: dict[str, str] = {}
    for relative in sorted(source_files):
        path = _local(root, relative)
        digest = _hash(path)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise MainOrchestrationError(f"source changed while archiving: {relative}")
        expected = (plan["root_manifest_sha256"] if relative == "experiment_manifest.json"
                    else plan["source_file_sha256s"].get(relative))
        if expected is not None and digest != expected:
            raise MainOrchestrationError(f"proposed plan source differs: {relative}")
        source_bytes[relative], source_hashes[relative] = raw, digest
    preflight = {
        "schema_version": MAIN_SOURCE_ARCHIVE_VERSION,
        "status": "PREPARED_PROPOSED_SOURCE_ARCHIVE_EXCLUDED", "phase": "main",
        "eligible_for_main_analysis": False, "main_dispatch_allowed": False,
        "model_calls": 0, "candidate_runs": 0,
        "schedule_sha256": plan_sha256,
        "source_archive_sha256s": source_hashes,
        "source_archive_inventory_sha256": hashlib.sha256(_canonical(source_hashes)).hexdigest(),
        "source_git_commit": plan["source_git_commit"],
        "planned_full_episode_count": 600, "planned_c5_pair_capacity": 100,
        "planned_c5_continuation_capacity": 200,
        "r1_candidate_status": candidate_manifest["status"],
        "r1_candidate_admitted_for_main": False,
        "r1_candidate_bound_as_main_provider": False,
        "main_collector_capability": False,
        "plan_retrieval_manifest_sha256": plan["retrieval_manifest_sha256"],
        "r1_candidate_manifest_file_sha256": source_hashes[
            "benchmark/retrieval_manifest_r1_20_candidate.json"],
        "source_snapshot_cannot_replace_main_gate": True,
        "created_at_utc": _utc_now(),
    }
    preflight["preflight_sha256"] = hashlib.sha256(_canonical(preflight)).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_once(output_dir / "schedule.json", plan_bytes)
    for relative, raw in source_bytes.items():
        _write_once(output_dir / "source_archive" / relative, raw)
    _write_once(output_dir / "preflight.json", preflight)
    verified = verify_proposed_main_source_archive(output_dir, root=root)
    if verified["current_source_matches_pre_run_archive"] is not True:
        raise MainOrchestrationError("source changed before proposed archive pre-dispatch verification")
    return verified


def verify_proposed_main_source_archive(
    output_dir: Path, *, root: Path = ROOT,
) -> dict[str, Any]:
    """Check archived proposal bytes and current source identity without dispatch."""

    output_dir, root = Path(output_dir).resolve(), Path(root).resolve()
    if {path.name for path in output_dir.iterdir()} != {
            "schedule.json", "source_archive", "preflight.json"}:
        raise MainOrchestrationError("proposed archive has missing or unplanned root artifacts")
    plan = _read(output_dir / "schedule.json")
    preflight = _read(output_dir / "preflight.json")
    source_files = _proposed_main_source_files(plan)
    if (preflight.get("schema_version") != MAIN_SOURCE_ARCHIVE_VERSION
            or preflight.get("status") != "PREPARED_PROPOSED_SOURCE_ARCHIVE_EXCLUDED"
            or preflight.get("phase") != "main"
            or preflight.get("eligible_for_main_analysis") is not False
            or preflight.get("main_dispatch_allowed") is not False
            or preflight.get("model_calls") != 0 or preflight.get("candidate_runs") != 0
            or preflight.get("schedule_sha256") != _hash(output_dir / "schedule.json")
            or preflight.get("source_git_commit") != plan["source_git_commit"]
            or preflight.get("planned_full_episode_count") != 600
            or preflight.get("planned_c5_pair_capacity") != 100
            or preflight.get("planned_c5_continuation_capacity") != 200
            or preflight.get("r1_candidate_status") != "EXCLUDED_PROTOTYPE_UNREVIEWED"
            or preflight.get("r1_candidate_admitted_for_main") is not False
            or preflight.get("r1_candidate_bound_as_main_provider") is not False
            or preflight.get("main_collector_capability") is not False
            or preflight.get("plan_retrieval_manifest_sha256") != plan["retrieval_manifest_sha256"]
            or preflight.get("source_snapshot_cannot_replace_main_gate") is not True):
        raise MainOrchestrationError("proposed main archive preflight differs")
    saved_preflight_hash = preflight.pop("preflight_sha256", None)
    if saved_preflight_hash != hashlib.sha256(_canonical(preflight)).hexdigest():
        raise MainOrchestrationError("proposed main preflight hash differs")
    preflight["preflight_sha256"] = saved_preflight_hash
    source_hashes = preflight.get("source_archive_sha256s")
    if (not isinstance(source_hashes, dict) or set(source_hashes) != source_files
            or preflight.get("source_archive_inventory_sha256") !=
            hashlib.sha256(_canonical(source_hashes)).hexdigest()
            or preflight.get("r1_candidate_manifest_file_sha256") != source_hashes.get(
                "benchmark/retrieval_manifest_r1_20_candidate.json")):
        raise MainOrchestrationError("proposed source archive inventory differs")
    archive = output_dir / "source_archive"
    if not archive.is_dir() or archive.is_symlink():
        raise MainOrchestrationError("proposed source archive is missing or redirected")
    entries = list(archive.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise MainOrchestrationError("proposed source archive contains a symlink")
    archived_files = {path.relative_to(archive).as_posix() for path in entries if path.is_file()}
    if archived_files != source_files:
        raise MainOrchestrationError("proposed source archive has missing or unplanned files")
    for relative in sorted(source_files):
        archived_hash = _hash(_local(archive, relative))
        expected = (plan["root_manifest_sha256"] if relative == "experiment_manifest.json"
                    else plan["source_file_sha256s"].get(relative))
        if archived_hash != source_hashes[relative] or (expected is not None and archived_hash != expected):
            raise MainOrchestrationError(f"proposed source archive byte drift: {relative}")
    try:
        verify_plan(plan, root=root)
        current_matches = all(_hash(_local(root, relative)) == source_hashes[relative]
                              for relative in source_files)
        current_matches = current_matches and (
            _read(root / "benchmark/retrieval_manifest_r1_20_candidate.json") ==
            candidate_r1_20.freeze_candidate_manifest()
        )
    except (MainOrchestrationError, KeyError, TypeError, OSError, ValueError):
        current_matches = False
    return {
        "status": ("VERIFIED_PROPOSED_SOURCE_ARCHIVE_EXCLUDED" if current_matches else
                   "ARCHIVE_INTEGRITY_VERIFIED_SOURCE_DRIFT"),
        "phase": "main", "eligible_for_main_analysis": False,
        "main_dispatch_allowed": False, "model_calls": 0, "candidate_runs": 0,
        "planned_full_episode_count": 600, "planned_c5_pair_capacity": 100,
        "planned_c5_continuation_capacity": 200,
        "source_archive_file_count": len(source_files),
        "current_source_matches_pre_run_archive": current_matches,
        "r1_candidate_admitted_for_main": False,
        "r1_candidate_bound_as_main_provider": False,
        "main_collector_capability": False,
        "preflight_sha256": _hash(output_dir / "preflight.json"),
        "schedule_sha256": _hash(output_dir / "schedule.json"),
    }


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
            if plan.get("schema_version") == FINAL_MAIN_PLAN_VERSION:
                verify_final_main_schedule(plan, root=root)
            else:
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
                                           "run-rehearsal", "verify-rehearsal",
                                           "dry-run-c5-allocation",
                                           "prepare-proposed-main-archive",
                                           "verify-proposed-main-archive",
                                           "prepare-final-main-schedule",
                                           "verify-final-main-schedule",
                                           "verify-manifest-only-freeze-sequence"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--design-artifacts", type=Path)
    parser.add_argument("--precursor-ledger", type=Path)
    parser.add_argument("--seed", type=int, default=20261004)
    parser.add_argument("--all-families-r0", action="store_true",
                        help="prepare a 100-slot excluded R0 rehearsal over all 20 finite families")
    args = parser.parse_args(argv)
    try:
        if args.action == "main-gate":
            result = assess_main_gate(plan_path=args.plan)
            code = 2
        elif args.action == "verify-final-main-schedule":
            if args.plan is None:
                parser.error("--plan is required for final schedule verification")
            verify_final_main_schedule(_read(args.plan))
            result = {"status": "VERIFIED_FINAL_SCHEDULE_IDENTITY_UNGATED",
                      "main_dispatch_allowed": False, "schedule_sha256": _hash(args.plan)}
            code = 0
        elif args.action == "verify-manifest-only-freeze-sequence":
            if args.plan is None:
                parser.error("--plan is required for manifest-only sequence verification")
            result, code = verify_manifest_only_freeze_sequence(args.plan), 0
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
            elif args.action == "dry-run-c5-allocation":
                if args.plan is None or args.precursor_ledger is None:
                    parser.error("--plan and --precursor-ledger are required for a C5 dry-run")
                result, code = save_c5_allocation_dry_run(
                    plan_path=args.plan, precursor_ledger_path=args.precursor_ledger,
                    output_dir=args.output_dir,
                ), 0
            elif args.action == "prepare-proposed-main-archive":
                if args.plan is None:
                    parser.error("--plan is required for a proposed main source archive")
                result, code = prepare_proposed_main_source_archive(
                    plan_path=args.plan, output_dir=args.output_dir,
                ), 0
            elif args.action == "verify-proposed-main-archive":
                result, code = verify_proposed_main_source_archive(args.output_dir), 0
            elif args.action == "prepare-final-main-schedule":
                if args.plan is None or args.design_artifacts is None:
                    parser.error("--plan and --design-artifacts are required for final schedule preparation")
                result, code = prepare_final_main_schedule(
                    proposal_path=args.plan, design_artifacts_path=args.design_artifacts,
                    output_dir=args.output_dir,
                ), 0
            else:
                result, code = verify_rehearsal(args.output_dir), 0
    except (MainOrchestrationError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "INVALID", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

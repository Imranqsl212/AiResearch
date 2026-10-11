"""Preschedule a small, excluded v7 truthful-evidence and hidden-veto pilot.

This is a finite-mode engineering study, not a main release or an estimate of
security repair in general software. Every slot is written once and retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import urllib.request
from pathlib import Path
from typing import Any

from agent.v1_ollama_adapter import V1OllamaAdapter
from analysis.v1_pipeline import load_episode
from experiments.main_orchestrator import ROOT, _SOURCE_FILES, _catalog, _hash, _write_once
from experiments.v1_collector import collect_episode


VERSION = "excluded-v7-decisive-pilot-1.0.0"
INDEX = "benchmark/tasks/v7_batch_c/index.json"
FAMILIES = ("csrf_origin", "environment_injection")
CONDITIONS = ("C1", "C2", "C3", "C4", "C5")
REPEATS = 3
TEMPERATURE = 0.3
SEED = 20261005
MODEL = "qwen3:4b"
MAX_STEPS = 4
TIMEOUT_SECONDS = 150
REQUEST_TIMEOUT_SECONDS = 90
MAX_OUTPUT_TOKENS = 256
CONTEXT_WINDOW = 4096
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE = tuple(sorted(set(_SOURCE_FILES) | {
    "experiments/run_v7_decisive_excluded_pilot.py",
    "benchmark/finite_batch_c_v7.py",
    "benchmark/finite_batch_c_reference_v7.py",
    "agent/prompts/finite_options_system.txt",
    "benchmark/retrieval_corpus_v1.jsonl",
    INDEX,
}))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def plan(*, model_digest: str, runtime_version: str, root: Path = ROOT) -> dict[str, Any]:
    """Lock two authored families, five conditions and three shared seed blocks."""
    if not isinstance(model_digest, str) or _HEX.fullmatch(model_digest) is None:
        raise ValueError("model digest must be a full lowercase SHA-256")
    if not isinstance(runtime_version, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", runtime_version):
        raise ValueError("runtime version must be explicit")
    catalog = _catalog((INDEX,), root)
    selected = [row for row in catalog if row["family"] in FAMILIES]
    if (len(selected) != len(FAMILIES) * len(CONDITIONS)
            or {row["family"] for row in selected} != set(FAMILIES)
            or any({row["condition"] for row in selected if row["family"] == family}
                   != set(CONDITIONS) for family in FAMILIES)):
        raise ValueError("selected v7 cells are incomplete")
    by_cell = {(row["family"], row["condition"]): row for row in selected}
    rng = random.Random(SEED)
    slots: list[dict[str, Any]] = []
    for family in FAMILIES:
        for repeat in range(1, REPEATS + 1):
            shared_seed = rng.randrange(0, 2**31)
            for condition in CONDITIONS:
                slots.append({
                    **by_cell[(family, condition)],
                    "repeat": repeat,
                    "inference_seed": shared_seed,
                    "episode_id": f"v7-{family}-{condition.lower()}-r{repeat}",
                })
    rng.shuffle(slots)
    for order, slot in enumerate(slots, 1):
        slot["slot_id"] = f"slot-{order:06d}"
        slot["order"] = order
    source_paths = set(_SOURCE)
    source_paths.update(row["task_path"] for row in selected)
    source_paths.update(row["proof_path"] for row in selected)
    hashes = {name: _hash(root / name) for name in sorted(source_paths)}
    return {
        "schema_version": VERSION,
        "phase": "pilot",
        "eligible_for_main_analysis": False,
        "purpose": "finite_oracle_truthful_evidence_and_hidden_veto_feasibility",
        "scope": "bounded_stateless_modes_and_authored_finite_worlds_only",
        "model": MODEL,
        "model_digest": model_digest,
        "ollama_runtime_version": runtime_version,
        "temperature": TEMPERATURE,
        "base_seed": SEED,
        "repeats_per_cell": REPEATS,
        "families": list(FAMILIES),
        "conditions": list(CONDITIONS),
        "max_steps": MAX_STEPS,
        "episode_timeout_seconds": TIMEOUT_SECONDS,
        "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "context_window": CONTEXT_WINDOW,
        "retry_policy": "one_attempt_per_prescheduled_slot_no_replacement",
        "source_file_sha256s": hashes,
        "slots": slots,
    }


def prepare(output_dir: Path, *, model_digest: str, runtime_version: str) -> dict[str, Any]:
    schedule = plan(model_digest=model_digest, runtime_version=runtime_version)
    output_dir.mkdir(parents=True, exist_ok=False)
    archive = output_dir / "source_archive"
    for name, expected_hash in schedule["source_file_sha256s"].items():
        source = ROOT / name
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"missing or symlinked source: {name}")
        data = source.read_bytes()
        if _sha(data) != expected_hash:
            raise ValueError(f"source changed during archive: {name}")
        _write_once(archive / name, data)
    _write_once(output_dir / "schedule.json", schedule)
    return {
        "schedule_path": str((output_dir / "schedule.json").resolve()),
        "schedule_sha256": _hash(output_dir / "schedule.json"),
        "planned_slots": len(schedule["slots"]),
    }


def _validate_schedule(output_dir: Path) -> dict[str, Any]:
    saved = _read(output_dir / "schedule.json")
    if saved.get("schema_version") != VERSION or saved.get("eligible_for_main_analysis") is not False:
        raise ValueError("schedule is not this excluded pilot")
    rebuilt = plan(model_digest=saved["model_digest"],
                   runtime_version=saved["ollama_runtime_version"])
    if rebuilt != saved:
        raise ValueError("schedule, task or current source hashes drifted")
    archive = output_dir / "source_archive"
    archived = {p.relative_to(archive).as_posix() for p in archive.rglob("*") if p.is_file()}
    if archived != set(saved["source_file_sha256s"]):
        raise ValueError("source archive inventory differs")
    for name, expected_hash in saved["source_file_sha256s"].items():
        if _hash(archive / name) != expected_hash:
            raise ValueError(f"archived source differs: {name}")
    return saved


def _observed_provider(base_url: str, model: str) -> tuple[str, str]:
    base = base_url.rstrip("/")
    with urllib.request.urlopen(f"{base}/api/version", timeout=10) as response:
        version = json.load(response)["version"]
    with urllib.request.urlopen(f"{base}/api/tags", timeout=10) as response:
        tags = json.load(response)
    for row in tags.get("models", []):
        if row.get("name") == model or row.get("model") == model:
            return str(row["digest"]), str(version)
    raise ValueError("frozen model is absent from Ollama tags")


def _slot_summary(manifest_path: Path) -> dict[str, Any]:
    loaded = load_episode(manifest_path, source_root=ROOT)
    manifest = loaded["manifest"]
    actions = [event for event in loaded["events"] if event.get("event_type") == "ACTION"]
    submissions = [event for event in actions if event.get("action_type") == "SUBMIT"]
    secure = [event for event in submissions if event.get("security_oracle_result") == "SECURE"]
    discordant = [event for event in submissions
                  if event.get("security_oracle_result") == "SECURE"
                  and event.get("benchmark_verdict") == "FAIL"]
    return {
        "status": "INVALIDATED" if loaded["invalidated"] else "VALID_EXCLUDED",
        "stop_reason": manifest["stop_reason"],
        "actions": len(actions),
        "submitted_candidates": len(submissions),
        "oracle_secure_submissions": len(secure),
        "first_secure_action_step": secure[0]["step"] if secure else None,
        "secure_oracle_gate_discordant_submissions": len(discordant),
        "early_voluntary_stop": manifest["stop_reason"] == "VOLUNTARY"
                                and len(actions) < manifest["max_steps"],
        "manifest_sha256": _hash(manifest_path),
    }


def execute(output_dir: Path, *, base_url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    schedule = _validate_schedule(output_dir)
    if (output_dir / "run.receipt.json").exists() or any(output_dir.glob("slot-*")):
        raise ValueError("pilot already began; refusing an implicit retry")
    observed_digest, observed_version = _observed_provider(base_url, schedule["model"])
    if observed_digest != schedule["model_digest"] or observed_version != schedule["ollama_runtime_version"]:
        raise ValueError("Ollama model or runtime differs from schedule")
    schedule_hash = _hash(output_dir / "schedule.json")
    results: list[dict[str, Any]] = []
    for slot in schedule["slots"]:
        slot_dir = output_dir / slot["slot_id"]
        slot_dir.mkdir(exist_ok=False)
        _write_once(slot_dir / "reservation.json", {
            "slot_id": slot["slot_id"], "episode_id": slot["episode_id"],
            "schedule_sha256": schedule_hash, "attempt_index": 1,
        })
        try:
            adapter = V1OllamaAdapter(
                model=schedule["model"], base_url=base_url,
                max_output_tokens=schedule["max_output_tokens"],
                context_window=schedule["context_window"],
                request_timeout=schedule["request_timeout_seconds"],
            )
            collected = collect_episode(
                task_path=ROOT / slot["task_path"], proof_path=ROOT / slot["proof_path"],
                adapter=adapter, output_dir=slot_dir, episode_id=slot["episode_id"],
                experiment_id="excluded-v7-decisive-pilot", phase="pilot",
                model=schedule["model"], baseline_code="B3", retrieval_mode="R0",
                max_steps=schedule["max_steps"],
                timeout_seconds=schedule["episode_timeout_seconds"],
                seed=slot["inference_seed"], temperature=schedule["temperature"],
            )
            summary = _slot_summary(Path(collected["manifest"]))
        except Exception as exc:
            summary = {"status": "INVALIDATED", "error_type": type(exc).__name__,
                       "error_sha256": _sha(str(exc).encode("utf-8", errors="replace"))}
        row = {
            "slot_id": slot["slot_id"], "episode_id": slot["episode_id"],
            "family": slot["family"], "condition": slot["condition"],
            "repeat": slot["repeat"], "inference_seed": slot["inference_seed"],
            **summary,
        }
        _write_once(slot_dir / "slot_result.json", row)
        results.append(row)
        print(json.dumps({
            "slot": slot["slot_id"], "condition": slot["condition"],
            "family": slot["family"], "status": row["status"],
            "submissions": row.get("submitted_candidates"),
        }, sort_keys=True), flush=True)
    receipt = {
        "schema_version": VERSION, "phase": "pilot",
        "eligible_for_main_analysis": False,
        "schedule_sha256": schedule_hash,
        "planned_slots": len(schedule["slots"]),
        "valid_slots": sum(row["status"] == "VALID_EXCLUDED" for row in results),
        "invalidated_slots": sum(row["status"] == "INVALIDATED" for row in results),
        "results": results,
    }
    _write_once(output_dir / "run.receipt.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "execute"))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model-digest")
    parser.add_argument("--runtime-version")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    if args.action == "prepare":
        if args.model_digest is None or args.runtime_version is None:
            parser.error("prepare requires --model-digest and --runtime-version")
        result = prepare(args.output_dir, model_digest=args.model_digest,
                         runtime_version=args.runtime_version)
    else:
        result = execute(args.output_dir, base_url=args.base_url)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

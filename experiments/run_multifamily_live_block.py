"""Prepare and execute a no-replacement, excluded ten-slot finite-family pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

from agent.v1_ollama_adapter import V1OllamaAdapter
from analysis.summarize_finite_family_pilot import summarize_block, validate_schedule
from analysis.v1_pipeline import load_episode
from experiments.v1_collector import _IMPLEMENTATION_FILES, V1CollectionError, collect_episode


ROOT = Path(__file__).resolve().parents[1]
ORDER = tuple((family, condition) for condition in ("C4", "C1", "C5", "C2", "C3")
              for family in ("path-boundary", "transaction_replay"))
TASKS = {
    "path-boundary": ("v2_path", "fp-path-boundary"),
    "transaction_replay": ("v3_replay", "fr-transaction-replay"),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_once(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def prepare(block_dir: Path, *, model: str, model_digest: str, seed: int = 7,
            temperature: float = 0.0, max_steps: int = 6,
            max_output_tokens: int = 256) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", model_digest):
        raise ValueError("model digest must be the full lowercase SHA-256")
    if type(seed) is not int or seed < 0 or not 0 <= temperature <= 2 or max_steps <= 0 or max_output_tokens <= 0:
        raise ValueError("invalid fixed pilot budget or sampling settings")
    slots = []
    for family, condition in ORDER:
        directory, prefix = TASKS[family]
        stem = f"{prefix}-{condition.lower()}"
        task_path = ROOT / "benchmark" / "tasks" / directory / f"{stem}.task.json"
        proof_path = ROOT / "benchmark" / "tasks" / directory / f"{stem}.proof.json"
        slots.append({
            "episode_id": f"{family}-{condition.lower()}-seed{seed}",
            "family": family, "condition": condition,
            "task_path": str(task_path.resolve()), "task_sha256": _sha256(task_path),
            "proof_path": str(proof_path.resolve()), "proof_sha256": _sha256(proof_path),
        })
    schedule = {
        "kind": "excluded_finite_multifamily_r0_10slot", "schema_version": "1.0",
        "phase": "pilot", "purpose": "excluded_exploratory_live_multifamily_block",
        "model": model, "model_digest": model_digest, "retrieval_mode": "R0",
        "seed": seed, "temperature": float(temperature), "max_steps": max_steps,
        "max_output_tokens": max_output_tokens, "no_retries_or_replacements": True,
        "slots": slots,
        "source_file_sha256s": {name: _sha256(ROOT / name) for name in _IMPLEMENTATION_FILES},
        "runner_sha256": _sha256(Path(__file__)),
        "summarizer_sha256": _sha256(ROOT / "analysis" / "summarize_finite_family_pilot.py"),
    }
    validate_schedule(schedule)
    block_dir.mkdir(parents=True, exist_ok=False)
    _write_once(block_dir / "block_schedule.json", schedule)
    return {"schedule_path": str((block_dir / "block_schedule.json").resolve()),
            "schedule_sha256": _sha256(block_dir / "block_schedule.json"), "scheduled_slots": len(slots)}


def _observed_model_digest(model: str, base_url: str) -> str:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=10) as response:
        payload = json.load(response)
    for row in payload.get("models", []):
        if row.get("name") == model or row.get("model") == model:
            return str(row.get("digest", ""))
    raise V1CollectionError(f"model {model} is absent from local Ollama tags")


def execute(block_dir: Path, *, base_url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    schedule_path = block_dir / "block_schedule.json"
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    validate_schedule(schedule)
    if any(block_dir.glob("*.manifest.json")) or any(block_dir.glob("*.jsonl")) or (block_dir / "block_receipt.json").exists():
        raise V1CollectionError("block already has run artifacts; refusing an implicit retry")
    if schedule["runner_sha256"] != _sha256(Path(__file__)) or schedule["summarizer_sha256"] != _sha256(ROOT / "analysis" / "summarize_finite_family_pilot.py"):
        raise V1CollectionError("runner or summarizer changed after schedule freeze")
    if any(_sha256(ROOT / name) != digest for name, digest in schedule["source_file_sha256s"].items()):
        raise V1CollectionError("implementation changed after schedule freeze")
    if any(_sha256(Path(slot["task_path"])) != slot["task_sha256"] or
           _sha256(Path(slot["proof_path"])) != slot["proof_sha256"] for slot in schedule["slots"]):
        raise V1CollectionError("task or proof changed after schedule freeze")
    observed_digest = _observed_model_digest(schedule["model"], base_url)
    if observed_digest != schedule["model_digest"]:
        raise V1CollectionError("local model digest differs from frozen schedule")

    for index, slot in enumerate(schedule["slots"], start=1):
        episode_id = slot["episode_id"]
        adapter = V1OllamaAdapter(
            model=schedule["model"], base_url=base_url,
            max_output_tokens=schedule["max_output_tokens"], request_timeout=90,
        )
        try:
            result = collect_episode(
                task_path=Path(slot["task_path"]), proof_path=Path(slot["proof_path"]),
                adapter=adapter, output_dir=block_dir, episode_id=episode_id,
                experiment_id="excluded-live-multifamily-pilot", phase="pilot",
                model=schedule["model"], baseline_code="B3", retrieval_mode="R0",
                max_steps=schedule["max_steps"], timeout_seconds=120,
                seed=schedule["seed"], temperature=schedule["temperature"],
            )
            loaded = load_episode(Path(result["manifest"]), source_root=ROOT)
            print(json.dumps({"slot": index, "episode_id": episode_id,
                              "stop_reason": loaded["manifest"]["stop_reason"],
                              "invalidated": loaded["invalidated"]}), flush=True)
        except Exception as exc:
            # Preserve the scheduled slot and continue unaffected slots once.
            # No raw provider error text enters the receipt.
            if not (block_dir / f"{episode_id}.manifest.json").exists():
                error = {"episode_id": episode_id, "error_type": type(exc).__name__,
                         "error_sha256": hashlib.sha256(str(exc).encode("utf-8", errors="replace")).hexdigest()}
                _write_once(block_dir / f"{episode_id}.slot_error.json", error)
            print(json.dumps({"slot": index, "episode_id": episode_id,
                              "status": "INVALIDATED", "error_type": type(exc).__name__}), flush=True)
    report = summarize_block(block_dir, source_root=ROOT)
    _write_once(block_dir / "block_receipt.json", report)
    summarize_block(block_dir, source_root=ROOT, verify_receipt=True)
    return {"validated_slots": report["validated_slots"], "invalidated_slots": report["invalidated_slots"],
            "receipt": str((block_dir / "block_receipt.json").resolve())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "execute"))
    parser.add_argument("--block-dir", type=Path, required=True)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--model-digest")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    if args.action == "prepare":
        if args.model_digest is None:
            parser.error("prepare requires --model-digest")
        result = prepare(args.block_dir, model=args.model, model_digest=args.model_digest)
    else:
        result = execute(args.block_dir, base_url=args.base_url)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""One excluded C1/C2 live feasibility block across every finite family.

This pilot measures whether the frozen local action protocol can produce an
agent-generated secure onset. It cannot contribute to prospective estimates.
Every slot is reserved and attempted once; failures remain in the ledger.
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
from experiments.main_orchestrator import ALL_FINITE_INDEXES, ROOT, _SOURCE_FILES, _catalog, _hash, _write_once
from experiments.v1_collector import collect_episode


VERSION = "excluded-full-catalog-live-feasibility-1.0.0"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,127}\Z")
_SOURCE = tuple(sorted(set(_SOURCE_FILES) | {
    "experiments/run_full_catalog_live_feasibility.py",
}))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _plan(*, model: str, model_digest: str, seed: int,
          temperature: float, root: Path = ROOT) -> dict[str, Any]:
    if not isinstance(model, str) or not _MODEL.fullmatch(model):
        raise ValueError("unsafe model name")
    if not isinstance(model_digest, str) or not _HEX64.fullmatch(model_digest):
        raise ValueError("model digest must be a full lowercase SHA-256")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be nonnegative")
    if type(temperature) not in (int, float) or not 0 <= temperature <= 2:
        raise ValueError("invalid temperature")
    catalog = _catalog(ALL_FINITE_INDEXES, root)
    tasks = [row for row in catalog if row["condition"] in {"C1", "C2"}]
    if len(tasks) != 40 or len({row["family"] for row in tasks}) != 20:
        raise ValueError("the C1/C2 finite catalog is incomplete")
    rng = random.Random(seed)
    slots = [{**task, "inference_seed": rng.randrange(0, 2**31)} for task in tasks]
    rng.shuffle(slots)
    for number, slot in enumerate(slots, 1):
        slot["slot_id"] = f"slot-{number:06d}"
        slot["episode_id"] = f"live-{number:06d}"
        slot["order"] = number
    source_paths = set(_SOURCE) | {"experiment_manifest.json", "benchmark/retrieval_corpus_v1.jsonl"}
    source_paths.update(ALL_FINITE_INDEXES)
    for task in catalog:
        source_paths.update((task["task_path"], task["proof_path"]))
    return {
        "schema_version": VERSION,
        "phase": "pilot",
        "eligible_for_main_analysis": False,
        "purpose": "agent_generated_secure_onset_and_protocol_feasibility_only",
        "model": model,
        "model_digest": model_digest,
        "seed": seed,
        "temperature": float(temperature),
        "retrieval_mode": "R0",
        "conditions": ["C1", "C2"],
        "max_steps": 6,
        "episode_timeout_seconds": 180,
        "request_timeout_seconds": 90,
        "max_output_tokens": 256,
        "context_window": 4096,
        "retry_policy": "one_attempt_per_prescheduled_slot_no_replacement",
        "source_file_sha256s": {name: _hash(root / name) for name in sorted(source_paths)},
        "slots": slots,
    }


def prepare(output_dir: Path, *, model: str, model_digest: str,
            seed: int = 20261005, temperature: float = 0.3) -> dict[str, Any]:
    plan = _plan(model=model, model_digest=model_digest,
                 seed=seed, temperature=temperature)
    output_dir.mkdir(parents=True, exist_ok=False)
    archive = output_dir / "source_archive"
    for relative, expected_hash in plan["source_file_sha256s"].items():
        source = ROOT / relative
        target = archive / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"source artifact is missing or symlinked: {relative}")
        with source.open("rb") as reader:
            data = reader.read()
        if _sha256(data) != expected_hash:
            raise ValueError(f"source changed during archive: {relative}")
        _write_once(target, data)
    _write_once(output_dir / "schedule.json", plan)
    return {"schedule_path": str((output_dir / "schedule.json").resolve()),
            "schedule_sha256": _hash(output_dir / "schedule.json"),
            "planned_slots": len(plan["slots"])}


def _validate_plan(output_dir: Path) -> dict[str, Any]:
    plan = _read(output_dir / "schedule.json")
    if plan.get("schema_version") != VERSION or plan.get("phase") != "pilot" or plan.get("eligible_for_main_analysis") is not False:
        raise ValueError("schedule is not the excluded live feasibility protocol")
    rebuilt = _plan(model=plan["model"], model_digest=plan["model_digest"],
                    seed=plan["seed"], temperature=plan["temperature"])
    if plan != rebuilt:
        raise ValueError("schedule, task, or current source hashes drifted")
    archive = output_dir / "source_archive"
    archived = {path.relative_to(archive).as_posix() for path in archive.rglob("*") if path.is_file()}
    if archived != set(plan["source_file_sha256s"]):
        raise ValueError("source archive inventory differs from schedule")
    for relative, expected in plan["source_file_sha256s"].items():
        if _hash(archive / relative) != expected:
            raise ValueError(f"source archive hash differs: {relative}")
    return plan


def _observed_model_digest(model: str, base_url: str) -> str:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=10) as response:
        payload = json.load(response)
    for row in payload.get("models", []):
        if row.get("name") == model or row.get("model") == model:
            return str(row.get("digest", ""))
    raise ValueError("frozen model is absent from Ollama tags")


def _slot_summary(manifest_path: Path) -> dict[str, Any]:
    loaded = load_episode(manifest_path, source_root=ROOT)
    manifest = loaded["manifest"]
    actions = [event for event in loaded["events"] if event["event_type"] == "ACTION"]
    secure = [event for event in actions if event["action_type"] == "SUBMIT"
              and event["security_oracle_result"] == "SECURE"]
    return {
        "status": "INVALIDATED" if loaded["invalidated"] else "VALID_EXCLUDED",
        "stop_reason": manifest["stop_reason"],
        "model_decisions": loaded["events"][-1].get("provider_request_count"),
        "submitted_candidates": sum(event["action_type"] == "SUBMIT" for event in actions),
        "secure_onset": bool(secure),
        "first_secure_action_step": secure[0]["step"] if secure else None,
        "provider_request_count": loaded["events"][-1].get("provider_request_count"),
        "request_archive_complete": manifest.get("provider_request_archive_complete"),
        "manifest_sha256": _hash(manifest_path),
    }


def execute(output_dir: Path, *, base_url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    plan = _validate_plan(output_dir)
    if (output_dir / "run.receipt.json").exists() or any(output_dir.glob("slot-*")):
        raise ValueError("block already began; refusing an implicit retry")
    if _observed_model_digest(plan["model"], base_url) != plan["model_digest"]:
        raise ValueError("Ollama model digest changed after scheduling")
    schedule_hash = _hash(output_dir / "schedule.json")
    results: list[dict[str, Any]] = []
    for slot in plan["slots"]:
        slot_dir = output_dir / slot["slot_id"]
        slot_dir.mkdir(exist_ok=False)
        _write_once(slot_dir / "reservation.json", {
            "slot_id": slot["slot_id"], "episode_id": slot["episode_id"],
            "schedule_sha256": schedule_hash, "attempt_index": 1,
        })
        try:
            adapter = V1OllamaAdapter(
                model=plan["model"], base_url=base_url,
                max_output_tokens=plan["max_output_tokens"],
                context_window=plan["context_window"],
                request_timeout=plan["request_timeout_seconds"],
            )
            result = collect_episode(
                task_path=ROOT / slot["task_path"], proof_path=ROOT / slot["proof_path"],
                adapter=adapter, output_dir=slot_dir,
                episode_id=slot["episode_id"], experiment_id="excluded-full-catalog-feasibility",
                phase="pilot", model=plan["model"], baseline_code="B3", retrieval_mode="R0",
                max_steps=plan["max_steps"], timeout_seconds=plan["episode_timeout_seconds"],
                seed=slot["inference_seed"], temperature=plan["temperature"],
            )
            summary = _slot_summary(Path(result["manifest"]))
        except Exception as exc:
            summary = {"status": "INVALIDATED", "error_type": type(exc).__name__,
                       "error_sha256": _sha256(str(exc).encode("utf-8", errors="replace"))}
        row = {"slot_id": slot["slot_id"], "episode_id": slot["episode_id"],
               "family": slot["family"], "condition": slot["condition"], **summary}
        _write_once(slot_dir / "slot_result.json", row)
        results.append(row)
        print(json.dumps({"slot": slot["slot_id"], "family": slot["family"],
                          "condition": slot["condition"], "status": row["status"],
                          "secure_onset": row.get("secure_onset")}, sort_keys=True), flush=True)
    receipt = {
        "schema_version": VERSION, "phase": "pilot", "eligible_for_main_analysis": False,
        "schedule_sha256": schedule_hash, "planned_slots": len(plan["slots"]),
        "valid_slots": sum(row["status"] == "VALID_EXCLUDED" for row in results),
        "invalidated_slots": sum(row["status"] == "INVALIDATED" for row in results),
        "secure_onset_slots": sum(row.get("secure_onset") is True for row in results),
        "secure_onset_families": len({row["family"] for row in results if row.get("secure_onset") is True}),
        "results": results,
    }
    _write_once(output_dir / "run.receipt.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "execute"))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--model-digest")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--seed", type=int, default=20261005)
    parser.add_argument("--temperature", type=float, default=0.3)
    args = parser.parse_args()
    if args.action == "prepare":
        if args.model_digest is None:
            parser.error("prepare requires --model-digest")
        result = prepare(args.output_dir, model=args.model, model_digest=args.model_digest,
                         seed=args.seed, temperature=args.temperature)
    else:
        result = execute(args.output_dir, base_url=args.base_url)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

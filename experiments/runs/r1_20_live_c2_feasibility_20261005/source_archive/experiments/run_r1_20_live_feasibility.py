"""Prescheduled excluded C2 R0/R1 live feasibility across 20 finite families.

This probes the unreviewed top-one candidate retriever and local model only.
Every scheduled slot is retained; no episode is eligible for main analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import urllib.request
from pathlib import Path
from typing import Any

from agent.v1_ollama_adapter import V1OllamaAdapter
from analysis.v1_pipeline import load_episode
from benchmark.retrieval_r1_20_candidate import freeze_candidate_manifest
from experiments.main_orchestrator import ALL_FINITE_INDEXES, ROOT, _SOURCE_FILES, _catalog, _hash
from experiments.v1_collector import collect_episode


VERSION = "excluded-r1-20-live-c2-feasibility-1.0.0"
OUTPUT = ROOT / "experiments/runs/r1_20_live_c2_feasibility_20261005"
MANIFEST = ROOT / "benchmark/retrieval_manifest_r1_20_candidate.json"
MODEL = "qwen3:4b"
MODEL_DIGEST = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"
SEED = 2026100515
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE = tuple(sorted(set(_SOURCE_FILES) | {
    "experiments/run_r1_20_live_feasibility.py",
    "benchmark/retrieval_r1_20_candidate.py",
    "benchmark/retrieval_corpus_r1_20_candidate.jsonl",
    "benchmark/retrieval_manifest_r1_20_candidate.json",
    "benchmark/retrieval_corpus_v2.jsonl",
}))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _file_hash(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or symlinked artifact: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _write_once(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(_canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def _plan() -> dict[str, Any]:
    if not _HEX64.fullmatch(MODEL_DIGEST):
        raise ValueError("model digest is not SHA-256")
    candidate_manifest = _read(MANIFEST)
    if candidate_manifest != freeze_candidate_manifest():
        raise ValueError("unreviewed candidate manifest/corpus/provider drifted")
    catalog = _catalog(ALL_FINITE_INDEXES, ROOT)
    c2 = [task for task in catalog if task["condition"] == "C2"]
    if len(c2) != 20 or len({task["family"] for task in c2}) != 20:
        raise ValueError("20 C2 family rows required")
    rng = random.Random(SEED)
    blocks = []
    for task in c2:
        seed = rng.randrange(0, 2**31)
        pair = [{**task, "retrieval_mode": mode, "inference_seed": seed}
                for mode in ("R0", "R1")]
        rng.shuffle(pair)
        blocks.append(pair)
    rng.shuffle(blocks)
    slots = [slot for pair in blocks for slot in pair]
    for index, slot in enumerate(slots, 1):
        slot.update({"slot_id": f"slot-{index:06d}",
                     "episode_id": f"r1live-{index:06d}", "order": index})
    source_paths = set(_SOURCE) | {"experiment_manifest.json"}
    source_paths.update(ALL_FINITE_INDEXES)
    for task in c2:
        source_paths.update((task["task_path"], task["proof_path"]))
    return {"version": VERSION, "phase": "pilot", "eligible_for_main_analysis": False,
            "purpose": "unreviewed_20_family_top_one_R1_live_integration_only",
            "model": MODEL, "model_digest": MODEL_DIGEST,
            "seed": SEED, "temperature": 0.3,
            "conditions": ["C2"], "retrieval_modes": ["R0", "R1"],
            "retrieval_provider": "r1_20_candidate",
            "retrieval_manifest_path": str(MANIFEST.resolve()),
            "retrieval_manifest_sha256": _file_hash(MANIFEST),
            "max_steps": 6, "episode_timeout_seconds": 240,
            "request_timeout_seconds": 120,
            "max_output_tokens": 256, "context_window": 4096,
            "retry_policy": "one_attempt_per_prescheduled_slot_no_replacement",
            "paired_seed_policy": "same_seed_within_family_R0_R1_independent_contexts",
            "source_file_sha256s": {name: _hash(ROOT / name) for name in sorted(source_paths)},
            "slots": slots}


def prepare(output: Path = OUTPUT) -> dict[str, Any]:
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("output exists; refusing overwrite")
    plan = _plan()
    output.mkdir(parents=True, exist_ok=False)
    archive = output / "source_archive"
    for relative, digest in plan["source_file_sha256s"].items():
        source = ROOT / relative
        if _file_hash(source) != digest:
            raise ValueError("source changed during plan archive")
        destination = archive / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as handle:
            handle.write(source.read_bytes())
        if _file_hash(destination) != digest:
            raise ValueError("source archive differs")
    _write_once(output / "schedule.json", plan)
    return {"schedule_path": str(output / "schedule.json"),
            "schedule_sha256": _file_hash(output / "schedule.json"),
            "planned_slots": len(plan["slots"])}


def _validate(output: Path) -> dict[str, Any]:
    plan = _read(output / "schedule.json")
    if plan != _plan():
        raise ValueError("scheduled source, task, model or retrieval manifest drifted")
    archive = output / "source_archive"
    archived = {path.relative_to(archive).as_posix()
                for path in archive.rglob("*") if path.is_file()}
    if archived != set(plan["source_file_sha256s"]):
        raise ValueError("source archive inventory differs")
    for name, digest in plan["source_file_sha256s"].items():
        if _file_hash(archive / name) != digest:
            raise ValueError(f"archived source changed: {name}")
    return plan


def _observed_digest(model: str, base_url: str) -> str:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=10) as response:
        payload = json.load(response)
    for row in payload.get("models", []):
        if row.get("name") == model or row.get("model") == model:
            return str(row.get("digest", ""))
    raise ValueError("scheduled Ollama model tag is missing")


def execute(output: Path = OUTPUT, *, base_url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    output = Path(output).resolve()
    plan = _validate(output)
    if (output / "run.receipt.json").exists():
        raise FileExistsError("block already completed; no rerun")
    if _observed_digest(plan["model"], base_url) != plan["model_digest"]:
        raise ValueError("model digest differs before model dispatch")
    schedule_hash = _file_hash(output / "schedule.json")
    started_path = output / "started.json"
    if started_path.exists():
        if _read(started_path) != {"version": VERSION, "phase": "pilot",
                                   "schedule_sha256": schedule_hash,
                                   "no_retries": True}:
            raise ValueError("started receipt differs")
    else:
        _write_once(started_path, {"version": VERSION, "phase": "pilot",
                                   "schedule_sha256": schedule_hash, "no_retries": True})
    results = []
    for slot in plan["slots"]:
        slot_dir = output / slot["slot_id"]
        slot_result_path = slot_dir / "slot_result.json"
        if slot_result_path.exists():
            row = _read(slot_result_path)
            if (row.get("slot_id") != slot["slot_id"] or
                    row.get("episode_id") != slot["episode_id"] or
                    row.get("family") != slot["family"] or
                    row.get("retrieval_mode") != slot["retrieval_mode"]):
                raise ValueError("previous slot result identity differs")
            row["batch_resume_status"] = "PRIOR_RESULT_REUSED_NO_MODEL_RETRY"
        elif slot_dir.exists():
            row = {"slot_id": slot["slot_id"], "episode_id": slot["episode_id"],
                   "family": slot["family"], "condition": "C2",
                   "retrieval_mode": slot["retrieval_mode"],
                   "status": "INVALIDATED", "error_type": "ORPHANED_AFTER_START"}
            _write_once(slot_result_path, row)
        else:
            slot_dir.mkdir()
            _write_once(slot_dir / "reservation.json", {
                "slot_id": slot["slot_id"], "episode_id": slot["episode_id"],
                "schedule_sha256": schedule_hash, "attempt_index": 1})
            try:
                adapter = V1OllamaAdapter(
                    model=plan["model"], base_url=base_url,
                    max_output_tokens=plan["max_output_tokens"],
                    context_window=plan["context_window"],
                    request_timeout=plan["request_timeout_seconds"])
                result = collect_episode(
                    task_path=ROOT / slot["task_path"], proof_path=ROOT / slot["proof_path"],
                    adapter=adapter, output_dir=slot_dir,
                    episode_id=slot["episode_id"], experiment_id="excluded-r1-20-live-c2",
                    phase="pilot", model=plan["model"],
                    baseline_code="B3" if slot["retrieval_mode"] == "R0" else "B5",
                    retrieval_mode=slot["retrieval_mode"],
                    retrieval_provider="r1_20_candidate", retrieval_manifest_path=MANIFEST,
                    max_steps=plan["max_steps"], timeout_seconds=plan["episode_timeout_seconds"],
                    seed=slot["inference_seed"], temperature=plan["temperature"])
                manifest_path = Path(result["manifest"])
                episode = load_episode(manifest_path, source_root=ROOT)
                manifest = episode["manifest"]
                actions = [e for e in episode["events"] if e["event_type"] == "ACTION"]
                secure = [e for e in actions if e["action_type"] == "SUBMIT"
                          and e["security_oracle_result"] == "SECURE"]
                row = {"slot_id": slot["slot_id"], "episode_id": slot["episode_id"],
                       "family": slot["family"], "condition": "C2",
                       "retrieval_mode": slot["retrieval_mode"],
                       "status": "INVALIDATED" if episode["invalidated"] else "VALID_EXCLUDED",
                       "manifest_sha256": _file_hash(manifest_path),
                       "stop_reason": manifest["stop_reason"],
                       "secure_onset": bool(secure),
                       "provider_requests": len(manifest.get("provider_request_archive", []))}
            except Exception as exc:
                row = {"slot_id": slot["slot_id"], "episode_id": slot["episode_id"],
                       "family": slot["family"], "condition": "C2",
                       "retrieval_mode": slot["retrieval_mode"],
                       "status": "INVALIDATED", "error_type": type(exc).__name__,
                       "error_sha256": hashlib.sha256(str(exc).encode("utf-8", errors="replace")).hexdigest()}
            _write_once(slot_result_path, row)
        results.append(row)
        print(json.dumps({key: row.get(key) for key in
                          ("slot_id", "family", "retrieval_mode", "status", "secure_onset")},
                         sort_keys=True), flush=True)
    receipt = {"version": VERSION, "phase": "pilot", "eligible_for_main_analysis": False,
               "schedule_sha256": schedule_hash, "started_sha256": _file_hash(started_path),
               "planned_slots": len(plan["slots"]),
               "valid_slots": sum(r["status"] == "VALID_EXCLUDED" for r in results),
               "invalidated_slots": sum(r["status"] == "INVALIDATED" for r in results),
               "results": results, "no_retries": True}
    _write_once(output / "run.receipt.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "execute"))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--allow-live-local-ollama", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare(args.output_dir), ensure_ascii=False, sort_keys=True))
    else:
        if not args.allow_live_local_ollama:
            parser.error("live local Ollama requires --allow-live-local-ollama")
        receipt = execute(args.output_dir, base_url=args.base_url)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

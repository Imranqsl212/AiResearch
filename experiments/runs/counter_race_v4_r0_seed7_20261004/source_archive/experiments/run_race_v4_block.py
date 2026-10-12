"""Preschedule, execute, and audit an excluded five-slot counter-race v4 pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

from agent.v1_ollama_adapter import V1OllamaAdapter
from analysis.v1_pipeline import V1ValidationError, load_episode
from benchmark.validate_finite_race_v4 import validate as validate_race_fixture
from experiments.v1_collector import _IMPLEMENTATION_FILES, V1CollectionError, collect_episode


ROOT = Path(__file__).resolve().parents[1]
KIND = "excluded_counter_race_v4_r0_5slot"
CONDITIONS = ("C4", "C1", "C5", "C2", "C3")
PROMPT_PATH = ROOT / "agent" / "prompts" / "race_v4_system.txt"
FIXTURE_DIR = ROOT / "benchmark" / "tasks" / "v4_race"
EXTRA_FROZEN_FILES = (
    "analysis/v1_pipeline.py", "benchmark/validate_finite_race_v4.py",
    "experiments/run_race_v4_block.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_once(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _archive_file_names() -> tuple[str, ...]:
    fixture_files = tuple(str(path.relative_to(ROOT)) for path in sorted(FIXTURE_DIR.iterdir())
                          if path.is_file())
    return tuple(sorted(set(_IMPLEMENTATION_FILES) | set(EXTRA_FROZEN_FILES) | set(fixture_files)))


def _verify_source_archive(block_dir: Path, schedule: dict[str, Any]) -> None:
    expected = schedule.get("source_archive_file_sha256s")
    if not isinstance(expected, dict) or set(expected) != set(_archive_file_names()):
        raise V1ValidationError("counter-race source archive inventory differs from schedule")
    archive = block_dir / "source_archive"
    index_path = block_dir / "source_archive_index.json"
    if not archive.is_dir() or not index_path.is_file():
        raise V1ValidationError("counter-race source archive or index is missing")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if (index.get("kind") != "pre_inference_frozen_source_archive"
        or index.get("schedule_sha256") != _sha256(block_dir / "block_schedule.json")
        or index.get("file_sha256s") != expected):
        raise V1ValidationError("counter-race source archive index disagrees with schedule")
    for name, digest in expected.items():
        archived = archive / name
        if not archived.is_file() or _sha256(archived) != digest:
            raise V1ValidationError(f"counter-race frozen source bytes differ: {name}")


def _schedule(block_dir: Path) -> dict[str, Any]:
    path = block_dir / "block_schedule.json"
    if not path.is_file():
        raise V1ValidationError("counter-race v4 schedule is missing")
    schedule = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(schedule, dict) or schedule.get("kind") != KIND
        or schedule.get("phase") != "pilot" or schedule.get("retrieval_mode") != "R0"
        or schedule.get("protocol_version") != "finite_json_v1"
        or schedule.get("no_retries_or_replacements") is not True
        or not isinstance(schedule.get("slots"), list) or len(schedule["slots"]) != 5
        or [slot.get("condition") for slot in schedule["slots"]] != list(CONDITIONS)
        or not isinstance(schedule.get("source_file_sha256s"), dict)
        or len(schedule["source_file_sha256s"]) < 10):
        raise V1ValidationError("counter-race v4 schedule is incomplete")
    _verify_source_archive(block_dir, schedule)
    return schedule


def prepare(block_dir: Path, *, model: str, model_digest: str, seed: int = 7,
            temperature: float = 0.0, max_steps: int = 6, max_output_tokens: int = 256,
            request_timeout_seconds: float = 90.0,
            episode_timeout_seconds: int = 120) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", model_digest):
        raise ValueError("model digest must be a full lowercase SHA-256")
    if (type(seed) is not int or seed < 0 or not 0 <= temperature <= 2
        or type(max_steps) is not int or not 1 <= max_steps <= 6
        or type(max_output_tokens) is not int or max_output_tokens <= 0
        or request_timeout_seconds <= 0
        or episode_timeout_seconds <= 0):
        raise ValueError("invalid counter-race pilot settings")
    validate_race_fixture()
    slots = []
    for condition in CONDITIONS:
        stem = f"fr-counter-race-{condition.lower()}"
        task_path = ROOT / "benchmark" / "tasks" / "v4_race" / f"{stem}.task.json"
        proof_path = ROOT / "benchmark" / "tasks" / "v4_race" / f"{stem}.proof.json"
        slots.append({
            "episode_id": f"race-{condition.lower()}-seed{seed}",
            "condition": condition,
            "task_path": str(task_path.resolve()), "task_sha256": _sha256(task_path),
            "proof_path": str(proof_path.resolve()), "proof_sha256": _sha256(proof_path),
        })
    schedule = {
        "kind": KIND, "schema_version": "1.0", "phase": "pilot",
        "purpose": "excluded_exploratory_counter_race_v4_pilot",
        "model": model, "model_digest": model_digest,
        "retrieval_mode": "R0", "protocol_version": "finite_json_v1",
        "seed": seed, "temperature": float(temperature),
        "max_steps": max_steps, "max_output_tokens": max_output_tokens,
        "request_timeout_seconds": float(request_timeout_seconds),
        "episode_timeout_seconds": episode_timeout_seconds,
        "no_retries_or_replacements": True, "slots": slots,
        "source_file_sha256s": {name: _sha256(ROOT / name) for name in _IMPLEMENTATION_FILES},
        "source_archive_file_sha256s": {name: _sha256(ROOT / name) for name in _archive_file_names()},
        "runner_sha256": _sha256(Path(__file__)),
        "prompt_template_sha256": _sha256(PROMPT_PATH),
    }
    block_dir.mkdir(parents=True, exist_ok=False)
    _write_once(block_dir / "block_schedule.json", schedule)
    archive = block_dir / "source_archive"
    for name, digest in schedule["source_archive_file_sha256s"].items():
        source = ROOT / name
        destination = archive / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as handle:
            handle.write(source.read_bytes())
        if _sha256(destination) != digest:
            raise V1CollectionError(f"source changed while freezing archive: {name}")
    _write_once(block_dir / "source_archive_index.json", {
        "kind": "pre_inference_frozen_source_archive",
        "schedule_sha256": _sha256(block_dir / "block_schedule.json"),
        "file_sha256s": schedule["source_archive_file_sha256s"],
    })
    _verify_source_archive(block_dir, schedule)
    return {"schedule": str((block_dir / "block_schedule.json").resolve()),
            "schedule_sha256": _sha256(block_dir / "block_schedule.json"),
            "source_archive_index_sha256": _sha256(block_dir / "source_archive_index.json"),
            "scheduled_slots": 5}


def _local_digest(model: str, base_url: str) -> str:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=10) as response:
        payload = json.load(response)
    for row in payload.get("models", []):
        if row.get("name") == model or row.get("model") == model:
            return str(row.get("digest", ""))
    raise V1CollectionError("scheduled local model is missing")


def summarize(block_dir: Path, *, verify_receipt: bool = False) -> dict[str, Any]:
    schedule = _schedule(block_dir)
    expected_ids = {slot["episode_id"] for slot in schedule["slots"]}
    actual_ids = {path.name.removesuffix(".manifest.json") for path in block_dir.glob("*.manifest.json")}
    if not actual_ids <= expected_ids:
        raise V1ValidationError("unplanned counter-race v4 manifest")
    rows = []
    for slot in schedule["slots"]:
        episode_id = slot["episode_id"]
        manifest_path = block_dir / f"{episode_id}.manifest.json"
        error_path = block_dir / f"{episode_id}.slot_error.json"
        if manifest_path.exists() and error_path.exists():
            raise V1ValidationError(f"{episode_id}: conflicting artifacts")
        if error_path.exists():
            error = json.loads(error_path.read_text(encoding="utf-8"))
            if error.get("episode_id") != episode_id:
                raise V1ValidationError(f"{episode_id}: wrong error marker")
            rows.append({"episode_id": episode_id, "condition": slot["condition"],
                         "status": "INVALIDATED_BEFORE_MANIFEST", "error_type": error["error_type"],
                         "error_sha256": error["error_sha256"]})
            continue
        if not manifest_path.exists():
            raise V1ValidationError(f"{episode_id}: scheduled slot is incomplete")
        episode = load_episode(manifest_path, source_root=ROOT)
        manifest = episode["manifest"]
        if (manifest["episode_id"] != episode_id or manifest["family"] != "counter_race"
            or manifest["condition"] != slot["condition"] or manifest["model"] != schedule["model"]
            or manifest["phase"] != "pilot" or manifest["retrieval_mode"] != "R0"
            or manifest["protocol_version"] != "finite_json_v1"
            or manifest["seed"] != schedule["seed"] or manifest["temperature"] != schedule["temperature"]
            or manifest["max_steps"] != schedule["max_steps"]
            or manifest["provider_request_timeout_seconds"] != schedule["request_timeout_seconds"]
            or manifest["episode_timeout_seconds"] != schedule["episode_timeout_seconds"]
            or manifest["task_sha256"] != slot["task_sha256"]
            or manifest["oracle_proof_sha256"] != slot["proof_sha256"]
            or manifest["eligible_for_main_analysis"] is not False):
            raise V1ValidationError(f"{episode_id}: manifest differs from schedule")
        if any(manifest["implementation_file_sha256s"].get(name) != digest
               for name, digest in schedule["source_file_sha256s"].items()):
            raise V1ValidationError(f"{episode_id}: source hashes differ from schedule")
        prompt = json.loads(Path(manifest["prompt_path"]).read_text(encoding="utf-8"))
        request = prompt["request"]
        if (prompt["protocol_version"] != "finite_json_v1"
            or prompt["prompt_template_sha256"] != schedule["prompt_template_sha256"]
            or request["model"] != schedule["model"]
            or request["options"]["seed"] != schedule["seed"]
            or request["options"]["temperature"] != schedule["temperature"]
            or request["options"]["num_predict"] != schedule["max_output_tokens"]):
            raise V1ValidationError(f"{episode_id}: provider prompt differs from schedule")
        events = episode["events"]
        actions = [event for event in events if event["event_type"] == "ACTION"]
        if len(actions) + events[-1]["remaining_action_budget"] != schedule["max_steps"]:
            raise V1ValidationError(f"{episode_id}: action budget differs from schedule")
        submissions = [event for event in actions if event["action_type"] == "SUBMIT"]
        rows.append({
            "episode_id": episode_id, "condition": slot["condition"],
            "status": "INVALIDATED" if episode["invalidated"] else "VALIDATED_PILOT",
            "proof_verified": episode["proof_verified"],
            "candidate_replay_verified": episode["candidate_replay_verified"],
            "stop_reason": events[-1]["stop_reason"], "action_count": len(actions),
            "submission_count": len(submissions),
            "secure_submission_count": sum(event["security_oracle_result"] == "SECURE" for event in submissions),
            "gate_pass_submission_count": sum(event["benchmark_verdict"] == "PASS" for event in submissions),
            "secure_gate_fail_submission_count": sum(
                event["security_oracle_result"] == "SECURE" and event["benchmark_verdict"] == "FAIL"
                for event in submissions),
            "starter_verdict": {key: events[0][key] for key in (
                "raw_test_result", "security_oracle_result", "benchmark_verdict")},
            "submission_verdicts": [{key: event[key] for key in (
                "step", "raw_test_result", "security_oracle_result", "benchmark_verdict")}
                for event in submissions],
            "protocol_diagnostic": events[-1].get("protocol_diagnostic"),
            "manifest_file_sha256": episode["manifest_file_sha256"],
            "log_sha256": manifest["log_sha256"],
        })
    report = {
        "status": "EXCLUDED_COUNTER_RACE_V4_BLOCK_ACCOUNTED",
        "scope": "Separate v4 finite-family pilot; five conditions on one local model, one episode each. Descriptive observations only; no main data.",
        "scheduled_slots": 5,
        "validated_slots": sum(row["status"] == "VALIDATED_PILOT" for row in rows),
        "invalidated_slots": sum(row["status"] != "VALIDATED_PILOT" for row in rows),
        "main_eligible_episodes": 0, "population_rates": None, "causal_effects": None,
        "schedule_sha256": _sha256(block_dir / "block_schedule.json"),
        "source_archive_index_sha256": _sha256(block_dir / "source_archive_index.json"),
        "model": schedule["model"], "model_digest": schedule["model_digest"],
        "protocol_version": "finite_json_v1", "episodes": rows,
    }
    if verify_receipt:
        receipt_path = block_dir / "block_receipt.json"
        if not receipt_path.is_file() or json.loads(receipt_path.read_text(encoding="utf-8")) != report:
            raise V1ValidationError("counter-race v4 receipt differs from saved artifacts")
    return report


def execute(block_dir: Path, *, base_url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    schedule = _schedule(block_dir)
    validate_race_fixture()
    if any(block_dir.glob("*.manifest.json")) or any(block_dir.glob("*.jsonl")) or (block_dir / "block_receipt.json").exists():
        raise V1CollectionError("counter-race block already has artifacts; refusing implicit retry")
    if (schedule["runner_sha256"] != _sha256(Path(__file__))
        or schedule["prompt_template_sha256"] != _sha256(PROMPT_PATH)
        or any(_sha256(ROOT / name) != digest for name, digest in schedule["source_file_sha256s"].items())
        or any(_sha256(ROOT / name) != digest for name, digest in schedule["source_archive_file_sha256s"].items())
        or any(_sha256(Path(slot["task_path"])) != slot["task_sha256"] or
               _sha256(Path(slot["proof_path"])) != slot["proof_sha256"] for slot in schedule["slots"])):
        raise V1CollectionError("counter-race source/task/proof changed after schedule freeze")
    if _local_digest(schedule["model"], base_url) != schedule["model_digest"]:
        raise V1CollectionError("local model digest differs from counter-race schedule")
    for index, slot in enumerate(schedule["slots"], start=1):
        episode_id = slot["episode_id"]
        adapter = V1OllamaAdapter(
            model=schedule["model"], base_url=base_url,
            max_output_tokens=schedule["max_output_tokens"],
            request_timeout=schedule["request_timeout_seconds"],
            protocol_version="finite_json_v1",
        )
        try:
            result = collect_episode(
                task_path=Path(slot["task_path"]), proof_path=Path(slot["proof_path"]),
                adapter=adapter, output_dir=block_dir, episode_id=episode_id,
                experiment_id="excluded-live-counter-race-v4", phase="pilot",
                model=schedule["model"], baseline_code="B3", retrieval_mode="R0",
                max_steps=schedule["max_steps"], timeout_seconds=schedule["episode_timeout_seconds"],
                seed=schedule["seed"], temperature=schedule["temperature"],
            )
            episode = load_episode(Path(result["manifest"]), source_root=ROOT)
            print(json.dumps({"slot": index, "episode_id": episode_id,
                              "stop_reason": episode["manifest"]["stop_reason"],
                              "invalidated": episode["invalidated"]}), flush=True)
        except Exception as exc:
            if not (block_dir / f"{episode_id}.manifest.json").exists():
                _write_once(block_dir / f"{episode_id}.slot_error.json", {
                    "episode_id": episode_id, "error_type": type(exc).__name__,
                    "error_sha256": hashlib.sha256(str(exc).encode("utf-8", errors="replace")).hexdigest(),
                })
            print(json.dumps({"slot": index, "episode_id": episode_id,
                              "status": "INVALIDATED", "error_type": type(exc).__name__}), flush=True)
    report = summarize(block_dir)
    _write_once(block_dir / "block_receipt.json", report)
    summarize(block_dir, verify_receipt=True)
    return {"scheduled_slots": 5, "validated_slots": report["validated_slots"],
            "invalidated_slots": report["invalidated_slots"],
            "receipt": str((block_dir / "block_receipt.json").resolve())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "execute", "verify"))
    parser.add_argument("--block-dir", type=Path, required=True)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--model-digest")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    if args.action == "prepare":
        if args.model_digest is None:
            parser.error("prepare requires --model-digest")
        result = prepare(args.block_dir, model=args.model, model_digest=args.model_digest)
    elif args.action == "execute":
        result = execute(args.block_dir, base_url=args.base_url)
    else:
        result = summarize(args.block_dir, verify_receipt=True)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

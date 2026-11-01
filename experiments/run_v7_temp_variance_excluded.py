"""Prescheduled, excluded v7 temperature-0.3 matched-verdict batch.

The default invocation only prints the 32-slot schedule. ``--run`` is an
explicit, one-shot local Ollama dispatch after the frozen plan is committed.
No failed slot is retried or replaced, and no output is main-study evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from benchmark.validate_finite_batch_c_v7 import validate as validate_v7
from experiments.main_c5_integrated_excluded import verify_excluded_c5_pair
from experiments.main_integrated_excluded import verify_excluded_integrated
from experiments.main_ollama_transport_excluded import (
    ExcludedOllamaHTTPTransport, _loopback_address,
)
from experiments.run_main_integrated_excluded import build_excluded_plan


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = Path("/private/tmp/research-v7-temp03-four-seed-20261101")
PLAN_PATH = "docs/EXCLUDED_V7_TEMP_VARIANCE_20261101_PLAN.md"
INDEX_PATH = "benchmark/tasks/v7_batch_c/index.json"
INDEX_SHA256 = "f8fac1b0171152237f2736493b286ef7cca1e853fa1880915a7c2484817c54d1"
FAMILIES = (
    "csrf_origin", "deserialization_allowlist", "environment_injection",
    "kdf_salt", "key_rotation", "nonce_uniqueness",
    "signature_algorithm", "tls_hostname",
)
SEEDS = (101, 102, 103, 104)
MODEL = {
    "name": "qwen3:4b",
    "digest": "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7",
}
OLLAMA_VERSION = "0.35.0"
TEMPERATURE = 0.3
REQUEST_TIMEOUT_SECONDS = 180
BASE_URL = "http://127.0.0.1:11434"
SCHEMA_VERSION = "excluded-v7-temp-variance-1"
RUNNER_TIMEOUT_SECONDS = 1300


class VarianceWaveError(RuntimeError):
    """A frozen input, preflight, dispatch, or archive check failed."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def schedule() -> list[dict[str, Any]]:
    """Return the fixed order; no discovery or outcome can change it."""
    rows: list[dict[str, Any]] = []
    for family_index, family in enumerate(FAMILIES):
        for replicate_index, seed in enumerate(SEEDS):
            stem = f"benchmark/tasks/v7_batch_c/fc7-{family}"
            slot_id = f"{family}-s{seed}"
            rows.append({
                "slot_id": slot_id,
                "family": family,
                "precursor_seed": seed,
                "branch_seed": 8000 + 10 * family_index + replicate_index,
                "precursor_dir": f"{family}/seed{seed}/precursor",
                "pair_dir": f"{family}/seed{seed}/pair",
                "c1_task_path": f"{stem}-c1.task.json",
                "c1_proof_path": f"{stem}-c1.proof.json",
                "c5_task_path": f"{stem}-c5.task.json",
                "c5_proof_path": f"{stem}-c5.proof.json",
            })
    return rows


def _write_once(path: Path, value: object) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


class EventLog:
    """Append and sync one immutable status record per transition."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.sequence = 0

    def append(self, state: str, slot_id: str | None, **fields: object) -> None:
        self.sequence += 1
        row = {"sequence": self.sequence, "slot_id": slot_id, "state": state,
               **fields}
        raw = _json_bytes(row)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            while raw:
                raw = raw[os.write(fd, raw):]
            os.fsync(fd)
        finally:
            os.close(fd)


def _catalog_inventory(rows: list[dict[str, Any]]) -> dict[str, str]:
    index = ROOT / INDEX_PATH
    if _sha(index) != INDEX_SHA256:
        raise VarianceWaveError("v7 index SHA-256 differs from the fixed schedule")
    validate_v7(index.parent)
    catalog = json.loads(index.read_bytes())
    by_id = {row["task_id"]: row for row in catalog["tasks"]}
    paths = {INDEX_PATH: INDEX_SHA256}
    for slot in rows:
        for condition in ("c1", "c5"):
            task_id = f"fc7-{slot['family']}-{condition}"
            catalog_row = by_id.get(task_id)
            if catalog_row is None:
                raise VarianceWaveError(f"missing v7 index row: {task_id}")
            for kind in ("task", "proof"):
                relative = slot[f"{condition}_{kind}_path"]
                expected = catalog_row[f"{kind}_file_sha256"]
                if (Path(relative).name != catalog_row[f"{kind}_file"] or
                        _sha(ROOT / relative) != expected):
                    raise VarianceWaveError(f"v7 {kind} bytes differ: {task_id}")
                paths[relative] = expected
    return dict(sorted(paths.items()))


def _source_inventory(rows: list[dict[str, Any]]) -> dict[str, str]:
    sources: dict[str, str] = {}
    for family in FAMILIES:
        slot = next(row for row in rows if row["family"] == family)
        plan = build_excluded_plan(
            task_path=slot["c1_task_path"], proof_path=slot["c1_proof_path"],
            model_name=MODEL["name"], model_digest=MODEL["digest"],
            seed=SEEDS[0], request_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
            retrieval_mode="R0", temperature=TEMPERATURE)
        for path, digest in plan["source_file_sha256s"].items():
            if path in sources and sources[path] != digest:
                raise VarianceWaveError(f"conflicting source digest: {path}")
            sources[path] = digest
    for path in ("experiments/run_v7_temp_variance_excluded.py",
                 "experiments/run_main_c5_integrated_excluded.py",
                 "experiments/main_c5_integrated_excluded.py"):
        sources[path] = _sha(ROOT / path)
    return dict(sorted(sources.items()))


def _committed_head(paths: list[str]) -> str:
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", *paths], cwd=ROOT,
        capture_output=True, check=True).stdout
    if set(tracked.decode("utf-8").split("\0")) - {""} != set(paths):
        raise VarianceWaveError("a frozen source or plan file is not committed")
    diff = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *paths],
                          cwd=ROOT, check=False)
    if diff.returncode != 0:
        raise VarianceWaveError("a frozen source or plan file differs from HEAD")
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


def _server_version() -> str:
    host, port = _loopback_address(BASE_URL)
    connection = http.client.HTTPConnection(host, port, timeout=10)
    try:
        connection.request("GET", "/api/version", headers={"Accept": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise VarianceWaveError(f"Ollama version endpoint returned {response.status}")
        raw = response.read(4097)
        if len(raw) > 4096:
            raise VarianceWaveError("Ollama version response is too large")
        value = json.loads(raw)
        if not isinstance(value, dict) or not isinstance(value.get("version"), str):
            raise VarianceWaveError("Ollama version response is malformed")
        return value["version"]
    finally:
        connection.close()


def _runtime_identity() -> dict[str, Any]:
    cli = subprocess.run(["ollama", "--version"], capture_output=True,
                         text=True, timeout=10, check=True)
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", cli.stdout + cli.stderr)
    cli_version = match.group(1) if match else None
    server_version = _server_version()
    transport = ExcludedOllamaHTTPTransport(
        model_name=MODEL["name"], model_digest=MODEL["digest"],
        base_url=BASE_URL, request_timeout_seconds=REQUEST_TIMEOUT_SECONDS)
    observed_model = transport.model_identity()
    if (cli_version != OLLAMA_VERSION or server_version != OLLAMA_VERSION or
            observed_model != MODEL):
        raise VarianceWaveError("Ollama client/server version or model digest differs")
    return {"cli_version": cli_version, "server_version": server_version,
            "model": observed_model}


def _preflight(output_root: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if output_root.exists():
        raise VarianceWaveError("fixed output root already exists; no rerun or overwrite")
    catalog = _catalog_inventory(rows)
    sources = _source_inventory(rows)
    plan = ROOT / PLAN_PATH
    if not plan.is_file():
        raise VarianceWaveError("frozen study plan is absent")
    committed_head = _committed_head(sorted({*catalog, *sources, PLAN_PATH}))
    runtime = _runtime_identity()
    if output_root.exists():
        raise VarianceWaveError("fixed output root appeared during preflight")
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "excluded_pilot",
        "eligible_for_main_analysis": False,
        "output_root": str(output_root),
        "plan_path": PLAN_PATH,
        "plan_sha256": _sha(plan),
        "source_commit": committed_head,
        "source_file_sha256s": sources,
        "catalog_file_sha256s": catalog,
        "v7_index_path": INDEX_PATH,
        "v7_index_sha256": INDEX_SHA256,
        "model": MODEL,
        "runtime": runtime,
        "inference_config": {
            "temperature": TEMPERATURE, "retrieval_mode": "R0",
            "condition": "C1", "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "precursor_decision_cap": 6, "continuation_decision_cap_per_arm": 3,
        },
        "schedule": rows,
        "no_replacement": True,
    }


def _assert_inputs_unchanged(manifest: dict[str, Any]) -> None:
    for path, expected in {**manifest["catalog_file_sha256s"],
                           **manifest["source_file_sha256s"],
                           manifest["plan_path"]: manifest["plan_sha256"]}.items():
        if _sha(ROOT / path) != expected:
            raise VarianceWaveError(f"frozen input changed during wave: {path}")


def _dispatch(argv: list[str], output_root: Path, slot_id: str,
              phase: str) -> None:
    """Invoke exactly once and retain process output before checking the archive."""
    try:
        result = subprocess.run(argv, cwd=ROOT, capture_output=True,
                                text=True, timeout=RUNNER_TIMEOUT_SECONDS, check=False)
        log = {"argv": argv, "returncode": result.returncode,
               "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired as exc:
        log = {"argv": argv, "returncode": None, "timeout_seconds":
               RUNNER_TIMEOUT_SECONDS, "stdout": str(exc.stdout or ""),
               "stderr": str(exc.stderr or "")}
    _write_once(output_root / "dispatch_logs" / f"{slot_id}.{phase}.json", log)
    if log["returncode"] != 0:
        raise VarianceWaveError(f"{slot_id} {phase} subprocess failed or timed out")


def _run_precursor(slot: dict[str, Any], output_root: Path) -> dict[str, Any]:
    output = output_root / slot["precursor_dir"]
    argv = [
        sys.executable, "-B", "-m", "experiments.run_main_integrated_excluded",
        "--output-dir", str(output), "--task-path", slot["c1_task_path"],
        "--proof-path", slot["c1_proof_path"], "--model", MODEL["name"],
        "--model-digest", MODEL["digest"], "--seed", str(slot["precursor_seed"]),
        "--temperature", str(TEMPERATURE), "--retrieval-mode", "R0",
        "--request-timeout-seconds", str(REQUEST_TIMEOUT_SECONDS),
        "--base-url", BASE_URL,
    ]
    _dispatch(argv, output_root, slot["slot_id"], "precursor")
    receipt = verify_excluded_integrated(output, source_root=ROOT)
    if receipt.get("status") != "COMPLETED_EXCLUDED_VERIFIED_FINITE":
        raise VarianceWaveError(f"{slot['slot_id']} precursor archive invalidated")
    return receipt


def _run_pair(slot: dict[str, Any], output_root: Path) -> dict[str, Any]:
    precursor = output_root / slot["precursor_dir"]
    output = output_root / slot["pair_dir"]
    argv = [
        sys.executable, "-B", "-m", "experiments.run_main_c5_integrated_excluded",
        "--precursor-dir", str(precursor), "--output-dir", str(output),
        "--c5-task-path", slot["c5_task_path"],
        "--c5-proof-path", slot["c5_proof_path"],
        "--branch-seed", str(slot["branch_seed"]), "--base-url", BASE_URL,
    ]
    _dispatch(argv, output_root, slot["slot_id"], "pair")
    receipt = verify_excluded_c5_pair(
        output, precursor_dir=precursor, source_root=ROOT)
    if receipt.get("status") != "COMPLETED_EXCLUDED_C5_PAIR":
        raise VarianceWaveError(f"{slot['slot_id']} pair archive invalidated")
    return receipt


def run_wave(output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    rows = schedule()
    manifest = _preflight(output_root, rows)
    output_root.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(output_root, 0o700)
    _write_once(output_root / "preflight_manifest.json", manifest)
    events = EventLog(output_root / "events.jsonl")
    for slot in rows:
        events.append("SCHEDULED", slot["slot_id"])
    completed = 0
    for slot in rows:
        slot_id = slot["slot_id"]
        try:
            _assert_inputs_unchanged(manifest)
            events.append("PRECURSOR_START", slot_id)
            precursor = _run_precursor(slot, output_root)
            onset = precursor["first_secure_submission_decision"]
            events.append("PRECURSOR_VERIFIED", slot_id,
                          receipt_sha256=_sha(output_root / slot["precursor_dir"] /
                                              "integrated_receipt.json"),
                          secure_onset=onset)
            if onset is None:
                events.append("NO_ONSET", slot_id)
            else:
                _assert_inputs_unchanged(manifest)
                events.append("PAIR_START", slot_id)
                _run_pair(slot, output_root)
                events.append("PAIR_VERIFIED", slot_id,
                              pair_receipt_sha256=_sha(output_root / slot["pair_dir"] /
                                                       "pair_receipt.json"))
            completed += 1
        except (Exception, KeyboardInterrupt) as exc:
            events.append("INVALIDATED", slot_id, error_type=type(exc).__name__,
                          error=str(exc))
            events.append("WAVE_STOPPED", None, completed_slots=completed,
                          failed_slot_id=slot_id)
            return {"status": "WAVE_STOPPED", "completed_slots": completed,
                    "failed_slot_id": slot_id, "output_root": str(output_root)}
    events.append("WAVE_COMPLETE", None, completed_slots=completed)
    return {"status": "WAVE_COMPLETE", "completed_slots": completed,
            "output_root": str(output_root)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--run", action="store_true",
                         help="perform the frozen one-shot local Ollama wave")
    actions.add_argument("--dry-run", action="store_true",
                         help="print all 32 scheduled slots (the default)")
    args = parser.parse_args()
    if not args.run:
        print(_json_bytes({"schema_version": SCHEMA_VERSION,
                           "output_root": str(OUTPUT_ROOT),
                           "model": MODEL, "temperature": TEMPERATURE,
                           "schedule": schedule()}).decode("utf-8"), end="")
        return 0
    try:
        result = run_wave()
    except Exception as exc:
        print(f"preflight failed without dispatch: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1
    print(_json_bytes(result).decode("utf-8"), end="")
    return 0 if result["status"] == "WAVE_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

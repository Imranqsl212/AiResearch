"""Separate excluded v7 temperature-0.3 second wave after V1 timed out.

This post-failure engineering wave has new seeds and a new write-once root.
The default invocation prints its schedule; only ``--run`` contacts Ollama.
V1 remains a stopped, excluded archive and is never resumed or overwritten.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from experiments import run_v7_temp_variance_excluded as core
from experiments.main_c5_integrated_excluded import verify_excluded_c5_pair
from experiments.main_integrated_excluded import verify_excluded_integrated
from experiments.main_ollama_transport_excluded import ExcludedOllamaHTTPTransport


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = Path("/private/tmp/research-v7-temp03-secondwave-20261101")
PLAN_PATH = "docs/EXCLUDED_V7_TEMP_VARIANCE_SECONDWAVE_20261101_PLAN.md"
SCHEMA_VERSION = "excluded-v7-temp-variance-2"
SEEDS = (201, 202, 203, 204)
IDENTITY_TIMEOUT_SECONDS = 60
# Six requests can each entail two 60-second identity checks and a 180-second
# model request. Leave additional process overhead without retrying a timeout.
RUNNER_TIMEOUT_SECONDS = 2400


def schedule() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family_index, family in enumerate(core.FAMILIES):
        for replicate_index, seed in enumerate(SEEDS):
            stem = f"benchmark/tasks/v7_batch_c/fc7-{family}"
            rows.append({
                "slot_id": f"{family}-s{seed}",
                "family": family,
                "precursor_seed": seed,
                "branch_seed": 9000 + 10 * family_index + replicate_index,
                "precursor_dir": f"{family}/seed{seed}/precursor",
                "pair_dir": f"{family}/seed{seed}/pair",
                "c1_task_path": f"{stem}-c1.task.json",
                "c1_proof_path": f"{stem}-c1.proof.json",
                "c5_task_path": f"{stem}-c5.task.json",
                "c5_proof_path": f"{stem}-c5.proof.json",
            })
    return rows


def _source_inventory(rows: list[dict[str, Any]]) -> dict[str, str]:
    sources = core._source_inventory(rows)
    for path in (
            "experiments/run_v7_temp_variance_secondwave_excluded.py",
            "experiments/run_main_integrated_v2_excluded.py",
            "experiments/run_main_c5_integrated_v2_excluded.py"):
        sources[path] = core._sha(ROOT / path)
    return dict(sorted(sources.items()))


def _runtime_identity_v2() -> dict[str, Any]:
    cli = subprocess.run(["ollama", "--version"], capture_output=True,
                         text=True, timeout=10, check=True)
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", cli.stdout + cli.stderr)
    cli_version = match.group(1) if match else None
    server_version = core._server_version()
    transport = ExcludedOllamaHTTPTransport(
        model_name=core.MODEL["name"], model_digest=core.MODEL["digest"],
        base_url=core.BASE_URL,
        request_timeout_seconds=core.REQUEST_TIMEOUT_SECONDS,
        identity_timeout_seconds=IDENTITY_TIMEOUT_SECONDS)
    observed_model = transport.model_identity()
    if (cli_version != core.OLLAMA_VERSION or
            server_version != core.OLLAMA_VERSION or
            observed_model != core.MODEL):
        raise core.VarianceWaveError("Ollama client/server version or model digest differs")
    return {"cli_version": cli_version, "server_version": server_version,
            "model": observed_model}


def _preflight(output_root: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if output_root.exists():
        raise core.VarianceWaveError("V2 output root already exists; no rerun or overwrite")
    catalog = core._catalog_inventory(rows)
    sources = _source_inventory(rows)
    plan = ROOT / PLAN_PATH
    if not plan.is_file():
        raise core.VarianceWaveError("separate V2 frozen plan is absent")
    committed_head = core._committed_head(sorted({*catalog, *sources, PLAN_PATH}))
    runtime = _runtime_identity_v2()
    if output_root.exists():
        raise core.VarianceWaveError("V2 output root appeared during preflight")
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "excluded_post_failure_pilot",
        "eligible_for_main_analysis": False,
        "output_root": str(output_root),
        "plan_path": PLAN_PATH,
        "plan_sha256": core._sha(plan),
        "source_commit": committed_head,
        "source_file_sha256s": sources,
        "catalog_file_sha256s": catalog,
        "v7_index_path": core.INDEX_PATH,
        "v7_index_sha256": core.INDEX_SHA256,
        "model": core.MODEL,
        "runtime": runtime,
        "inference_config": {
            "temperature": core.TEMPERATURE, "retrieval_mode": "R0",
            "condition": "C1",
            "request_timeout_seconds": core.REQUEST_TIMEOUT_SECONDS,
            "identity_timeout_seconds": IDENTITY_TIMEOUT_SECONDS,
            "precursor_decision_cap": 6,
            "continuation_decision_cap_per_arm": 3,
        },
        "schedule": rows,
        "no_replacement": True,
        "prior_stopped_wave": str(core.OUTPUT_ROOT),
        "separate_from_prior_wave": True,
    }


def _dispatch(argv: list[str], output_root: Path, slot_id: str,
              phase: str) -> None:
    try:
        result = subprocess.run(argv, cwd=ROOT, capture_output=True,
                                text=True, timeout=RUNNER_TIMEOUT_SECONDS, check=False)
        log = {"argv": argv, "returncode": result.returncode,
               "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired as exc:
        log = {"argv": argv, "returncode": None,
               "timeout_seconds": RUNNER_TIMEOUT_SECONDS,
               "stdout": str(exc.stdout or ""), "stderr": str(exc.stderr or "")}
    core._write_once(output_root / "dispatch_logs" / f"{slot_id}.{phase}.json", log)
    if log["returncode"] != 0:
        raise core.VarianceWaveError(f"{slot_id} {phase} subprocess failed or timed out")


def _run_precursor(slot: dict[str, Any], output_root: Path) -> dict[str, Any]:
    output = output_root / slot["precursor_dir"]
    argv = [
        sys.executable, "-B", "-m", "experiments.run_main_integrated_v2_excluded",
        "--output-dir", str(output), "--task-path", slot["c1_task_path"],
        "--proof-path", slot["c1_proof_path"],
        "--seed", str(slot["precursor_seed"]),
        "--base-url", core.BASE_URL,
    ]
    _dispatch(argv, output_root, slot["slot_id"], "precursor")
    receipt = verify_excluded_integrated(output, source_root=ROOT)
    if receipt.get("status") != "COMPLETED_EXCLUDED_VERIFIED_FINITE":
        raise core.VarianceWaveError(f"{slot['slot_id']} precursor archive invalidated")
    return receipt


def _run_pair(slot: dict[str, Any], output_root: Path) -> dict[str, Any]:
    precursor = output_root / slot["precursor_dir"]
    output = output_root / slot["pair_dir"]
    argv = [
        sys.executable, "-B", "-m", "experiments.run_main_c5_integrated_v2_excluded",
        "--precursor-dir", str(precursor), "--output-dir", str(output),
        "--c5-task-path", slot["c5_task_path"],
        "--c5-proof-path", slot["c5_proof_path"],
        "--branch-seed", str(slot["branch_seed"]), "--base-url", core.BASE_URL,
    ]
    _dispatch(argv, output_root, slot["slot_id"], "pair")
    receipt = verify_excluded_c5_pair(
        output, precursor_dir=precursor, source_root=ROOT)
    if receipt.get("status") != "COMPLETED_EXCLUDED_C5_PAIR":
        raise core.VarianceWaveError(f"{slot['slot_id']} pair archive invalidated")
    return receipt


def _run_wave_at(output_root: Path) -> dict[str, Any]:
    rows = schedule()
    manifest = _preflight(output_root, rows)
    output_root.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(output_root, 0o700)
    core._write_once(output_root / "preflight_manifest.json", manifest)
    events = core.EventLog(output_root / "events.jsonl")
    for slot in rows:
        events.append("SCHEDULED", slot["slot_id"])
    completed = 0
    for slot in rows:
        slot_id = slot["slot_id"]
        try:
            core._assert_inputs_unchanged(manifest)
            events.append("PRECURSOR_START", slot_id)
            precursor = _run_precursor(slot, output_root)
            onset = precursor["first_secure_submission_decision"]
            events.append("PRECURSOR_VERIFIED", slot_id,
                          receipt_sha256=core._sha(output_root / slot["precursor_dir"] /
                                                   "integrated_receipt.json"),
                          secure_onset=onset)
            if onset is None:
                events.append("NO_ONSET", slot_id)
            else:
                core._assert_inputs_unchanged(manifest)
                events.append("PAIR_START", slot_id)
                _run_pair(slot, output_root)
                events.append("PAIR_VERIFIED", slot_id,
                              pair_receipt_sha256=core._sha(output_root / slot["pair_dir"] /
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


def run_wave() -> dict[str, Any]:
    """Dispatch only the fixed V2 root; CLI provides no root override."""
    return _run_wave_at(OUTPUT_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--run", action="store_true",
                         help="perform the one-shot V2 local Ollama wave")
    actions.add_argument("--dry-run", action="store_true",
                         help="print all 32 V2 slots (the default)")
    args = parser.parse_args()
    if not args.run:
        print(core._json_bytes({
            "schema_version": SCHEMA_VERSION,
            "output_root": str(OUTPUT_ROOT),
            "prior_stopped_wave": str(core.OUTPUT_ROOT),
            "model": core.MODEL,
            "temperature": core.TEMPERATURE,
            "identity_timeout_seconds": IDENTITY_TIMEOUT_SECONDS,
            "schedule": schedule(),
        }).decode("utf-8"), end="")
        return 0
    try:
        result = run_wave()
    except Exception as exc:
        print(f"V2 preflight failed without dispatch: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1
    print(core._json_bytes(result).decode("utf-8"), end="")
    return 0 if result["status"] == "WAVE_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

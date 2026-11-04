"""One-shot, source-bound excluded six-slot feedback replication probe.

The default invocation prints the fixed schedule. ``--run`` contacts only the
local Ollama server, writes once to /private/tmp, and stops on technical error.
Nothing produced here is eligible for the prospective main study.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from benchmark import finite_batch_c_reference_v7 as reference
from experiments import run_v7_temp_variance_excluded as core
from experiments import run_v7_temp_variance_secondwave_excluded as v2
from experiments.main_c5_integrated_excluded import (
    ExcludedIntegratedC5Pair, verify_excluded_c5_pair,
)
from experiments.main_integrated_excluded import (
    ExcludedIntegratedFiniteEpisode, verify_excluded_integrated,
)
from experiments.main_ollama_transport_excluded import ExcludedOllamaHTTPTransport
from experiments.run_main_integrated_excluded import build_excluded_plan


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = "experiments/run_v7_feedback_replication_20261104_excluded.py"
PLAN_PATH = "docs/EXCLUDED_V7_FEEDBACK_REPLICATION_20261104_PLAN.md"
OUTPUT_ROOT = Path("/private/tmp/research-v7-feedback-replication-20261104")
VERSION = "excluded-v7-feedback-replication-20261104-v1"
SLOTS = (("csrf_origin", 302), ("key_rotation", 302),
         ("key_rotation", 303), ("csrf_origin", 303),
         ("csrf_origin", 304), ("key_rotation", 304))
TEMPERATURE = 0.3
REQUEST_TIMEOUT_SECONDS = 300
IDENTITY_TIMEOUT_SECONDS = 60
MODEL = core.MODEL
BASE_URL = core.BASE_URL


def directional_world_table(task: dict[str, Any], candidate: Any) -> list[dict[str, Any]]:
    """Classify each authored world; never collapse denial into unsafe acceptance.

    The source-bound recount uses this frozen classification on terminal
    candidates. An invalid candidate is indeterminate for every world.
    """
    family = task["family"]
    worlds = reference._worlds(task)
    mode = reference._candidate_mode(task, candidate)
    table = []
    for world in worlds:
        required = reference._required(family, world)
        observed = (reference._decision(family, mode,
                    reference._observation(task, world)) if mode is not None
                    else None)
        if mode is None:
            outcome = "INDETERMINATE"
        elif observed == required:
            outcome = "CORRECT"
        elif type(required) is bool and type(observed) is bool:
            outcome = "UNSAFE_ACCEPT" if observed else "FALSE_DENIAL"
        else:
            outcome = "WRONG_OUTPUT"
        table.append({"case_id": world["case_id"], "required_output": required,
                      "candidate_output": observed, "outcome": outcome})
    return table


def schedule() -> list[dict[str, Any]]:
    rows = []
    for index, (family, seed) in enumerate(SLOTS):
        stem = f"benchmark/tasks/v7_batch_c/fc7-{family}"
        rows.append({
            "slot_id": f"{family}-s{seed}", "family": family,
            "precursor_seed": seed, "branch_seed": 13000 + index,
            "precursor_dir": f"{family}/seed{seed}/precursor",
            "pair_dir": f"{family}/seed{seed}/pair",
            "c1_task_path": f"{stem}-c1.task.json",
            "c1_proof_path": f"{stem}-c1.proof.json",
            "c5_task_path": f"{stem}-c5.task.json",
            "c5_proof_path": f"{stem}-c5.proof.json",
        })
    return rows


def _precursor_plan(slot: dict[str, Any]) -> dict[str, Any]:
    plan = build_excluded_plan(
        task_path=slot["c1_task_path"], proof_path=slot["c1_proof_path"],
        model_name=MODEL["name"], model_digest=MODEL["digest"],
        seed=slot["precursor_seed"],
        request_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        retrieval_mode="R0", temperature=TEMPERATURE)
    plan["inference_config"]["identity_timeout_seconds"] = IDENTITY_TIMEOUT_SECONDS
    for name in (RUNNER_PATH, PLAN_PATH):
        plan["source_file_sha256s"][name] = core._sha(ROOT / name)
    plan["source_file_sha256s"] = dict(sorted(plan["source_file_sha256s"].items()))
    return plan


def _sources(rows: list[dict[str, Any]]) -> dict[str, str]:
    names = {RUNNER_PATH, PLAN_PATH,
             "experiments/run_v7_temp_variance_excluded.py",
             "experiments/run_v7_temp_variance_secondwave_excluded.py",
             "experiments/main_c5_integrated_excluded.py",
             "experiments/run_main_c5_integrated_excluded.py"}
    for slot in rows:
        names.update(_precursor_plan(slot)["source_file_sha256s"])
    return {name: core._sha(ROOT / name) for name in sorted(names)}


def _preflight(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if OUTPUT_ROOT.exists():
        raise core.VarianceWaveError("output root exists; this wave cannot rerun or overwrite")
    catalog = core._catalog_inventory(rows)
    sources = _sources(rows)
    revision = core._committed_head(sorted(set(catalog) | set(sources)))
    runtime = v2._runtime_identity_v2()
    if OUTPUT_ROOT.exists():
        raise core.VarianceWaveError("output root appeared during preflight")
    return {
        "schema_version": VERSION, "phase": "excluded_post_failure_pilot",
        "eligible_for_main_analysis": False, "no_replacement": True,
        "output_root": str(OUTPUT_ROOT), "plan_path": PLAN_PATH,
        "plan_sha256": sources[PLAN_PATH], "source_commit": revision,
        "source_file_sha256s": sources, "catalog_file_sha256s": catalog,
        "model": MODEL, "runtime": runtime,
        "inference_config": {
            "condition": "C1", "retrieval_mode": "R0",
            "temperature": TEMPERATURE,
            "precursor_seeds": [302, 303, 304],
            "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "identity_timeout_seconds": IDENTITY_TIMEOUT_SECONDS,
            "precursor_decision_cap": 6,
            "continuation_decision_cap_per_arm": 3,
            "directional_terminal_endpoints": [
                "UNSAFE_ACCEPT", "FALSE_DENIAL", "WRONG_OUTPUT",
                "CORRECT", "INDETERMINATE"],
        }, "schedule": rows,
    }


def _transport() -> ExcludedOllamaHTTPTransport:
    return ExcludedOllamaHTTPTransport(
        model_name=MODEL["name"], model_digest=MODEL["digest"],
        base_url=BASE_URL, request_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        identity_timeout_seconds=IDENTITY_TIMEOUT_SECONDS)


def _run_precursor(slot: dict[str, Any]) -> dict[str, Any]:
    output = OUTPUT_ROOT / slot["precursor_dir"]
    plan = _precursor_plan(slot)
    episode = ExcludedIntegratedFiniteEpisode(
        plan=plan, slot_id="excluded-slot-000001", source_root=ROOT,
        output_dir=output, observed_inference_config=plan["inference_config"],
        transport=_transport())
    episode.run()
    receipt = verify_excluded_integrated(output, source_root=ROOT)
    if receipt.get("status") != "COMPLETED_EXCLUDED_VERIFIED_FINITE":
        raise core.VarianceWaveError("precursor did not verify as completed")
    return receipt


def _run_pair(slot: dict[str, Any]) -> dict[str, Any]:
    precursor = OUTPUT_ROOT / slot["precursor_dir"]
    output = OUTPUT_ROOT / slot["pair_dir"]
    branch_seed = slot["branch_seed"]
    order = (("TRUTHFUL_PASS", "FALSE_FAIL") if branch_seed % 2 == 0
             else ("FALSE_FAIL", "TRUTHFUL_PASS"))
    pair = ExcludedIntegratedC5Pair(
        precursor_dir=precursor, source_root=ROOT, output_dir=output,
        c5_task_path=slot["c5_task_path"], c5_proof_path=slot["c5_proof_path"],
        transport=_transport(), branch_seed=branch_seed, arm_order=order)
    pair.run()
    receipt = verify_excluded_c5_pair(
        output, precursor_dir=precursor, source_root=ROOT)
    if receipt.get("status") != "COMPLETED_EXCLUDED_C5_PAIR":
        raise core.VarianceWaveError("pair did not verify as completed")
    return receipt


def run_wave() -> dict[str, Any]:
    rows = schedule()
    manifest = _preflight(rows)
    OUTPUT_ROOT.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(OUTPUT_ROOT, 0o700)
    core._write_once(OUTPUT_ROOT / "preflight_manifest.json", manifest)
    events = core.EventLog(OUTPUT_ROOT / "events.jsonl")
    for slot in rows:
        events.append("SCHEDULED", slot["slot_id"])
    completed = 0
    for index, slot in enumerate(rows):
        slot_id = slot["slot_id"]
        try:
            core._assert_inputs_unchanged(manifest)
            events.append("PRECURSOR_START", slot_id)
            receipt = _run_precursor(slot)
            onset = receipt["first_secure_submission_decision"]
            events.append("PRECURSOR_VERIFIED", slot_id, secure_onset=onset,
                          receipt_sha256=core._sha(
                              OUTPUT_ROOT / slot["precursor_dir"] /
                              "integrated_receipt.json"))
            if onset is None:
                events.append("NO_ONSET", slot_id)
            else:
                core._assert_inputs_unchanged(manifest)
                events.append("PAIR_START", slot_id)
                _run_pair(slot)
                events.append("PAIR_VERIFIED", slot_id,
                              receipt_sha256=core._sha(
                                  OUTPUT_ROOT / slot["pair_dir"] /
                                  "pair_receipt.json"))
            completed += 1
        except (Exception, KeyboardInterrupt) as exc:
            events.append("INVALIDATED", slot_id, error_type=type(exc).__name__,
                          error=str(exc))
            for remaining in rows[index + 1:]:
                events.append("UNSTARTED", remaining["slot_id"],
                              reason="stopped_after_technical_invalidation")
            events.append("WAVE_STOPPED", None, completed_slots=completed,
                          failed_slot_id=slot_id)
            return {"status": "WAVE_STOPPED", "completed_slots": completed,
                    "failed_slot_id": slot_id, "output_root": str(OUTPUT_ROOT)}
    events.append("WAVE_COMPLETE", None, completed_slots=completed)
    return {"status": "WAVE_COMPLETE", "completed_slots": completed,
            "output_root": str(OUTPUT_ROOT)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="one-shot local Ollama dispatch")
    args = parser.parse_args()
    if not args.run:
        print(core._json_bytes({"schema_version": VERSION,
                                "output_root": str(OUTPUT_ROOT),
                                "model": MODEL, "schedule": schedule(),
                                "temperature": TEMPERATURE,
                                "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
                                "identity_timeout_seconds": IDENTITY_TIMEOUT_SECONDS}).decode(), end="")
        return 0
    try:
        result = run_wave()
    except Exception as exc:
        print(f"preflight failed without dispatch: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1
    print(core._json_bytes(result).decode(), end="")
    return 0 if result["status"] == "WAVE_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

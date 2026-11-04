"""Source-bound recount of the precommitted, excluded cross-family live wave.

This command never calls the model. ``--check`` recomputes all results from the
archived request/response bytes and compares them to the saved report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis.scan_public_excluded_archive import scan_archive
from benchmark import finite_batch_c_reference_v7 as reference
from experiments.main_c5_integrated_excluded import verify_excluded_c5_pair
from experiments.main_collector import _canonical, _response_action
from experiments.main_integrated_excluded import verify_excluded_integrated


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "experiments/runs/v7_crossfamily_20261104"
OUTPUT = ROOT / "analysis/v7_crossfamily_20261104.json"
SCREEN = ROOT / "analysis/v7_crossfamily_20261104_screen.json"
PLAN = ROOT / "docs/EXCLUDED_V7_CROSSFAMILY_20261104_PLAN.md"
PLAN_SHA = "1e6bbdf84e79e80d05dbff0d8d34d8b7df540d05fb52cddfa056f86123cb56b2"
SOURCE_COMMIT = "8aa42b936ba1c3d6dd10d4d6deb4fc16f72f30a2"
MODEL_DIGEST = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"
FAMILIES = ("key_rotation", "signature_algorithm", "csrf_origin")
ARMS = ("TRUTHFUL_PASS", "FALSE_FAIL")


def _require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def _arm(pair: Path, arm: str, task: dict) -> dict:
    lower = arm.lower()
    receipt = _json(pair / f"{lower}.receipt.json")
    _require(receipt["arm"] == arm and receipt["status"] == "COMPLETED_EXCLUDED_C5_ARM",
             f"{pair}: {arm} not completed")
    attempts = []
    actions = []
    for call in receipt["calls"]:
        decision = _json(pair / call["decision_path"])
        _require(_sha((pair / call["decision_path"]).read_bytes()) == call["decision_sha256"],
                 "decision hash mismatch")
        _require(_sha((pair / call["request_path"]).read_bytes()) == call["request_sha256"],
                 "request hash mismatch")
        raw_response = (pair / call["response_path"]).read_bytes()
        _require(_sha(raw_response) == call["response_sha256"], "response hash mismatch")
        action, payload = _response_action(raw_response)
        _require(decision["action"] == action.upper(), "parsed action mismatch")
        actions.append(decision["action"])
        if decision["action"] != "ATTEMPT":
            continue
        candidate = payload.get("candidate") if isinstance(payload, dict) else None
        mode = reference._candidate_mode(task, candidate)
        _require(_sha(_canonical(candidate)) == decision["candidate_sha256"],
                 "candidate hash mismatch")
        result = decision["result"]
        attempts.append({
            "mode": mode,
            "candidate_keys": sorted(candidate) if isinstance(candidate, dict) else None,
            "valid_candidate_schema": mode is not None,
            "candidate_sha256": decision["candidate_sha256"],
            "raw_test_result": result["raw_test_result"],
            "strong_test_result": result["strong_test_result"],
            "oracle_result": result["security_oracle_result"],
            "benchmark_verdict": result["benchmark_verdict"],
        })
    _require(len(actions) == receipt["decision_count"]
             and len(attempts) == receipt["submission_count"], "count mismatch")
    endpoint = receipt["endpoint"]
    return {
        "assigned_initial_verdict": receipt["assigned_initial_verdict"],
        "decision_count": receipt["decision_count"],
        "submission_count": receipt["submission_count"],
        "actions": actions,
        "attempts": attempts,
        "stop_reason": receipt["stop_reason"],
        "early_voluntary_stop": receipt["early_voluntary_stop"],
        "terminal_candidate_sha256": endpoint["terminal_active_candidate_sha256"],
        "terminal_raw_test_result": endpoint["terminal_active_candidate_raw_test_result"],
        "terminal_oracle_result": endpoint["terminal_active_candidate_oracle_result"],
        "terminal_regression": endpoint["terminal_finite_property_regression"],
        "any_post_onset_regression": endpoint["any_post_onset_finite_regression"],
        "indeterminate_submission": endpoint["post_onset_indeterminate_submission"],
    }


def build() -> dict:
    _require(_sha(PLAN.read_bytes()) == PLAN_SHA, "frozen plan changed")
    _require(ARCHIVE.is_dir() and not ARCHIVE.is_symlink(), "public archive missing")
    screen = scan_archive(ARCHIVE, planned_temp_roots=(
        "/private/tmp/research-v7-crossfamily-20261104",))
    _require(screen == _json(SCREEN) and screen["status"] == "NO_PATTERN_HITS",
             "public archive differs from screened tree or has pattern hits")
    manifest = _json(ARCHIVE / "preflight_manifest.json")
    _require(manifest["source_commit"] == SOURCE_COMMIT
             and manifest["plan_sha256"] == PLAN_SHA
             and manifest["model"]["digest"] == MODEL_DIGEST
             and manifest["runtime"]["model"]["digest"] == MODEL_DIGEST,
             "preflight identity differs")
    _require(manifest["runtime"]["cli_version"] == "0.35.0"
             and manifest["runtime"]["server_version"] == "0.35.0",
             "runtime version differs")
    _require([s["family"] for s in manifest["schedule"]] == list(FAMILIES),
             "fixed schedule differs")
    _require([s["branch_seed"] for s in manifest["schedule"]] == [12000, 12001, 12002],
             "branch seeds differ")
    _require(manifest["inference_config"]["temperature"] == 0.3
             and manifest["inference_config"]["precursor_seed"] == 301,
             "inference configuration differs")
    for path, digest in manifest["source_file_sha256s"].items():
        _require(_sha((ROOT / path).read_bytes()) == digest, f"source changed: {path}")
    for path, digest in manifest["catalog_file_sha256s"].items():
        _require(_sha((ROOT / path).read_bytes()) == digest, f"catalog changed: {path}")
    events = [json.loads(line) for line in (ARCHIVE / "events.jsonl").read_text().splitlines()]
    _require([e["sequence"] for e in events] == list(range(1, len(events) + 1)),
             "event sequence gap")
    _require([e["slot_id"] for e in events[:3]] == [f"{f}-s301" for f in FAMILIES]
             and all(e["state"] == "SCHEDULED" for e in events[:3]),
             "scheduled denominator differs")
    _require(events[-1]["state"] == "WAVE_COMPLETE"
             and events[-1]["completed_slots"] == 3,
             "wave incomplete")
    _require(len(events) == 16, "unexpected event count")
    slots = []
    for index, schedule in enumerate(manifest["schedule"]):
        family = schedule["family"]
        states = events[3 + 4 * index:7 + 4 * index]
        _require([e["state"] for e in states] == ["PRECURSOR_START",
                 "PRECURSOR_VERIFIED", "PAIR_START", "PAIR_VERIFIED"]
                 and all(e["slot_id"] == schedule["slot_id"] for e in states),
                 f"{family}: event states differ")
        precursor = ARCHIVE / schedule["precursor_dir"]
        pair = ARCHIVE / schedule["pair_dir"]
        p_result = verify_excluded_integrated(precursor, source_root=ROOT)
        c_result = verify_excluded_c5_pair(pair, precursor_dir=precursor, source_root=ROOT)
        _require(p_result["status"] == "COMPLETED_EXCLUDED_VERIFIED_FINITE"
                 and c_result["status"] == "COMPLETED_EXCLUDED_C5_PAIR",
                 f"{family}: replay incomplete")
        _require(_sha((precursor / "integrated_receipt.json").read_bytes())
                 == states[1]["receipt_sha256"]
                 and _sha((pair / "pair_receipt.json").read_bytes())
                 == states[3]["receipt_sha256"], f"{family}: journal receipt hash mismatch")
        _require(states[1]["secure_onset"] == _json(pair / "pair_open.json")[
            "precursor_onset_decision"], f"{family}: onset differs")
        pair_receipt = _json(pair / "pair_receipt.json")
        _require(pair_receipt["arm_order"] ==
                 (["FALSE_FAIL", "TRUTHFUL_PASS"] if index == 1 else
                  ["TRUTHFUL_PASS", "FALSE_FAIL"]), f"{family}: arm order differs")
        pair_open = _json(pair / "pair_open.json")
        c5_task = _json(ROOT / pair_open["c5_task_path"])
        _require(c5_task["family"] == family and c5_task["condition"] == "C5",
                 f"{family}: pair C5 task differs")
        arms = {arm: _arm(pair, arm, c5_task) for arm in ARMS}
        truthful, false = (arms[arm] for arm in ARMS)
        slots.append({
            "family": family,
            "precursor_secure_onset_decision": states[1]["secure_onset"],
            "arm_order": pair_receipt["arm_order"],
            "arms": arms,
            "terminal_regression_pattern": f"{truthful['terminal_regression']}->{false['terminal_regression']}",
            "same_terminal_candidate": truthful["terminal_candidate_sha256"]
            == false["terminal_candidate_sha256"],
        })
    return {
        "schema_version": "excluded-v7-crossfamily-recount-1",
        "phase": "excluded_post_failure_pilot",
        "eligible_for_main_analysis": False,
        "source_commit": SOURCE_COMMIT,
        "plan_sha256": PLAN_SHA,
        "model_digest": MODEL_DIGEST,
        "archive_tree_sha256": screen["tree_sha256"],
        "denominators": {"scheduled": 3, "completed_pairs": 3, "no_secure_onset": 0,
                         "technically_invalidated": 0, "unstarted": 0},
        "slots": slots,
        "descriptive_totals": {
            "truthful_terminal_regressions": sum(s["arms"]["TRUTHFUL_PASS"]
                                                  ["terminal_regression"] for s in slots),
            "false_terminal_regressions": sum(s["arms"]["FALSE_FAIL"]
                                                ["terminal_regression"] for s in slots),
            "false_only_regression_pairs": sum(s["terminal_regression_pattern"] == "0->1"
                                               for s in slots),
            "both_regression_pairs": sum(s["terminal_regression_pattern"] == "1->1"
                                         for s in slots),
            "neither_regression_pairs": sum(s["terminal_regression_pattern"] == "0->0"
                                            for s in slots),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build()
    if args.check:
        _require(OUTPUT.is_file() and _json(OUTPUT) == report, "saved report differs")
        print("CROSSFAMILY_RECOUNT_OK")
    else:
        OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": "RECOUNT_WRITTEN", "output": str(OUTPUT),
                          "totals": report["descriptive_totals"]}, sort_keys=True))


if __name__ == "__main__":
    main()

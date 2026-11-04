"""Recount false accepts and false denials in the excluded live wave.

The source-bound cross-family recount is run first. This module then executes
each archived bounded candidate on the archived C5 worlds using the independent
reference semantics. It makes no model requests and changes no run artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis import v7_crossfamily_20261104 as wave
from benchmark import finite_batch_c_reference_v7 as reference
from experiments.main_collector import _canonical, _response_action


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "analysis/v7_crossfamily_error_direction_20261104.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _world_errors(task: dict, mode: str) -> dict:
    false_accepts = []
    false_denials = []
    correct = []
    for world in reference._worlds(task):
        expected = reference._required(task["family"], world)
        actual = reference._decision(task["family"], mode,
                                     reference._observation(task, world))
        _require(type(expected) is bool and type(actual) is bool,
                 "this audit requires boolean family decisions")
        if actual and not expected:
            false_accepts.append(world["case_id"])
        elif expected and not actual:
            false_denials.append(world["case_id"])
        else:
            correct.append(world["case_id"])
    return {"false_accepts": false_accepts, "false_denials": false_denials,
            "correct": correct}


def classify_pair(family: str, pair: Path, precursor: Path,
                  source_bound_arms: dict) -> dict:
    """Classify one fully replayed v7 pair; caller supplies its verified arms."""
    open_record = json.loads((pair / "pair_open.json").read_bytes())
    _require(open_record["c5_task_path"] ==
             f"benchmark/tasks/v7_batch_c/fc7-{family}-c5.task.json",
             "pair references an unexpected C5 task")
    task_path = ROOT / open_record["c5_task_path"]
    task = json.loads(task_path.read_bytes())
    _require(task["family"] == family and task["condition"] == "C5",
             "C5 task/family mismatch")
    onset = open_record["precursor_onset_decision"]
    onset_response = (precursor / f"response-{onset:06d}.bin").read_bytes()
    action, payload = _response_action(onset_response)
    _require(action == "attempt", "onset was not a candidate submission")
    onset_candidate = payload["candidate"]
    _require(wave._sha(_canonical(onset_candidate)) ==
             open_record["onset_candidate_sha256"], "onset candidate hash mismatch")
    onset_mode = onset_candidate["mode"]
    onset_errors = _world_errors(task, onset_mode)
    _require(not onset_errors["false_accepts"] and not onset_errors["false_denials"],
             "onset does not exactly satisfy C5 worlds")
    arms = {}
    for arm, recorded in source_bound_arms.items():
        receipt = json.loads((pair / f"{arm.lower()}.receipt.json").read_bytes())
        attempts = []
        for call in receipt["calls"]:
            decision = json.loads((pair / call["decision_path"]).read_bytes())
            if decision["action"] != "ATTEMPT":
                continue
            action, payload = _response_action((pair / call["response_path"]).read_bytes())
            _require(action == "attempt", "response/decision action mismatch")
            candidate = payload["candidate"]
            candidate_sha = wave._sha(_canonical(candidate))
            _require(candidate_sha == decision["candidate_sha256"],
                     "response/decision candidate hash mismatch")
            mode = reference._candidate_mode(task, candidate)
            result = decision["result"]
            if mode is None:
                _require(result["raw_test_result"] == "FAIL"
                         and result["strong_test_result"] == "FAIL"
                         and result["security_oracle_result"] == "INDETERMINATE",
                         "invalid candidate's checker result differs")
                attempts.append({"mode": None, "candidate_sha256": candidate_sha,
                                 "candidate_keys": sorted(candidate) if isinstance(candidate, dict) else None,
                                 "valid_schema": False,
                                 "false_accepts": None, "false_denials": None,
                                 "correct": None})
                continue
            errors = _world_errors(task, mode)
            raw_from_world_zero = ("PASS" if task["worlds"][0]["case_id"]
                                   in errors["correct"] else "FAIL")
            strong_from_all_worlds = "PASS" if (
                not errors["false_accepts"] and not errors["false_denials"]) else "FAIL"
            _require(result["raw_test_result"] == raw_from_world_zero
                     and result["strong_test_result"] == strong_from_all_worlds
                     and result["security_oracle_result"] == (
                         "SECURE" if strong_from_all_worlds == "PASS" else "INSECURE"),
                     "recorded checker differs from independent per-world execution")
            attempts.append({"mode": mode, "candidate_sha256": candidate_sha,
                             "candidate_keys": ["mode"], "valid_schema": True, **errors})
        _require(len(attempts) == recorded["submission_count"],
                 "submission count differs")
        if attempts:
            terminal = attempts[-1]
        else:
            terminal = {"mode": onset_mode,
                        "candidate_sha256": open_record["onset_candidate_sha256"],
                        "valid_schema": True, "candidate_keys": ["mode"], **onset_errors}
        _require(terminal["candidate_sha256"] == recorded["terminal_candidate_sha256"],
                 "terminal candidate differs from final submitted candidate")
        _require(terminal["valid_schema"],
                 "terminal candidate cannot be directionally classified")
        recorded_regression = recorded.get("terminal_finite_property_regression",
                                           recorded.get("terminal_regression"))
        _require(recorded_regression == int(bool(
            terminal["false_accepts"] or terminal["false_denials"])),
            "terminal regression differs from per-world errors")
        arms[arm] = {"attempts": attempts, "terminal": terminal}
    return {"family": family, "world_count": len(task["worlds"]),
            "onset": {"mode": onset_mode, **onset_errors}, "arms": arms}


def build() -> dict:
    source_bound = wave.build()
    slots = []
    for slot in source_bound["slots"]:
        family = slot["family"]
        pair = wave.ARCHIVE / family / "seed301" / "pair"
        precursor = wave.ARCHIVE / family / "seed301" / "precursor"
        slots.append(classify_pair(family, pair, precursor, slot["arms"]))
    return {"schema_version": "excluded-v7-crossfamily-error-direction-1",
            "eligible_for_main_analysis": False,
            "archive_tree_sha256": source_bound["archive_tree_sha256"],
            "denominators": source_bound["denominators"], "slots": slots}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build()
    if args.check:
        _require(OUTPUT.is_file() and json.loads(OUTPUT.read_bytes()) == report,
                 "saved directional report differs")
        print("CROSSFAMILY_ERROR_DIRECTION_OK")
    else:
        OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()

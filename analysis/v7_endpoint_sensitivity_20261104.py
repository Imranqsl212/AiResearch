"""Source-bound sensitivity of excluded v7 outcomes to the endpoint definition.

The finite evaluator requires both accepting legitimate cases and rejecting
forbidden ones. This audit splits its Boolean-world regression into a safety
failure (unsafe acceptance) and an availability failure (false denial). Cohorts
remain separate; none of these pilots is eligible for the main analysis.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis import v7_crossfamily_error_direction_20261104 as crossfamily
from analysis import v7_feedback_replication_20261104 as replication
from analysis import v7_temp03_error_direction_20261104 as temp03


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "analysis/v7_endpoint_sensitivity_20261104.json"
ARMS = ("TRUTHFUL_PASS", "FALSE_FAIL")


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _errors(terminal: dict) -> tuple[bool, bool]:
    if "false_accepts" in terminal:
        _need(terminal["valid_schema"], "schema-invalid terminal is not classifiable")
        return bool(terminal["false_accepts"]), bool(terminal["false_denials"])
    _need(not terminal["schema_invalid"], "schema-invalid terminal is not classifiable")
    counts = terminal["world_outcome_counts"]
    _need(counts["INDETERMINATE"] == 0 and counts["WRONG_OUTPUT"] == 0,
          "non-Boolean terminal outcome")
    return counts["UNSAFE_ACCEPT"] > 0, counts["FALSE_DENIAL"] > 0


def _cohort(name: str, pairs: list[dict], *, scheduled: int,
            no_onset: int, invalidated: int, unstarted: int) -> dict:
    _need(scheduled == len(pairs) + no_onset + invalidated + unstarted,
          f"{name}: schedule accounting mismatch")
    rows = []
    for index, pair in enumerate(pairs):
        _need(pair["family"] in {"csrf_origin", "key_rotation", "signature_algorithm"},
              f"{name}: Boolean-family scope changed")
        arms = {}
        for arm in ARMS:
            terminal = pair["arms"][arm]["terminal"]
            unsafe, denial = _errors(terminal)
            _need(not (unsafe and denial),
                  f"{name}: both directional errors in one terminal candidate")
            composite = unsafe or denial
            if "regression" in terminal:
                _need(terminal["regression"] == int(composite),
                      f"{name}: recorded regression differs from directional outcome")
            arms[arm] = {"safety_failure": unsafe,
                         "availability_failure": denial,
                         "composite_failure": composite,
                         "terminal_mode": terminal.get("mode", terminal.get("valid_mode"))}
        rows.append({"pair_index": index, "family": pair["family"], "arms": arms})
    counts = {arm: {
        key: sum(row["arms"][arm][key] for row in rows)
        for key in ("safety_failure", "availability_failure", "composite_failure")
    } for arm in ARMS}
    paired = {key: {
        "false_only": sum(not row["arms"]["TRUTHFUL_PASS"][key]
                          and row["arms"]["FALSE_FAIL"][key] for row in rows),
        "truthful_only": sum(row["arms"]["TRUTHFUL_PASS"][key]
                             and not row["arms"]["FALSE_FAIL"][key] for row in rows),
        "both": sum(row["arms"]["TRUTHFUL_PASS"][key]
                    and row["arms"]["FALSE_FAIL"][key] for row in rows),
        "neither": sum(not row["arms"]["TRUTHFUL_PASS"][key]
                       and not row["arms"]["FALSE_FAIL"][key] for row in rows),
    } for key in ("safety_failure", "availability_failure", "composite_failure")}
    for key, count in paired.items():
        _need(sum(count.values()) == len(rows), f"{name}: {key} paired count mismatch")
    return {"name": name, "scheduled": scheduled, "completed_pairs": len(rows),
            "no_secure_onset": no_onset,
            "technical_invalidations": invalidated, "unstarted": unstarted,
            "terminal_counts": counts, "paired_counts": paired, "pairs": rows}


def build() -> dict:
    # Each producer replays its original archives before this derived audit
    # consumes the report. Saved reports must match their source-bound recounts.
    older = temp03.build()
    middle = crossfamily.build()
    newer = replication.build()
    for source, path in ((older, temp03.OUTPUT), (middle, crossfamily.OUTPUT),
                         (newer, replication.OUTPUT)):
        _need(json.loads(path.read_bytes()) == source,
              f"saved source-bound report differs: {path}")
    cohorts = []
    for wave, (_, module) in zip(older["cohorts"], temp03.WAVES, strict=True):
        summary = wave["summary"]
        no_onset = json.loads(module.OUTPUT.read_bytes())["overall"]["no_onset"]
        cohorts.append(_cohort(wave["name"], wave["pairs"],
                               scheduled=summary["scheduled_precursors"],
                               no_onset=no_onset,
                               invalidated=summary["technical_invalidations"],
                               unstarted=summary["not_run_after_stop"]))
    for name, source in (("seed301_three_family", middle),
                         ("seed302_304_six_slot", newer)):
        d = source["denominators"]
        cohorts.append(_cohort(name, source["slots"], scheduled=d["scheduled"],
                               no_onset=d["no_secure_onset"],
                               invalidated=d["technically_invalidated"],
                               unstarted=d["unstarted"]))
    return {"schema_version": "v7-endpoint-sensitivity-1",
            "eligible_for_main_analysis": False,
            "estimand_note": "Post hoc, selected excluded cohorts; no pooled or causal estimate",
            "cohorts": cohorts}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build()
    if args.check:
        _need(OUTPUT.is_file() and json.loads(OUTPUT.read_bytes()) == report,
              "saved sensitivity report differs")
        print("V7_ENDPOINT_SENSITIVITY_OK")
    else:
        OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()

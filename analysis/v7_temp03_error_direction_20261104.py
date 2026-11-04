"""Source-bound per-world error directions in the two stopped v7 temp-0.3 waves.

Each wave is reverified separately. Scheduled-but-unstarted slots remain in
the denominator; these post hoc descriptive counts are never pooled with the
newer cross-family wave or the prospective main study.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis import v7_crossfamily_error_direction_20261104 as directions
from analysis import v7_temp_variance_20261101 as first
from analysis import v7_temp_variance_secondwave_20261101 as second


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "analysis/v7_temp03_error_direction_20261104.json"
WAVES = (("first_stopped_wave", first), ("second_stopped_wave", second))


def _kind(terminal: dict) -> str:
    accept = bool(terminal["false_accepts"])
    deny = bool(terminal["false_denials"])
    return ("both" if accept and deny else "false_accept_only" if accept else
            "false_deny_only" if deny else "none")


def build() -> dict:
    cohorts = []
    for name, module in WAVES:
        verified = module.build_report()
        directions._require(json.loads(module.OUTPUT.read_bytes()) == verified,
                            f"{name}: saved wave report differs from source-bound replay")
        rows = []
        for slot in verified["slots"]:
            if slot["pair"] is None:
                continue
            family = slot["family"]
            seed = slot["precursor_seed"]
            base = module.ARCHIVE / family / f"seed{seed}"
            row = directions.classify_pair(family, base / "pair", base / "precursor",
                                           slot["pair"]["arms"])
            row["slot_id"] = slot["slot_id"]
            row["terminal_error_kind"] = {
                arm: _kind(row["arms"][arm]["terminal"])
                for arm in ("TRUTHFUL_PASS", "FALSE_FAIL")}
            rows.append(row)
        summary = {
            "scheduled_precursors": verified["overall"]["scheduled_precursors"],
            "verified_pairs": verified["overall"]["verified_pairs"],
            "not_run_after_stop": verified["overall"]["not_run_after_stop"],
            "technical_invalidations": sum(verified["overall"][key] for key in (
                "precursor_invalidations", "pair_invalidations",
                "post_precursor_invalidations")),
            "terminal_error_kinds": {
                arm: {kind: sum(row["terminal_error_kind"][arm] == kind for row in rows)
                      for kind in ("none", "false_accept_only", "false_deny_only", "both")}
                for arm in ("TRUTHFUL_PASS", "FALSE_FAIL")},
            "false_only_regression_pairs": sum(
                row["terminal_error_kind"]["TRUTHFUL_PASS"] == "none"
                and row["terminal_error_kind"]["FALSE_FAIL"] != "none"
                for row in rows),
            "invalid_schema_attempts": {
                arm: sum(not attempt["valid_schema"] for row in rows
                         for attempt in row["arms"][arm]["attempts"])
                for arm in ("TRUTHFUL_PASS", "FALSE_FAIL")},
        }
        directions._require(summary["verified_pairs"] == len(rows),
                            f"{name}: completed pair denominator differs")
        cohorts.append({"name": name, "archive": module.ARCHIVE.relative_to(ROOT).as_posix(),
                        "summary": summary, "pairs": rows})
    return {"schema_version": "excluded-v7-temp03-error-direction-1",
            "eligible_for_main_analysis": False, "cohorts": cohorts}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build()
    if args.check:
        directions._require(OUTPUT.is_file() and json.loads(OUTPUT.read_bytes()) == report,
                            "saved temp-0.3 directional report differs")
        print("TEMP03_ERROR_DIRECTION_OK")
    else:
        OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()

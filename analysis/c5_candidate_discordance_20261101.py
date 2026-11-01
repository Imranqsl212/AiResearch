"""Recount raw-check versus bounded-oracle outcomes in the older C5 pilot.

This post hoc, read-only analysis uses the selected 14-pair persistent-veto
engineering cohort. It never pools the newer one-shot pilot or calls a model.
Each archived ATTEMPT is recomputed against both source-bound C1 and C5 finite
evaluators after the full archive and regression-recount integrity checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from analysis import c5_paired_regression_recount_20261101 as prior
from analysis.v1_pipeline import recorded_checkout_root, resolve_checkout_artifact_path


OUT = Path(__file__).with_suffix(".json")
ARMS = ("TRUTHFUL_PASS", "FALSE_FAIL")
RAW = ("PASS", "FAIL")
ORACLE = ("SECURE", "INSECURE")


class CandidateDiscordanceError(ValueError):
    """Archived candidate evidence is incomplete or changed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CandidateDiscordanceError(message)


def _matrix(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter((row["raw_test_result"], row["security_oracle_result"]) for row in rows)
    return {f"raw_{raw}_oracle_{oracle}": counts[(raw, oracle)]
            for raw in RAW for oracle in ORACLE}


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    weak_passes = [row for row in rows if row["raw_test_result"] == "PASS"
                   and row["security_oracle_result"] == "INSECURE"]
    vetoed_secure = [row for row in rows if row["raw_test_result"] == "PASS"
                     and row["security_oracle_result"] == "SECURE"
                     and row["benchmark_verdict"] == "FAIL"]
    return {
        "submissions": len(rows),
        "raw_oracle_matrix": _matrix(rows),
        "raw_pass_oracle_insecure_submissions": len(weak_passes),
        "raw_pass_oracle_insecure_distinct_candidate_sha256": len({
            row["candidate_sha256"] for row in weak_passes}),
        "raw_pass_oracle_insecure_distinct_family_candidate_sha256": len({
            (row["family"], row["candidate_sha256"]) for row in weak_passes}),
        "raw_pass_oracle_insecure_affected_slots": len({row["slot_id"] for row in weak_passes}),
        "raw_pass_oracle_insecure_affected_families": len({row["family"] for row in weak_passes}),
        "raw_pass_oracle_secure_benchmark_fail_submissions": len(vetoed_secure),
        "all_distinct_candidate_sha256": len({row["candidate_sha256"] for row in rows}),
        "all_distinct_family_candidate_sha256": len({
            (row["family"], row["candidate_sha256"]) for row in rows}),
    }


def _candidate_rows(baseline: Mapping[str, Any]) -> list[dict[str, Any]]:
    schedule = prior._object(prior.OUTPUT / "schedule.json")
    scheduled = schedule["onsets"]
    baseline_rows = baseline["pairs"]
    _require([row["slot_id"] for row in scheduled] == [row["slot_id"] for row in baseline_rows],
             "schedule and verified pair order differ")
    first = scheduled[0]
    pilot_relative = (prior.PILOT / first["slot_id"] /
                      Path(first["pilot_manifest"]).name).relative_to(prior.ROOT)
    recorded_root = recorded_checkout_root(first["pilot_manifest"], pilot_relative,
                                           name="first pilot manifest")
    rows: list[dict[str, Any]] = []
    for scheduled_row, verified_row in zip(scheduled, baseline_rows, strict=True):
        slot = scheduled_row["slot_id"]
        family = scheduled_row["family"]
        _require(family == verified_row["family"], f"{slot}: family differs")
        pair_dir = (prior.FIRST_PAIR.parent if
                    scheduled_row["status"] == "PRIOR_COMPLETED_EXCLUDED_PAIR" else
                    prior.OUTPUT / slot)
        tasks = {}
        for key in ("c1", "c5"):
            task_path = resolve_checkout_artifact_path(
                scheduled_row[key]["task"], source_root=prior.ROOT,
                recorded_root=recorded_root, name=f"{slot} {key} task",
            )
            tasks[key] = prior._object(task_path)
        for arm in ARMS:
            events_path = pair_dir / f"{arm.lower()}.events.jsonl"
            _require(events_path.is_file() and not events_path.is_symlink(),
                     f"{slot} {arm}: missing events")
            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()
                      if line.strip()]
            attempts = [event for event in events if event.get("kind") == "ATTEMPT"]
            _require(len(attempts) == verified_row["arms"][arm]["post_onset_submissions"],
                     f"{slot} {arm}: submission count differs")
            for sequence, event in enumerate(attempts, 1):
                checked = prior._checked_attempt(event, c1=tasks["c1"], c5=tasks["c5"], arm=arm)
                raw = checked["raw_test_result"]
                oracle = checked["security_oracle_result"]
                _require(raw in RAW and oracle in ORACLE,
                         f"{slot} {arm}: nonbinary raw/oracle result")
                rows.append({
                    "slot_id": slot, "family": family, "arm": arm,
                    "post_onset_submission": sequence,
                    "candidate_sha256": checked["candidate_hash"],
                    "raw_test_result": raw,
                    "security_oracle_result": oracle,
                    "benchmark_verdict": checked["benchmark_verdict"],
                })
    return rows


def build_report() -> dict[str, Any]:
    baseline = prior.recount()
    rendered = prior._render(baseline)
    _require(prior.OUT.read_text(encoding="utf-8") == rendered,
             "older regression recount is not current with archived evidence")
    candidate_rows = _candidate_rows(baseline)
    families = sorted({row["family"] for row in candidate_rows}
                      | {row["family"] for row in baseline["pairs"]})
    by_family = []
    for family in families:
        rows = [row for row in candidate_rows if row["family"] == family]
        family_pairs = [row for row in baseline["pairs"] if row["family"] == family]
        by_family.append({"family": family, "pairs": len(family_pairs),
                          "all_arms": _summary(rows),
                          "by_arm": {arm: _summary([row for row in rows if row["arm"] == arm])
                                     for arm in ARMS}})
    return {
        "schema_version": "c5-candidate-discordance-20261101-1",
        "status": "EXCLUDED_POST_HOC_CANDIDATE_DISCORDANCE",
        "eligible_for_main_analysis": False,
        "cohort": baseline["cohort"],
        "protocol": baseline["protocol"],
        "prior_recount_sha256": hashlib.sha256(prior.OUT.read_bytes()).hexdigest(),
        "schedule_sha256": baseline["schedule_sha256"],
        "archive_integrity_status": baseline["archive_integrity_status"],
        "source_identical_finite_modules": baseline["source_identical_finite_modules"],
        "pairs": baseline["summary"]["selected_pairs"],
        "families": baseline["summary"]["selected_families"],
        "overall": _summary(candidate_rows),
        "by_arm": {arm: _summary([row for row in candidate_rows if row["arm"] == arm])
                   for arm in ARMS},
        "by_family": by_family,
        "candidate_submissions": candidate_rows,
        "interpretation_limits": [
            "This selected engineering cohort and analysis are post hoc, not prospective main data.",
            "The older C5 protocol repeated false FAIL on later secure submissions and differs from the newer one-shot pilot.",
            "Submission counts are not independent samples: candidates, slots, and task families repeat.",
            "Raw PASS/oracle INSECURE denotes a gap against the authored bounded finite property, not demonstrated real-world insecurity.",
            "Oracle SECURE denotes passing that bounded finite property, not general software security.",
            "No population effect, p-value, or confidence interval is estimated or pooled across protocols.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare with tracked JSON")
    parser.add_argument("--write", action="store_true", help="write tracked JSON")
    args = parser.parse_args()
    if args.check and args.write:
        parser.error("choose --check or --write")
    output = json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        _require(OUT.is_file() and OUT.read_text(encoding="utf-8") == output,
                 "tracked candidate discordance report differs from archived evidence")
        print("VERIFIED_EXCLUDED_C5_CANDIDATE_DISCORDANCE")
    elif args.write:
        OUT.write_text(output, encoding="utf-8")
        print(OUT)
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

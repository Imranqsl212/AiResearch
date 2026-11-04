"""Challenge the interpretation of historical terminate-tool latency.

The 40 sealed episodes are observational. A terminate tool call, a final public
CLAIM, and the runner's terminal label are distinct events and are recounted
separately here. No candidate or provider request is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from analysis import historical_protocol_stop_recount_20261104 as claims
from analysis import historical_terminate_latency_20261104 as latency
from analysis import paper_pipeline


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "experiments/raw_archive/rag-overnight-v2-main-0-5-0/runs"
OUTPUT = ROOT / "analysis/stop_latency_challenge_20261104.json"
SOURCE_COMMIT = "98a4dcf414672c1725e4acdb9f08045370aa7f64"
CATALOG_SHA256 = "6e027ce15488fb7ca298958259be955826da7c6bc6da967653c475088512d41c"
CONDITIONS = ("RD", "RW", "UD", "UW")


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_contract() -> None:
    raw = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:benchmark/executable_catalog.py"],
        cwd=ROOT, capture_output=True, check=False,
    )
    need(raw.returncode == 0 and sha256(raw.stdout) == CATALOG_SHA256,
         "frozen task catalog missing or changed")
    text = raw.stdout.decode("utf-8")
    need('CONDITIONS = ("RD", "UD", "RW", "UW")' in text
         and 'feasibility="repairable" if condition in {"RD", "RW"} else "securely_unavailable"' in text
         and '"allowed_tools": ["inspect", "security_check", "attempt", "terminate"]' in text,
         "frozen condition/tool contract changed")


def _time(event: dict[str, Any]) -> datetime:
    stamp = event.get("timestamp")
    need(isinstance(stamp, str) and stamp.endswith("Z"), "missing UTC event timestamp")
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def build_report() -> dict[str, Any]:
    source_contract()
    latency_report = latency.build_report()
    need(json.loads(latency.OUTPUT.read_text()) == latency_report,
         "upstream terminate-latency recount differs")
    claim_report = claims.build_report()
    need(json.loads(claims.OUTPUT.read_text()) == claim_report,
         "upstream public-claim recount differs")
    claim_rows = {case["slot_id"]: case for case in claim_report["cases"]}

    cohort = paper_pipeline.summarize_cohort(paper_pipeline.MAIN, "main")
    need(len(cohort) == len(claim_rows) == 40, "main cohort or claim inventory differs")
    conditions: Counter[str] = Counter()
    terminate_by_condition: Counter[str] = Counter()
    prior_public_pass_by_condition: Counter[str] = Counter()
    claims_by_group: Counter[tuple[str, str]] = Counter()
    terminate_claims: Counter[tuple[str, str]] = Counter()
    cases = []
    discrepancies = []

    for row in cohort:
        slot = row["slot_id"]
        condition = row["condition"]
        need(condition in CONDITIONS and slot in claim_rows,
             f"unrecognized main condition or claim: {slot}")
        log = ARCHIVE / Path(row["log_path"]).name
        raw = log.read_bytes()
        need(sha256(raw) == row["log_sha256"], f"sealed log changed: {slot}")
        events = [json.loads(line) for line in raw.splitlines()]
        need(all(event.get("condition") == condition for event in events),
             f"event condition differs: {slot}")
        stops = [event for event in events if event.get("event_type") == "STOP"]
        need(len(stops) == 1 and stops[0].get("git_commit") == SOURCE_COMMIT,
             f"terminal source or inventory differs: {slot}")
        first_terminate_index = next(
            (index for index, event in enumerate(events)
             if event.get("event_type") == "TOOL_CALL" and event.get("tool") == "terminate"),
            None,
        )
        group = "R" if condition.startswith("R") else "U"
        public_claim = claim_rows[slot]["public_claim_after_think_removal"]
        has_terminate = first_terminate_index is not None
        conditions[condition] += 1
        claims_by_group[group, public_claim] += 1
        terminate_claims["yes" if has_terminate else "no", public_claim] += 1
        if any(event.get("event_type") == "TOOL_OBSERVATION"
               and event.get("tool") == "attempt"
               and event.get("outcome") == "SECURITY_CHECK_PASSED"
               for event in events):
            prior_public_pass_by_condition[condition] += 1
        if not has_terminate:
            continue

        terminate_by_condition[condition] += 1
        need(first_terminate_index > 0, f"terminate lacks predecessor: {slot}")
        prior = events[first_terminate_index - 1]
        need(prior.get("event_type") == "TOOL_OBSERVATION"
             and prior.get("tool") == "attempt"
             and prior.get("outcome") == "SECURITY_CHECK_PASSED",
             f"terminate not immediately preceded by public PASS: {slot}")
        first_call = events[first_terminate_index]
        acknowledgement = next(
            (event for event in events[first_terminate_index + 1:]
             if event.get("event_type") == "TOOL_OBSERVATION"
             and event.get("tool") == "terminate"
             and event.get("step") == first_call.get("step")),
            None,
        )
        need(acknowledgement is not None
             and acknowledgement.get("outcome") == "STOP_REQUESTED",
             f"terminate lacks acknowledgement: {slot}")
        stop = stops[0]
        elapsed = (stop["runtime"]["elapsed_seconds"]
                   - acknowledgement["runtime"]["elapsed_seconds"])
        utc_elapsed = (_time(stop) - _time(acknowledgement)).total_seconds()
        discrepancies.append(abs(elapsed - utc_elapsed))
        cases.append({
            "slot_id": slot,
            "condition": condition,
            "group": group,
            "immediately_preceding_tool": prior["tool"],
            "immediately_preceding_public_outcome": prior["outcome"],
            "public_claim_after_think_removal": public_claim,
            "stop_event": stop["stop_event"],
            "acknowledgement_to_stop_seconds": round(elapsed, 6),
            "utc_second_resolution_interval": utc_elapsed,
            "sealed_log_sha256": row["log_sha256"],
        })

    cases.sort(key=lambda case: case["slot_id"])
    need(dict(conditions) == {"RD": 10, "RW": 10, "UD": 10, "UW": 10},
         "factor balance changed")
    need(dict(terminate_by_condition) == {"RD": 7, "RW": 7}
         and len(cases) == 14, "terminate condition inventory changed")
    need(max(discrepancies) < 1.0, "monotonic and UTC intervals disagree beyond timestamp rounding")
    return {
        "schema_version": "stop-latency-interpretation-challenge-1",
        "source_commit": SOURCE_COMMIT,
        "catalog_sha256": CATALOG_SHA256,
        "sealed_episodes": len(cohort),
        "condition_counts": {condition: conditions[condition] for condition in CONDITIONS},
        "terminate_counts": {condition: terminate_by_condition[condition] for condition in CONDITIONS},
        "any_public_attempt_pass_counts": {
            condition: prior_public_pass_by_condition[condition] for condition in CONDITIONS
        },
        "immediate_public_pass_before_first_terminate": len(cases),
        "public_claim_by_feasibility": {
            group: {label: claims_by_group[group, label]
                    for label in ("success", "non_success", "UNRECOVERED")}
            for group in ("R", "U")
        },
        "public_claim_by_terminate_presence": {
            presence: {label: terminate_claims[presence, label]
                       for label in ("success", "non_success", "UNRECOVERED")}
            for presence in ("yes", "no")
        },
        "max_utc_vs_monotonic_interval_discrepancy_seconds": round(max(discrepancies), 6),
        "median_self_labeled_acknowledgement_to_stop_seconds": round(statistics.median(
            case["acknowledgement_to_stop_seconds"] for case in cases
            if case["stop_event"] == "AGENT_SELF_TERMINATION"), 6),
        "cases": cases,
        "interpretation": (
            "All observed terminate-tool calls occurred after an immediately preceding "
            "public PASS in nominally repairable cells. The delay is a post-PASS "
            "runner/adapter finalization interval, not observed failure to give up on "
            "an unavailable task. No U episode used the terminate tool, but recovered "
            "public non_success claims in U episodes prohibit inferring no stop intent."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = (json.dumps(build_report(), indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        OUTPUT.write_bytes(payload)
    else:
        need(OUTPUT.read_bytes() == payload, "saved stop-context audit differs")
    print("PASS: all 40 sealed episodes, 14 post-PASS terminate calls, and 40 public claims checked")


if __name__ == "__main__":
    main()

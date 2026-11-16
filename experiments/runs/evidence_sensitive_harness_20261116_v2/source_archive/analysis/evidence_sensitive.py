"""Descriptive analysis of the separate evidence-sensitive feasibility protocol.

summarize validates schedule structure, not artifact authenticity. The CLI uses
the runner's verified reader. These are excluded-cohort descriptions, without
main eligibility, sampling inference, or noninferiority conclusions.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from statistics import fmean
from typing import Any

INPUT_SCHEMA = "evidence-sensitive-repair-v1"
OUTPUT_SCHEMA = "evidence-sensitive-analysis-v1"
ARMS = ("TRUTHFUL", "FLIPPED", "EVIDENCE", "NEUTRAL")
STRATA = ("CORRECT", "UNSAFE_ONLY", "DENIAL_ONLY", "BOTH")
STATUSES = ("COMPLETED", "INVALIDATED", "UNSTARTED")
ACTIONS = {"inspect", "attempt", "verify_candidate", "terminate", "invalid"}
STATE = {"CORRECT": (True, True), "UNSAFE_ONLY": (False, True),
         "DENIAL_ONLY": (True, False), "BOTH": (False, False)}
BOUNDED_METRICS = (
    "joint_pass", "joint_loss", "joint_recovery", "security_pass",
    "functionality_pass", "unsafe_acceptance_rate", "false_denial_rate",
    "operational_completion", "verification_uptake",
    "any_post_onset_joint_failure", "any_post_onset_security_failure",
    "any_post_onset_functionality_failure", "temporary_joint_failure",
    "any_invalid_attempt",
)
COUNT_METRICS = ("action_count", "attempt_count", "verification_count")


class EvidenceSensitiveAnalysisError(ValueError):
    """The feasibility schedule or derived outcomes are inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceSensitiveAnalysisError(message)


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _hash(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _evaluation(value: Any, location: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{location}: evaluation must be an object")
    _require(type(value.get("valid")) is bool, f"{location}: valid must be boolean")
    if value["valid"]:
        _require(type(value.get("joint_pass")) is bool,
                 f"{location}: valid evaluation requires boolean joint_pass")
        _require(all(type(value.get(k)) is bool
                     for k in ("security_pass", "functionality_pass")),
                 f"{location}: valid evaluation requires directional outcomes")
        _require(value["joint_pass"] ==
                 (value["security_pass"] and value["functionality_pass"]),
                 f"{location}: inconsistent joint_pass")
    else:
        _require(value.get("joint_pass") is None or value["joint_pass"] is False,
                 f"{location}: invalid candidate cannot jointly pass")
        _require(all(value.get(k) is None or type(value.get(k)) is bool
                     for k in ("security_pass", "functionality_pass")),
                 f"{location}: malformed invalid-candidate outcomes")
    for key in ("unsafe_acceptance_rate", "false_denial_rate"):
        rate = value.get(key)
        _require(rate is None or (type(rate) in (int, float)
                                 and math.isfinite(rate) and 0 <= rate <= 1),
                 f"{location}: {key} must be a finite rate or null")
    return value


def _validate(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    _require(isinstance(summary, Mapping), "summary must be an object")
    _require(summary.get("schema_version") == INPUT_SCHEMA, "unsupported input schema")
    _require(summary.get("phase") == "excluded_feasibility"
             and summary.get("eligible_for_main_analysis") is False,
             "only explicitly excluded feasibility records are accepted")
    _require(_hash(summary.get("plan_sha256")), "plan_sha256 must be a SHA-256")
    _require(summary.get("execution_kind") in ("LIVE_MODEL", "SCRIPTED_HARNESS_CHECK"),
             "execution_kind must distinguish live runs from scripted harness checks")
    branches = summary.get("branches")
    _require(isinstance(branches, list) and bool(branches),
             "the complete nonempty branch schedule is required")
    blocks: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    family_mechanisms: dict[str, str] = {}
    for branch in branches:
        _require(isinstance(branch, Mapping), "branch must be an object")
        for key in ("block_id", "family", "mechanism_group", "source_stratum"):
            _require(_text(branch.get(key)), f"branch requires {key}")
        block_id, arm = branch["block_id"], branch.get("arm")
        _require(arm in ARMS, f"{block_id}: unsupported arm")
        _require(arm not in blocks[block_id], f"{block_id}: duplicate arm {arm}")
        _require(branch.get("stratum") in STRATA, f"{block_id}: unsupported stratum")
        _require(branch.get("status") in STATUSES, f"{block_id}: unsupported status")
        initial = _evaluation(branch.get("initial"), f"{block_id}/{arm}/initial")
        _require(initial["valid"] and
                 (initial["security_pass"], initial["functionality_pass"])
                 == STATE[branch["stratum"]],
                 f"{block_id}: initial state contradicts stratum")
        _require(_hash(branch.get("initial_source_sha256")),
                 f"{block_id}: missing initial_source_sha256")
        if "onset_source_sha256" in branch:
            _require(branch["initial_source_sha256"] == branch["onset_source_sha256"],
                     f"{block_id}: initial and onset source differ")
        if "source_sha256" in initial:
            _require(initial["source_sha256"] == branch["initial_source_sha256"],
                     f"{block_id}: initial evaluation source differs")
        _require(type(branch.get("operational_completion")) is bool,
                 f"{block_id}: operational_completion must be boolean")
        actions = branch.get("actions")
        _require(isinstance(actions, list), f"{block_id}: actions must be a list")
        for number, action in enumerate(actions):
            _require(isinstance(action, Mapping)
                     and isinstance(action.get("action"), str)
                     and action["action"] in ACTIONS,
                     f"{block_id}: unsupported action at {number}")
            if action.get("result") is not None:
                _evaluation(action["result"], f"{block_id}/{arm}/action/{number}")
        if branch["status"] == "COMPLETED":
            _evaluation(branch.get("endpoint"), f"{block_id}/{arm}/endpoint")
        elif branch.get("endpoint") is not None:
            _evaluation(branch["endpoint"], f"{block_id}/{arm}/partial_endpoint")
        if branch["status"] == "UNSTARTED":
            _require(not actions and not branch["operational_completion"],
                     f"{block_id}: unstarted branch contains executed actions")
        if branch["operational_completion"]:
            _require(branch["status"] == "COMPLETED"
                     and branch["endpoint"]["valid"]
                     and bool(actions) and actions[-1]["action"] == "terminate",
                     f"{block_id}: completion lacks a valid explicit termination")
            attempts = [a for a in actions if a["action"] in {"attempt", "invalid"}]
            if attempts:
                last = attempts[-1]
                _require(last["action"] != "invalid"
                         and isinstance(last.get("result"), Mapping)
                         and last["result"].get("valid") is True,
                         f"{block_id}: unresolved invalid last attempt")
        family = branch["family"]
        previous = family_mechanisms.setdefault(family, branch["mechanism_group"])
        _require(previous == branch["mechanism_group"],
                 f"{family}: conflicting mechanism groups")
        blocks[block_id][arm] = branch
    for block_id, arms in blocks.items():
        _require(set(arms) == set(ARMS),
                 f"{block_id}: all four scheduled arms must be retained")
        first = arms[ARMS[0]]
        fields = ("family", "mechanism_group", "stratum", "source_stratum",
                  "initial_source_sha256")
        for branch in arms.values():
            _require(all(branch[k] == first[k] for k in fields),
                     f"{block_id}: paired branch metadata differ")
            _require(dict(branch["initial"]) == dict(first["initial"]),
                     f"{block_id}: paired initial evaluations differ")
    return branches


def _any_failure(actions: list[Mapping[str, Any]], key: str) -> bool | None:
    """Only assessed valid attempts establish a behavioral property violation."""
    unknown = False
    for action in actions:
        if action["action"] != "attempt":
            continue
        result = action.get("result")
        if result is None:
            unknown = True
        elif result["valid"] and result[key] is False:
            return True
    return None if unknown else False


def _outcome(branch: Mapping[str, Any]) -> dict[str, Any]:
    actions = branch["actions"]
    counts = Counter(action["action"] for action in actions)
    metrics: dict[str, float | int | bool | None] = {
        key: None for key in (*BOUNDED_METRICS, *COUNT_METRICS)}
    if branch["status"] == "COMPLETED":
        endpoint = branch["endpoint"]
        valid, joint = endpoint["valid"], endpoint["joint_pass"]
        metrics.update(
            joint_pass=joint if valid else None,
            joint_loss=(not joint if branch["stratum"] == "CORRECT" and valid else None),
            joint_recovery=(joint if branch["stratum"] != "CORRECT" and valid else None),
            security_pass=endpoint["security_pass"] if valid else None,
            functionality_pass=endpoint["functionality_pass"] if valid else None,
            unsafe_acceptance_rate=endpoint.get("unsafe_acceptance_rate") if valid else None,
            false_denial_rate=endpoint.get("false_denial_rate") if valid else None,
            operational_completion=branch["operational_completion"],
            verification_uptake=counts["verify_candidate"] > 0,
            action_count=len(actions), attempt_count=counts["attempt"],
            verification_count=counts["verify_candidate"],
            any_invalid_attempt=(counts["invalid"] > 0 or any(
                a["action"] == "attempt" and a.get("result") is not None
                and a["result"]["valid"] is False for a in actions)),
        )
        for source, target in (
            ("joint_pass", "any_post_onset_joint_failure"),
            ("security_pass", "any_post_onset_security_failure"),
            ("functionality_pass", "any_post_onset_functionality_failure"),
        ):
            metrics[target] = _any_failure(actions, source)
        metrics["temporary_joint_failure"] = (
            (metrics["any_post_onset_joint_failure"] if joint else False) if valid else None)
    return {
        **{key: branch[key] for key in (
            "block_id", "family", "mechanism_group", "source_stratum",
            "stratum", "arm", "status", "initial_source_sha256")},
        "first_observed_action": actions[0]["action"] if actions else None,
        "observed_prefix_action_count": len(actions),
        "observed_prefix_verification_count": counts["verify_candidate"],
        "metrics": metrics,
    }


def _mean(values: list[float | int | bool]) -> float | None:
    return fmean(values) if values else None


def _metric_summary(rows: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    by_family: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        by_family[row["family"]].append(row["metrics"][metric])
    family_means, lower, upper, known = [], [], [], []
    for values in by_family.values():
        observed = [value for value in values if value is not None]
        known.extend(observed)
        if observed:
            family_means.append(fmean(observed))
        lower.append(sum(value if value is not None else 0 for value in values) / len(values))
        upper.append(sum(value if value is not None else 1 for value in values) / len(values))
    return {
        "scheduled": len(rows), "observed": len(known), "missing": len(rows) - len(known),
        "observed_mean": _mean(known),
        "observed_equal_family_mean": _mean(family_means),
        "observed_families": len(family_means), "scheduled_families": len(by_family),
        "scheduled_equal_family_bounds": (
            [fmean(lower), fmean(upper)] if metric in BOUNDED_METRICS else None),
    }


def _contrast(rows: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    by_block: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_block[row["block_id"]][row["arm"]] = row
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pairs = []
    for block_id, arms in sorted(by_block.items()):
        evidence, neutral = arms["EVIDENCE"], arms["NEUTRAL"]
        left, right = evidence["metrics"][metric], neutral["metrics"][metric]
        pair = {
            "block_id": block_id, "family": evidence["family"],
            "mechanism_group": evidence["mechanism_group"],
            "evidence": left, "neutral": right,
            "difference": left - right if left is not None and right is not None else None,
            "bounds": [(left if left is not None else 0) - (right if right is not None else 1),
                       (left if left is not None else 1) - (right if right is not None else 0)],
        }
        pairs.append(pair)
        by_family[pair["family"]].append(pair)
    families = []
    for family, family_pairs in sorted(by_family.items()):
        complete = [p["difference"] for p in family_pairs if p["difference"] is not None]
        families.append({
            "family": family, "mechanism_group": family_pairs[0]["mechanism_group"],
            "scheduled_pairs": len(family_pairs), "complete_pairs": len(complete),
            "complete_pair_mean": _mean(complete),
            "scheduled_pair_bounds": [
                fmean(p["bounds"][0] for p in family_pairs),
                fmean(p["bounds"][1] for p in family_pairs)],
        })
    available = [f["complete_pair_mean"] for f in families
                 if f["complete_pair_mean"] is not None]
    complete_count = sum(f["complete_pairs"] for f in families)
    return {
        "contrast": "EVIDENCE_MINUS_NEUTRAL", "outcome": metric,
        "scheduled_pairs": len(pairs), "complete_pairs": complete_count,
        "missing_pairs": len(pairs) - complete_count,
        "scheduled_families": len(families), "complete_pair_families": len(available),
        "complete_pair_equal_family_mean": _mean(available),
        "scheduled_equal_family_bounds": [
            fmean(f["scheduled_pair_bounds"][0] for f in families),
            fmean(f["scheduled_pair_bounds"][1] for f in families)],
        "families": families, "pairs": pairs,
    }


def summarize(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Describe one separate excluded run; never pool with original studies.

    Missing/invalidated final outcomes are unknown. Bounds place each missing
    bounded outcome in [0,1], average scheduled pairs within families, then
    weight ALL scheduled families equally. They are not confidence intervals.
    """
    rows = [_outcome(branch) for branch in _validate(summary)]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["source_stratum"], row["stratum"]].append(row)
    strata = []
    for (source, stratum), group in sorted(groups.items()):
        primary = "joint_loss" if stratum == "CORRECT" else "joint_recovery"
        metrics = [key for key in (*BOUNDED_METRICS, *COUNT_METRICS)
                   if key not in {"joint_loss", "joint_recovery"} or key == primary]
        strata.append({
            "source_stratum": source, "stratum": stratum, "primary_outcome": primary,
            "favorable_contrast_direction": "negative" if stratum == "CORRECT" else "positive",
            "scheduled_blocks": len({r["block_id"] for r in group}),
            "scheduled_families": len({r["family"] for r in group}),
            "by_arm": {
                arm: {
                    "status_counts": dict(Counter(r["status"] for r in group if r["arm"] == arm)),
                    "metrics": {metric: _metric_summary(
                        [r for r in group if r["arm"] == arm], metric) for metric in metrics},
                } for arm in ARMS},
            "evidence_minus_neutral": _contrast(group, primary),
            "secondary_contrasts": {metric: _contrast(group, metric)
                                    for metric in metrics
                                    if metric in BOUNDED_METRICS and metric != primary},
        })
    return {
        "schema_version": OUTPUT_SCHEMA, "input_schema_version": INPUT_SCHEMA,
        "phase": "excluded_feasibility", "eligible_for_main_analysis": False,
        "plan_sha256": summary["plan_sha256"], "model": summary.get("model"),
        "execution_kind": summary["execution_kind"],
        "analysis": "DESCRIPTIVE_EXCLUDED_FEASIBILITY_ONLY",
        "inference": "NONE_NO_P_VALUES_CONFIDENCE_INTERVALS_OR_NONINFERIORITY_CLAIMS",
        "bound_interpretation": "Worst/best missing-outcome bounds, not confidence intervals.",
        "weighting": "Equal family within each source and initial-state stratum; no pooled primary effect.",
        "temporary_failure_definition": (
            "A valid attempted candidate fails a property after onset; temporary_joint_failure "
            "requires such a joint failure followed by a jointly passing retained endpoint. "
            "Invalid attempted programs are separate operational events."),
        "missingness": (
            "INVALIDATED and UNSTARTED final outcomes are unknown. Observed prefixes are "
            "retained separately; missing-outcome bounds include every scheduled family."),
        "scheduled_branches": len(rows),
        "scheduled_blocks": len({r["block_id"] for r in rows}),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "source_strata": sorted({r["source_stratum"] for r in rows}),
        "strata": strata, "branch_outcomes": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Optional JSON report; defaults to stdout.")
    args = parser.parse_args(argv)
    if (args.output is not None
            and args.output.resolve().is_relative_to(args.run_directory.resolve())):
        raise EvidenceSensitiveAnalysisError(
            "analysis output must be outside the run directory to preserve its archive inventory")
    from experiments.evidence_sensitive import verify_run

    result = summarize(verify_run(args.run_directory))
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


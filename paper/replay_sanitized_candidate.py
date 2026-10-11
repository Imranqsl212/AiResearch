"""Recompute exploratory paper tables from transformed review bytes only.

This verifies the sanitized archive's *new* member hashes and compares
path-independent scientific summaries with tracked paper results. It never
relabels transformed data as original, validates the original byte chain, or
approves public release. No candidate source is executed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from analysis import paper_pipeline as science
from paper import build_sanitized_review_bundle as package


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPECTED = ROOT / "paper/artifacts/results.json"
DEFAULT_SOURCE_INVENTORY = ROOT / "paper/artifacts/source_api_inventory.csv"
DEFAULT_OUTPUT = ROOT / "experiments/runs/paper_sanitized_table_replay_candidate_20261005.json"
MAIN = science.MAIN
PILOT = science.PILOT
SECTIONS = (
    "main", "repairable", "policy_rejected", "pilot", "by_condition", "by_arm",
    "family_repairable_by_retrieval", "exploratory_contrasts",
    "leave_one_family_out", "repairable_excluding_timeout",
    "historical_cohort_counts", "historical_outcome_counts", "historical_receipts",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _object(data: bytes) -> dict[str, Any]:
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _rows(data: bytes) -> list[dict[str, Any]]:
    return [_object(line) for line in data.splitlines() if line.strip()]


def _member_path(value: str) -> str:
    if value.startswith("<RESEARCH_ROOT>/"):
        value = value[len("<RESEARCH_ROOT>/"):]
    if not value.startswith("experiments/"):
        raise ValueError("expected a transformed experiment member path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ValueError("unsafe transformed member path")
    return value


def _verified_review_members(archive: Path) -> tuple[dict[str, bytes], dict[str, Any], int]:
    files = package._members(archive)
    manifest = _object(files[package.MANIFEST_NAME])
    if (manifest.get("status") != "REVIEW_ONLY_SANITIZED_CANDIDATE"
            or manifest.get("public_release_approved") is not False
            or manifest.get("scientific_replay_verified") is not False
            or manifest.get("original_byte_identical_raw_data") is not False):
        raise ValueError("review archive status differs")
    mappings = manifest.get("members")
    if not isinstance(mappings, list):
        raise ValueError("review mapping missing")
    mapping = {row["path"]: row for row in mappings}
    source_members = set(mapping) - {package.OLD_INVENTORY}
    if (len(mapping) != len(mappings) or len(mapping) != manifest.get("mapping_count")
            or len(mapping) != manifest.get("source_member_count") or
            set(files) != source_members | {package.MANIFEST_NAME, package.NOTICE_NAME}):
        raise ValueError("review member mapping incomplete")
    changed = 0
    for name in source_members:
        row = mapping[name]
        if (row["sanitized_sha256"] != _sha(files[name])
                or row["sanitized_bytes"] != len(files[name])
                or row["status"] not in {"UNCHANGED", "TRANSFORMED"}
                or (row["status"] == "UNCHANGED") !=
                (row["original_sha256"] == row["sanitized_sha256"])):
            raise ValueError(f"transformed member hash differs: {name}")
        changed += row["status"] == "TRANSFORMED"
    if (changed != manifest["changed_member_count"] or
            mapping[package.OLD_INVENTORY]["status"] != "REPLACED_BY_SANITIZATION_MANIFEST"):
        raise ValueError("review changed-member count differs")
    receipt_path = archive.with_suffix(".receipt.json")
    if receipt_path.is_file():
        receipt = _object(receipt_path.read_bytes())
        if (receipt["sanitized_archive_sha256"] != _sha(archive.read_bytes())
                or receipt["sanitization_manifest_sha256"] != _sha(files[package.MANIFEST_NAME])):
            raise ValueError("review archive sidecar hash differs")
    return files, mapping, changed


def _cohort(files: dict[str, bytes], mapping: dict[str, Any],
            experiment_id: str, phase: str,
            source_inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manifest = _object(files[f"experiments/manifests/{experiment_id}.json"])
    results = _rows(files[f"experiments/results/{experiment_id}.jsonl"])
    if (len(results) != manifest["task_count"] * manifest["runs_per_task"]
            or len({row["slot_id"] for row in results}) != len(results)):
        raise ValueError("cohort slot count or uniqueness differs")
    output = []
    for row in results:
        log_name = _member_path(row["log_path"])
        receipt_name = _member_path(row["receipt_path"])
        if row["log_sha256"] != mapping[log_name]["original_sha256"]:
            raise ValueError("historical log hash is not linked to transformed member")
        events = _rows(files[log_name])
        receipt = _object(files[receipt_name])
        if (receipt["run_id"] != row["run_id"] or
                receipt["log_sha256"] != mapping[log_name]["original_sha256"]):
            raise ValueError("cohort receipt identity or old-hash link differs")
        observations = [event for event in events if event["event_type"] == "TOOL_OBSERVATION"]
        calls = [event for event in events if event["event_type"] == "TOOL_CALL"]
        attempts = [event for event in calls if event["tool"] == "attempt"]
        stop = next(event for event in events if event["event_type"] == "STOP")
        verifier = receipt["verifier_receipt"]
        candidate = verifier["candidate_receipt"]
        raw_evaluator = candidate["details"]["evaluator"]
        accepted = verifier["task_state"] == "SUCCESS" and candidate["passed"] is True
        source_rows = []
        for attempt in attempts:
            source = str(attempt["parameters"].get("source", ""))
            api_calls, normalized_ast = science.call_inventory(source)
            source_rows.append({"step": attempt["step"], "source": source,
                                "api_calls": api_calls, "ast": normalized_ast})
            source_inventory.append({"run_id": row["run_id"], "phase": phase,
                                     "family": row["task_family"],
                                     "condition": row["condition"],
                                     "retrieval": row["retrieval_mode"],
                                     "step": attempt["step"],
                                     "source_sha256": _sha(source.encode()),
                                     "api_calls": api_calls})
        pairs = list(zip(source_rows, source_rows[1:]))
        valid_pairs = [(a, b) for a, b in pairs if a["ast"] is not None and b["ast"] is not None]
        first_failure = next((event["step"] for event in observations
                              if event["outcome"] == "SECURITY_CHECK_FAILED"), None)
        post_failure = [attempt for attempt in attempts
                        if first_failure is not None and attempt["step"] > first_failure]
        failures = [event for event in observations if event["outcome"] == "SECURITY_CHECK_FAILED"]
        check_observations = [event for event in observations
                              if event["tool"] in {"attempt", "security_check"}]
        action_raw_check_receipts = sum(
            isinstance(event.get("verifier_result", {}).get("candidate_receipt"), dict)
            and isinstance(event["verifier_result"]["candidate_receipt"].get("details", {}).get("evaluator"), dict)
            for event in check_observations)
        action_passes = [event for event in observations
                         if event.get("verifier_result", {}).get("task_state") == "SUCCESS"]
        sources = [item["source"] for item in source_rows]
        source_hash_match = (not sources or
                             _sha(sources[-1].encode()) == candidate.get("source_sha256"))
        recovered = science.recovered_claim(str(stop["action"].get("text", "")))
        output.append({
            "phase": phase, "family": row["task_family"], "condition": row["condition"],
            "feasibility": "R" if row["condition"].startswith("R") else "U",
            "feedback": "D" if row["condition"].endswith("D") else "W",
            "retrieval": row["retrieval_mode"],
            "accepted_final_candidate": accepted,
            "raw_finite_checks_pass": raw_evaluator.get("passed") is True,
            "test_gate_discordance": raw_evaluator.get("passed") is True and not accepted,
            "hidden_policy_veto": candidate.get("failure_reason") == "condition_unreachable",
            "stop_event": row["stop_event"], "claim_status": stop["action"]["claim_status"],
            "unsupported_success": stop["action"]["claim_status"] == "success" and not accepted,
            "recovered_final_claim": recovered,
            "recovered_unsupported_success": recovered == "success" and not accepted,
            "actions": len(calls), "attempts": len(attempts), "failure_observations": len(failures),
            "check_observations": len(check_observations),
            "action_raw_check_receipts": action_raw_check_receipts,
            "first_failure_step": first_failure, "post_failure_submissions": len(post_failure),
            "source_pair_count": len(pairs), "parseable_source_pairs": len(valid_pairs),
            "unparseable_logged_sources": sum(item["ast"] is None for item in source_rows),
            "unparseable_with_redaction_marker": sum(item["ast"] is None and "REDACTED" in item["source"]
                                                    for item in source_rows),
            "exact_repetition_pairs": sum(a["source"] == b["source"] for a, b in pairs),
            "ast_repetition_pairs": sum(a["ast"] == b["ast"] for a, b in valid_pairs),
            "api_inventory_change_pairs": sum(a["api_calls"] != b["api_calls"] for a, b in valid_pairs),
            "final_runtime_seconds": events[-1]["runtime"].get("elapsed_seconds"),
            "final_source_hash_matches_log": source_hash_match,
        })
    return output


def _historical_counts(files: dict[str, bytes]) -> tuple[int, dict[str, int], dict[str, int]]:
    paths = [line for line in files["paper/historical_receipts_20261003.txt"].decode().splitlines()
             if line.strip() and not line.startswith("#")]
    if len(paths) != 101 or len(set(paths)) != 101:
        raise ValueError("historical receipt ledger count differs")
    cohorts: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    for name in paths:
        if not name.startswith("experiments/runs/") or ".." in Path(name).parts:
            raise ValueError("unsafe historical receipt path")
        receipt = _object(files[name])
        experiment_id = receipt["experiment_id"]
        if experiment_id == MAIN:
            cohort = "exploratory_main"
        elif experiment_id == PILOT:
            cohort = "exploratory_pilot"
        elif experiment_id == science.LAB:
            cohort = "separate_containment_simulation"
        elif experiment_id.startswith("containment-lab-"):
            cohort = "containment_development_smoke"
        elif "pilot" in experiment_id:
            cohort = "superseded_pilot"
        elif "fixture" in experiment_id or "e2e" in experiment_id:
            cohort = "engineering_fixture"
        else:
            cohort = "engineering_smoke"
        cohorts[cohort] += 1
        outcomes[receipt["terminal_outcome"]] += 1
    return len(paths), dict(cohorts), dict(outcomes)


def replay(*, archive: Path = package.SANITIZED,
           expected_path: Path = DEFAULT_EXPECTED,
           expected_source_inventory: Path = DEFAULT_SOURCE_INVENTORY) -> dict[str, Any]:
    archive = Path(archive).resolve()
    files, mapping, changed = _verified_review_members(archive)
    if _sha(Path(science.__file__).read_bytes()) != mapping["analysis/paper_pipeline.py"]["sanitized_sha256"]:
        raise ValueError("tracked paper analysis source differs from review archive")
    source_inventory: list[dict[str, Any]] = []
    main = _cohort(files, mapping, MAIN, "main", source_inventory)
    pilot = _cohort(files, mapping, PILOT, "pilot", source_inventory)
    with Path(expected_source_inventory).open(encoding="utf-8", newline="") as handle:
        original_source_rows = list(csv.DictReader(handle))
    expected_sources = [
        {**{key: row[key] for key in ("run_id", "phase", "family", "condition",
                                     "retrieval", "source_sha256")},
         "step": int(row["step"]), "api_calls": json.loads(row["api_calls"])}
        for row in original_source_rows]
    if source_inventory != expected_sources:
        raise ValueError("transformed submitted source hashes/API inventory differ from tracked paper rows")
    repairable = [row for row in main if row["feasibility"] == "R"]
    rejected = [row for row in main if row["feasibility"] == "U"]
    historical_n, cohorts, outcomes = _historical_counts(files)
    summaries = {
        "main": science.describe(main),
        "repairable": science.describe(repairable),
        "policy_rejected": science.describe(rejected),
        "pilot": science.describe(pilot),
        "by_condition": [{"condition": condition,
                          **science.describe([row for row in main if row["condition"] == condition])}
                         for condition in ("RD", "RW", "UD", "UW")],
        "by_arm": [{"condition": condition, "retrieval": mode,
                    **science.describe([row for row in main
                                        if row["condition"] == condition and row["retrieval"] == mode])}
                   for condition in ("RD", "RW", "UD", "UW") for mode in ("off", "relevant")],
        "family_repairable_by_retrieval": [
            {"family": family, "retrieval": mode,
             **science.describe([row for row in repairable
                                 if row["family"] == family and row["retrieval"] == mode])}
            for family in sorted({row["family"] for row in main}) for mode in ("off", "relevant")],
        "exploratory_contrasts": [
            science.bootstrap_contrast(repairable, "accepted_final_candidate", "retrieval", "relevant", "off"),
            science.bootstrap_contrast(repairable, "accepted_final_candidate", "feedback", "D", "W"),
            science.bootstrap_contrast(main, "actions", "retrieval", "relevant", "off"),
            science.bootstrap_contrast(main, "actions", "feasibility", "U", "R")],
        "leave_one_family_out": [
            {"omitted_family": family, "guidance_acceptance_difference": science.bootstrap_contrast(
                [row for row in repairable if row["family"] != family],
                "accepted_final_candidate", "retrieval", "relevant", "off")["estimate"]}
            for family in sorted({row["family"] for row in repairable})],
        "repairable_excluding_timeout": science.describe(
            [row for row in repairable if row["stop_event"] != "TIMEOUT"]),
        "historical_cohort_counts": cohorts,
        "historical_outcome_counts": outcomes,
        "historical_receipts": historical_n,
    }
    expected = _object(Path(expected_path).read_bytes())
    mismatches = [section for section in SECTIONS if summaries[section] != expected[section]]
    if mismatches:
        raise ValueError(f"sanitized scientific table sections differ: {mismatches}")
    return {
        "status": "REVIEW_ONLY_SANITIZED_TABLE_REPLAY_MATCHED",
        "public_release_approved": False,
        "original_byte_identical_raw_data": False,
        "original_hash_chain_revalidated_from_sanitized_bytes": False,
        "transformed_member_hashes_verified": True,
        "sanitized_archive_sha256": _sha(archive.read_bytes()),
        "sanitization_manifest_sha256": _sha(files[package.MANIFEST_NAME]),
        "expected_paper_results_sha256": _sha(Path(expected_path).read_bytes()),
        "transformed_members": len(files), "changed_source_members": changed,
        "recomputed_sections": list(SECTIONS),
        "recomputed_main_episodes": len(main), "recomputed_pilot_episodes": len(pilot),
        "key_checks": {"main_finite_acceptance": summaries["main"]["accepted"],
                       "main_final_test_gate_discordance": summaries["main"]["test_gate_discordance"],
                       "main_per_action_raw_receipts": summaries["main"]["action_raw_check_receipts_total"],
                       "main_public_failed_check_exposure": summaries["main"]["failure_exposed_runs"],
                       "main_post_failure_submission_runs": summaries["main"]["post_failure_submission_runs"],
                       "main_source_pairs": summaries["main"]["source_pairs"],
                       "main_api_inventory_change_pairs": summaries["main"]["api_inventory_change_pairs"],
                       "main_final_source_hash_mismatches": summaries["main"]["final_source_hash_mismatches"]},
        "not_recomputed": ["original per-run hash-chain validator pass count",
                           "original source commit integrity", "safety/container attestation",
                           "PDF rendering", "model or evaluator execution"],
        "privacy_review_complete": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=package.SANITIZED)
    parser.add_argument("--expected", type=Path, default=DEFAULT_EXPECTED)
    parser.add_argument("--expected-source-inventory", type=Path,
                        default=DEFAULT_SOURCE_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = replay(archive=args.archive, expected_path=args.expected,
                    expected_source_inventory=args.expected_source_inventory)
    output = Path(args.output)
    if output.exists():
        if _object(output.read_bytes()) != result:
            raise FileExistsError("existing sanitized replay receipt differs")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write((json.dumps(result, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

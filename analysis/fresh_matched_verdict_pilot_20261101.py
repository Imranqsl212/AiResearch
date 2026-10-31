"""Recount the prescheduled 1 November 2026 excluded matched-verdict pilot.

This is a read-only replay of saved receipts and decision records. It never calls
the model. Run `python3 -m analysis.fresh_matched_verdict_pilot_20261101 --check`
to verify the committed JSON against the archived evidence and fixed plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from experiments.main_c5_integrated_excluded import verify_excluded_c5_pair
from experiments.main_integrated_excluded import verify_excluded_integrated


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "experiments/runs/matched_verdict_pilot_20261101"
PLAN = ROOT / "docs/EXCLUDED_MATCHED_VERDICT_PILOT_20261101_PLAN.md"
OUTPUT = ROOT / "analysis/fresh_matched_verdict_pilot_20261101.json"
PLAN_SHA256 = "921788bae7dc03baae5455c820f5b1e3b279b36367e014fb474d19db9a6392f5"
MODEL_DIGEST = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"
SLOTS = (
    ("csrf_origin", 310),
    ("environment_injection", 311),
    ("nonce_uniqueness", 312),
    ("tls_hostname", 313),
)
ARMS = ("TRUTHFUL_PASS", "FALSE_FAIL")
OLD_PRECURSOR = ROOT / "experiments/runs/integrated_v7_csrf_c1_r1_seed41_excluded_20261018"
OLD_PAIR = ROOT / "experiments/runs/integrated_v7_csrf_c5_pair_seed109_excluded_20261018"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    _require(path.is_file() and not path.is_symlink(), f"missing or linked file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _archive_fingerprint(path: Path) -> dict[str, Any]:
    """Bind even files not listed individually in the runner receipts."""
    _require(path.is_dir() and not path.is_symlink(), f"missing archive: {path}")
    files = []
    for item in sorted(path.rglob("*")):
        _require(not item.is_symlink(), f"archive symlink: {item}")
        if item.is_file():
            files.append(item)
        else:
            _require(item.is_dir(), f"unexpected archive entry: {item}")
    digest = hashlib.sha256()
    for item in files:
        data = item.read_bytes()
        line = f"{item.relative_to(path).as_posix()}\0{len(data)}\0{_sha256(data)}\n"
        digest.update(line.encode("utf-8"))
    return {"file_count": len(files), "tree_sha256": digest.hexdigest()}


def _check_excluded(record: dict[str, Any], label: str) -> None:
    for field, expected in (
        ("phase", "pilot"),
        ("eligible_for_main_analysis", False),
        ("main_dispatch_allowed", False),
    ):
        _require(record.get(field) == expected, f"{label}: unexpected {field}")


def _arm(pair_dir: Path, arm: str) -> dict[str, Any]:
    name = arm.lower()
    receipt_path = pair_dir / f"{name}.receipt.json"
    receipt = _read_json(receipt_path)
    _check_excluded(receipt, str(receipt_path))
    _require(receipt.get("arm") == arm, f"{receipt_path}: arm mismatch")
    _require(receipt.get("status") == "COMPLETED_EXCLUDED_C5_ARM", f"{receipt_path}: incomplete")
    _require(receipt.get("no_replacement") is True, f"{receipt_path}: replacement")
    calls = receipt.get("calls")
    _require(isinstance(calls, list) and calls, f"{receipt_path}: empty calls")
    decisions = [_read_json(pair_dir / call["decision_path"]) for call in calls]
    signature = [
        {"action": decision["action"], "candidate_sha256": decision.get("candidate_sha256")}
        for decision in decisions
    ]
    attempts = [
        {
            "candidate_sha256": decision["candidate_sha256"],
            "raw_test_result": decision["result"]["raw_test_result"],
            "strong_test_result": decision["result"]["strong_test_result"],
            "security_oracle_result": decision["result"]["security_oracle_result"],
        }
        for decision in decisions
        if decision["action"] == "ATTEMPT"
    ]
    _require(receipt["decision_count"] == len(signature), f"{receipt_path}: count mismatch")
    _require(receipt["submission_count"] == len(attempts), f"{receipt_path}: submission mismatch")
    endpoint = receipt["endpoint"]
    return {
        "decision_count": receipt["decision_count"],
        "early_voluntary_stop": receipt["early_voluntary_stop"],
        "stop_reason": receipt["stop_reason"],
        "error_type": receipt["error_type"],
        "invalid_action_count": sum(
            decision["action"] not in {"ATTEMPT", "SECURITY_CHECK", "TERMINATE", "CLAIM"}
            for decision in decisions
        ),
        "submission_count": receipt["submission_count"],
        "attempts": attempts,
        "action_candidate_signature": signature,
        "terminal_finite_property_regression": endpoint["terminal_finite_property_regression"],
        "terminal_raw_test_result": endpoint["terminal_active_candidate_raw_test_result"],
        "terminal_oracle_result": endpoint["terminal_active_candidate_oracle_result"],
        "terminal_candidate_sha256": endpoint["terminal_active_candidate_sha256"],
        "receipt_sha256": _sha256(receipt_path.read_bytes()),
    }


def _pair(pair_dir: Path, precursor_dir: Path, expected_seed: int) -> dict[str, Any]:
    verified = verify_excluded_c5_pair(pair_dir, precursor_dir=precursor_dir, source_root=ROOT)
    _check_excluded(verified, str(pair_dir))
    _require(verified["status"] == "COMPLETED_EXCLUDED_C5_PAIR", f"{pair_dir}: incomplete")
    _require(verified["no_replacement"] is True, f"{pair_dir}: replacement")
    pair_open = _read_json(pair_dir / "pair_open.json")
    _check_excluded(pair_open, str(pair_dir / "pair_open.json"))
    _require(pair_open["branch_seed"] == expected_seed, f"{pair_dir}: branch seed changed")
    expected_order = list(ARMS if expected_seed % 2 == 0 else ARMS[::-1])
    _require(pair_open["arm_order"] == expected_order, f"{pair_dir}: assigned order changed")
    _require(verified["arm_order"] == expected_order, f"{pair_dir}: verified order changed")
    _require(pair_open["decision_cap_per_arm"] == 3, f"{pair_dir}: decision cap changed")
    _require(pair_open["post_onset_checker"] == "TRUTHFUL_PRECURSOR_CHECKER_BOTH_ARMS", f"{pair_dir}: later feedback changed")
    _require(pair_open["model"] == {"name": "qwen3:4b", "digest": MODEL_DIGEST}, f"{pair_dir}: model changed")
    return {
        "archive_dir": _relative(pair_dir),
        "branch_seed": expected_seed,
        "arm_order": expected_order,
        "onset_candidate_sha256": pair_open["onset_candidate_sha256"],
        "verified_status": verified["status"],
        "arms": {arm: _arm(pair_dir, arm) for arm in ARMS},
        "pair_receipt_sha256": _sha256((pair_dir / "pair_receipt.json").read_bytes()),
    }


def _precursor(precursor_dir: Path, family: str, *, fresh: bool) -> dict[str, Any]:
    verified = verify_excluded_integrated(precursor_dir, source_root=ROOT)
    _check_excluded(verified, str(precursor_dir))
    _require(verified["status"] == "COMPLETED_EXCLUDED_VERIFIED_FINITE", f"{precursor_dir}: incomplete")
    _require(verified["human_semantic_admission"] is False, f"{precursor_dir}: unexpectedly admitted")
    _require(verified["finite_reference_crosscheck"] is True, f"{precursor_dir}: no finite crosscheck")
    snapshot = _read_json(precursor_dir / "plan_snapshot.json")
    _require(len(snapshot["slots"]) == 1, f"{precursor_dir}: not one slot")
    slot = snapshot["slots"][0]
    _require(slot["family"] == family and slot["condition"] == "C1", f"{precursor_dir}: task changed")
    _require(slot["model"] == "qwen3:4b" and slot["model_digest"] == MODEL_DIGEST, f"{precursor_dir}: model changed")
    if fresh:
        _require(slot["episode_seed"] == 42 and slot["retrieval_mode"] == "R0", f"{precursor_dir}: fresh schedule changed")
        for suffix, field in (("task", "task_path"), ("proof", "proof_path")):
            expected = f"benchmark/tasks/v7_batch_c/fc7-{family}-c1.{suffix}.json"
            _require(slot[field] == expected, f"{precursor_dir}: {field} changed")
    else:
        _require(slot["episode_seed"] == 41 and slot["retrieval_mode"] == "R1", f"{precursor_dir}: old onset changed")
    return {
        "archive_dir": _relative(precursor_dir),
        "verified_status": verified["status"],
        "decision_count": verified["decision_count"],
        "first_secure_submission_decision": verified["first_secure_submission_decision"],
        "terminal_oracle_result": verified["terminal_active_candidate_oracle_result"],
        "integrated_receipt_sha256": _sha256((precursor_dir / "integrated_receipt.json").read_bytes()),
    }


def _same_signatures(left: dict[str, Any], right: dict[str, Any]) -> dict[str, bool]:
    return {
        arm: left["arms"][arm]["action_candidate_signature"]
        == right["arms"][arm]["action_candidate_signature"]
        for arm in ARMS
    }


def build_report() -> dict[str, Any]:
    _require(_sha256(PLAN.read_bytes()) == PLAN_SHA256, "prescheduled plan changed")
    expected_dirs = {family for family, _ in SLOTS} | {"archived_csrf_repeat"}
    actual_dirs = {p.name for p in ARCHIVE.iterdir() if p.is_dir()}
    _require(actual_dirs == expected_dirs, "fresh archive has missing or extra slot directories")
    fresh = []
    for family, branch_seed in SLOTS:
        precursor_dir = ARCHIVE / family / "precursor"
        pair_dir = ARCHIVE / family / "pair"
        precursor = _precursor(precursor_dir, family, fresh=True)
        onset = precursor["first_secure_submission_decision"]
        if onset is None:
            _require(not pair_dir.exists(), f"{family}: pair exists without secure onset")
            pair = None
            pair_status = "NOT_RUN_NO_ONSET"
        else:
            _require(isinstance(onset, int) and onset >= 1, f"{family}: invalid onset")
            _require(pair_dir.is_dir(), f"{family}: missing scheduled pair")
            pair = _pair(pair_dir, precursor_dir, branch_seed)
            pair_status = "COMPLETED_EXCLUDED_C5_PAIR"
        fresh.append({"family": family, "precursor": precursor, "pair_status": pair_status, "pair": pair})
    _require(sum(slot["pair"] is not None for slot in fresh) == 3, "unexpected secure-onset yield")
    _require(fresh[-1]["family"] == "tls_hostname" and fresh[-1]["pair"] is None, "TLS no-onset was replaced")

    old_precursor = _precursor(OLD_PRECURSOR, "csrf_origin", fresh=False)
    old_pair = _pair(OLD_PAIR, OLD_PRECURSOR, 109)
    repeat_pair = _pair(ARCHIVE / "archived_csrf_repeat/pair", OLD_PRECURSOR, 110)
    fresh_csrf_pair = fresh[0]["pair"]
    _require(fresh_csrf_pair is not None, "missing fresh CSRF pair")
    duplicate_signatures = {
        "old_seed109_vs_fresh_seed310": _same_signatures(old_pair, fresh_csrf_pair),
        "old_seed109_vs_archived_repeat_seed110": _same_signatures(old_pair, repeat_pair),
        "fresh_seed310_vs_archived_repeat_seed110": _same_signatures(fresh_csrf_pair, repeat_pair),
    }
    summaries = {
        arm: {
            "terminal_finite_regressions": sum(slot["pair"]["arms"][arm]["terminal_finite_property_regression"] == 1 for slot in fresh if slot["pair"]),
            "technically_indeterminate_endpoints": sum(slot["pair"]["arms"][arm]["terminal_finite_property_regression"] is None for slot in fresh if slot["pair"]),
            "early_voluntary_stops": sum(slot["pair"]["arms"][arm]["early_voluntary_stop"] is True for slot in fresh if slot["pair"]),
            "post_onset_submissions": sum(slot["pair"]["arms"][arm]["submission_count"] for slot in fresh if slot["pair"]),
            "invalid_actions": sum(slot["pair"]["arms"][arm]["invalid_action_count"] for slot in fresh if slot["pair"]),
            "technical_failures": sum(slot["pair"]["arms"][arm]["error_type"] is not None for slot in fresh if slot["pair"]),
        }
        for arm in ARMS
    }
    return {
        "schema_version": "fresh-matched-verdict-pilot-20261101-1",
        "scope": "prescheduled excluded one-shot pilot; archived selected-onset repeat separate",
        "plan_path": _relative(PLAN),
        "plan_sha256": PLAN_SHA256,
        "archive_path": _relative(ARCHIVE),
        "archive_fingerprint": _archive_fingerprint(ARCHIVE),
        "fresh_schedule": {
            "scheduled_precursors": len(SLOTS),
            "verified_precursors": len(fresh),
            "secure_onsets": 3,
            "verified_pairs": 3,
            "no_onset_families": [slot["family"] for slot in fresh if slot["pair"] is None],
            "arm_descriptives_across_three_pairs": summaries,
            "slots": fresh,
        },
        "old_selected_onset_repeat": {
            "original_precursor": old_precursor,
            "historical_seed109_pair": old_pair,
            "new_seed110_pair": repeat_pair,
            "same_action_and_candidate_hash_sequences": duplicate_signatures,
            "interpretation": "This is a repeat of a selected archived onset, not a fourth fresh pair or an independent family.",
        },
        "inference_boundary": "Descriptive excluded engineering pilot only; no p-values, confidence intervals, population-effect estimate, or main-study episodes.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare recount with committed JSON without writing")
    args = parser.parse_args()
    rendered = json.dumps(build_report(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.check:
        _require(OUTPUT.is_file(), f"missing report: {OUTPUT}")
        _require(OUTPUT.read_text(encoding="utf-8") == rendered, "saved JSON differs from archived recount")
        print(f"PASS: {OUTPUT.relative_to(ROOT)} matches verified archives and fixed plan")
    else:
        OUTPUT.write_text(rendered, encoding="utf-8")
        print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

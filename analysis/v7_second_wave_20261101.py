"""Read-only, source-bound recount of the excluded v7 second one-shot wave.

The model is never called. ``--check`` compares a fresh replay of the saved
receipts and decision records with the committed machine-readable report.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from analysis import fresh_matched_verdict_pilot_20261101 as first
from experiments.main_collector import _canonical, _response_action


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "experiments/runs/v7_second_wave_20261101"
PLAN = ROOT / "docs/EXCLUDED_V7_SECOND_WAVE_20261101_PLAN.md"
OUTPUT = ROOT / "analysis/v7_second_wave_20261101.json"
PLAN_SHA256 = "150544bb1183bdfb01247cd155a0ad1a60eee8db0d4db4678fc3c0968a11c0ac"
SLOTS = (
    ("signature_algorithm", 314),
    ("deserialization_allowlist", 315),
    ("key_rotation", 316),
    ("kdf_salt", 317),
)
ARMS = first.ARMS


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _attempt_modes(pair_dir: Path, arm: str) -> list[str]:
    """Recover each submitted finite mode from the archived model response."""
    receipt = first._read_json(pair_dir / f"{arm.lower()}.receipt.json")
    modes = []
    for call in receipt["calls"]:
        decision = first._read_json(pair_dir / call["decision_path"])
        if decision["action"] != "ATTEMPT":
            continue
        response_path = pair_dir / call["response_path"]
        _require(response_path.is_file() and not response_path.is_symlink(),
                 f"missing or linked response: {response_path}")
        action, payload = _response_action(response_path.read_bytes())
        candidate = payload.get("candidate") if isinstance(payload, dict) else None
        _require(action == "attempt" and isinstance(candidate, dict)
                 and isinstance(candidate.get("mode"), str),
                 f"malformed archived attempt: {response_path}")
        _require(first._sha256(_canonical(candidate)) == decision["candidate_sha256"],
                 f"candidate mode differs from archived decision: {response_path}")
        modes.append(candidate["mode"])
    _require(len(modes) == receipt["submission_count"], "mode count differs from receipt")
    return modes


def _precursor(precursor_dir: Path, family: str) -> dict[str, Any]:
    result = first._precursor(precursor_dir, family, fresh=True)
    snapshot = first._read_json(precursor_dir / "plan_snapshot.json")
    config = snapshot["inference_config"]
    for field, expected in (
        ("temperature", 0.0), ("max_steps", 6),
        ("episode_timeout_seconds", 900), ("request_timeout_seconds", 180),
    ):
        _require(config.get(field) == expected, f"{family}: unexpected {field}")
    receipt = first._read_json(precursor_dir / "integrated_receipt.json")
    _require(receipt.get("error_type") is None and receipt.get("invalidation_reason") is None,
             f"{family}: precursor has technical failure or invalidation")
    starter = first._read_json(precursor_dir / "starter_evaluation.json")
    starter_result = starter["result"]
    result["starter"] = {
        "candidate_sha256": starter["candidate_sha256"],
        "raw_test_result": starter_result["raw_test_result"],
        "strong_test_result": starter_result["strong_test_result"],
        "finite_oracle_result": starter_result["security_oracle_result"],
    }
    result["terminal_raw_test_result"] = verified_raw = receipt[
        "terminal_active_candidate_raw_test_result"]
    if result["first_secure_submission_decision"] is None:
        _require(receipt["terminal_active_candidate_sha256"] == starter["candidate_sha256"]
                 and verified_raw == starter_result["raw_test_result"]
                 and result["terminal_oracle_result"] == starter_result["security_oracle_result"],
                 f"{family}: no-onset terminal state is not the verified starter")
    return result


def _pair(pair_dir: Path, precursor_dir: Path, family: str, seed: int) -> dict[str, Any]:
    result = first._pair(pair_dir, precursor_dir, seed)
    pair_open = first._read_json(pair_dir / "pair_open.json")
    for suffix, field in (("task", "c5_task_path"), ("proof", "c5_proof_path")):
        expected = f"benchmark/tasks/v7_batch_c/fc7-{family}-c5.{suffix}.json"
        _require(pair_open.get(field) == expected, f"{family}: {field} differs from plan")
    for arm in ARMS:
        result["arms"][arm]["attempt_modes"] = _attempt_modes(pair_dir, arm)
        result["arms"][arm]["raw_pass_strong_fail_attempts"] = sum(
            attempt["raw_test_result"] == "PASS"
            and attempt["strong_test_result"] == "FAIL"
            and attempt["security_oracle_result"] == "INSECURE"
            for attempt in result["arms"][arm]["attempts"]
        )
    result["same_post_onset_candidate_sequence"] = (
        [attempt["candidate_sha256"] for attempt in result["arms"][ARMS[0]]["attempts"]]
        == [attempt["candidate_sha256"] for attempt in result["arms"][ARMS[1]]["attempts"]]
    )
    return result


def build_report() -> dict[str, Any]:
    _require(first._sha256(PLAN.read_bytes()) == PLAN_SHA256, "fixed second-wave plan changed")
    _require(ARCHIVE.is_dir() and not ARCHIVE.is_symlink(), "second-wave archive missing")
    _require({p.name for p in ARCHIVE.iterdir()} == {family for family, _ in SLOTS},
             "second-wave archive family set differs from fixed plan")
    slots = []
    for family, seed in SLOTS:
        precursor_dir = ARCHIVE / family / "precursor"
        pair_dir = ARCHIVE / family / "pair"
        precursor = _precursor(precursor_dir, family)
        onset = precursor["first_secure_submission_decision"]
        if onset is None:
            _require(not pair_dir.exists(), f"{family}: pair was run without a secure onset")
            pair = None
            pair_status = "NOT_RUN_NO_ONSET"
        else:
            _require(type(onset) is int and onset >= 1, f"{family}: invalid onset")
            _require(pair_dir.is_dir(), f"{family}: scheduled pair missing")
            pair = _pair(pair_dir, precursor_dir, family, seed)
            pair_status = "COMPLETED_EXCLUDED_C5_PAIR"
        slots.append({"family": family, "precursor": precursor,
                      "pair_status": pair_status, "pair": pair})
    pairs = [slot["pair"] for slot in slots if slot["pair"] is not None]
    arms = {
        arm: {
            "terminal_finite_regressions": sum(p["arms"][arm]["terminal_finite_property_regression"] == 1 for p in pairs),
            "indeterminate_endpoints": sum(p["arms"][arm]["terminal_finite_property_regression"] is None for p in pairs),
            "early_voluntary_stops": sum(p["arms"][arm]["early_voluntary_stop"] is True for p in pairs),
            "post_onset_submissions": sum(p["arms"][arm]["submission_count"] for p in pairs),
            "raw_pass_strong_fail_attempts": sum(p["arms"][arm]["raw_pass_strong_fail_attempts"] for p in pairs),
            "technical_failures": sum(p["arms"][arm]["error_type"] is not None for p in pairs),
            "invalid_actions": sum(p["arms"][arm]["invalid_action_count"] for p in pairs),
        }
        for arm in ARMS
    }
    first_report = first.build_report()
    first_summary = first_report["fresh_schedule"]
    return {
        "schema_version": "excluded-v7-second-wave-20261101-1",
        "eligible_for_main_analysis": False,
        "scope": "prescheduled second one-shot engineering wave; descriptive only",
        "plan_path": _relative(PLAN), "plan_sha256": PLAN_SHA256,
        "archive_path": _relative(ARCHIVE),
        "archive_fingerprint": first._archive_fingerprint(ARCHIVE),
        "second_wave": {
            "scheduled_precursors": len(SLOTS),
            "verified_precursors": len(slots),
            "secure_onsets": len(pairs),
            "verified_pairs": len(pairs),
            "no_onset_families": [s["family"] for s in slots if s["pair"] is None],
            "arm_descriptives": arms,
            "slots": slots,
        },
        "sequential_wave_context_not_pooled": [
            {
                "wave": "first, planned after earlier selected CSRF case",
                "scheduled_precursors": first_summary["scheduled_precursors"],
                "verified_pairs": first_summary["verified_pairs"],
                "terminal_finite_regressions_by_arm": {
                    arm: first_summary["arm_descriptives_across_three_pairs"][arm]["terminal_finite_regressions"]
                    for arm in ARMS
                },
            },
            {
                "wave": "second, planned after observing first-wave outcomes",
                "scheduled_precursors": len(SLOTS),
                "verified_pairs": len(pairs),
                "terminal_finite_regressions_by_arm": {
                    arm: arms[arm]["terminal_finite_regressions"] for arm in ARMS
                },
            },
        ],
        "inference_boundary": (
            "Both waves are excluded and sequentially planned; no pooled inferential "
            "estimate, p-value, population confidence interval, or main-study episode. "
            "SECURE is bounded finite-reference agreement, not general security."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare with saved JSON without writing")
    args = parser.parse_args()
    rendered = json.dumps(build_report(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.check:
        _require(OUTPUT.is_file(), f"saved report missing: {OUTPUT}")
        _require(OUTPUT.read_text(encoding="utf-8") == rendered,
                 "saved second-wave JSON differs from verified archive recount")
        print(f"PASS: {OUTPUT.relative_to(ROOT)} matches both verified wave archives")
    else:
        OUTPUT.write_text(rendered, encoding="utf-8")
        print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

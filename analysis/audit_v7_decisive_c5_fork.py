"""Audit the one excluded v7 agent-onset PASS/false-FAIL continuation pair."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from analysis.audit_c5_remaining_onsets import _verify_pair
from analysis.audit_v7_decisive_excluded_pilot import audit as audit_precursor


ROOT = Path(__file__).resolve().parents[1]
PAIR = ROOT / "experiments/runs/v7_decisive_c5_fork_20261005_v1"
OUTPUT = ROOT / "analysis/v7_decisive_c5_fork_audit_20261005.json"
VERSION = "excluded-v7-decisive-c5-fork-audit-1.0.0"
if not __debug__:
    raise RuntimeError("fork audit requires Python assertions")


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _sha(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing artifact: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(pair: Path = PAIR) -> dict[str, Any]:
    precursor = audit_precursor()
    if precursor["valid_slots"] != 30:
        raise ValueError("the predecessor pilot is incomplete")
    pair = Path(pair).resolve()
    preflight = _read(pair / "preflight.json")
    inputs = preflight["input_artifacts"]
    manifest_path = Path(inputs["pilot_manifest"]["path"])
    if (preflight["family"] != "environment_injection"
            or preflight["precursor_condition"] != "C1"
            or manifest_path.parent.name != "slot-000022"
            or preflight["eligible_for_main_analysis"] is not False):
        raise ValueError("fork does not use the sole planned C1 secure onset")
    row = {
        "slot_id": manifest_path.parent.name,
        "family": preflight["family"],
        "precursor_condition": preflight["precursor_condition"],
        "pilot_manifest": str(manifest_path),
        "pilot_manifest_sha256": inputs["pilot_manifest"]["sha256"],
        "c1": {"task": inputs["c1_task"]["path"],
               "proof": inputs["c1_proof"]["path"]},
        "c5": {"task": inputs["c5_task"]["path"],
               "proof": inputs["c5_proof"]["path"]},
    }
    verified = _verify_pair(pair, row)
    if verified["pair_invalidated"]:
        status = "INVALIDATED_EXCLUDED"
    else:
        status = "VALID_EXCLUDED_DESCRIPTIVE_ONLY"
    return {
        "analysis_version": VERSION,
        "status": status,
        "eligible_for_main_analysis": False,
        "precursor_schedule_sha256": precursor["schedule_sha256"],
        "precursor_run_receipt_sha256": precursor["run_receipt_sha256"],
        "preflight_sha256": _sha(pair / "preflight.json"),
        "run_receipt_sha256": _sha(pair / "run.receipt.json"),
        "pair": verified,
        "inference": None,
        "interpretation": (
            "This is one post-outcome-selected agent-generated secure onset "
            "from two authored finite families. Branch requests differ only "
            "in public verdict and feedback after the same candidate; one "
            "pair cannot estimate a population effect or validate an "
            "unrestricted security-repair benchmark."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = audit()
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != payload:
            raise SystemExit("saved v7 fork audit differs")
        print(json.dumps({"status": result["status"], "arms": result["pair"]["arms"]},
                         sort_keys=True))
    else:
        args.output.write_text(payload, encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

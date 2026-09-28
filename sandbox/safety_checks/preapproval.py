"""Run the complete suite against the fixed candidate lock, without approving it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from sandbox.safety_checks.checks import run_complete_safety_suite, write_latest_report


CANDIDATE_LOCK = Path(__file__).resolve().parents[1] / "images" / "candidate_images.json"
CANDIDATE_REPORT = Path(__file__).resolve().parent / "candidate_result.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preapproval safety tests for the fixed local candidate image.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_complete_safety_suite(image_lock_path=CANDIDATE_LOCK)
    report["approval_scope"] = "CANDIDATE_ONLY_NOT_APPROVED"
    report["experiment_permitted"] = False
    write_latest_report(report, path=CANDIDATE_REPORT)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Candidate preapproval {'PASS' if report['overall_passed'] else 'FAIL-CLOSED'}: {CANDIDATE_REPORT}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

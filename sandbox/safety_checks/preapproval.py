"""Run the complete suite against the fixed candidate lock, without approving it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from sandbox.safety_checks.checks import (
    CANDIDATE_LOCK_PATH,
    CANDIDATE_V2_LOCK_PATH,
    run_complete_safety_suite,
    write_latest_report,
)


CANDIDATE_REPORT = Path(__file__).resolve().parent / "candidate_result.json"
CANDIDATE_V2_REPORT = Path(__file__).resolve().parent / "candidate_result_v2.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preapproval safety tests for the fixed local candidate image.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--candidate-v2", action="store_true", help="test the separately versioned v2 candidate lock")
    args = parser.parse_args(argv)
    lock_path = CANDIDATE_V2_LOCK_PATH if args.candidate_v2 else CANDIDATE_LOCK_PATH
    report_path = CANDIDATE_V2_REPORT if args.candidate_v2 else CANDIDATE_REPORT
    report = run_complete_safety_suite(image_lock_path=lock_path)
    report["approval_scope"] = "CANDIDATE_ONLY_NOT_APPROVED"
    report["experiment_permitted"] = False
    write_latest_report(report, path=report_path)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Candidate preapproval {'PASS' if report['overall_passed'] else 'FAIL-CLOSED'}: {report_path}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

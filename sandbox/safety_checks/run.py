"""CLI entry point for the fail-closed local sandbox safety gate."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from sandbox.safety_checks.checks import run_complete_safety_suite, write_latest_report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local-only Docker sandbox safety checks.")
    parser.add_argument("--json", action="store_true", help="Print the complete report as JSON.")
    args = parser.parse_args(argv)
    report = run_complete_safety_suite()
    path = write_latest_report(report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "PASS" if report["overall_passed"] else "FAIL-CLOSED"
        print(f"{status}: {report['suite']}; experiment_permitted={report['experiment_permitted']}")
        print(f"Safety report: {path}")
        for item in report["checks"]:
            print(f"  {item['check_id']}: {item['status']}")
        for blocker in report["blocking_reasons"]:
            print(f"  blocker: {blocker}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

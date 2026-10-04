"""Small v1 primary-outcome view; withholds rates before a released main run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from analysis.v1_pipeline import V1ValidationError, analyze_manifests


def summarize_primary(analysis_result: Mapping[str, Any]) -> dict[str, Any]:
    if analysis_result.get("status") != "DESCRIPTIVE_ONLY":
        return {"status": "NO_ELIGIBLE_DATA", "primary_outcomes": None,
                "stopping_survival": None, "evaluator_validity": None}
    return {
        "status": "DESCRIPTIVE_ONLY",
        "eligible_main_episodes": analysis_result["eligible_main_episodes"],
        "primary_outcomes": analysis_result["primary_outcomes"],
        "stopping_survival": analysis_result["stopping_survival"],
        "evaluator_validity": analysis_result["evaluator_validity"],
        "warning": "Rates are finite-domain descriptive outcomes; no confirmatory inference is run.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-dir", type=Path, default=Path("experiments/v1/manifests"))
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--study-lock", type=Path)
    parser.add_argument("--main-run-receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        result = analyze_manifests(
            sorted(args.manifest_dir.glob("*.manifest.json")) if args.manifest_dir.is_dir() else [],
            source_root=args.source_root, study_lock_path=args.study_lock,
            main_run_receipt_path=args.main_run_receipt,
        )
    except V1ValidationError as exc:
        print(json.dumps({"status": "INVALID_INPUT", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(summarize_primary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

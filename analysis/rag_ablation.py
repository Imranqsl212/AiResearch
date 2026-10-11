"""Descriptive R0/R1/R2 summaries from released, eligible v1 main episodes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from analysis.v1_pipeline import V1ValidationError, analyze_manifests


def summarize_rag(analysis_result: Mapping[str, Any]) -> dict[str, Any]:
    if analysis_result.get("status") != "DESCRIPTIVE_ONLY":
        return {"status": "NO_ELIGIBLE_DATA", "mode_summaries": [],
                "matched_family_contrasts": [], "causal_effect": None}
    rows = list(analysis_result["episodes"])
    summaries = []
    for mode in ("R0", "R1", "R2"):
        group = [row for row in rows if row["retrieval_mode"] == mode]
        repairable = [row for row in group if row["ground_truth_state"] == "REPAIRABLE"]
        unrepairable = [row for row in group if row["ground_truth_state"] == "UNREPAIRABLE"]
        u_assessable = [row for row in unrepairable if row["operational_appropriate_stopping"] is not None]
        summaries.append({
            "mode": mode, "episodes": len(group), "families": len({row["family"] for row in group}),
            "repairable_n": len(repairable),
            "secure_recovery_n": sum(row["oracle_secure_recovery"] is True for row in repairable),
            "secure_recovery_rate": (sum(row["oracle_secure_recovery"] is True for row in repairable) / len(repairable)) if repairable else None,
            "unrepairable_stopping_assessable_n": len(u_assessable),
            "operational_stop_after_evidence_n": sum(row["operational_appropriate_stopping"] is True for row in u_assessable),
            "operational_stop_after_evidence_rate": (sum(row["operational_appropriate_stopping"] is True for row in u_assessable) / len(u_assessable)) if u_assessable else None,
            "oracle_gate_discordance_delivery_n": sum(
                row["oracle_gate_discordance_delivered"] for row in group),
        })
    repairable_rows = [row for row in rows if row["ground_truth_state"] == "REPAIRABLE"]
    contrasts = []
    for left, right in (("R1", "R0"), ("R2", "R0"), ("R2", "R1")):
        paired = []
        for family in sorted({row["family"] for row in repairable_rows}):
            within_family = []
            keys = sorted({(row["condition"], row["model"]) for row in repairable_rows
                           if row["family"] == family})
            for condition, model in keys:
                left_rows = [row for row in repairable_rows if row["family"] == family
                             and row["condition"] == condition and row["model"] == model
                             and row["retrieval_mode"] == left]
                right_rows = [row for row in repairable_rows if row["family"] == family
                              and row["condition"] == condition and row["model"] == model
                              and row["retrieval_mode"] == right]
                if left_rows and right_rows:
                    left_rate = sum(row["oracle_secure_recovery"] is True for row in left_rows) / len(left_rows)
                    right_rate = sum(row["oracle_secure_recovery"] is True for row in right_rows) / len(right_rows)
                    within_family.append(left_rate - right_rate)
            if within_family:
                paired.append({"family": family,
                               "difference": sum(within_family) / len(within_family),
                               "matched_condition_model_cells": len(within_family)})
        contrasts.append({"contrast": f"{left} minus {right}", "matched_families": len(paired),
                          "mean_family_difference": (sum(row["difference"] for row in paired) / len(paired)) if paired else None,
                          "family_differences": paired})
    return {"status": "DESCRIPTIVE_ONLY", "mode_summaries": summaries,
            "matched_family_contrasts": contrasts,
            "causal_effect": None,
            "warning": "Retrieval exposure is checked, but these rates alone do not identify a causal RAG effect."}


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
    print(json.dumps(summarize_rag(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Pilot-informed *synthetic* C5 onset sensitivity; never an empirical power fit.

Reads the sealed excluded 40-slot feasibility receipt only to anchor scenario
bounds. It does not inspect outcomes to tune treatment effects or pair-loss rates.
The frozen v1 simulation implementation and grid are imported, not modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from analysis import v1_power_sensitivity as power


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "experiments/runs/full_catalog_live_feasibility_20261005/run.receipt.json"
JSON_OUT = ROOT / "analysis/c5_pilot_informed_sensitivity_20261005.json"
MD_OUT = ROOT / "analysis/c5_pilot_informed_sensitivity_20261005.md"
EXPECTED_RECEIPT_SHA256 = "36f91eda1ffeeb07f9c7f705ca128158f913d39e674e750db359f6adbaed556c"
VERSION = "c5-pilot-informed-synthetic-sensitivity-1.0.0"
REPLICATES = 2000
SEED = 20261005
REACH_VALUES = (0.35, 0.50, 0.60)
PAIR_LOSS_VALUES = (0.05, 0.25)
EFFECT_VALUES = (0.20, 0.0)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_pilot() -> dict[str, Any]:
    data = RECEIPT.read_bytes()
    if _sha(data) != EXPECTED_RECEIPT_SHA256:
        raise ValueError("excluded pilot receipt changed; do not silently relabel scenarios")
    receipt = json.loads(data)
    expected = {
        "schema_version": "excluded-full-catalog-live-feasibility-1.0.0",
        "phase": "pilot",
        "eligible_for_main_analysis": False,
        "planned_slots": 40,
        "valid_slots": 30,
        "invalidated_slots": 10,
        "secure_onset_slots": 14,
        "secure_onset_families": 10,
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("excluded pilot receipt counts/status differ from frozen planning inputs")
    if len(receipt.get("results", [])) != expected["planned_slots"]:
        raise ValueError("excluded pilot receipt result count differs from assigned slots")
    return {"relative_path": str(RECEIPT.relative_to(ROOT)), "sha256": _sha(data),
            **expected, "observed_assigned_slot_onset_lower_bound": 14 / 40,
            "extreme_upper_bound_if_all_invalidations_hid_onsets": (14 + 10) / 40,
            "precursor_invalidation_fraction": 10 / 40}


def calculate() -> dict[str, Any]:
    pilot = _read_pilot()
    rows: list[dict[str, Any]] = []
    for reach in REACH_VALUES:
        for pair_loss in PAIR_LOSS_VALUES:
            for effect in EFFECT_VALUES:
                scenario = power.Scenario(
                    families=20,
                    precursors_per_family=10,
                    max_onsets_per_family=5,
                    onset_reach_probability=reach,
                    technical_pair_loss=pair_loss,
                    false_fail_stop_reduction=effect,
                )
                rows.append(power.simulate(scenario, replicates=REPLICATES, seed=SEED))
    return {
        "version": VERSION,
        "status": "PILOT_INFORMED_SYNTHETIC_PLANNING_ONLY_NOT_READY",
        "pilot": pilot,
        "protocol": "docs/preregistration_v1_20261005.md",
        "simulation_module": "analysis/v1_power_sensitivity.py",
        "simulation_module_sha256": _sha(Path(power.__file__).read_bytes()),
        "generator_sha256": _sha(Path(__file__).read_bytes()),
        "seed": SEED,
        "replicates_per_scenario": REPLICATES,
        "inferential_unit": "family; equal-family paired onset differences",
        "test": "two-sided equal-family Student-t at alpha=0.05; at least 15 contributing families",
        "scenario_interpretation": {
            "reach_0_35": "14/40 observed secure onsets across all assigned precursor slots; lower bound only because 10 slots were technically invalidated",
            "reach_0_50": "intermediate hypothetical reach probability",
            "reach_0_60": "extreme upper bound (14+10)/40 only if every invalidated precursor would have reached a secure onset",
            "loss_0_05": "original hypothetical pair-level loss assumption from v1 simulation defaults",
            "loss_0_25": "separate pair-loss stress; 10/40 precursor invalidations are NOT an estimate of post-onset branch-pair loss",
            "effect_0_20": "hypothetical 20-percentage-point reduction in early voluntary stop under false FAIL",
            "effect_0_00": "synthetic null/type-I-error check under the same other assumptions",
            "calibration": "pilot does not estimate treatment effects, post-onset pair loss, family heterogeneity, or pair dependence; none of these rows is empirically calibrated power",
        },
        "scenarios": rows,
    }


def _render_md(report: dict[str, Any]) -> str:
    pilot = report["pilot"]
    by_key = {(row["scenario"]["onset_reach_probability"],
               row["scenario"]["technical_pair_loss"],
               row["scenario"]["false_fail_stop_reduction"]): row
              for row in report["scenarios"]}
    lines = [
        "# C5 pilot-informed synthetic sensitivity appendix — 5 October 2026",
        "",
        "**Status: PILOT-INFORMED SYNTHETIC PLANNING ONLY; NOT READY.** This appendix",
        "uses the completed *excluded* feasibility pilot to bound hypothetical onset",
        "reach scenarios. It does not estimate a treatment effect or calibrated power.",
        "The frozen earlier grid in `v1_power_sensitivity_20261005.json` is unchanged.",
        "",
        "## Pilot anchor and scenario limits",
        "",
        f"Receipt: `{pilot['relative_path']}` (SHA-256 `{pilot['sha256']}`). It records",
        "40 assigned precursor slots, 30 valid slots, 10 technical invalidations,",
        "and 14 observed agent-generated oracle-secure onsets in 10 families.",
        "The observed assigned-slot yield **14/40 = 0.35** is a lower bound if an",
        "invalidated precursor could have hidden an onset. **0.60 = (14+10)/40**",
        "is an extreme upper bound requiring all ten invalidated precursors to",
        "have reached onset; 0.50 is an intermediate scenario. These are planning",
        "bounds, not estimates for a future 20-family study.",
        "",
        "The pilot's **10/40 = 25% precursor invalidation** is not an estimate of",
        "post-onset branch-pair loss. We show a separate 25% *hypothetical pair-loss",
        "stress*, alongside the original 5% hypothetical loss. Neither is calibrated",
        "to observed C5 fork failures. The 20-percentage-point stop effect is likewise",
        "hypothetical; the pilot contains no randomized C5 paired outcome.",
        "",
        "## Simulation",
        "",
        "The unchanged `analysis.v1_power_sensitivity.simulate` draws 2,000 datasets",
        "per scenario with seed `20261005`: 20 independent families, 10 precursor",
        "slots/family, at most five onsets/family, a truthful-PASS early-stop",
        "probability of 0.65, default family shifts and branch dependence, and the",
        "predeclared two-sided equal-family paired-difference t rule (α = 0.05).",
        "At least 15 families must contribute a valid pair. A rejection probability",
        "counts nonestimable datasets as non-rejections. The null rows are a simulated",
        "type-I-error check, not evidence that the model is calibrated to real data.",
        "",
        "| Reach | Pair loss | P(reject), hypothetical −0.20 stop effect | Mean contributing families | Mean valid pairs | Nonestimable / 2,000 | Null P(reject) |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for reach in REACH_VALUES:
        for pair_loss in PAIR_LOSS_VALUES:
            effect = by_key[(reach, pair_loss, 0.20)]
            null = by_key[(reach, pair_loss, 0.0)]
            lines.append(
                f"| {reach:.2f} | {pair_loss:.2f} | "
                f"{effect['unconditional_rejection_probability']:.3f} | "
                f"{effect['mean_contributing_families']:.2f} | "
                f"{effect['mean_valid_onset_pairs']:.2f} | "
                f"{effect['nonestimable_replicates']} | "
                f"{null['unconditional_rejection_probability']:.3f} |"
            )
    lines.extend([
        "",
        "The JSON contains each scenario's full assumptions, rejection count,",
        "Monte Carlo Wilson interval, mean family count, and mean valid-pair count.",
        "Differences across rows include Monte Carlo noise because the existing",
        "simulator derives a separate random stream for each scenario.",
        "",
        "**Interpretation:** These rows quantify how a *specified synthetic model*",
        "behaves if onset reach and pair loss take the listed values. They cannot",
        "clear the preregistration's C5 implementation or design gates, substitute",
        "for a matched PASS/false-FAIL pilot across families, or justify an 80% power",
        "claim from the 40-slot feasibility pilot.",
        "",
        "Reproduce from the repository root with the sealed Git-ignored pilot",
        "receipt present: `python3 -B -m analysis.c5_pilot_informed_sensitivity_20261005`",
        "using new output paths; the script refuses to overwrite either output file.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path, default=JSON_OUT)
    parser.add_argument("--md-output", type=Path, default=MD_OUT)
    args = parser.parse_args()
    if args.json_output.exists() or args.md_output.exists():
        parser.error("output already exists; preserve provenance and use new paths")
    result = calculate()
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.md_output.parent.mkdir(parents=True, exist_ok=True)
    with args.json_output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    with args.md_output.open("x", encoding="utf-8") as handle:
        handle.write(_render_md(result))


if __name__ == "__main__":
    main()

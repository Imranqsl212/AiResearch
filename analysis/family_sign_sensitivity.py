"""Exact, illustrative family-sign sensitivity for a future matched study.

This deliberately uses no agent data. It is a simple sensitivity calculation,
not the preregistered GEE decision rule or a main-study power calculation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "analysis" / "family_sign_sensitivity_20261004.json"
MARKDOWN_PATH = ROOT / "docs" / "FAMILY_SIGN_SENSITIVITY_20261004.md"
FAMILY_COUNTS = (15, 20, 30, 40)
CONCORDANCE_PROBABILITIES = (Fraction(3, 5), Fraction(7, 10), Fraction(3, 4), Fraction(4, 5))
FAMILYWISE_ALPHA = Fraction(1, 20)
ILLUSTRATIVE_CONTRASTS = 3


def exact_null_tail(n_families: int, favorable_families: int) -> Fraction:
    """One-sided null tail for positive signs after conditioning on non-ties."""

    if not 0 <= favorable_families <= n_families:
        raise ValueError("favorable_families must be within [0, n_families]")
    return Fraction(sum(comb(n_families, j) for j in range(favorable_families, n_families + 1)),
                    2**n_families)


def critical_favorable_count(n_families: int, alpha: Fraction) -> int | None:
    """Smallest positive-sign count whose exact one-sided null tail is <= alpha."""

    if n_families < 1 or not Fraction(0) < alpha < Fraction(1):
        raise ValueError("n_families must be positive and alpha must lie in (0, 1)")
    return next((k for k in range(n_families + 1)
                 if exact_null_tail(n_families, k) <= alpha), None)


def exact_rejection_probability(n_families: int, favorable_families: int,
                                concordance_probability: Fraction) -> Fraction:
    """Probability of meeting a fixed cutoff under iid family sign probability q."""

    if not 0 <= favorable_families <= n_families:
        raise ValueError("favorable_families must be within [0, n_families]")
    if not Fraction(0) <= concordance_probability <= Fraction(1):
        raise ValueError("concordance_probability must lie in [0, 1]")
    q = concordance_probability
    return sum((Fraction(comb(n_families, j)) * q**j * (1 - q)**(n_families - j)
                for j in range(favorable_families, n_families + 1)), Fraction(0))


def _decimal(value: Fraction) -> float:
    # The exact fraction is retained separately; significant digits preserve tiny
    # illustrative p-values that fixed decimal-place rounding would erase.
    return float(format(float(value), ".12g"))


def build_report() -> dict[str, Any]:
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    steps = []
    for rank in range(1, ILLUSTRATIVE_CONTRASTS + 1):
        alpha = FAMILYWISE_ALPHA / (ILLUSTRATIVE_CONTRASTS - rank + 1)
        cutoff = critical_favorable_count(20, alpha)
        assert cutoff is not None
        steps.append({
            "rank": rank,
            "holm_alpha_fraction": str(alpha),
            "holm_alpha_decimal": _decimal(alpha),
            "minimum_favorable_families": cutoff,
            "attained_null_p_fraction": str(exact_null_tail(20, cutoff)),
            "attained_null_p_decimal": _decimal(exact_null_tail(20, cutoff)),
            "one_below_attained_null_p_fraction": str(exact_null_tail(20, cutoff - 1)),
            "one_below_attained_null_p_decimal": _decimal(exact_null_tail(20, cutoff - 1)),
        })
    scenarios = []
    strict_alpha = FAMILYWISE_ALPHA / ILLUSTRATIVE_CONTRASTS
    for n in FAMILY_COUNTS:
        cutoff = critical_favorable_count(n, strict_alpha)
        assert cutoff is not None
        for q in CONCORDANCE_PROBABILITIES:
            probability = exact_rejection_probability(n, cutoff, q)
            scenarios.append({
                "non_tied_families": n,
                "minimum_favorable_families": cutoff,
                "concordance_probability_fraction": str(q),
                "concordance_probability_decimal": _decimal(q),
                "strict_first_step_alpha_fraction": str(strict_alpha),
                "attained_null_p_fraction": str(exact_null_tail(n, cutoff)),
                "attained_null_p_decimal": _decimal(exact_null_tail(n, cutoff)),
                "rejection_probability_fraction": str(probability),
                "rejection_probability_decimal": _decimal(probability),
            })
    exact_family_p = exact_null_tail(20, 16)
    naive_repeat_p = exact_null_tail(100, 80)
    seven_contrast_alpha = FAMILYWISE_ALPHA / 7
    seven_contrast_cutoff = critical_favorable_count(20, seven_contrast_alpha)
    return {
        "schema_version": "1.0",
        "kind": "illustrative_precollection_family_sign_sensitivity_not_agent_data",
        "source_sha256": source_hash,
        "main_ready": False,
        "pilot_data_used": False,
        "method": "one-sided exact sign-flip test on one matched, nonzero contrast per independent family",
        "assumptions": {
            "familywise_alpha_fraction": str(FAMILYWISE_ALPHA),
            "illustrative_secondary_contrasts": ILLUSTRATIVE_CONTRASTS,
            "independent_family_signs": True,
            "null_positive_sign_probability_fraction": "1/2",
            "alternative_positive_sign_probability_is_common_across_families": True,
            "condition_on_non_ties": True,
            "effect_magnitudes_used": False,
            "missingness_modelled": False,
            "actual_preregistered_gee_modelled": False,
        },
        "minimum_master_design": {
            "independent_families": 20,
            "core_conditions": 4,
            "fresh_repeats_per_condition": 5,
            "core_episode_count": 400,
            "independent_signs_per_matched_contrast_before_ties": 20,
        },
        "holm_steps_at_20_non_tied_families": steps,
        "seven_contrast_first_step_at_20_non_tied_families": {
            "alpha_fraction": str(seven_contrast_alpha),
            "minimum_favorable_families": seven_contrast_cutoff,
            "attained_null_p_fraction": str(exact_null_tail(20, seven_contrast_cutoff)),
        },
        "strict_first_step_scenarios": scenarios,
        "pseudo_replication_illustration": {
            "actual_family_concordance": "16/20",
            "correct_family_p_fraction": str(exact_family_p),
            "correct_family_p_decimal": _decimal(exact_family_p),
            "hypothetical_identical_five_repeat_signs": "80/100",
            "incorrect_independent_repeat_p_fraction": str(naive_repeat_p),
            "incorrect_independent_repeat_p_decimal": _decimal(naive_repeat_p),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    steps = report["holm_steps_at_20_non_tied_families"]
    scenarios = report["strict_first_step_scenarios"]
    scenario_lookup = {(row["non_tied_families"], row["concordance_probability_fraction"]): row
                       for row in scenarios}
    first = steps[0]
    pseudo = report["pseudo_replication_illustration"]
    q_headers = " | ".join(f"q = {float(q):.2f}" for q in CONCORDANCE_PROBABILITIES)
    lines = [
        "# Exact family-sign sensitivity for the minimum study design",
        "",
        "**Status: ILLUSTRATIVE PLANNING ONLY.** This calculation contains no pilot or main agent outcomes, "
        "does not implement the preregistered GEE, and does not clear a power or READY gate. "
        "The [machine-readable calculation](../analysis/family_sign_sensitivity_20261004.json) "
        "comes from [stdlib code](../analysis/family_sign_sensitivity.py).",
        "",
        "## Setup",
        "",
        "The master's minimum design has 20 independent task families, four core conditions, and "
        "five fresh runs per condition: 400 core episodes. For one matched directional contrast, "
        "average the repeated outcome within each arm and family, take the sign of the paired "
        "family difference, and count positive signs. This yields at most **20 independent signs**, "
        "after excluding zero differences. The examples below assume all stated families are non-tied. "
        "Illustrative contrasts could compare C2 with C1 on repair, C4 with C3 on stopping, "
        "and R1 with R0 within the same task stratum; RAG arms would require additional "
        "episodes beyond the 400 core episodes. No actual contrasts, endpoints, directions, "
        "or multiplicity family are frozen here.",
        "",
        "Under a sign-symmetric null with independent families, the one-sided exact sign-flip "
        "tail is `sum(comb(n,j), j=k..n) / 2**n`. Under a hypothetical common family concordance "
        "probability `q`, the chance of crossing a fixed cutoff is "
        "`sum(comb(n,j) * q**j * (1-q)**(n-j), j=k..n)`. Both are evaluated as exact "
        "rational numbers before decimal display. Effect magnitudes are deliberately ignored.",
        "",
        "## Multiplicity illustration at 20 non-tied families",
        "",
        "For an *illustrative* family of three one-sided secondary contrasts with familywise "
        "alpha 0.05, Holm's ordered thresholds and attainable sign cutoffs are:",
        "",
        "| Ordered p-value rank | Holm threshold | Minimum positive families | Attained null p (exact fraction, rounded decimal) |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for row in steps:
        lines.append(f"| {row['rank']} | {row['holm_alpha_fraction']} "
                     f"({row['holm_alpha_decimal']:.6f}) | {row['minimum_favorable_families']}/20 "
                     f"| {row['attained_null_p_fraction']} ≈ {row['attained_null_p_decimal']:.6f} |")
    lines += [
        "",
        f"At the first step, {first['minimum_favorable_families'] - 1}/20 gives "
        f"p = {first['one_below_attained_null_p_decimal']:.6f} and misses 0.05/3; "
        f"{first['minimum_favorable_families']}/20 gives "
        f"p = {first['attained_null_p_decimal']:.6f}. This strict first-step criterion "
        "is sufficient for a given contrast "
        "to be rejected by Holm regardless of the dependence between contrasts. Later ranks "
        "can use their larger thresholds only if earlier ranks pass. If seven contrasts are "
        "chosen instead, the first threshold is 0.05/7 and still needs 16/20 because "
        "the attainable p-values are discrete. The real multiplicity family must be frozen "
        "before main outcomes are inspected.",
        "",
        "## Exact sensitivity under hypothetical concordance",
        "",
        f"The table gives the chance that **one** contrast meets the conservative 0.05/{ILLUSTRATIVE_CONTRASTS} "
        "first-step cutoff. `q` is the probability that an independent non-tied family "
        "favors the predeclared direction; these values are planning scenarios, not pilot estimates.",
        "",
        f"| Non-tied families | Positive cutoff | {q_headers} |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for n in FAMILY_COUNTS:
        values = [scenario_lookup[(n, str(q))] for q in CONCORDANCE_PROBABILITIES]
        cutoff = values[0]["minimum_favorable_families"]
        probabilities = " | ".join(f"{row['rejection_probability_decimal']:.3f}" for row in values)
        lines.append(f"| {n} | {cutoff}/{n} | {probabilities} |")
    lines += [
        "",
        "The 15-family row represents five tied or otherwise unusable family contrasts "
        "out of a scheduled 20; it is not a missingness model. With q = 0.70 and 20 "
        f"non-tied families, this simple sign-only rule has rejection probability "
        f"{scenario_lookup[(20, str(Fraction(7, 10)))]['rejection_probability_decimal']:.3f} "
        "for one contrast. This is a different, less information-rich rule than the existing "
        "family-t planning proxy and cannot establish the actual GEE's power or the joint "
        "power of several hypotheses. The 30- and 40-family rows show how this specific "
        "sensitivity changes if independently reviewed families are added.",
        "",
        "## Why five repeats are not 100 families",
        "",
        "Repeats can make each family's arm averages more stable, reduce ties, and reveal "
        "within-family variation. They do not create new independent task families. For "
        "example, suppose 16 of 20 family contrasts are positive and each sign repeats "
        "identically five times. The correct one-sided family p is "
        f"**{pseudo['correct_family_p_decimal']:.6f}**. Treating "
        "the copied signs as 80 of 100 independent signs would report "
        f"**{pseudo['incorrect_independent_repeat_p_decimal']:.2e}**, severe "
        "pseudoreplication. The example is hypothetical, not an "
        "observed result.",
        "",
        "## Limits and use",
        "",
        "Independent, sign-symmetric families and a common q are strong assumptions. "
        "Ties, unequal family effects, outcome-dependent missingness, flawed security "
        "oracles, incomplete failure exposure, model drift, and cross-contrast dependence "
        "can change operating characteristics. A sign test also throws away effect "
        "magnitudes. These numbers motivate evaluating whether the minimum 20-family "
        "design is adequate, rather than declaring a required sample size. Freeze the "
        "real estimands, multiplicity family, GEE decision rule, and plausible data-generating "
        "scenarios; then simulate that exact rule before main collection. Additional repeats "
        "cannot substitute for additional independent families if that power gate fails.",
        "",
        "## Reproduce",
        "",
        "```sh",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_family_sign_sensitivity -v",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -m analysis.family_sign_sensitivity --check",
        "```",
        "",
        f"Source SHA-256: `{report['source_sha256']}`.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=JSON_PATH)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN_PATH)
    parser.add_argument("--check", action="store_true", help="compare saved artifacts without writing")
    args = parser.parse_args()
    report = build_report()
    json_bytes = (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    markdown_bytes = render_markdown(report).encode("utf-8")
    if args.check:
        if args.json.read_bytes() != json_bytes or args.markdown.read_bytes() != markdown_bytes:
            raise SystemExit("saved family-sign sensitivity artifacts differ from code")
    else:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_bytes(json_bytes)
        args.markdown.write_bytes(markdown_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

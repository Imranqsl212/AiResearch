"""Cluster-respecting descriptive estimates and preregistered fallback tests."""

from __future__ import annotations

import hashlib
import itertools
import math
import random
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from statistics import fmean
from typing import Any


def _seed(label: str) -> int:
    return int.from_bytes(hashlib.sha256(label.encode("utf-8")).digest()[:8], "big")


def _quantile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("quantile requires at least one value")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def cluster_bootstrap_mean(
    values: Sequence[float], *, replicates: int = 10_000, label: str = "cluster-bootstrap"
) -> dict[str, float | int | None]:
    """Percentile interval by resampling whole task-family summaries.

    `values` contains one aggregate per family, never a list of actions or an
    unclustered list of runs. The deterministic seed makes regenerated output
    byte-stable for a fixed input lock and analysis version.
    """

    if not values:
        return {"estimate": None, "ci_low": None, "ci_high": None, "n_families": 0}
    estimate = fmean(values)
    if len(values) == 1:
        return {
            "estimate": estimate,
            "ci_low": None,
            "ci_high": None,
            "n_families": 1,
        }
    rng = random.Random(_seed(label))
    samples = [
        fmean([values[rng.randrange(len(values))] for _ in range(len(values))])
        for _ in range(replicates)
    ]
    samples.sort()
    return {
        "estimate": estimate,
        "ci_low": _quantile(samples, 0.025),
        "ci_high": _quantile(samples, 0.975),
        "n_families": len(values),
    }


def _family_means(
    run_metrics: Sequence[Mapping[str, Any]], metric: str
) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in run_metrics:
        value = row.get(metric)
        family = row.get("task_family")
        condition = row.get("condition")
        if isinstance(value, (int, float)):
            # bool is intentionally accepted as 0/1; strings and missing values are not.
            if isinstance(family, str) and family and family != "UNRESOLVED_FAMILY" and isinstance(condition, str):
                grouped[condition][family].append(float(value))
    return {
        condition: {family: fmean(values) for family, values in by_family.items()}
        for condition, by_family in grouped.items()
    }


def condition_summaries(
    run_metrics: Sequence[Mapping[str, Any]],
    metrics: Iterable[str],
    *,
    replicates: int,
) -> list[dict[str, Any]]:
    """Summarize run-level metrics after first averaging nested runs per family."""

    output: list[dict[str, Any]] = []
    for metric in metrics:
        families = _family_means(run_metrics, metric)
        for condition in sorted(families):
            values = [families[condition][family] for family in sorted(families[condition])]
            result = cluster_bootstrap_mean(
                values, replicates=replicates, label=f"{metric}:{condition}"
            )
            n_runs = sum(
                row.get(metric) is not None
                and row.get("condition") == condition
                and row.get("task_family") != "UNRESOLVED_FAMILY"
                for row in run_metrics
            )
            output.append(
                {
                    "metric": metric,
                    "condition": condition,
                    "estimate": result["estimate"],
                    "ci_low": result["ci_low"],
                    "ci_high": result["ci_high"],
                    "n_families": result["n_families"],
                    "n_runs": n_runs,
                    "uncertainty_method": "95% task-family cluster bootstrap percentile interval",
                }
            )
    return output


def paired_cluster_comparison(
    run_metrics: Sequence[Mapping[str, Any]],
    *,
    metric: str,
    condition_a: str,
    condition_b: str,
    replicates: int,
    permutations: int = 10_000,
) -> dict[str, Any]:
    """Matched-family difference with a within-family label-swap p-value.

    This is the preregistered fallback for the RD/RW and RD/UD contrasts when
    a mixed model is unavailable or non-convergent. It is not used as an
    action-level test and refuses unresolved task-family labels.
    """

    means = _family_means(run_metrics, metric)
    a = means.get(condition_a, {})
    b = means.get(condition_b, {})
    families = sorted(set(a) & set(b))
    differences = [a[family] - b[family] for family in families]
    if not differences:
        return {
            "metric": metric,
            "condition_a": condition_a,
            "condition_b": condition_b,
            "effect_type": "paired task-family mean difference",
            "estimate": None,
            "ci_low": None,
            "ci_high": None,
            "p_value": None,
            "test": "NOT_ESTIMABLE",
            "n_paired_families": 0,
            "odds_ratio": None,
        }
    estimate = fmean(differences)
    interval = cluster_bootstrap_mean(
        differences,
        replicates=replicates,
        label=f"paired:{metric}:{condition_a}:{condition_b}",
    )
    p_value, test = _paired_label_swap_p_value(
        differences,
        permutations=permutations,
        label=f"permutation:{metric}:{condition_a}:{condition_b}",
    )
    odds_ratio = _odds_ratio(
        fmean([a[family] for family in families]), fmean([b[family] for family in families])
    )
    return {
        "metric": metric,
        "condition_a": condition_a,
        "condition_b": condition_b,
        "effect_type": "paired task-family mean difference",
        "estimate": estimate,
        "ci_low": interval["ci_low"],
        "ci_high": interval["ci_high"],
        "p_value": p_value,
        "test": test,
        "n_paired_families": len(differences),
        "odds_ratio": odds_ratio,
    }


def _paired_label_swap_p_value(
    differences: Sequence[float], *, permutations: int, label: str
) -> tuple[float, str]:
    observed = abs(fmean(differences))
    family_count = len(differences)
    if family_count <= 15:
        distribution = [
            abs(fmean([sign * value for sign, value in zip(signs, differences)]))
            for signs in itertools.product((-1.0, 1.0), repeat=family_count)
        ]
        p_value = sum(value >= observed - 1e-15 for value in distribution) / len(distribution)
        return p_value, "exact within-family label-swap permutation"
    rng = random.Random(_seed(label))
    exceedances = 0
    for _ in range(permutations):
        value = abs(
            fmean([(-1.0 if rng.randrange(2) else 1.0) * difference for difference in differences])
        )
        exceedances += value >= observed - 1e-15
    return (exceedances + 1) / (permutations + 1), "Monte Carlo within-family label-swap permutation"


def _odds_ratio(probability_a: float, probability_b: float) -> float | None:
    """Descriptive odds ratio from family-mean probabilities, without continuity hacks."""

    if not 0.0 < probability_a < 1.0 or not 0.0 < probability_b < 1.0:
        return None
    return (probability_a / (1.0 - probability_a)) / (probability_b / (1.0 - probability_b))


def holm_adjust(rows: Sequence[Mapping[str, Any]], *, planned_family_size: int | None = None) -> list[dict[str, Any]]:
    """Return Holm-adjusted p-values without changing the original row order."""

    adjusted = [dict(row) for row in rows]
    eligible = sorted(
        ((index, row["p_value"]) for index, row in enumerate(adjusted) if isinstance(row.get("p_value"), float)),
        key=lambda item: item[1],
    )
    total = max(len(eligible), planned_family_size or 0)
    running = 0.0
    for rank, (index, p_value) in enumerate(eligible):
        candidate = min(1.0, (total - rank) * p_value)
        running = max(running, candidate)
        adjusted[index]["holm_adjusted_p_value"] = running
    for row in adjusted:
        row.setdefault("holm_adjusted_p_value", None)
    return adjusted


def _h1_component_cells(
    run_metrics: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, list[float]]]:
    """Collect only failure-exposed, interpretable H1 run endpoints by family."""

    by_family: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in run_metrics:
        family = row.get("task_family")
        condition = row.get("condition")
        if not isinstance(family, str) or not family or family == "UNRESOLVED_FAMILY":
            continue
        if row.get("failure_exposed") is not True or row.get("analysis_eligible") is False:
            continue
        metric = (
            "recovered_after_meaningful_adaptation" if condition == "RD"
            else "operationally_justified_stop" if condition == "UD" else None
        )
        if metric is None:
            continue
        value = row.get(metric)
        if value is None:
            continue
        if not isinstance(value, bool):
            raise ValueError(f"H1 {metric} must be a boolean run endpoint")
        by_family[family][condition].append(float(value))
    return by_family


def calibration_pair_scores(run_metrics: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Compute preregistered CPS only for families with both diagnostic cells."""

    by_family = _h1_component_cells(run_metrics)
    output: list[dict[str, Any]] = []
    for family in sorted(by_family):
        recovery = by_family[family].get("RD", [])
        justified = by_family[family].get("UD", [])
        if not recovery or not justified:
            continue
        r_value = fmean(recovery)
        u_value = fmean(justified)
        cps = 2 * r_value * u_value / (r_value + u_value) if r_value + u_value else 0.0
        output.append(
            {
                "task_family": family,
                "rd_recovery_after_adaptation": r_value,
                "ud_operationally_justified_stop": u_value,
                "calibration_pair_score": cps,
                "rd_runs": len(recovery),
                "ud_runs": len(justified),
            }
        )
    return output


def calibration_component_summaries(
    run_metrics: Sequence[Mapping[str, Any]],
    calibration: Sequence[Mapping[str, Any]],
    *, replicates: int,
) -> list[dict[str, Any]]:
    """Describe each H1 component on its own observed families, CPS on pairs.

    The confirmatory GEE test is deliberately *not* computed here. These
    family-bootstrap intervals and the CPS point estimate remain descriptive.
    """

    cells = _h1_component_cells(run_metrics)
    rows = sorted(calibration, key=lambda row: str(row["task_family"]))
    families = [row["task_family"] for row in rows]
    if len(set(families)) != len(families):
        raise ValueError("H1 calibration rows must contain unique task families")
    output: list[dict[str, Any]] = []
    for component, condition, source in (
        ("RD_recovery_after_adaptation", "RD", None),
        ("UD_operationally_justified_stop", "UD", None),
        ("calibration_pair_score", None, "calibration_pair_score"),
    ):
        if condition is None:
            values = [float(row[source]) for row in rows]
            n_runs = None
        else:
            condition_cells = [cells[family][condition] for family in sorted(cells)
                               if cells[family].get(condition)]
            values = [fmean(cell) for cell in condition_cells]
            n_runs = sum(len(cell) for cell in condition_cells)
        if not values:
            continue
        if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in values):
            raise ValueError(f"invalid H1 component value for {component}")
        interval = cluster_bootstrap_mean(values, replicates=replicates, label=f"H1:{component}")
        output.append({
            "component": component,
            "estimate": interval["estimate"],
            "ci_low": interval["ci_low"],
            "ci_high": interval["ci_high"],
            "n_families": interval["n_families"],
            "n_runs": n_runs,
            "uncertainty_method": (
                "95% task-family cluster bootstrap percentile interval"
                if len(values) >= 2 else "NOT_ESTIMABLE_LT_2_FAMILIES"
            ),
            "confirmatory_test_status": "NOT_RUN_GEE_UNIMPLEMENTED",
        })
    return output


def h1_lower_bound_sensitivity(
    run_metrics: Sequence[Mapping[str, Any]],
    schedule_rows: Sequence[Mapping[str, Any]],
    *, replicates: int,
) -> list[dict[str, Any]]:
    """Zero-fill absent exposed RD/UD cells in all planned paired main families."""

    planned: dict[str, set[str]] = defaultdict(set)
    for row in schedule_rows:
        family = row.get("task_family")
        condition = row.get("condition")
        if (row.get("stratum") == "MAIN" and isinstance(family, str) and family
                and family != "UNRESOLVED_FAMILY" and condition in {"RD", "UD"}):
            planned[family].add(condition)
    families = sorted(family for family, conditions in planned.items()
                      if conditions == {"RD", "UD"})
    if not families:
        return []
    cells = _h1_component_cells(run_metrics)
    output: list[dict[str, Any]] = []
    for condition, component in (
        ("RD", "RD_recovery_after_adaptation"),
        ("UD", "UD_operationally_justified_stop"),
    ):
        observed = [cells.get(family, {}).get(condition, []) for family in families]
        values = [fmean(cell) if cell else 0.0 for cell in observed]
        interval = cluster_bootstrap_mean(values, replicates=replicates,
                                          label=f"H1:zero-filled:{component}")
        output.append({
            "component": component,
            "estimate": interval["estimate"],
            "ci_low": interval["ci_low"],
            "ci_high": interval["ci_high"],
            "n_planned_families": len(families),
            "n_observed_cells": sum(bool(cell) for cell in observed),
            "n_zero_filled_cells": sum(not cell for cell in observed),
            "uncertainty_method": (
                "95% task-family cluster bootstrap percentile interval"
                if len(families) >= 2 else "NOT_ESTIMABLE_LT_2_FAMILIES"
            ),
            "interpretation": "zero-filled incomplete exposed family-condition cells; sensitivity only",
        })
    return output

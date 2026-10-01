"""Precollection H1 power sensitivity on synthetic clustered Bernoulli outcomes.

This is a planning proxy, not the preregistered confirmatory GEE implementation.
No agent trajectory, task oracle, or experimental result is read by this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean
from typing import Any


POWER_SIMULATION_VERSION = "0.2.0"
PLANNING_ALPHA = 0.05
_CONTINUED_FRACTION_TOLERANCE = 3e-14


def _beta_fraction(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularized incomplete beta function."""

    tiny = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 401):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _CONTINUED_FRACTION_TOLERANCE:
            return h
    raise ArithmeticError("incomplete beta continued fraction did not converge")


def _regularized_beta(x: float, a: float, b: float) -> float:
    if not 0.0 <= x <= 1.0 or a <= 0.0 or b <= 0.0:
        raise ValueError("invalid regularized beta arguments")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    factor = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return factor * _beta_fraction(a, b, x) / a
    return 1.0 - factor * _beta_fraction(b, a, 1.0 - x) / b


def student_t_survival(t_statistic: float, degrees_of_freedom: int) -> float:
    """One-sided Student-t upper tail; dependency-free and testable against closed forms."""

    if not isinstance(degrees_of_freedom, int) or isinstance(degrees_of_freedom, bool) or degrees_of_freedom <= 0:
        raise ValueError("degrees_of_freedom must be a positive integer")
    if math.isnan(t_statistic):
        raise ValueError("t_statistic must not be NaN")
    if t_statistic == math.inf:
        return 0.0
    if t_statistic == -math.inf:
        return 1.0
    x = degrees_of_freedom / (degrees_of_freedom + t_statistic * t_statistic)
    upper_positive = 0.5 * _regularized_beta(x, degrees_of_freedom / 2.0, 0.5)
    return upper_positive if t_statistic >= 0.0 else 1.0 - upper_positive


def student_t_critical_one_sided(degrees_of_freedom: int, alpha: float = PLANNING_ALPHA) -> float:
    if not 0.0 < alpha < 0.5:
        raise ValueError("alpha must be between zero and one half")
    high = 1.0
    while student_t_survival(high, degrees_of_freedom) > alpha:
        high *= 2.0
    low = 0.0
    for _ in range(65):
        middle = (low + high) / 2.0
        if student_t_survival(middle, degrees_of_freedom) > alpha:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def family_cluster_t_test(
    family_cell_means: list[float], *, null_probability: float = 0.5
) -> dict[str, float | int | None]:
    """Equal-family-weighted one-sample t test with F−1 degrees of freedom.

    Each family supplies one mean over its eligible runs. The statistic tests
    the mean family residual under H0 using empirical between-family variance.
    It is a studentized family-mean planning proxy, *not* the preregistered GEE
    score test. The two methods must not be relabeled as equivalent.
    """

    if not 0.0 < null_probability < 1.0:
        raise ValueError("null_probability must lie strictly between zero and one")
    if any(not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0
           for value in family_cell_means):
        raise ValueError("family cell means must be probabilities")
    count = len(family_cell_means)
    estimate = fmean(family_cell_means) if count else None
    if count < 2:
        return {"n_families": count, "estimate": estimate,
                "t_statistic": None, "one_sided_p_value": None}
    residuals = [value - null_probability for value in family_cell_means]
    score = fmean(residuals)
    sum_squares = sum((value - score) ** 2 for value in residuals)
    if sum_squares <= 0.0:
        # A zero empirical cluster variance is non-estimable, not p=0.
        return {"n_families": count, "estimate": estimate,
                "t_statistic": None, "one_sided_p_value": None}
    standard_error = math.sqrt(sum_squares / ((count - 1) * count))
    t_statistic = score / standard_error
    return {"n_families": count, "estimate": estimate,
            "t_statistic": t_statistic,
            "one_sided_p_value": student_t_survival(t_statistic, count - 1)}


def _wilson_interval(successes: int, trials: int) -> tuple[float, float]:
    if not 0 <= successes <= trials or trials <= 0:
        raise ValueError("invalid Monte Carlo count")
    z = 1.959963984540054
    p = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = (p + z2 / (2.0 * trials)) / denominator
    half_width = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * trials)) / trials) / denominator
    return max(0.0, center - half_width), min(1.0, center + half_width)


@dataclass(frozen=True)
class PlanningConfig:
    families: int = 32
    runs_per_condition: int = 3
    exposure_probability: float = 0.8
    incomplete_cell_probability: float = 0.05
    intraclass_correlation: float = 0.10
    replicates: int = 10_000
    seed: int = 20_260_929
    alpha: float = PLANNING_ALPHA

    def __post_init__(self) -> None:
        for field in ("families", "runs_per_condition", "replicates"):
            value = getattr(self, field)
            minimum = 2 if field == "families" else 1
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"{field} must be an integer >= {minimum}")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if not 0.0 < self.exposure_probability <= 1.0:
            raise ValueError("exposure_probability must be in (0, 1]")
        if not 0.0 <= self.incomplete_cell_probability < 1.0:
            raise ValueError("incomplete_cell_probability must be in [0, 1)")
        if not 0.0 <= self.intraclass_correlation < 1.0:
            raise ValueError("intraclass_correlation must be in [0, 1)")
        if not 0.0 < self.alpha < 0.5:
            raise ValueError("alpha must be in (0, 0.5)")
        no_exposure = (1.0 - self.exposure_probability) ** self.runs_per_condition
        if self.incomplete_cell_probability < no_exposure:
            raise ValueError("target incomplete-cell rate is lower than unavoidable no-exposure rate")


def _scenario_seed(config: PlanningConfig, label: str) -> int:
    digest = hashlib.sha256(f"{config.seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _latent_probability(mean: float, icc: float, sign: int) -> float:
    deviation = math.sqrt(icc * mean * (1.0 - mean))
    value = mean + sign * deviation
    if not 0.0 <= value <= 1.0:
        raise ValueError("two-point family heterogeneity exceeds probability bounds")
    return value


def _cell_mean(
    rng: random.Random, *, probability: float, config: PlanningConfig, technical_missing_rate: float
) -> float | None:
    if rng.random() < technical_missing_rate:
        return None
    outcomes = [float(rng.random() < probability)
                for _ in range(config.runs_per_condition)
                if rng.random() < config.exposure_probability]
    return fmean(outcomes) if outcomes else None


def _run_scenario(
    config: PlanningConfig, *, rd_probability: float, ud_probability: float,
    cross_condition_dependence: str, critical_values: dict[int, float]
) -> dict[str, Any]:
    if cross_condition_dependence not in {"shared", "independent", "opposite"}:
        raise ValueError("unknown cross-condition dependence")
    label = f"RD={rd_probability}:UD={ud_probability}:cross={cross_condition_dependence}"
    rng = random.Random(_scenario_seed(config, label))
    no_exposure = (1.0 - config.exposure_probability) ** config.runs_per_condition
    technical_missing_rate = (config.incomplete_cell_probability - no_exposure) / (1.0 - no_exposure)
    rejections = 0
    nonestimable = 0
    incomplete_cells = 0
    observed_rd_families = 0
    observed_ud_families = 0
    for _ in range(config.replicates):
        rd_means: list[float] = []
        ud_means: list[float] = []
        for _family in range(config.families):
            rd_sign = 1 if rng.random() < 0.5 else -1
            ud_sign = (rd_sign if cross_condition_dependence == "shared" else
                       -rd_sign if cross_condition_dependence == "opposite" else
                       (1 if rng.random() < 0.5 else -1))
            rd_mean = _cell_mean(rng, probability=_latent_probability(rd_probability,
                                  config.intraclass_correlation, rd_sign),
                                 config=config, technical_missing_rate=technical_missing_rate)
            ud_mean = _cell_mean(rng, probability=_latent_probability(ud_probability,
                                  config.intraclass_correlation, ud_sign),
                                 config=config, technical_missing_rate=technical_missing_rate)
            if rd_mean is None:
                incomplete_cells += 1
            else:
                rd_means.append(rd_mean)
            if ud_mean is None:
                incomplete_cells += 1
            else:
                ud_means.append(ud_mean)
        observed_rd_families += len(rd_means)
        observed_ud_families += len(ud_means)
        rd_test = family_cluster_t_test(rd_means)
        ud_test = family_cluster_t_test(ud_means)
        rd_t = rd_test["t_statistic"]
        ud_t = ud_test["t_statistic"]
        if rd_t is None or ud_t is None:
            nonestimable += 1
            continue
        if rd_t > critical_values[len(rd_means)] and ud_t > critical_values[len(ud_means)]:
            rejections += 1
    lower, upper = _wilson_interval(rejections, config.replicates)
    return {
        "scenario": label,
        "rd_probability": rd_probability,
        "ud_probability": ud_probability,
        "cross_condition_dependence": cross_condition_dependence,
        "intra_condition_icc": config.intraclass_correlation,
        "cross_condition_outcome_correlation_for_matched_runs": (
            config.intraclass_correlation if cross_condition_dependence == "shared" else
            -config.intraclass_correlation if cross_condition_dependence == "opposite" else 0.0
        ),
        "rejections": rejections,
        "replicates": config.replicates,
        "estimated_intersection_rejection_probability": rejections / config.replicates,
        "monte_carlo_95pct_wilson_low": lower,
        "monte_carlo_95pct_wilson_high": upper,
        "nonestimable_replicates": nonestimable,
        "mean_incomplete_cell_fraction": incomplete_cells / (2 * config.families * config.replicates),
        "mean_rd_observed_families": observed_rd_families / config.replicates,
        "mean_ud_observed_families": observed_ud_families / config.replicates,
    }


def simulate_planning_power(config: PlanningConfig) -> dict[str, Any]:
    """Estimate IUT power and composite-null size under three latent couplings."""

    critical_values = {families: student_t_critical_one_sided(families - 1, config.alpha)
                       for families in range(2, config.families + 1)}
    scenarios = [
        _run_scenario(config, rd_probability=rd, ud_probability=ud,
                      cross_condition_dependence=cross, critical_values=critical_values)
        for rd, ud in ((0.7, 0.7), (0.5, 0.7), (0.7, 0.5))
        for cross in ("shared", "independent", "opposite")
    ]
    alternative = [row for row in scenarios if row["rd_probability"] == 0.7 and row["ud_probability"] == 0.7]
    boundary_null = [row for row in scenarios if row not in alternative]
    source_path = Path(__file__).resolve()
    report = {
        "schema_version": POWER_SIMULATION_VERSION,
        "kind": "precollection_synthetic_power_sensitivity_not_agent_data",
        "decision_rule": "equal-family-weighted one-sample t test with F-1 degrees of freedom; intersection requires both one-sided p<0.05",
        "status": "PLANNING_PROXY_NOT_PREREGISTERED_GEE",
        "config": asdict(config),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "python_version": sys.version.split()[0],
        "assumptions": [
            "Independent task families; three fresh runs per diagnostic condition within family.",
            "Two-point family propensity has the requested marginal probability and ICC; it is not a universal task-difficulty model.",
            "Shared, independent and opposite family latent signs bracket three cross-condition dependence assumptions.",
            "Failure exposure is independent Bernoulli at 0.80; technical cell missingness is independent of outcome and calibrated so total incomplete-cell probability is 0.05.",
            "No task-family selection, nonignorable missingness, model drift, annotation error or verifier error is simulated.",
        ],
        "scenarios": scenarios,
        "minimum_alternative_power_mc_lower_bound": min(row["monte_carlo_95pct_wilson_low"] for row in alternative),
        "maximum_boundary_null_rejection_mc_upper_bound": max(row["monte_carlo_95pct_wilson_high"] for row in boundary_null),
        "planning_proxy_exceeds_80pct_all_alt_scenarios": all(
            row["monte_carlo_95pct_wilson_low"] >= 0.8 for row in alternative
        ),
        "preregistration_power_gate_cleared": False,
        "gate_reason": "The exact preregistered small-sample GEE score implementation, independent statistical review, and main task/exposure validation remain absent.",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=32)
    parser.add_argument("--replicates", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20_260_929)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    config = PlanningConfig(families=args.families, replicates=args.replicates, seed=args.seed)
    report = simulate_planning_power(config)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{report['status']}: proxy all-alternative lower bound "
              f"{report['minimum_alternative_power_mc_lower_bound']:.3f}; "
              "actual preregistration gate remains NOT_CLEARED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

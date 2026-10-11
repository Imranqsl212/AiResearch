"""Pre-main C5 family-level power sensitivity; synthetic scenarios only.

This module never reads agent runs. It simulates the paired verdict-onset design in
docs/preregistration_v1_20261005.md and applies that document's two-sided
equal-family paired-difference t decision rule. It cannot clear a READY gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean
from typing import Any

from analysis.power_simulation import student_t_critical_one_sided


VERSION = "c5-onset-power-sensitivity-1.0.0"
ALPHA = 0.05
MIN_FAMILIES = 15


@dataclass(frozen=True)
class Scenario:
    families: int = 20
    precursors_per_family: int = 10
    max_onsets_per_family: int = 5
    onset_reach_probability: float = 0.5
    false_fail_stop_reduction: float = 0.2
    technical_pair_loss: float = 0.05
    truthful_pass_stop_probability: float = 0.65
    family_baseline_shift: float = 0.08
    family_effect_shift: float = 0.08
    family_reach_shift: float = 0.12
    paired_shared_uniform_fraction: float = 0.5

    def __post_init__(self) -> None:
        for key in ("families", "precursors_per_family", "max_onsets_per_family"):
            value = getattr(self, key)
            if type(value) is not int or value < 1:
                raise ValueError(f"{key} must be a positive integer")
        if self.families < MIN_FAMILIES:
            raise ValueError("families must be at least the prespecified inferential minimum")
        if self.max_onsets_per_family > self.precursors_per_family:
            raise ValueError("onset cap exceeds precursor slots")
        for key in ("onset_reach_probability", "false_fail_stop_reduction",
                    "technical_pair_loss", "truthful_pass_stop_probability",
                    "family_baseline_shift", "family_effect_shift",
                    "family_reach_shift", "paired_shared_uniform_fraction"):
            value = getattr(self, key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{key} must be finite and in [0, 1]")
        if not 0 < self.onset_reach_probability < 1:
            raise ValueError("onset reach probability must be in (0, 1)")
        if not 0 < self.truthful_pass_stop_probability < 1:
            raise ValueError("truthful stop probability must be in (0, 1)")
        if (self.onset_reach_probability - self.family_reach_shift < 0 or
            self.onset_reach_probability + self.family_reach_shift > 1):
            raise ValueError("family reach propensities leave [0, 1]")
        lowest = (self.truthful_pass_stop_probability - self.family_baseline_shift
                  - self.false_fail_stop_reduction - self.family_effect_shift)
        highest = (self.truthful_pass_stop_probability + self.family_baseline_shift
                   - self.false_fail_stop_reduction + self.family_effect_shift)
        if lowest < 0 or highest > 1:
            raise ValueError("false-failure stop probabilities leave [0, 1]")
        if (self.truthful_pass_stop_probability - self.family_baseline_shift < 0 or
            self.truthful_pass_stop_probability + self.family_baseline_shift > 1):
            raise ValueError("truthful-pass stop probabilities leave [0, 1]")


def _seed(master_seed: int, scenario: Scenario) -> int:
    data = json.dumps({"seed": master_seed, "scenario": asdict(scenario)},
                      sort_keys=True, separators=(",", ":")).encode()
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "big")


def _wilson(successes: int, trials: int) -> tuple[float, float]:
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("invalid count")
    z = 1.959963984540054
    p = successes / trials
    z2 = z * z
    denominator = 1 + z2 / trials
    center = (p + z2 / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def _one_dataset(rng: random.Random, scenario: Scenario,
                 critical: dict[int, float]) -> tuple[bool | None, int, int, float | None]:
    differences: list[float] = []
    valid_pairs = 0
    for _ in range(scenario.families):
        # Each sign is a family-level random effect; five repeats never become
        # five independent family units. The effects are hypothetical.
        base_sign = 1 if rng.random() < 0.5 else -1
        effect_sign = 1 if rng.random() < 0.5 else -1
        reach_sign = 1 if rng.random() < 0.5 else -1
        p_pass = scenario.truthful_pass_stop_probability + base_sign * scenario.family_baseline_shift
        p_false = (p_pass - scenario.false_fail_stop_reduction
                   + effect_sign * scenario.family_effect_shift)
        p_reach = scenario.onset_reach_probability + reach_sign * scenario.family_reach_shift
        pair_differences: list[int] = []
        reached = 0
        for _slot in range(scenario.precursors_per_family):
            if rng.random() >= p_reach:
                continue
            if reached >= scenario.max_onsets_per_family:
                continue
            reached += 1
            if rng.random() < scenario.technical_pair_loss:
                continue
            if rng.random() < scenario.paired_shared_uniform_fraction:
                common = rng.random()
                truthful_stop = common < p_pass
                false_stop = common < p_false
            else:
                truthful_stop = rng.random() < p_pass
                false_stop = rng.random() < p_false
            pair_differences.append(int(false_stop) - int(truthful_stop))
        if pair_differences:
            differences.append(fmean(pair_differences))
            valid_pairs += len(pair_differences)
    count = len(differences)
    if count < MIN_FAMILIES:
        return None, count, valid_pairs, None
    mean = fmean(differences)
    sum_sq = sum((value - mean) ** 2 for value in differences)
    if sum_sq == 0:
        return None, count, valid_pairs, mean
    se = math.sqrt(sum_sq / ((count - 1) * count))
    reject = abs(mean / se) > critical[count]
    return reject, count, valid_pairs, mean


def simulate(scenario: Scenario, *, replicates: int, seed: int) -> dict[str, Any]:
    """Unconditional rejection and nonestimability under one synthetic scenario."""
    if type(replicates) is not int or replicates < 1:
        raise ValueError("replicates must be positive")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    rng = random.Random(_seed(seed, scenario))
    critical = {count: student_t_critical_one_sided(count - 1, ALPHA / 2)
                for count in range(MIN_FAMILIES, scenario.families + 1)}
    rejected = 0
    estimable = 0
    family_total = 0
    pair_total = 0
    estimate_total = 0.0
    for _ in range(replicates):
        decision, n_families, n_pairs, estimate = _one_dataset(rng, scenario, critical)
        family_total += n_families
        pair_total += n_pairs
        if decision is not None:
            estimable += 1
            rejected += int(decision)
            assert estimate is not None
            estimate_total += estimate
    lower, upper = _wilson(rejected, replicates)
    return {
        "scenario": asdict(scenario),
        "replicates": replicates,
        "rejections": rejected,
        "estimable_replicates": estimable,
        "nonestimable_replicates": replicates - estimable,
        "unconditional_rejection_probability": rejected / replicates,
        "monte_carlo_95pct_wilson_interval": [lower, upper],
        "conditional_rejection_probability_given_estimable": rejected / estimable if estimable else None,
        "mean_contributing_families": family_total / replicates,
        "mean_valid_onset_pairs": pair_total / replicates,
        "mean_estimated_family_difference_when_estimable": estimate_total / estimable if estimable else None,
    }


def scenario_grid() -> list[Scenario]:
    """Frozen planning grid, centered on the proposed 20-family design."""
    cases: list[Scenario] = []
    for families in (15, 20, 30, 40):
        for reach in (0.3, 0.5, 0.8):
            for effect in (0.0, 0.1, 0.2, 0.3):
                cases.append(Scenario(families=families, onset_reach_probability=reach,
                                      false_fail_stop_reduction=effect))
    for cap in (3, 10):
        for effect in (0.0, 0.2, 0.3):
            cases.append(Scenario(max_onsets_per_family=cap,
                                  false_fail_stop_reduction=effect))
    for loss in (0.0, 0.1):
        for effect in (0.0, 0.2, 0.3):
            cases.append(Scenario(technical_pair_loss=loss,
                                  false_fail_stop_reduction=effect))
    for effect_shift in (0.0, 0.15):
        for effect in (0.0, 0.2, 0.3):
            cases.append(Scenario(family_effect_shift=effect_shift,
                                  false_fail_stop_reduction=effect))
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicates", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261005)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; use a new path to preserve provenance")
    result = {
        "version": VERSION,
        "status": "SYNTHETIC_PLANNING_ONLY_NOT_READY",
        "protocol": "docs/preregistration_v1_20261005.md",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "master_seed": args.seed,
        "test": "two-sided equal-family paired-difference Student-t, alpha=0.05; at least 15 contributing families",
        "assumptions": {
            "binary_endpoint": "voluntary stop with at least one of three post-verdict decisions unused",
            "family_propensities": "two-point +/- family shifts; independent reach, baseline, and treatment-effect signs",
            "pair_dependence": "shared uniform with stated probability, else independent uniforms",
            "technical_loss": "pair-level independent missingness",
            "scope": "C5 onset contrast only; no companion Holm power calculated",
        },
        "scenarios": [simulate(case, replicates=args.replicates, seed=args.seed)
                      for case in scenario_grid()],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()

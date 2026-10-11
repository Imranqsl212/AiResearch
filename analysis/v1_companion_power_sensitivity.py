"""Synthetic family-level power for C1/C2, C3/C4, and R1/R0 with Holm.

No agent data or task result is read. These are assumed binary-outcome scenarios,
not estimates of actual model behavior or a main-study READY decision.
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

from analysis.power_simulation import student_t_survival


VERSION = "v1-companion-holm-power-1.0.0"
ALPHA = 0.05
LABELS = ("C2_minus_C1_recovery", "C4_minus_C3_early_stop", "R1_minus_R0_recovery")


@dataclass(frozen=True)
class Scenario:
    families: int = 20
    repeats: int = 5
    technical_run_loss: float = 0.05
    diagnostic_effect: float = 0.2
    proof_effect: float = 0.3
    rag_effect: float = 0.1
    family_baseline_shift: float = 0.08
    family_effect_shift: float = 0.08
    coupling: str = "independent"

    def __post_init__(self) -> None:
        if type(self.families) is not int or self.families < 15:
            raise ValueError("families must be an integer >= 15")
        if type(self.repeats) is not int or self.repeats < 1:
            raise ValueError("repeats must be positive")
        if self.coupling not in {"shared", "independent"}:
            raise ValueError("coupling must be shared or independent")
        for key in ("technical_run_loss", "diagnostic_effect", "proof_effect",
                    "rag_effect", "family_baseline_shift", "family_effect_shift"):
            value = getattr(self, key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value < 1:
                raise ValueError(f"{key} must be finite and in [0, 1)")
        # The shared family signs below can all point in the same direction.
        low_recovery = 0.35 - self.family_baseline_shift - 2 * self.family_effect_shift
        high_recovery = (0.35 + self.family_baseline_shift + self.diagnostic_effect
                         + self.rag_effect + 2 * self.family_effect_shift)
        high_proof = 0.20 + self.family_baseline_shift + self.proof_effect + self.family_effect_shift
        if low_recovery < 0 or high_recovery > 1 or high_proof > 1:
            raise ValueError("family propensities leave [0, 1]")


def _seed(seed: int, scenario: Scenario) -> int:
    payload = json.dumps({"seed": seed, "scenario": asdict(scenario)}, sort_keys=True).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _bernoulli_mean(rng: random.Random, p: float, repeats: int, loss: float) -> float | None:
    observations = [float(rng.random() < p) for _ in range(repeats) if rng.random() >= loss]
    return fmean(observations) if observations else None


def _family_contrasts(rng: random.Random, scenario: Scenario) -> tuple[float | None, float | None, float | None]:
    sign = 1 if rng.random() < 0.5 else -1
    if scenario.coupling == "shared":
        diag_sign = proof_sign = rag_sign = sign
    else:
        diag_sign = 1 if rng.random() < 0.5 else -1
        proof_sign = 1 if rng.random() < 0.5 else -1
        rag_sign = 1 if rng.random() < 0.5 else -1
    base = 0.35 + sign * scenario.family_baseline_shift
    diag = scenario.diagnostic_effect + diag_sign * scenario.family_effect_shift
    rag = scenario.rag_effect + rag_sign * scenario.family_effect_shift
    stop_base = 0.20 + sign * scenario.family_baseline_shift
    proof = scenario.proof_effect + proof_sign * scenario.family_effect_shift
    c1r0 = _bernoulli_mean(rng, base, scenario.repeats, scenario.technical_run_loss)
    c2r0 = _bernoulli_mean(rng, base + diag, scenario.repeats, scenario.technical_run_loss)
    c1r1 = _bernoulli_mean(rng, base + rag, scenario.repeats, scenario.technical_run_loss)
    c2r1 = _bernoulli_mean(rng, base + diag + rag, scenario.repeats, scenario.technical_run_loss)
    c3r0 = _bernoulli_mean(rng, stop_base, scenario.repeats, scenario.technical_run_loss)
    c4r0 = _bernoulli_mean(rng, stop_base + proof, scenario.repeats, scenario.technical_run_loss)
    diagnostic = c2r0 - c1r0 if c1r0 is not None and c2r0 is not None else None
    stopping = c4r0 - c3r0 if c3r0 is not None and c4r0 is not None else None
    retrieval = (0.5 * ((c1r1 - c1r0) + (c2r1 - c2r0))
                 if all(v is not None for v in (c1r0, c2r0, c1r1, c2r1)) else None)
    return diagnostic, stopping, retrieval


def _family_t_p(values: list[float]) -> float | None:
    count = len(values)
    if count < 15:
        return None
    mean = fmean(values)
    sum_sq = sum((value - mean) ** 2 for value in values)
    if sum_sq <= 0:
        return None
    se = math.sqrt(sum_sq / ((count - 1) * count))
    return min(1.0, 2 * student_t_survival(abs(mean / se), count - 1))


def _holm(p_values: tuple[float, float, float]) -> tuple[bool, bool, bool]:
    order = sorted(range(3), key=lambda index: p_values[index])
    rejected = [False, False, False]
    for rank, index in enumerate(order):
        if p_values[index] > ALPHA / (3 - rank):
            break
        rejected[index] = True
    return tuple(rejected)  # type: ignore[return-value]


def _wilson(successes: int, trials: int) -> list[float]:
    z = 1.959963984540054
    p = successes / trials
    z2 = z * z
    denominator = 1 + z2 / trials
    center = (p + z2 / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials)) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def simulate(scenario: Scenario, *, replicates: int, seed: int) -> dict[str, Any]:
    if type(replicates) is not int or replicates < 1:
        raise ValueError("replicates must be positive")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be non-negative")
    rng = random.Random(_seed(seed, scenario))
    rejected = [0, 0, 0]
    all_rejected = 0
    any_rejected = 0
    nonestimable = 0
    family_counts = [0, 0, 0]
    for _ in range(replicates):
        contrasts = [[], [], []]
        for _family in range(scenario.families):
            values = _family_contrasts(rng, scenario)
            for index, value in enumerate(values):
                if value is not None:
                    contrasts[index].append(value)
        for index, values in enumerate(contrasts):
            family_counts[index] += len(values)
        p = tuple(_family_t_p(values) for values in contrasts)
        if any(value is None for value in p):
            nonestimable += 1
            continue
        decisions = _holm(p)  # type: ignore[arg-type]
        for index, decision in enumerate(decisions):
            rejected[index] += int(decision)
        all_rejected += int(all(decisions))
        any_rejected += int(any(decisions))
    return {
        "scenario": asdict(scenario),
        "replicates": replicates,
        "nonestimable_replicates": nonestimable,
        "mean_contributing_families": {label: family_counts[i] / replicates
                                        for i, label in enumerate(LABELS)},
        "holm_rejection_probability_by_contrast": {label: rejected[i] / replicates
                                                    for i, label in enumerate(LABELS)},
        "holm_rejection_monte_carlo_95pct_wilson_by_contrast": {
            label: _wilson(rejected[i], replicates) for i, label in enumerate(LABELS)
        },
        "probability_any_holm_rejection": any_rejected / replicates,
        "any_rejection_monte_carlo_95pct_wilson": _wilson(any_rejected, replicates),
        "probability_all_three_holm_rejections": all_rejected / replicates,
        "all_three_monte_carlo_95pct_wilson": _wilson(all_rejected, replicates),
    }


def scenario_grid() -> list[Scenario]:
    effects = ((0.0, 0.0, 0.0), (0.1, 0.15, 0.05), (0.2, 0.3, 0.1), (0.2, 0.2, 0.2))
    return [Scenario(families=families, technical_run_loss=loss,
                     diagnostic_effect=diag, proof_effect=proof, rag_effect=rag,
                     coupling=coupling)
            for families in (20, 30, 40)
            for loss in (0.0, 0.05, 0.10)
            for diag, proof, rag in effects
            for coupling in ("shared", "independent")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicates", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261005)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    result = {
        "version": VERSION,
        "status": "SYNTHETIC_PLANNING_ONLY_NOT_READY",
        "protocol": "docs/preregistration_v1_20261005.md",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "master_seed": args.seed,
        "rule": "two-sided equal-family paired-difference t tests, three-test Holm alpha=0.05",
        "note": "R1-R0 shares C1/C2 R0 cells with C2-C1 in each simulated dataset",
        "scenarios": [simulate(scenario, replicates=args.replicates, seed=args.seed)
                      for scenario in scenario_grid()],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()

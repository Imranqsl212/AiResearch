# Precollection H1 power sensitivity — planning proxy only

**Status:** `PLANNING_PROXY_NOT_PREREGISTERED_GEE`; **preregistration power gate: NOT CLEARED**. This is a synthetic design calculation, not a benchmark result or an AI-agent observation. No raw trajectory is read or generated.

## Question and decision rule

The draft [preregistration](../docs/preregistration.md) proposes 32 independent task families, three fresh RD and UD runs per family, and an intersection–union test (IUT): both RD validated recovery and UD operationally justified stopping must exceed 0.50 at one-sided α = 0.05. It requires at least 80% power when both true component rates equal 0.70, within-family ICC is at most 0.10, and no more than 5% of condition cells are incomplete.

This calculation uses **one family mean per condition** and a one-sided Student-t test with `F−1` degrees of freedom for each component. The IUT rejects only when both components reject. That is an equal-family-weighted, studentized planning proxy; it is **not** the predeclared GEE robust score test. Published small-sample research distinguishes robust score and Wald-type behavior under clustering: [Guo et al., 2005](https://pubmed.ncbi.nlm.nih.gov/15977302/) and [Fay & Graubard, 2001](https://onlinelibrary.wiley.com/doi/10.1111/j.0006-341X.2001.01198.x). Those papers motivate caution; neither validates this project's proxy for its eventual task distribution.

## Frozen simulation assumptions

The [machine-readable result](power_simulation_result.json) uses version `0.2.0`, seed `20260929`, 10,000 independent simulated datasets **per scenario**, 32 families, three runs per diagnostic condition, 80% independent failure exposure per run, 5% total incomplete condition cells, and ICC = 0.10. Conditional outcomes are Bernoulli with a two-point family propensity selected to produce the requested marginal rate and ICC. Family propensity signs are shared, independent, or opposite across RD and UD; these yield approximately +0.10, 0, or −0.10 correlation between matched run outcomes. Technical missingness is independent of outcome and calibrated jointly with non-exposure to reach 5% incomplete cells. Each simulation reports a 95% Wilson interval for **Monte Carlo error only**.

| True RD/UD rate | Cross-condition coupling | IUT rejection frequency | Monte Carlo 95% interval |
| --- | --- | ---: | ---: |
| 0.70 / 0.70 | Shared | 0.8702 | 0.8635–0.8766 |
| 0.70 / 0.70 | Independent | 0.8596 | 0.8527–0.8663 |
| 0.70 / 0.70 | Opposite | 0.8573 | 0.8503–0.8640 |
| 0.50 / 0.70 | Shared / independent / opposite | 0.0450 / 0.0457 / 0.0469 | See exact result JSON |
| 0.70 / 0.50 | Shared / independent / opposite | 0.0448 / 0.0422 / 0.0439 | See exact result JSON |

The lowest alternative-scenario Monte Carlo lower bound is **0.8503**, above the 0.80 planning target **for this proxy and these assumptions**. The largest boundary-null Monte Carlo upper bound is **0.0512**; this does not prove nominal size for other data-generating mechanisms. Simulated incomplete-cell fractions were about 0.05 in each scenario. None of these numbers estimates agent behavior or establishes the preregistered GEE's power.

## Why the gate remains closed

The exact small-sample GEE score implementation and its independent statistical review are still absent. The confirmatory task families, independently reviewed **executable-target** action-timed verifier, failure-exposure distribution, provider configuration, and actual missingness process are also unknown. The in-memory pilot's action witness is not a substitute. Outcome-dependent missingness, family selection, heterogeneous exposure, coding error, model drift, and verifier error could reduce power or bias the estimand. The simulation does not justify freezing 32 families yet; it shows that 32 are plausible under a transparent favorable planning model. The final test and sensitivity grid must be chosen **before** main outcomes are inspected and the calculation rerun against that frozen method. If the actual power gate then fails, increase independent task families rather than merely repeats.

## Reproduction and provenance

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_power_simulation -v
power_replay_dir=$(mktemp -d)
PYTHONDONTWRITEBYTECODE=1 python3 -B -m analysis.power_simulation \
  --replicates 10000 --seed 20260929 --output "$power_replay_dir/replay.json"
cmp analysis/power_simulation_result.json "$power_replay_dir/replay.json"
```

Use a fresh output path because the generator refuses to overwrite an existing result. Python version for the saved report: `3.14.6`. Source SHA-256: `11f9a4369948cdb8d71430c16b5b814a241a2bfe851b4f1d7230a5c9784ca80b`. Result SHA-256: `9419e138004e85854998efc0f8fe3debe5930cb7ce424c51dbf78d50f442cc65`. The report embeds its source hash and all assumptions, counts, estimates, and Monte Carlo intervals. The saved v0.2.0 report must be byte-for-byte reproducible with the command above.

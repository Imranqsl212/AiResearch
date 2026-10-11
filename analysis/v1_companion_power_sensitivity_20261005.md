# C1/C2, C3/C4, and RAG power sensitivity — synthetic planning only

**Status:** `SYNTHETIC_PLANNING_ONLY_NOT_READY`. The [script](v1_companion_power_sensitivity.py)
simulates the three predeclared secondary contrasts in the
[`v1 protocol`](../docs/preregistration_v1_20261005.md) with five repeats per
family and the exact three-test Holm procedure. It reads no agent trajectories.
The [JSON result](v1_companion_power_sensitivity_20261005.json) preserves all
72 scenarios, their inputs, and Monte Carlo intervals.
The current collector supports R1 only for authorization. The reconciled
proposed main planner requires R1 for C1/C2 in every family, but that planner
has no released main execution path. Consequently the 20-family RAG design
assumed here cannot run or be validated as main yet.

The simulated binary rates start at 0.35 for C1/R0 oracle recovery and 0.20 for
C3/R0 early voluntary stopping. Hypothetical family baselines shift by ±0.08,
and treatment effects shift by ±0.08. The RAG comparison uses C1 and C2 in
both R0 and R1; the same R0 observations also enter the C2−C1 contrast, so
the tests are not spuriously treated as independent. Each run has 5% independent
technical-loss probability in the table below. A family contributes a contrast
only if its required cells have at least one valid repeat. A test needs at least
15 contributing families and nonzero family variance. Each row is based on
2,000 synthetic datasets; displayed uncertainty is Monte Carlo error only.

| Families | Assumed effects: C2−C1 / C4−C3 / R1−R0 | Holm detection C2−C1 | C4−C3 | R1−R0 | All three |
| ---: | --- | ---: | ---: | ---: | ---: |
| 20 | 0 / 0 / 0, null | 0.015 | 0.016 | 0.018 | 0.000 |
| 20 | 0.10 / 0.15 / 0.05 | 0.145 | 0.401 | 0.078 | 0.018 |
| 20 | 0.20 / 0.30 / 0.10 | 0.662 | 0.963 | 0.389 | 0.304 |
| 20 | 0.20 / 0.20 / 0.20 | 0.702 | 0.779 | 0.933 | 0.563 |
| 30 | 0.20 / 0.30 / 0.10 | 0.863 | 0.999 | 0.605 | 0.555 |
| 40 | 0.20 / 0.30 / 0.10 | 0.959 | 1.000 | 0.734 | 0.712 |

For the all-null 20-family scenario, the probability of **any** Holm rejection
was 0.047 (Monte Carlo 95% Wilson interval 0.038–0.057), near the nominal 0.05
under these simulation assumptions. In the 20-family 0.20/0.30/0.10 scenario,
the RAG contrast had only 0.389 rejection probability (Monte Carlo interval
0.368–0.410), and the chance of detecting all three was 0.304 (0.284–0.325).
Even at 40 families, a 10-point RAG effect does not reach 80% detection in this
model. Thus the proposed 20-family study cannot honestly promise a decisive
three-effect result. The protocol appropriately treats these as a Holm-adjusted
secondary family, rather than making all three significant findings a condition
for the primary C5 claim.

This generator varies family count, technical loss, effect size, and shared
versus independent family-effect signs. Its Bernoulli assumptions, independent
technical loss, and chosen baseline rates may be wrong. It does not address
document relevance, token-length confounding, actual model reachability,
oracle error, or cross-model drift. It cannot clear task admission, implementation,
RAG parity, or the final power gate. Before main collection, an independent
statistical review should accept a smallest meaningful effect and evaluate
power under realistic reach and loss ranges. If the available family count
cannot support precise RAG inference, keep RAG descriptive or publish its wide
intervals without a positive claim.

## Reproduce

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_v1_companion_power_sensitivity -v
power_replay_dir=$(mktemp -d)
PYTHONDONTWRITEBYTECODE=1 python3 -B -m analysis.v1_companion_power_sensitivity \
  --replicates 2000 --seed 20261005 \
  --output "$power_replay_dir/replay.json"
cmp analysis/v1_companion_power_sensitivity_20261005.json "$power_replay_dir/replay.json"
```

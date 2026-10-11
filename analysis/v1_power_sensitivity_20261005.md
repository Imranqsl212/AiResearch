# Prospective C5 onset power sensitivity — synthetic planning only

**Status:** `SYNTHETIC_PLANNING_ONLY_NOT_READY`. This is a reproducible scenario
calculation for the primary C5 decision rule in the new
[`v1 protocol`](../docs/preregistration_v1_20261005.md), not an agent result,
observed effect, or proof that the design is sufficiently powered. The
[`JSON output`](v1_power_sensitivity_20261005.json) contains all 66 scenarios,
assumptions, counts, and Monte Carlo intervals. The script reads no trajectories.
The proposed main planner now reserves conditional C5 onset pairs rather than
scheduling C5 as full episodes. It still cannot execute those branches, and the
current v1 collector stops on `PASS`. The excluded two-decision scripted probe
is also a different design. These calculations apply only after a versioned
main-path implementation passes the protocol's branch-parity gate.

## Rule simulated

For each family, pair a truthful `PASS` and injected false `FAIL` at the *same*
agent-generated oracle-secure onset. The binary endpoint is a voluntary stop with
at least one of three post-verdict decisions unused. Average `FAIL − PASS` within
family, then apply the **two-sided family-level paired-difference Student-t test**
at α = 0.05. An experiment with fewer than 15 contributing families or zero
between-family contrast variance is non-estimable, never a rejection.

The base synthetic scenario has 10 precursor slots per family, a cap of five
valid onset pairs, 50% onset reach probability, 5% independent technical pair
loss, truthful-pass stop probability 0.65, family baseline and treatment-effect
shifts of ±0.08, family reach shifts of ±0.12, and a shared within-pair random
draw half the time. The assumed shifts are synthetic heterogeneity; they are
not fitted to the excluded pilots. Each row uses 2,000 independent simulated
datasets. Wilson intervals quantify **Monte Carlo error only**.

| Families | Onset reach | Assumed false-FAIL reduction in early stop | Unconditional rejection probability | Monte Carlo 95% interval | Mean valid pairs |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | 0.50 | 0.00, null | 0.048 | 0.039–0.058 | 80.0 |
| 20 | 0.50 | 0.10 | 0.341 | 0.321–0.362 | 80.1 |
| 20 | 0.50 | 0.20 | 0.779 | 0.761–0.797 | 80.2 |
| 20 | 0.50 | 0.30 | 0.972 | 0.963–0.978 | 80.0 |
| 20 | 0.30 | 0.20 | 0.588 | 0.566–0.609 | 54.2 |
| 20 | 0.80 | 0.20 | 0.896 | 0.882–0.909 | 94.2 |
| 30 | 0.50 | 0.20 | 0.929 | 0.917–0.939 | 120.1 |
| 40 | 0.30 | 0.20 | 0.870 | 0.855–0.884 | 108.4 |

At 20 families, a 20-percentage-point stop-rate difference is close to but
below 80% power under the **50% reach assumptions**. A 10-point effect is
unlikely to be detected reliably. When reach is only 30%, the nominal 20-family
design has about 59% power for a 20-point effect. Thirty families at 50% reach
or forty at 30% reach exceed 80% *in this favorable synthetic model*. Neither
family expansion nor repetition is authorized by these numbers alone: first
define the smallest effect worth detecting and review whether enough independent
families can be admitted.

One-factor sensitivity at 20 families, 50% reach, and a 20-point effect yielded
rejection probabilities of 0.663 with a three-onset cap, 0.833 with a ten-onset
cap, 0.807 at zero technical loss, 0.754 at 10% technical loss, and 0.757 when
between-family treatment-effect shift rose to ±0.15. Increasing repeats
reduces noise within families but does not turn them into additional independent
families. This is an anchored sensitivity grid, not a full factorial search.

## Limits and required next decision

The simulation assumes independent families, an exactly delivered verdict,
fair branch isolation, bounded binary outcomes generated from simple two-point
family effects, independent technical loss, and fixed family-level model behavior.
Real reach, within-family dependence, effect heterogeneity, coding or oracle
errors, provider drift, outcome-related missingness, or task selection can
change both power and type-I error. The family-t approximation also deserves
independent statistical review with only 20 clusters. A sign-flip analysis is
predeclared as sensitivity, not substituted for the primary rule. The RAG,
C1/C2, C3/C4 and Holm-adjusted companion tests have **not** been power-validated
by this C5 calculation. Their power gate remains open.

Before main collection, freeze a scientifically meaningful minimum effect,
target onset reach, family admission count, and planned analysis version;
simulate the full confirmatory family under realistic dependence. If that
study cannot be supported by the available tasks or compute, narrow the claims
and label the work a methods study before observing main outcomes. No p-value
or run count from this document can promote the project to `READY`.

## Reproduce

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_v1_power_sensitivity -v
power_replay_dir=$(mktemp -d)
PYTHONDONTWRITEBYTECODE=1 python3 -B -m analysis.v1_power_sensitivity \
  --replicates 2000 --seed 20261005 \
  --output "$power_replay_dir/replay.json"
cmp analysis/v1_power_sensitivity_20261005.json "$power_replay_dir/replay.json"
```

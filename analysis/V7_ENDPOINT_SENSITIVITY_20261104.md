# Endpoint sensitivity: unsafe acceptance versus false denial

This post hoc audit replays the original excluded pilot archives through their
source-bound recounts, then splits a terminal Boolean-world error into two
observable directions:

- **Safety failure:** the candidate accepts a world that the authored property
  requires it to reject.
- **Availability failure:** the candidate rejects a world that the authored
  property requires it to accept.

The original finite-property regression is their union. This decomposition
tests how much the observed contrast depends on that composite endpoint; it
does not change the authored task objective. All cohorts are selected,
AI-authored, excluded pilot data without independent human semantic admission.

| Excluded cohort | Completed / scheduled pairs | False-feedback terminal composite | False-feedback terminal unsafe accept | False-feedback terminal false denial | Truthful terminal composite | Truthful terminal unsafe accept | Truthful terminal false denial |
|---|---:|---:|---:|---:|---:|---:|---:|
| First stopped temp-0.3 wave | 4 / 32 | 3 | 0 | 3 | 0 | 0 | 0 |
| Second stopped temp-0.3 wave | 4 / 32 | 3 | 0 | 3 | 1 | 0 | 1 |
| Seed-301 three-family wave | 3 / 3 | 2 | 1 | 1 | 1 | 1 | 0 |
| Seeds-302–304 six-slot wave | 6 / 6 | 4 | 1 | 3 | 1 | 0 | 1 |

The two stopped schedules have 24 and 22 unstarted slots respectively; they
must not be treated as 32 observed pairs each. Their other slots comprised
3 and 5 cases without a secure onset, plus one technical invalidation in
each wave. The cohorts were planned sequentially and selected using related
tasks; the table is **not pooled** into an effect estimate.

## What changes when the endpoint changes

Across the two stopped waves, all seven terminal composite regressions are
false denials of the authorized CSRF request. A safety-only terminal endpoint
would count **zero** unsafe-acceptance regressions in those completed pairs.
This is a substantive change in the interpretation of the outcome, not a
statistical correction. The later seed-301 and six-slot waves do contain
retired-key unsafe acceptance, including one truthful arm in seed 301.

The six-slot wave's pairwise composite contrast is three false-only
regressions, one both-arm regression, and two neither-arm regressions. Its
safety-only contrast is one false-only unsafe acceptance and five neither;
its availability-only contrast is three false-only denials, one truthful-only
denial, and two neither. Therefore a statement such as “false feedback made
the agent accept unsafe code in four of six pairs” would be false. The
defensible statement is that four false arms ended with an authored-property
error: three denied a legitimate request and one accepted a retired key.

This audit also limits the intuitive “security harm” story. Denying every
request preserves the narrow no-unauthorized-acceptance property while
breaking the task's required legitimate access. Both properties matter, but
they represent different user harms and should remain visibly separated.
These finite worlds do not establish whether a real deployment is secure.

## Reproduce

```sh
python3 -B -m analysis.v7_endpoint_sensitivity_20261104 --check
```

The command replays the source-bound directional reports for both stopped
waves, the seed-301 cross-family wave, and the seeds-302–304 six-slot wave,
checks those reports against their saved copies, and checks the derived
[JSON table](v7_endpoint_sensitivity_20261104.json). It makes no new model
requests or modifications to experiment archives.

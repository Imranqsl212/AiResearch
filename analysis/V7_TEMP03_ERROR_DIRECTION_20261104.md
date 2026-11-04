# Earlier CSRF regressions were overblocking, not bypasses

**Excluded post hoc audit, 4 November 2026.** The two previously archived
temperature-0.3 waves were stopped by technical invalidations. We separately
replayed each wave's source-bound checks and classified the terminal bounded
candidate against every authored CSRF world. The [program](v7_temp03_error_direction_20261104.py)
and [machine-readable report](v7_temp03_error_direction_20261104.json) retain
all scheduled and unstarted slots.

| Cohort | Scheduled | Verified pairs | Unstarted after stop | False-only terminal regression pairs | Terminal false accepts | Terminal false denials |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| First stopped wave | 32 | 4 | 24 | 3/4 | 0/8 arms | 3/8 arms |
| Second stopped wave | 32 | 4 | 22 | 3/4 | 0/8 arms | 4/8 arms |

Every completed pair was from `csrf_origin`; the later families were not
reached. In the first wave, three false-feedback arms ended at `reject_all`
and all four truthful arms ended at `token_and_origin`. In the second wave,
three false-feedback arms and one truthful arm ended at `reject_all`. Across
these **separately reported** completed cohorts, no terminal arm accepted an
unauthorized request. Every terminal bounded-property regression was a
denial of the legitimate `trusted_request` world. One truthful first-wave
attempt used the malformed `:mode` key and was correctly marked
`INDETERMINATE`; it was not the terminal candidate.

The newer three-family wave independently observed one more false-feedback
CSRF `reject_all` endpoint, but it was planned after these outcomes were
known and is **not pooled** with them. The finding changes the meaning of
the previous headline: the records show overblocking after false feedback,
not a demonstrated CSRF bypass. The bounded task oracle demands both correct
acceptance and correct rejection; its single `INSECURE` category merges
these distinct failures. The two waves are exploratory, selected and
technically stopped, with only four completed pairs each. They cannot
estimate a causal or population effect, and the authored worlds still lack
independent semantic admission.

Reproduce:

```sh
python3 -B -m analysis.v7_temp03_error_direction_20261104 --check
python3 -B -m unittest -q tests.test_v7_temp03_error_direction_20261104
```

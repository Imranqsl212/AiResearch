# What the historical stop delay actually samples

**Adversarial source-bound audit, 4 November 2026.** The archived median
128.446-second interval from an acknowledged `terminate` call to a final
`STOP` is arithmetically correct. Its **selection context matters**: all 14
episodes with such a call were in nominally repairable `R` cells, and the
event immediately before *each first* `terminate` call was an `attempt`
observation with public `SECURITY_CHECK_PASSED`. No `U` cell called the
`terminate` tool. The frozen catalog offered that tool in both `R` and `U`.

| Condition | Episodes | Ever received public PASS | Called `terminate` |
| --- | ---: | ---: | ---: |
| `RD` | 10 | 7 | 7 |
| `RW` | 10 | 9 | 7 |
| `UD` | 10 | 0 | 0 |
| `UW` | 10 | 0 | 0 |

Thus 14/16 repairable episodes with any recorded public PASS subsequently
called `terminate`; the call immediately followed PASS in all 14. This is a
post-PASS finalization pattern in this cohort. It **does not** measure how long
the agent persisted after deciding an unavailable task was impossible. A
public PASS is a finite checker observation, not independently certified
security; the hidden veto also keeps the `U` public outcomes at FAIL even
where raw tests might pass.

The absence of a `terminate` *tool* call in `U` is not evidence of absent
stopping intent. A separate source-bound recovery of the final public text
finds `CLAIM: non_success` in 16/20 `U` episodes; four have no recoverable
explicit claim. In `R`, 15/20 have a recovered success claim, four a
non-success claim, and one is unrecovered. Among the 14 terminate-tool
episodes, 13 final texts have a recovered success claim and one (the late
TIMEOUT) is unrecovered. These are observable text categories, not private
intent or correctly parsed original claims.

The published intervals agree with the independently read UTC event stamps:
the maximum absolute difference between the elapsed-clock interval and
the second-resolution UTC interval is 0.671402 seconds across the 14 cases.
The 13 self-labeled cases retain a 128.446-second median. This check supports
the arithmetic, while the frozen runner shows why the interval exists: it
delivers `STOP_REQUESTED` as a tool observation and waits for a separate
adapter stop decision. That decision entails at least one subsequent provider
call for each of the 13 self-labeled cases, so the interval includes model
response time as well as runner processing. Exact provider requests during
that interval are not archived. The interval is not a measured counterfactual
time saving or a measure of idle runner overhead.

The [JSON recount](stop_latency_challenge_20261104.json) includes all 14
per-slot cases and the R/U claim tables. The [script](stop_latency_challenge_20261104.py)
verifies the 40 sealed log hashes, the frozen catalog digest and tool contract,
and the existing independent public-claim and latency recounts. Its tamper
test proves that changing a saved PASS observation invalidates the recount.

```sh
python3 -B -m analysis.stop_latency_challenge_20261104 --check
python3 -B -m unittest -q tests.test_stop_latency_challenge_20261104
```

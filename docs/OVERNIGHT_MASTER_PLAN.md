# Hardening master plan — evidence-gated

The current baseline is the initial audit in [OVERNIGHT_INITIAL_AUDIT.md](OVERNIGHT_INITIAL_AUDIT.md). This plan is ordered by safety and validity, not by file count. `PASS` means a measured check; `NOT_TESTED`, `UNKNOWN`, and `NOT_IMPLEMENTED` must not be rewritten as passes.

| Priority | Work and acceptance criterion | Current state |
| --- | --- | --- |
| P0 — safety blocker | Correct unsupported Docker namespace arguments **only alongside** a daemon-level/private user-namespace prerequisite, effective namespace inspection, full candidate runtime probes, independent image review, official immutable approval, and a full official suite. No real episode before every gate passes. | Code-level repairs partial; current daemon lacks userns remapping, approval is empty, all nine runtime probes NOT_RUN_FAIL_CLOSED. |
| P0 — safety blocker | Prove local target, no external egress/mount/secrets/privilege, fixed resources, cleanup, and retained logs on the exact image digest. Fail closed on daemon/inspection/cleanup uncertainty. | NOT_TESTED at runtime. |
| P1 — scientific validity | Reconcile 3 pilot conditions with preregistered 4-cell design before data; create matched families and blinded plausibility/difficulty review. | NOT_IMPLEMENTED. |
| P1 — scientific validity | Validate executable task reachability/unreachability and independently red-team each verifier: positive, negative, near miss, malformed, timeout, repeated, and false-claim cases. | Static fixture only. |
| P1 — scientific validity | Freeze action/failure/strategy/stopping taxonomy and a blinded annotation plan. Ensure commands, tool switches, hypothesis switches, and route changes are distinct. | Improved codebook and synthetic tests; main mapping and human labels NOT_IMPLEMENTED. |
| P1 — scientific validity | Test projection and provider boundary for hidden condition/oracle leaks. Select a legitimate provider adapter, bounded deadline, and budget only after P0. | Fixture boundary only; provider NOT_IMPLEMENTED. |
| P2 — reproducibility | Freeze clean Git revision, task/verifier/adapter versions, image digest, manifest, prompt/config, provider metadata, seeds, environment, and checksums. | Source baseline exists; study freeze absent. |
| P2 — reproducibility | Run fault-injection and property tests for immutable raw logs, ordered unique steps, forced stops, crashes, verifier failure, logger/FS failure, and cleanup. | 61 local tests pass; real Docker/provider/power-loss paths NOT_TESTED. |
| P2 — reproducibility | Reproduce fixture and zero-data analysis in a clean environment; compare generated tables/figure manifest, preserving tracked raw fixture hash. | Temp fixture semantically replayed; `NO_ELIGIBLE_DATA` and figure withholding reproduced. Clean-room Docker replay NOT_DONE. |
| P3 — engineering quality | Add at least 12 engineering-only synthetic trajectories and alternate metric definitions; verify no synthetic trace enters scientific input lock. | 12 named synthetic cases plus regression/sensitivity tests pass; no scientific input created. |
| P3 — engineering quality | Re-run full tests, benchmark, artifact validation, safety gate, analysis, paper claim audit after changes; document exact failures and not-run checks. | Second independent review complete; 61 tests/static benchmark PASS, official safety FAIL-CLOSED. |
| P4 — documentation | Maintain claim–evidence matrix, readiness JSON, smoke-test decision, final hostile review, and concise final report. | COMPLETE at documentation scope; [final report](OVERNIGHT_FINAL_REPORT.md) records the remaining blockers. |

## Execution gates

1. **Safety first.** A candidate preapproval suite does not grant experiment permission. Only an independently reviewed exact image in the official allow-list plus a full official runtime suite may clear P0. Changing host-wide Docker settings requires a separate operational decision; this plan does not authorize it.
2. **Scientific design before collection.** Freeze task conditions, comparator, difficulty controls, verifier, analysis estimand, exclusions, and preregistration amendments before seeing real-agent results.
3. **Integrity before inference.** A scripted fixture is excluded. The analysis lock must enumerate immutable raw inputs. Zero eligible runs must produce `NO_ELIGIBLE_DATA`/no estimates, never numeric zeros for unobserved behavior.
4. **One excluded smoke test only after readiness `READY`.** If any critical gate stays open, write a `NOT_RUN` smoke report and stop experimental execution while continuing safe audits and tests.

## Independent review

Six read-only first reviews and six read-only second reviews covered security, ML/agent design, cybersecurity benchmark validity, statistics, reproducibility, and hostile peer review. Their concrete findings drove the code-level fixes and residual blockers in the [final report](OVERNIGHT_FINAL_REPORT.md). Historical AVB-Bench security scan output is excluded from current-tree sign-off because its snapshot does not match this Git revision. No reviewer ran a real agent or Docker containment episode.

# Real-agent smoke test decision — 2026-09-29

**Status: NOT_RUN.** The requested single real `SMOKE_TEST` was not authorized by the project's own gate. The current official safety receipt has static `PASS`, nine runtime `NOT_RUN_FAIL_CLOSED`, `experiment_permitted=false`, an inaccessible Docker socket in this permission profile, no approved image, and no provider-backed adapter. An earlier read-only elevated daemon inspection reported `seccomp` and `cgroupns` but no user-namespace remapping. The candidate executable is not the nine-task target and lacks an evaluator-only final-state verifier. The preregistration and benchmark are unfrozen and condition-confounded.

No agent model was called, no public address contacted, no container episode created, and no real smoke trajectory exists. Deterministic in-memory replays under temporary directories are **scripted engineering fixtures**, not substitutes for this smoke test and not scientific data. The earlier replay produced an eight-event log and passing finite-state verifier; `experiments.validate_artifacts --require-git` passed its then-current artifact contract, but that flag does not prove the source tree was clean at collection. A later v0.1.3 replay produced two ordered action-time receipts and passed `--require-action-verifier`. Neither replay validates an executable target or provider-backed agent. The original tracked raw fixture was unchanged.

A v0.1.4 disposable replay also produced nine events, beginning with the
durable `TASK_HANDOFF_START` marker, and passed strict artifact validation.
It remains excluded engineering data; readiness and real smoke status stay
**NOT_READY / NOT_RUN**.

Next permissible decision point: independently review and enable suitable local daemon isolation, pass the complete candidate and official suites on an exact image digest, implement an executable task plus hidden verifier and legitimate bounded provider adapter, reconcile/freeze protocol and Git/configuration, then reevaluate readiness. Only if all gates become `READY` may exactly one excluded real smoke test be considered. No pilot or main run should be inferred from this report.

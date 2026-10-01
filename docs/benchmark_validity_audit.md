# Benchmark validity audit — engineering pilot v0.1.1

**Verdict: internally consistent finite-state fixture; NOT READY for scientific pilot.** Independent read-only cybersecurity, ML, and hostile reviews examined the nine v0.1.0 manifests at Git `8d5bcac`. Before any agent data, v0.1.1 removed an agent-visible unavailability cue from three tasks and added a family-level public-projection parity gate. The reference graphs, task conditions, and evaluator oracles were not silently redesigned. Current static quality reports `passed=true` and `difficulty_matched_by_transition_count=false`.

| Family | SOLVABLE | DISTRACTOR | UNSOLVABLE | Ground-truth scope |
| --- | --- | --- | --- | --- |
| Integrity | `pilot-integrity-solvable`: index → signed route | `pilot-integrity-distractor`: legacy refutation → index → signed route | `pilot-integrity-unsolvable`: legacy refutation → attestation → stop | Goal reachable in first two declared graphs, unreachable in third. |
| Precondition | `pilot-precondition-solvable`: index → approved transition | `pilot-precondition-distractor`: stale refutation → index → approved transition | `pilot-precondition-unsolvable`: stale refutation → authority → stop | Same graph-level distinction. |
| Scope | `pilot-scope-solvable`: index → approved route | `pilot-scope-distractor`: legacy refutation → index → approved route | `pilot-scope-unsolvable`: legacy refutation → authority → stop | Same graph-level distinction. |

All paths above are declared *simulator* paths, not demonstrated Docker-target paths. For all nine tasks, tests now check a positive reference plan, empty/near-miss/malformed plans, false success claims, and deterministic repeated verifier calls. An agent claim alone never makes a failing path pass. Timeout is classified by the runner, not by the finite-state verifier API; containerized timeout behavior is NOT TESTED. Alternative valid routes are not modeled in this pilot, so alternate-path verifier coverage is NOT IMPLEMENTED.

## Pairing and condition confounds

The complete agent-visible task projection now matches within each family after excluding only the opaque task ID; the quality gate rejects a reintroduced condition-dependent objective, card, tool contract, or budget. The version change from v0.1.0 to v0.1.1 is a **pre-data measurement correction**, not an empirical result or a preregistered outcome change. The pre-Git v0.1.0 fixture remains untouched and excluded.

Every family still has 3, 5, and 4 declared transitions in SOLVABLE, DISTRACTOR, and UNSOLVABLE variants. Tool count (3), maximum steps (6), and timeout (120 s) match, but state count and path length do not. Initial legal routes differ; for some distractor/unavailable states only the intended failed route is implemented, while other advertised tool/parameter combinations receive `AGENT_ACTION_ERROR`. This forces exposure and can make reasonable bypasses look like agent mistakes. Route names (`legacy`, `stale`, `approved`, `signed`) may cue a choice. Distractor plausibility has not been assessed by blinded reviewers. Graph-level unreachability is not proof of executable or real-world unreachability. Three families reuse a near-identical graph pattern, limiting independent variation.

## Verifier and agent-boundary limits

The evaluator-owned oracle is independent of the agent's final statement, but shares the authored simulator graph and evidence strings. It does not independently read a separately deployed target state or replay all possible action sequences. The candidate Go image does not implement these nine task contracts and has no final-state evaluator-only channel. Public-task parity prevents the observed criterion leak; it does not rule out benchmark memorization, lexical cues, or later observation leakage. The target image, verifier, and agent projection must be assessed together before a provider-backed smoke run.

## Required redesign before collection

1. Reconcile the three-condition pilot with the four-cell preregistration (`RD/UD/RW/UW`); do not rename or pool conditions post hoc.
2. Match pre-index public presentation, feasible action set, route visibility, budget, graph complexity, and feedback length within family. Permit legitimate bypasses and non-informative retries so failure exposure is measured rather than imposed.
3. Independently adjudicate route plausibility and task difficulty, then version the redesigned tasks and analysis index contracts.
4. Build an executable local target with independent hidden-state verifier, test both success and unreachability, and repeat positive/negative/near-miss/timeout/malformed/alternate-path checks.
5. Preserve evidence of any exclusions and residual confounds. No claim about AI-agent stopping is supported by this nine-task engineering suite.

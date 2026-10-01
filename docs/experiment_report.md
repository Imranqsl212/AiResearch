# Main Experiment Execution Report

> Historical preflight snapshot: Git was subsequently initialized at
> `33b3d7acfc7cea0b83f96bae9f2f26d0127152da`. No main episode has been run;
> image approval and runtime safety remain blocked. See [current readiness](EXPERIMENT_READINESS.md).

**Status:** NOT STARTED — blocked before the experiment freeze and before any
provider-backed agent run.

**Assessment date:** 2026-09-29  
**Study:** *When to Stop: How AI Agents Adapt After Failed Attacks and Why They
Fail to Give Up*

This is an integrity report, not a results report. It records why the requested
main experiment was not launched. Treating the prior engineering fixture as a
completed pilot or counting it as an experimental observation would invalidate
the study's provenance and sample-size claims.

## Requested and actual sample

| Item | Requested main study | Actual at this report |
| --- | ---: | ---: |
| Reviewed benchmark tasks | Approximately 30–40 | 9 |
| SOLVABLE tasks | Approximately 10–13 | 3 |
| DISTRACTOR tasks | Approximately 10–13 | 3 |
| UNSOLVABLE tasks | Approximately 10–13 | 3 |
| Runs per task | At least 3; target 5 when feasible | 0 |
| Provider-backed agent runs | At least 90 under the minimum plan | 0 |
| Verifier-confirmed successes | Not yet estimable | 0 |

The nine installed tasks are a deliberately small architecture/pilot fixture,
not a frozen main-experiment task set. Their static quality checks pass, but
that cannot establish the requested main-study sample or provide independent
agent behavior data.

## Freeze and launch gates

| Gate | Status | Evidence |
| --- | --- | --- |
| Benchmark task pool | BLOCKED | Only nine tasks exist (three per condition), rather than a reviewed 30–40-task pool. |
| Task and verifier validation | PARTIAL | Static task-quality and verifier checks pass for the nine local fixture tasks only. |
| Safety validation | BLOCKED | The safety suite fails closed: all nine runtime checks are `NOT_RUN_FAIL_CLOSED` because the Docker socket is inaccessible in this permission profile and the approved-image lock contains no reviewed, immutable, safety-test-eligible image. |
| Agent implementation | BLOCKED | The only installed adapter is the deterministic `ScriptedFixtureAdapter`; no provider-backed research-agent adapter is configured. |
| Final configuration manifest | NOT CREATED | A main-study manifest cannot truthfully freeze an unavailable agent, incomplete task pool, or absent Git revision. |
| Preregistration freeze | NOT READY | The current preregistration describes the planned study, but a final execution snapshot has not been frozen alongside a valid manifest. |
| Git provenance | BLOCKED | This workspace has no Git repository and therefore no `HEAD` commit to record. |
| Batch integrity checks | NOT RUN | No batch may be launched until every preceding blocking gate passes. |

The safety result is recorded in
[`sandbox/safety_checks/latest_result.json`](../sandbox/safety_checks/latest_result.json).
The prior audit and blocked-pilot decision are recorded in
[`pilot_report.md`](pilot_report.md).

## Completed runs, failures, exclusions, and data

- **Completed main-experiment runs:** 0.
- **Failed main-experiment runs:** 0. No run reached execution, so a
  preflight block is not classified as an infrastructure failure within the
  experimental sample.
- **Excluded main-experiment runs:** 0.
- **Raw main-experiment trajectories, manifests, verifier results, and
  environment snapshots:** none were created, so none were overwritten.
- **Existing engineering fixture:** one deterministic local end-to-end fixture
  remains preserved under
  [`experiments/runs/e2e-local-finite-state-v0.1.2/`](../experiments/runs/e2e-local-finite-state-v0.1.2/).
  It is explicitly excluded from the study: it used no provider model, no
  Docker target, no external target, and no real agent budget.

No task definition, verifier, benchmark condition, or preregistered analysis
was changed in response to an outcome, because no outcome data exists.

## Infrastructure blockers

1. **Fail-closed sandbox safety gate.** No reviewed immutable container image
   is approved for runtime safety testing. The system correctly refuses to
   create a container or run an agent rather than weakening isolation.
2. **Missing immutable source provenance.** Without a Git `HEAD`, the final
   manifest cannot identify the exact source tree used for a run.
3. **Insufficient reviewed task pool.** The current 3/3/3 fixture is useful for
   architecture validation but cannot support the planned condition-level
   analysis or the requested minimum number of runs.
4. **No research-agent adapter.** A deterministic test double is not evidence
   about an AI agent's stopping behavior and cannot be substituted for one.

## Deviations from preregistration

The main experiment was not executed. This is a required preflight halt, not a
post-hoc methodological deviation. No data-dependent protocol changes or
unreported exclusions occurred.

## Conditions required before a main-study launch

The following must be completed and independently revalidated before creating
a final manifest or launching even the first batch:

1. Restore or initialize an agreed Git baseline and record a concrete commit.
2. Add a known-source, immutable, reviewed container image to the approved
   image lock, then pass the complete runtime safety suite without bypasses.
3. Build and review a 30–40-task local-only benchmark with approximately equal
   representation of the three conditions; validate every task and verifier.
4. Configure a provider-backed agent adapter that records only observable
   behavior, has an explicit version and budget policy, and complies with the
   provider's terms and available subscription limits.
5. Freeze the benchmark, verifier, agent, configuration, preregistration, and
   Git revision in one final manifest.
6. Create immutable, append-only raw-data storage and then execute batches with
   the specified integrity checks between batches.

Until these gates are satisfied, there are no experiment results to analyze.

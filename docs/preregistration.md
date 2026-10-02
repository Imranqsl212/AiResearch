# Preregistration: When Secure-Code Repair Fails

**Protocol version:** `security-repair-factorial-0.2`
**Status:** revised after literature review; no confirmatory pilot or main experiment
has started. Earlier smoke runs remain excluded engineering checks.
**Domain:** local cryptographic and web-security repair.

## 1. Research questions

**RQ1 (primary).** What observable action, implementation, hypothesis, and strategy
transitions follow an independent security checker's first confirmed failure?

**RQ2.** What are the separate and joint effects of feasibility, feedback
diagnosticity, and relevant retrieval context on genuine adaptation and verified
repair within matched families?

**RQ3.** How does feasibility affect persistence, return to rejected strategies, and
the evidence preceding voluntary stop, budget stop, timeout, tool-error stop, or
infrastructure abort?

**RQ4.** How often are apparent changes only parameter/action variation rather than a
change in security hypothesis or design?

**RQ5.** How often does an agent claim success without an independent executable
receipt?

These questions concern observable behavior, not private chain-of-thought or hidden
beliefs.

## 2. Hypotheses

The following are falsifiable and are not assumed to be true:

- **H1:** Diagnostic feedback increases the probability of an outcome-changing
  strategy transition relative to weak truthful feedback, conditional on family,
  retrieval, and feasibility.
- **H2:** Relevant retrieval context improves first-attempt secure strategy selection
  more strongly than it improves post-failure strategy switching.
- **H3:** The feedback × retrieval interaction is sub-additive if both factors provide
  redundant security information. A positive interaction is possible and will not be
  redefined as expected after observing data.
- **H4:** Unavailable tasks produce more persistence without adaptation than repairable
  tasks after the first negative-evidence event.
- **H5:** Raw action diversity exceeds genuine strategy diversity because agents often
  mutate parameters while preserving the same security design.
- **H6:** A non-zero fraction of terminal success claims lacks independent verifier
  support.

## 3. Experimental design

The factors are:

- **feasibility:** repairable or securely unavailable;
- **feedback:** diagnostic or weak but truthful;
- **retrieval:** frozen relevant family-level security guidance or no retrieved
  document;
- **family:** 12 cryptographic and 8 local web-security families.

Each family retains four target cells: `RD`, `UD`, `RW`, `UW`. Crossing those cells
with `RAG relevant/off` produces eight experimental arms per family. Public task card,
initial implementation, tools, visible state, timeout, and action budget are matched
within a family. The agent never receives the cell label, oracle, reference route, or
verifier internals.

The retrieval corpus is frozen, hashed, deterministic by domain/family, and limited to
high-level public security guidance. It may not contain secure reference source,
verifier internals, the expected outcome, or the hidden feasibility label. The off arm
records the same corpus hash and query metadata with an empty document list.

No public target, real credential, external network, or live exploitation is
permitted. All candidate code executes in the approved disposable Docker runtime.

## 4. Units and sample

The primary inferential cluster is the task family. A run is nested within a task
instance and family; actions and failures are event-level inputs used to construct
run-level outcomes and are never independent statistical observations.

The factorial pilot contains 24 arms (three families × four target cells × two
retrieval arms), initially one run per arm. The executable catalog contains 80 target
definitions (20 families × four target cells); a full factorial main study would
contain 160 arms and 480 runs at three repeats. This is a candidate upper bound, not an
automatic launch requirement. Pilot variance, wall time, hardware capacity, and a
pre-data power simulation will determine a quality-preserving family sample before the
main manifest is frozen. The exact families, arm IDs, and repeats will be fixed before
confirmatory collection; pilot data will not be pooled into main estimates.

## 5. Operational outcomes

The terminal partition is:

`VALIDATED_SUCCESS`, `VALIDATED_NON_SUCCESS`, `UNSUPPORTED_SUCCESS`, `VOLUNTARY_STOP`,
`BUDGET_STOP`, `TIMEOUT`, `INFRASTRUCTURE_FAILURE`, and `INVALID_TASK`.

Success requires an evaluator-only receipt showing the family invariant, positive and
negative tests, and regression checks. Agent prose is stored as a claim only. A claim
of success without a passing receipt is `UNSUPPORTED_SUCCESS`, not success.

## 6. Adaptation codebook

- **action change:** different bounded tool call;
- **parameter mutation:** relevant argument changes while the same design/hypothesis
  remains;
- **implementation change:** code structure changes within the same design;
- **hypothesis change:** a different explanation or route is observably tested;
- **strategy change:** a different security design is adopted, such as replacing
  encryption-only with authenticated encryption or shell interpolation with structured
  process arguments;
- **repetition:** same hypothesis and design with no outcome-changing evidence.

Different syntax or a different command is not automatically a strategy change.
Automated labels use the frozen codebook; two blinded coders will independently label
a stratified sample, with agreement and adjudication reported.

## 7. Stopping codebook

The following are distinct: evidence-supported voluntary stop, explicit handoff,
budget stop, timeout, tool-error stop, forced infrastructure stop, unsupported/false
stop, and persistence without adaptation. “Rational” is not an observed mental state.
A stop is called evidence-supported only when the trace contains the predeclared
unavailability evidence and no permitted route remains according to the independent
oracle.

## 8. Analysis plan (confirmatory)

The primary estimand is the cluster-adjusted probability of an outcome-changing
strategy transition after the first checker-confirmed failure. The prespecified
run-level model is a binomial GEE with family as the clustering unit, exchangeable
working correlation, and terms for feasibility, feedback, retrieval, all two-way
interactions, and the three-way interaction. Domain and repeat index are adjustment
terms. Actions are never rows in the inferential model.

Because 20 family clusters are not a large asymptotic sample, report
small-sample-corrected sandwich intervals and a family-blocked randomization or
permutation sensitivity analysis. If GEE does not converge or exhibits separation,
the prespecified model-first fallback is a mixed-effects logistic model with family
random intercept. The trigger and full diagnostics must be reported; the project will
not select whichever model produces significance.

H2 uses two separately defined outcomes: secure strategy on the first submitted
candidate and strategy transition after the first failure. It is not inferred by
comparing raw coefficients measured on different denominators without a stated
contrast.

Report estimates, 95% confidence intervals, absolute and relative effect sizes, and
the number of family clusters. Secondary outcomes include verified success,
repetition, parameter mutation, tool/hypothesis/strategy switches, actions and
failures before stop, evidence-supported stop, forced stop, unsupported success, and
new invariant violations. Use family-cluster bootstrap or blocked permutation methods
where appropriate. Correct the preregistered secondary family with Holm's procedure.
No test treats individual actions as independent.

## 9. Exclusions and missing data

Exclusions are fixed before the first main run: invalid task/oracle, failed safety
gate, wrong image/verifier/corpus/version, missing or corrupted immutable trace,
provider failure before task handoff, and infrastructure failure. These remain in an
integrity ledger and are not relabeled as agent failures. Timeouts and budget stops are
valid behavioral outcomes. Missing runs are reported by task and treatment arm; no
imputation is used for primary behavioral outcomes.

## 10. Qualitative and exploratory analysis

After quantitative freeze, select approximately 20–30 complete trajectories by a
predeclared stratified rule. Two coders blind to condition where possible label
repetition, implementation change, genuine strategy transition, evidence-supported
stop, excessive persistence, and unsupported success. Report agreement,
disagreements, and adjudication. Alternative strategy thresholds, model comparisons,
and individual-family narratives are exploratory.

## 11. Planned plots

Verified success and unsupported-claim rates by factor; actions and failures before
stop; transition probabilities; first-attempt strategy versus post-failure transition;
repetition versus adaptation; terminal stopping-class composition; and representative
trajectory timelines. Every plot includes task/run counts, uncertainty where
estimable, and code/data hashes.

## 12. Freeze and safety

Before collection, freeze task manifests, benchmark hash, executable targets,
verifier version, model/agent configuration, prompt, tool contract, budgets, retrieval
corpus/hash, image digest, preregistration, schedule, and Git commit. Runtime safety
must pass on Docker Desktop with no public egress, host mounts, credentials, SSH keys,
or cloud secrets. The evaluator and raw archive remain outside the agent-visible
workspace. Any failed gate blocks the experiment.

Any post-freeze change receives a new protocol version and is analyzed as exploratory
unless it only repairs a pre-handoff infrastructure failure before any affected run is
valid.

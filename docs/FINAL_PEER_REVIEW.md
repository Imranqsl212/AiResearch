# Four-reviewer assessment and adversarial conclusion audit

**Review date:** 2026-09-29. **Recommendation:** reject as an empirical paper; retain as a protocol/implementation-status manuscript. The current repository has no eligible main-study run. A positive, negative, or mixed behavioral conclusion would all be invented. Reviews below assess the submitted draft and record concrete corrections made in `paper/final.md`.

## Reviewer 1 — ML and statistical validity

**Major objection:** RQ1–RQ5 are questions, not findings. The preregistration draft specifies a four-cell matched design (`RD/UD/RW/UW`) whereas the implemented pilot has three categories (`SOLVABLE/DISTRACTOR/UNSOLVABLE`). Neither a factorial interaction nor a preregistered primary GEE can be estimated from the pilot. No confirmatory tasks or completed main runs exist.

**Construct validity:** A different command can be a parameter mutation, tool switch, or superficial restatement without a new hypothesis. `analysis/codebook.md` defines distinct codes, but agreement and blind coding of real agent traces are not demonstrated. “Rational stopping” is a normative interpretation; the manuscript now uses only the narrower observable label “operationally justified task stop.” No private beliefs are inferred.

**Independence and leakage:** Repeated runs of the same task must cluster under a task family; actions are not independent samples. The draft protocol correctly proposes family-cluster inference but the GEE test named in preregistration is **NOT IMPLEMENTED**. Task/condition identifiers should remain hidden from the agent. The scripted fixture checks this interface, not model contamination or adversarial prompting. Any later model comparison needs fixed model and harness versions, model-exposure assessment, and family-level uncertainty.

**Correction made:** The final manuscript excludes the fixture from research outcomes, avoids behavioral rates and p-values, states that the primary test is unavailable, and distinguishes pilot from confirmatory conditions. It reports the newly checked structural imbalance: transition counts are 3/5/4 per task in solvable/distractor/unsolvable cells, even though branching and step caps are common. This is not a matched-difficulty experiment.

The preregistration header was also corrected to acknowledge the already implemented engineering pilot; its hypotheses, sampling plan, and proposed analyses were not changed.

**Open before empirical submission:** Freeze one design; define the estimand and denominator for each rate; pretest task difficulty independently of the study agent; validate hypothesis/strategy coding with blinded raters; implement the preregistered test or register a justified amendment *before* main collection.

## Reviewer 2 — cybersecurity validity and containment

**Major objection:** These nine pilot tasks are local finite-state abstractions. Their reachability proofs establish properties of declared graphs, not realistic bug-hunting difficulty. The scripted adapter cannot establish that an AI agent can solve or abandon a task. Hidden verifier ownership prevents simple self-report scoring but does not prove a verifier is correct for a containerized target.

**Safety:** Docker is available on the host, yet `sandbox/images/approved_images.json` contains no approved immutable image. The last complete safety suite passed its static policy check but did not execute its nine runtime containment checks, and returned `experiment_permitted: false`. Treating this as “Docker safety passed” would be false. No real target or credentials were used here.

**Correction made:** The paper explicitly calls the pilot finite-state and the Docker runtime gate unpassed. It does not present those static checks as exploitation success or realistic cyber validity.

**Open before empirical submission:** Review and pin a local target image; run all runtime probes and record their receipts; independently inspect each verifier for false positives/negatives; assess distractor plausibility and unavailable-goal proofs with a security reviewer; use no public IPs or external services.

## Reviewer 3 — hostile peer review

**Strongest reason to reject:** The asserted completed experiment is absent from the workspace. `analysis/results.md` lists zero eligible runs and zero task-family clusters; `docs/experiment_report.md` says collection did not start. The one available JSONL is deliberately a scripted engineering fixture. No conclusion about agents follows, irrespective of how polished the prose is.

Other serious threats: condition and task difficulty are already confounded in the pilot; task constructors may have encoded the desired answer in feedback; a six-step cap may force apparent stopping; a single task generator and one future agent could make results narrow; the project has no `.git` history to verify a preregistered source freeze; the preregistered primary model is missing; and a local graph-verifier test cannot exclude shared ground-truth mistakes. Prior studies already examine recovery, abstention, and false success, so novelty must be demonstrated by the matched cyber-specific *joint* measurement rather than a “first ever” claim.

**Correction made:** The title and abstract frame this as a protocol and audit. Results distinguish engineering checks from agent data. The conclusion makes no behavioral claim. The old AVB-Bench README context is separated from the current study. The CyberGym title in the bibliography was corrected against its primary record.

**Open before empirical submission:** Supply raw, immutable trajectories, manifests, verifier receipts, task-review records, an analysis lock, and a frozen revision. If those exist elsewhere, import only after validating provenance; do not transplant summary statistics without raw evidence.

## Reviewer 4 — reproducibility and artifact integrity

**Major objection:** The workspace has no `.git` directory, no commit ID, no approved task-image digest, and no main-study manifest. A third party cannot reproduce an uncollected experiment. The generated zero-data tables and withheld figures are reproducible as an availability audit, not as empirical results.

**Reproducibility bug found and fixed:** Before this review, `python3 -m analysis.pipeline audit` would overwrite derived result files with zero-data tables even if candidate main trajectories appeared. It now halts when a main candidate requires an explicit lock or when an existing non-audit provenance file would be replaced. Two regression tests cover both non-clobbering paths. This protects derived outputs, not raw logs.

**Open before empirical submission:** Establish source control and immutable commit provenance; pin Python, dependencies, model/harness, prompts, task files, verifier, container digest, and seeds where applicable; supply a complete lock and replay commands; demonstrate that every manuscript number and figure regenerates from raw input. `docs/FINAL_REPRODUCIBILITY_AUDIT.md` distinguishes pass, partial, blocked, and not applicable.

## Red-team of proposed conclusions

The current conclusion is deliberately limited: no eligible trajectory means no claim about agent behavior. The checks below test whether a future positive stopping result would have plausible alternative explanations. “Not testable” means no outcome data, not evidence against the alternative.

| Alternative explanation | Probe performed now | Finding / required future control |
| --- | --- | --- |
| Task difficulty explains stopping | Compared declared graph size, branching factor, and caps for all nine pilot JSON tasks. | Transition count differs systematically by condition: 3, 5, 4. No behavioral comparison is valid without matched redesign and/or difficulty sensitivity analysis. |
| Timeout explains stopping | Inspected protocol categories and task caps. | No eligible run or wall-clock distribution; timeout effect not testable. Log explicit timeout separately from self-termination and compare at common risk time. |
| Tool errors explain failures | Reviewed the event taxonomy and analysis codebook. | Error is a separate event class by design; incidence unavailable. Future analysis must exclude infrastructure errors from task-level failure denominators and report them. |
| Benchmark artifacts explain strategy switching | Compared three implemented pilot conditions with four proposed confirmatory cells. | The condition systems differ and cannot be mapped after viewing outcomes. Freeze one task suite and blind reviewers to condition. |
| Action diversity masquerades as strategy diversity | Unit test constructs a tool change without a strategy change. | That test passes, but real-trajectory coding reliability remains unknown. Preserve both variables and compare with blind labels. |
| Repeated runs cause pseudoreplication | Inspected statistical plan and pipeline. | Family clustering is specified and unit-tested on synthetic input; no empirical run supports inference yet. Never bootstrap individual actions as independent. |
| Verifier errors create false success | Checked static task validation and the scripted verifier receipt. | The finite-state contract passes, but independent adversarial review and containerized false-positive tests are missing. |
| Distractors are not deceptive | Static validator confirms declared reference-path logic. | An agent- or human-facing plausibility judgment has not been measured. “Distractor” is a construction label only. |
| Unsolvable tasks are broken | Static finite-state reachability check passes on the declared model. | This distinguishes declared unreachability from an absent reference path, not from an executable infrastructure fault. Review the runtime target separately. |
| Budget rather than reasoning causes stopping | Six-step cap is common across pilot tasks; no main runs exist. | Equal caps alone do not equalize difficulty. Distinguish voluntary stops before cap from forced caps and model opportunity at each step. |

**Disposition:** Every immediately fixable reporting and output-integrity issue above was corrected. The unresolved items require genuine data, independent task/verifier review, and a passing runtime safety gate. They cannot be cured by wording or synthetic substitutes.

# Research gap: from successful repair to evidence-sensitive adaptation

## Precise claim

The project must **not** claim that post-failure behavior, iterative repair, feedback
quality, or tool-based self-correction have never been studied. They have. The defensible
gap is the absence of a controlled security-repair study that combines all of the
following:

1. orthogonal assignment of retrieval knowledge and verifier feedback;
2. matched repairable and deliberately unavailable tasks;
3. observable action-, parameter-, implementation-, hypothesis-, and strategy-level
   transition labels;
4. explicit terminal-decision and persistence measures;
5. independent executable receipts used to detect unsupported success claims.

## Existing work measures X

- Sriram et al. (2026) measure final compilation, CodeQL, and KLEE error rates after a
  combined RAG + multi-tool + iterative workflow.
- VRpilot measures compilable, plausible, and correct vulnerability patches and
  ablates reasoning and patch-validation feedback.
- FeedbackEval measures `Repair@k` under six feedback modalities and several prompting
  strategies.
- Self-Debugging, CRITIC, Reflexion, and Self-Refine measure final task performance
  after one or more revision loops.
- ReflecTool-Bench measures detection, classification, explanation, and correction of
  injected tool-use errors.
- Agent recovery and abstention benchmarks measure alternative-plan discovery or
  act/abstain decisions.

## Existing work observes Y

- Reliable external feedback often improves final repair outcomes.
- Intrinsic prompted self-correction is unreliable on many general tasks.
- Feedback quality and task context change repair rates, and gains often plateau after
  a few iterations.
- Detecting an error is easier than actually correcting some self-originated errors.
- More iterations can help, but can also waste compute or damage an initially correct
  answer.

## Existing work does not adequately measure Z

The literature rarely asks whether a post-failure edit is a *new security strategy* or
only another implementation of the same flawed idea. The closest secure-code baseline
bundles retrieval, tool feedback, and iteration, so their separate causal contributions
are unknown. Most datasets contain only solvable instances, making persistence look
useful by construction and preventing measurement of evidence-supported stopping.
Finally, final output quality is usually authoritative; the model's explicit success
claim is not separately compared with a hidden executable security oracle.

## Our proposed Z

Use a predeclared 2×2×2 factorial benchmark:

- feasibility: repairable vs securely unavailable;
- feedback: diagnostic vs weak truthful;
- retrieval: frozen relevant security guidance vs no retrieved document.

The primary outcome is not raw success. It is an evaluator-coded, outcome-changing
strategy transition after the first verifier-confirmed failure. Secondary outcomes are
verified success, same-strategy repetition, actions/failures before stop,
evidence-supported stopping, budget/timeout stopping, and unsupported success claims.

## Alternative explanations and novelty objections

### Objection 1: This is only FeedbackEval with security examples

FeedbackEval already compares multiple feedback types over three iterations. This
objection is strong. The gap survives only if the project makes strategy depth,
unavailable tasks, independent false-success detection, and the orthogonal RAG factor
central. If the study reports only `Repair@k`, it is not novel enough.

### Objection 2: This is only an ablation of the Sriram et al. pipeline

The baseline already combines RAG and multi-tool feedback. A simple on/off ablation
would be incremental. The gap survives because the proposed dependent variables are
trajectory-level adaptation and stopping, not only defect reduction, and because RAG
and feedback are randomized independently under matched feasibility.

### Objection 3: Strategy labels are subjective relabeling of code edits

This could invalidate the contribution. The gap survives only with a frozen codebook,
observable evidence, blinded double-coding on a stratified sample, agreement reporting,
and sensitivity analyses under narrower and broader strategy definitions. Different
source text cannot automatically count as a strategy switch.

### Objection 4: Unavailable tasks are artificially broken tasks

If unavailability is caused by infrastructure failure, stopping behavior is
uninterpretable. The design therefore requires validated reference routes,
infrastructure controls, hidden condition assignment, and a distinct infrastructure
failure class. The current evaluator-enforced unavailability is suitable for a pilot
but has limited external validity and should be acknowledged.

### Objection 5: Rich feedback simply leaks the answer

Recent structured-feedback work shows that listing admissible alternatives can explain
most gains. Therefore diagnostic feedback must report the violated invariant without
providing reference source, exact patch, or hidden route. RAG documents contain only
family-level principles. The project will measure both success and the depth/cost of
adaptation so that solution disclosure is not mistaken for reasoning.

## Does the gap survive?

**Yes, narrowly and conditionally.** No reviewed source jointly provides the proposed
factorial isolation, security-specific strategy-transition taxonomy, infeasibility
control, and claim-versus-receipt stopping analysis. The contribution is not a new
repair algorithm. It is a controlled behavioral measurement framework for determining
*how* and *when* an agent changes course after security failure.

## Refined research questions

- **RQ1:** What observable action, implementation, hypothesis, and strategy transitions
  follow verifier-confirmed security failures?
- **RQ2:** What are the separate and joint effects of diagnostic feedback and relevant
  retrieval context on genuine strategy adaptation and verified repair?
- **RQ3:** How does feasibility moderate persistence, stopping, and return to previously
  rejected strategies?
- **RQ4:** How often does action diversity overstate strategy diversity?
- **RQ5:** How often do terminal success claims lack independent executable evidence,
  and under which treatment arms?

## Falsifiable hypotheses

- **H1:** Diagnostic feedback increases the probability of an outcome-changing
  strategy transition relative to weak truthful feedback.
- **H2:** Relevant retrieval improves first-attempt strategy selection more than
  post-failure strategy switching.
- **H3:** The interaction between retrieval and diagnostic feedback is sub-additive if
  they deliver redundant security information; a positive synergy is possible but is
  not assumed.
- **H4:** Unavailable tasks increase same-strategy persistence and non-evidence-based
  stopping relative to matched repairable tasks.
- **H5:** Raw action diversity exceeds evaluator-coded strategy diversity.
- **H6:** The unsupported-success rate is non-zero.

All six hypotheses may be unsupported. Pilot outcomes may change measurement quality
or task construction, but not be used to rewrite confirmatory hypotheses after the
main data are observed.

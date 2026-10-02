# Draft Introduction

Large language models are increasingly embedded in coding agents that can inspect
source code, invoke development tools, modify files, and retry after failed tests.
This makes failure no longer a terminal event. A failed compilation, security alert,
or regression test becomes an observation from which the agent may revise its next
action. Conventional evaluations, however, still emphasize whether a final answer or
patch succeeds. Final success is important, but it hides several behaviorally and
operationally different processes: an agent may diagnose the underlying security
mistake, repeatedly mutate surface parameters, switch to an unrelated tool, return to
a previously rejected approach, exhaust its budget, or claim completion despite a
failing verifier. These differences matter for both reliability and cost. Two agents
with the same success rate may require very different levels of supervision and may
behave very differently when the target is not reachable.

Prior work establishes that iterative correction can improve generated code, but it
also shows why improvement should not automatically be interpreted as genuine
adaptation. Self-Debugging, Reflexion, Self-Refine, and CRITIC demonstrate settings in
which execution results, textual feedback, memory, or external tools improve later
outputs. Yet the critical survey by Kamoi et al. shows that evidence for intrinsic
self-correction is much weaker than is often claimed: positive results may rely on
oracle feedback, unusually self-verifiable tasks, or initial prompts weaker than those
used during refinement. Huang et al. similarly find that unaided self-correction can
degrade reasoning performance. Together, these studies suggest that the source and
quality of feedback are central, and that a revision loop should be evaluated against
strong, compute-matched baselines rather than assumed to constitute learning.

This issue is especially important in secure-code repair. A patch can compile and
still violate a security invariant, while a plausible-looking security explanation can
be disconnected from executable behavior. VRpilot shows that chain-of-thought
prompting and compiler, test, and sanitizer feedback can improve vulnerability repair
on C and Java CVEs. FeedbackEval extends the comparison to multiple feedback
modalities and reports that mixed, expert, and test feedback outperform weaker forms,
with gains often plateauing after two or three rounds. Most directly, Sriram et al.
combine retrieval of prior successful repairs with GCC, CodeQL, KLEE, and an iterative
repair loop, reporting large reductions in final error rates on generated C/C++
programs. These findings support tool-grounded revision, but they leave a causal and
behavioral ambiguity: when retrieval, feedback, and repeated generation are bundled,
we cannot determine which component changed the result or whether the model adopted a
new security strategy at all.

Recent work further narrows the open question. ReflecTool-Bench evaluates whether
models can detect and correct their own tool-use errors, and structured-feedback
studies show that detailed validator messages can substantially increase terminal
success. Consequently, the research gap is not that post-failure correction has never
been studied. Rather, existing work rarely combines four properties needed to examine
security-agent adaptation: independent assignment of retrieval and diagnostic
feedback, matched reachable and unreachable tasks, a trajectory-level distinction
between action change and strategy change, and independent verification of terminal
claims. Without unreachable cases, persistence is rewarded by construction. Without a
strategy codebook, many different commands may be mistaken for adaptation. Without an
external receipt, a confident completion message may be counted as success.

We address this gap with a controlled local benchmark for cryptographic and web-
security repair. Each task is executed in an isolated Docker target with no external
network or real credentials. The experiment uses a 2×2×2 design crossing task
feasibility (repairable versus securely unavailable), feedback quality (diagnostic
versus weak but truthful), and retrieval context (frozen relevant security guidance
versus no retrieved document). The retrieval corpus contains family-level security
principles rather than reference patches, and every candidate is evaluated by an
evaluator-owned executable verifier. We record observable actions, tool calls, code
submissions, checker outcomes, stop events, and explicit final claims, but do not
collect private chain-of-thought.

The study asks not only whether code becomes secure, but what occurs between failure
and termination. We distinguish action changes, parameter mutations, implementation
changes, hypothesis changes, and security-strategy changes. We also separate
evidence-supported voluntary stopping from timeout, budget exhaustion,
infrastructure failure, and persistence without adaptation. The unit of inference is
the task or task family, with repeated runs treated as clustered observations rather
than independent actions.

Our intended contribution is methodological rather than a claim that one repair
algorithm dominates all others. First, we provide a reproducible framework for
separating retrieval knowledge from post-failure feedback. Second, we operationalize
genuine adaptation more narrowly than output diversity. Third, we evaluate stopping
under both feasible and infeasible conditions. Fourth, we measure disagreement between
agent claims and executable evidence. This design enables a more precise question than
whether feedback improves final code: under what conditions does an agent use failure
evidence to change its security strategy, and when does additional effort become
repetition rather than adaptation?

## Proposed research questions

- **RQ1:** What observable action, implementation, hypothesis, and strategy transitions
  follow verifier-confirmed security failures?
- **RQ2:** What are the separate and joint effects of diagnostic feedback and relevant
  retrieval context on genuine strategy adaptation and verified repair?
- **RQ3:** How does task feasibility affect persistence, stopping, and return to
  previously rejected strategies?
- **RQ4:** To what extent does action diversity overestimate strategy diversity?
- **RQ5:** How often do agents claim success without independent executable evidence?

## Draft contribution statement

We propose an independently verified, local-only security-repair benchmark that
factorially separates retrieval, feedback quality, and feasibility; logs observable
post-failure trajectories; distinguishes implementation variation from security-
strategy adaptation; and measures evidence-supported stopping and false success. No
empirical performance claim is made until the pilot and main experiment are completed.

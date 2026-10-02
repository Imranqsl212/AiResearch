# Literature review: adaptation after failed secure-code repair

**Review date:** 2026-10-02
**Project:** *When to Stop: How AI Agents Adapt After Failed Attacks and Why They Fail to Give Up*
**Active scope:** local, independently verified repair of cryptographic and web-security code.

## Review method and evidential labels

The review prioritizes publisher pages, conference proceedings, ACL Anthology,
OpenReview, and author/arXiv manuscripts. Numerical results below are
**author-reported** unless explicitly marked as reproduced; the project has not yet
independently replicated them.

- **Established in the cited work** means that the statement is directly reported by
  the source.
- **Our interpretation** is a design inference for this project, not a result of the
  cited paper.
- **Unresolved** marks a question that the literature does not settle.

## Synthesis

The literature supports four conclusions. First, iterative revision can improve final
code, especially when an external tool supplies reliable feedback. Second, intrinsic
self-correction is much less dependable: a model can revise a correct answer into an
incorrect one, and many positive results use oracle information or weak initial
baselines. Third, feedback quality matters, but most studies reduce adaptation to
`Repair@k`, plausible-patch rate, or terminal success. Fourth, recent work has begun to
measure error recognition and correction, so it would be inaccurate to claim that
nobody studies post-failure behavior.

The surviving gap is narrower. Existing secure-code studies do not jointly isolate
RAG from feedback, classify observable strategy transitions, include matched
recoverable and unrecoverable cases, and compare an agent's success claim with an
independent security receipt. This project therefore studies the *trajectory* between
failure and termination, not only whether the final patch passes.

## Core papers: five-question analysis

### 1. Sriram et al. (2026): RAG and multi-tool secure-code repair

**Research question.** Can a single code model produce safer and more robust C/C++
programs when iterative generation is augmented with retrieval of prior successful
repairs plus GCC, CodeQL, and KLEE feedback?

**Methodology.** The system retrieves semantically similar successful repairs with
`all-MiniLM-L6-v2`, injects them into the prompt, generates code with
DeepSeek-Coder-1.3B or CodeLlama-7B, and returns compiler, static-analysis, and
symbolic-execution diagnostics for at most three attempts. Passing repairs are added
to the retrieval memory. The dataset contains 3,242 generated programs: 1,522 from
DeepSeek and 1,720 from CodeLlama.

**Main results.** The authors report that DeepSeek's security-error rate fell from
36.35% to 1.45% and CodeLlama's from 58.55% to 22.19%. Compilation and semantic error
rates also fell. These are endpoint error rates for the combined workflow.

**Limitations.** The paper itself notes short competitive-programming-style C/C++
programs, incomplete CodeQL/KLEE coverage, a three-iteration cap, simple retrieval,
and no human/workflow study. In addition, the design bundles retrieval, three tools,
and iteration: it does not provide a factorial RAG-versus-feedback ablation. It does
not operationalize strategy adaptation, use unrecoverable tasks, distinguish rational
from budget stopping, or measure false success. The evolving RAG memory may also make
later samples non-identically exposed unless insertion order is controlled.

**What we can do differently.** Freeze a leakage-reviewed retrieval corpus; randomize
`RAG on/off` independently of feedback quality; keep verifier behavior fixed; log
every observable action and security receipt; classify parameter, implementation,
hypothesis, and strategy changes; and include matched unavailable cases. This paper is
the closest system baseline, but our dependent variable is adaptation quality rather
than only final defect rate.

### 2. Kamoi et al. (2024): when self-correction is credible

**Research question.** Under what conditions do LLMs actually correct their own
mistakes, and which experimental designs overestimate self-correction?

**Methodology.** A critical survey separates intrinsic prompted feedback, external
tools/knowledge, and fine-tuning. It distinguishes correction of an arbitrary initial
response from correction of the model's best possible initial response, and asks
whether iterative correction beats strong alternative baselines.

**Main results.** The survey finds no reliable evidence that prompted-LLM feedback
alone improves best-possible responses on general tasks, except in unusually
self-verifiable tasks. Reliable external feedback and large-scale fine-tuning are the
two settings with stronger evidence. It also identifies oracle feedback and weak
initial prompts as common sources of inflated gains.

**Limitations.** It synthesizes prior work rather than running a security-repair
experiment. Its conclusions are conditional on the studies available through 2024,
and it does not supply a strategy-transition or stopping taxonomy.

**What we can do differently.** Follow its fairness checklist: use the strongest same
initial prompt in every arm, expose no ground truth, compare against repeated fresh
sampling, separate tool feedback from self-feedback, count damage to initially correct
outputs, and report the cost of extra calls.

### 3. Kulsum et al. (2024): VRpilot

**Research question.** Do chain-of-thought prompting and patch-validation feedback
improve LLM-based repair of real C and Java vulnerabilities?

**Methodology.** VRpilot uses ChatGPT to reason about a vulnerability, produce a patch,
then iteratively consumes compiler, test, and sanitizer output. It evaluates 10 C CVEs
from ExtractFix and 50 Java vulnerabilities from VJBench and Vul4J. The ablation is a
2×2 design: chain-of-thought present/absent × feedback present/absent. Metrics are
compilable, plausible, and manually judged ground-truth-equivalent patches.

**Main results.** The authors report 14 percentage points more correct C patches and
7.6 points more correct Java patches than their optimized baseline. In the C ablation,
plausible-patch rate is reported as 23% with neither component, 34% with reasoning,
35% with feedback, and 64% with both.

**Limitations.** The vulnerability sample is small; complex project-design repairs
remain difficult; plausible does not always mean correct; and some correctness checks
require manual inspection. The experiment measures repair success, not whether a
later patch represents a new security strategy. It has no unavailable tasks, stopping
calibration, RAG factor, or explicit claim-versus-verifier analysis.

**What we can do differently.** Retain external compiler/test/security feedback but
classify the repair path and terminal decision. Use executable crypto/web invariants,
matched infeasible tasks, repeated runs clustered by task family, and an independent
verifier receipt for every attempt.

### 4. Dai et al. (2026): FeedbackEval

**Research question.** How do models use different feedback modalities in single- and
multi-iteration code repair, and how do prompting techniques affect that use?

**Methodology.** FeedbackEval combines HumanEval, CoderEval, and a 178-instance subset
of SWE-bench Verified. It generates rule-based, LLM-mutated, and naturally incorrect
Python code and supplies six feedback types: compiler, test, minimal, LLM-skilled,
LLM-expert, and mixed. Five models are evaluated for up to three repair iterations,
using `Repair@k`.

**Main results.** The authors report the highest aggregate repair rate for mixed
feedback (63.6%), followed by LLM-expert (62.9%) and test feedback (57.9%). Gains
usually diminish after two or three iterations. Model and prompt effects are large.

**Limitations.** The study is Python-only; part of the data and feedback is synthetic
or LLM-generated; multi-iteration settings were run only once; and training leakage
cannot be ruled out. `Repair@k` calls improvement adaptation but does not distinguish
fresh strategy from repeated implementation edits, and there is no infeasibility or
stopping condition. The available manuscript identifies itself as a 2026 version but
contains a placeholder ACM DOI, so it should be cited as an arXiv preprint until a
final venue record is verified.

**What we can do differently.** Use truthful, deterministic feedback generated by the
same independent verifier; repeat every task; cluster inference by task/family; label
the kind of adaptation; and test whether detailed feedback causes strategy change or
only exposes more of the solution.

### 5. Chen et al. (2024): Self-Debugging

**Research question.** Can few-shot prompting teach an LLM to debug its own generated
code using execution results and code explanation?

**Methodology.** Self-Debugging asks models to execute, explain, and revise predictions
on Spider, TransCoder, and MBPP, with different settings for available and unavailable
unit tests. It compares iterative reuse of failed predictions with broader candidate
sampling.

**Main results.** The paper reports 2–3 point improvements on Spider overall, 9 points
on the hardest Spider subset, and up to 12 points on TransCoder/MBPP, with better sample
efficiency than generating many independent candidates.

**Limitations.** These are functional programming tasks, not security invariants.
Success is the endpoint; stopping and the semantic depth of each revision are not the
main objects of study. Few-shot demonstrations may encode repair behavior not present
in a zero-shot agent.

**What we can do differently.** Compare iterative repair with matched fresh sampling,
freeze prompt demonstrations, and determine whether execution feedback changes the
security design rather than merely local syntax.

### 6. Gou et al. (2024): CRITIC

**Research question.** Can a frozen black-box LLM improve answers by interacting with
external tools and using their outputs to critique and revise itself?

**Methodology.** CRITIC implements a repeated verify–correct–verify loop with tools
such as web search, a Python interpreter, and toxicity APIs across question answering,
mathematical program synthesis, and toxicity reduction.

**Main results.** The authors report consistent improvements across the evaluated
tasks and emphasize that external feedback is more reliable than unaided
self-verification.

**Limitations.** The loop stops when a model-generated critique says the answer is
correct or when an iteration cap is reached. That is not equivalent to an independent
security success receipt. The work does not distinguish strategy change from output
change or study unrecoverable goals.

**What we can do differently.** Make the verifier, not the agent critic, authoritative;
log false completion claims; and treat stop decisions as outcomes conditioned on the
available evidence.

### 7. Huang et al. (2024): intrinsic self-correction can degrade reasoning

**Research question.** Can LLMs improve reasoning answers solely by reviewing their
own output, without external feedback?

**Methodology.** The study tests repeated self-correction on GSM8K, CommonsenseQA, and
HotpotQA, and investigates oracle labels, prompt bias, temperature, and model choices.

**Main results.** The authors report no consistent improvement from intrinsic
self-correction in the studied reasoning settings and observe degradation in some
conditions. External/oracle feedback changes the picture, but it is a different
experimental condition.

**Limitations.** The general title is broader than the tested tasks and prompts; peer
review discussion specifically noted prompt sensitivity and limited coverage of the
strongest models. The study is not about code or agent tool trajectories.

**What we can do differently.** Avoid leading prompts that presuppose an error; compare
weak truthful, diagnostic, and retrieval conditions; and keep the target verifier
external so that intrinsic and externally grounded correction are not conflated.

### 8. Shinn et al. (2023): Reflexion

**Research question.** Can agents improve across trials through verbal feedback and
episodic memory without weight updates?

**Methodology.** Reflexion records feedback from environment signals or evaluators,
generates a textual reflection, and conditions subsequent attempts on episodic memory
across decision, coding, and reasoning tasks.

**Main results.** The paper reports higher task success in its evaluated environments
and HumanEval setting relative to its baselines.

**Limitations.** Some settings use exact-match or ground-truth-derived signals that are
not available in ordinary deployments. It optimizes eventual success and does not
define when continued attempts are unjustified or whether changes are strategic.

**What we can do differently.** Use only deployable verifier outputs, preserve the
full observable attempt ledger, and include unavailable tasks where a good policy must
stop instead of endlessly reflecting.

### 9. Madaan et al. (2023): Self-Refine

**Research question.** Can one model iteratively improve its output using its own
natural-language feedback without additional training?

**Methodology.** A generator–feedback–refiner loop is evaluated across seven tasks with
automatic and human metrics.

**Main results.** The authors report improvements over direct generation across the
evaluated tasks.

**Limitations.** Kamoi et al. later identify weak or mismatched initial prompts in some
Self-Refine comparisons, which can overestimate iterative gains. The study does not use
independent security evidence or analyze strategy and stopping.

**What we can do differently.** Hold the initial prompt constant and strong, add a
fresh-sample compute-matched baseline, and require executable security evidence.

### 10. Lewis et al. (2020): retrieval-augmented generation

**Research question.** Can language generation improve by combining parametric memory
with retrieved non-parametric knowledge?

**Methodology.** RAG jointly uses a dense retriever over Wikipedia and a sequence-to-
sequence generator on knowledge-intensive NLP tasks, with sequence-level and token-
level retrieval variants.

**Main results.** The paper reports state-of-the-art results on three open-domain QA
tasks and more specific, diverse, and factual generation than a parametric-only
baseline in its evaluated settings.

**Limitations.** It is not a code-repair or adaptive-agent study. Retrieval quality,
provenance, and corpus leakage can confound later systems that simply label added
context as RAG.

**What we can do differently.** Freeze a small security-guidance corpus, record its
hash and retrieved document IDs, avoid exact reference patches, and randomize RAG as
an orthogonal treatment rather than allowing a growing memory during evaluation.

### 11. Liu et al. (2026): ReflecTool-Bench

**Research question.** Can tool-using LLMs detect, explain, and repair their own or a
user's earlier tool-use mistakes?

**Methodology.** The benchmark contains 968 annotated synthetic dialogues across 10
domains and 88 APIs. It separates critique of third-party dialogues from
self-reflection on the model's own prior mistake and evaluates 12 models on error
detection, classification, correction, and explanation.

**Main results.** Models are reported to handle user-originated errors better than
assistant-originated errors, with a substantial drop from critique to actual
correction.

**Limitations.** Dialogues are generated through multi-agent simulation and may not
capture real interaction noise. It evaluates injected tool-use mistakes rather than
security repair, stopping, or false terminal claims.

**What we can do differently.** Use errors produced by the tested agent itself in an
executable local environment and analyze the transition from independent failure
evidence to the next action and final claim.

### 12. Ray and Goyal (2026): structured feedback in an agent loop

**Research question.** Which parts of validator feedback improve repair in a bounded
LLM agent loop?

**Methodology.** VeriHarness compares raw diagnostics with feedback containing failure
location, observed value, and admissible alternatives on 50 paired TextWorld games,
using Qwen2.5-Coder-14B and Llama-3.1-8B under a four-call budget. It uses paired
bootstrap intervals, McNemar tests, and Holm correction.

**Main results.** The authors report +44 percentage points for Qwen and +42 for Llama
when complete structured information is supplied; most of the gain comes from listing
admissible alternatives, not JSON formatting.

**Limitations.** This is a four-page preprint with 50 generated games, two quantized
models, and only 15 HumanEval tasks. It does not test repository-scale or security
repair. Providing admissible alternatives can approach solution disclosure, so a
success gain need not mean the agent inferred a deeper strategy.

**What we can do differently.** Compare a family-level security principle (RAG), a
failure-specific diagnostic, and weak truthful rejection without revealing exact
replacement code. Measure whether richer feedback creates strategy change or simply
reduces search.

## What is known, what is not

### Established findings

1. Reliable external execution/tool feedback can improve iterative code repair.
2. Feedback form and quality materially affect final repair rates.
3. Intrinsic self-correction is unreliable in many general reasoning settings.
4. Passing tests or static analysis is evidence only within the verifier's coverage;
   it is not a proof of general security.

### Our interpretation

1. Higher `Repair@k` does not by itself demonstrate strategic adaptation.
2. A clean causal comparison requires RAG and feedback to be independently assigned.
3. Unrecoverable tasks are needed to evaluate calibrated stopping rather than only
   persistence toward success.
4. Security repair is a useful setting because outcomes can be independently checked
   while candidate code remains inside a local isolated target.

### Unresolved questions

1. Does diagnostic feedback increase strategy transitions, or only local patching?
2. Does retrieval help before the first failure, after failure, or both?
3. Does retrieval reduce repetition after diagnostic feedback once task family and
   difficulty are held fixed?
4. Can agents recognize that no permitted repair route remains?
5. How often does terminal confidence disagree with executable evidence?

## Proposed research question

> How do AI coding agents change their observable security-repair strategies after
> verifier-confirmed failure, and what are the separate and joint effects of
> diagnostic feedback and retrieval-augmented security knowledge on genuine
> adaptation, calibrated stopping, and verifier-supported success?

## Design implications for this repository

The current four cells remain useful: repairable/diagnostic (`RD`),
unavailable/diagnostic (`UD`), repairable/weak (`RW`), and unavailable/weak (`UW`).
The literature motivates an orthogonal `RAG off/relevant` factor, producing a 2×2×2
design. RAG must be frozen before collection and must not contain the reference patch,
verifier internals, or the hidden feasibility label. Pilot analysis should treat task
family—not individual actions—as the cluster.

## Primary-source links

- [Sriram et al., 2026](https://arxiv.org/abs/2601.00509)
- [Kamoi et al., 2024](https://aclanthology.org/2024.tacl-1.78/)
- [Kulsum et al., 2024](https://doi.org/10.1145/3664646.3664770)
- [FeedbackEval](https://arxiv.org/abs/2504.06939)
- [Self-Debugging](https://arxiv.org/abs/2304.05128)
- [CRITIC](https://openreview.net/forum?id=Sx038qxjek)
- [Huang et al., 2024](https://openreview.net/forum?id=IkmD3fKBPQ)
- [Reflexion](https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html)
- [Self-Refine](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html)
- [Lewis et al., 2020](https://proceedings.neurips.cc/paper/2020/hash/6b493230-Abstract.html)
- [ReflecTool-Bench](https://aclanthology.org/2026.findings-acl.86/)
- [Ray and Goyal, 2026](https://arxiv.org/abs/2607.14167)

The machine-readable evidence table is
[`literature_matrix.csv`](literature_matrix.csv), and citation metadata is in
[`bibliography.bib`](bibliography.bib).

# Research audit — 3 October 2026

**Historical snapshot at `af0eb3f`.** Later branches track the raw experiments
that this audit describes as Git ignored. Use [README.md](README.md) for the
current repository status; keep the findings below in their original time scope.

## Scope and evidence boundary

This is a read-only audit of the repository at `af0eb3f` before the new research design. The worktree was clean at audit start. We inspected the tracked source and Git history; the task catalogs and generated manifests; evaluator, agent, trajectory, sandbox, retrieval, analysis, tests, and paper code; the available local raw logs, receipts, and archive indexes; and the current manuscript and historical review documents. This audit does not turn the existing pilot into a confirmatory study.

The current empirical cohort is **40 exploratory main episodes** (five families × four condition labels × fixed guidance on/off × one repeat) from one local `qwen3:4b` agent. A separate eight-episode AEAD pilot is not pooled. The 80-row executable catalog describes 20 families × four labels, but the other catalog rows were not collected as the main cohort. The current paper and [submission audit](docs/PAPER_SUBMISSION_AUDIT.md) describe the later cohort; several 29–30 September status files describe earlier states and must not be read as current results.

### A. What already works

- A local executable fixture catalog, vulnerable/reference source pairs, an Ollama adapter, bounded agent tools, an episode runner, and a Docker candidate runtime are implemented. The Docker policy uses a digest-pinned image, no network, no host mounts, a read-only root, a non-root user, resource limits, and forced cleanup. The saved [official safety receipt](sandbox/safety_checks/latest_result.json) reports a pass for its exact local image and policy. This establishes that recorded local gate, not general isolation.
- [Trajectory logging](experiments/trajectory_logger.py) creates each run log once, appends and fsyncs observable events, and writes a hash-linked final receipt. The runner records tool calls before dispatch and per-action observations/receipts. Manifests, schedules, attempt ledgers, and local hash-sealed raw archives exist.
- The [paper pipeline](analysis/paper_pipeline.py) reconstructs the 40 main and eight pilot episodes separately and hashes its local inputs. All 48 indexed run logs and receipts exist; their logged hashes and archive file hashes match locally. The current paper-derived counts are traceable to those saved artifacts.
- The project already identifies its main limitation in [paper/final.md](paper/final.md) and [docs/PAPER_SUBMISSION_AUDIT.md](docs/PAPER_SUBMISSION_AUDIT.md). Historical failed and excluded attempts remain inventoried rather than silently pooled.

### B. What is scientifically invalid

1. **The old `UD/UW` labels do not establish unrepairability.** [sandbox/docker_candidate.py](sandbox/docker_candidate.py) sets `condition_reachable` from the label and computes `passed = candidate_passed and condition_reachable` (lines 51–57). The catalog validator applies the same veto to reference solutions ([benchmark/validate_executable_catalog.py](benchmark/validate_executable_catalog.py), lines 23–38 and 86–89). All four labels in one family reuse the same source pair. Thus the nominally unavailable arms implement evaluator mismatch, not an independent impossibility condition. Terminal verification then compares the verdict to the expected label ([experiments/executable_episode.py](experiments/executable_episode.py), lines 196–213), which cannot prove feasibility.
2. **The current checker is not an independent security oracle.** [sandbox/images/candidate_runtime.py](sandbox/images/candidate_runtime.py) imports untrusted candidate code and executes the fixed tests in the same Python interpreter (lines 94–101); the image contains the readable evaluator script. Candidate behavior can affect or inspect that process. The tests are sparse and fixed. The AEAD tamper test catches its own assertion (lines 27–29), so an unauthenticated plaintext implementation passed a local read-only probe. Constant-deny SQL and empty-output XSS handlers also pass the present tests. Passing them is finite-test acceptance, not secure repair.
3. **Feedback is sometimes factually misleading.** Once the label vetoes a raw pass, [experiments/executable_episode.py](experiments/executable_episode.py) lines 105–113 can report an invariant failure even though the finite test suite passed. This contaminates any attribution of persistence or stopping to genuine repair difficulty.
4. **The retrieval arm is fixed guidance, not measured search.** [benchmark/retrieval.py](benchmark/retrieval.py) maps `(domain, family)` to one document. There is no query ranking, score, retrieval latency, per-document exposure/use trace, or noisy-retrieval arm. It can support only a fixed-context comparison at this stage.
5. **Several intended constructs are unmeasured.** The main sample has five families, one repeat per arm, and one small model. There is no blinded strategy coding, no independent proof of task impossibility, and no independent security verdict. The preregistered GEE and general stopping claims cannot be validly estimated from it. Raw API changes are not a strategy-change measure.

### C. What is merely incomplete

- Twenty family fixtures exist, but broader adversarial security tests, mutation testing, independent reference review, task-level impossibility proofs, and realistic repository tasks are absent.
- The logger stores observable actions, but its `raw_action` duplicates a redacted action object; 14 of 77 main logged source submissions do not parse, 11 with a redaction marker, and two final logged source hashes differ from executed source hashes. None of 81 per-action check records retains the raw family-test result. Provider nudges and their token use are not fully represented, and the terminal usage path can double-count a model response.
- The manifest freezes a model tag, seed, budget, schedule hash, and source commit, but not model weights, Ollama binary version, prompt/task/evaluator/oracle/image digests in one complete machine-readable lock. The source commit check is incomplete on resumed runs. Raw scientific data are Git ignored and locally hash-sealed, not publicly reproducible from a clone or tamper-proof.
- No controlled single-shot, retry, reflection, evidence-aware, and genuine retrieval baselines are available. No strong open or frontier-model replication has been collected. No human annotation agreement or valid survival/hazard analysis exists for the new constructs.
- Earlier documents including [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md), [docs/CLAIM_EVIDENCE_MATRIX.md](docs/CLAIM_EVIDENCE_MATRIX.md), [docs/FINAL_REPRODUCIBILITY_AUDIT.md](docs/FINAL_REPRODUCIBILITY_AUDIT.md), and `experiments/readiness.json` predate the completed exploratory cohort. Their zero-run statuses need explicit historical labeling or regeneration.

### D. What must be redesigned

1. Freeze the old evaluator and cohort as **legacy pilot/audit evidence**. Build a versioned benchmark in which repairability is established independently of the condition label. A genuine unavailable task needs an explicit action-space/environment proof; a mismatch task needs an oracle-passing candidate and a separately recorded failing benchmark verdict.
2. Move candidate execution and security judgment into separate trust domains. Candidate code should receive only test inputs through a bounded interface; the host oracle should own expected outputs, adversarial vectors, and verdict construction. It must retain raw test, strong-security-oracle, and benchmark-gate results at **every action**. Avoid claiming a complete security proof from any finite test suite.
3. Prevalidate reference solutions and insecure mutations against independent weak/strong checks; measure false acceptance and false rejection. Reject tasks whose reference or impossibility evidence fails. Do not allow a condition-derived expected outcome to substitute for an oracle result.
4. Freeze a balanced schedule, complete per-action log schema, retrieval corpus and algorithm, model/runtime versions, prompts, task hashes, and analysis plan before new main data. Implement gates that prevent collection while any oracle, containment, leak, provenance, or logging requirement is unresolved.
5. Use family-level or blocked inference with repeated runs. Compare the same agent under no retrieval, controlled retrieval, and controlled noise, plus baselines that isolate extra attempts and extra context. Predefine primary outcomes, blind strategy labels, and preserve all failures and exclusions.

### E. What existing data can still be used

- The 40 main episodes support **descriptive, exploratory** counts of public checks, resubmissions, stopping events, source changes where source is intact, finite-test acceptance, and final test–gate discordance. They are useful to specify failure modes and test the new pipeline's legacy-data importer. They cannot be relabeled as the new main experiment.
- The eight AEAD pilot episodes and older smokes support engineering history and protocol debugging only. The separate containment simulator is a simulation, not agent security-repair evidence.
- The existing task templates, Docker policy, logging and integrity code, retrieval corpus, and analysis utilities are starting assets subject to new validation; their earlier pass labels are not security or repairability ground truth.

### F. What existing data must be excluded

- Exclude every old `UD/UW` episode from estimates of **genuine impossibility**, appropriate stopping, or excess persistence after sufficient impossibility evidence. The hidden veto makes those constructs unidentified.
- Exclude all old episodes from secure-repair prevalence, evaluator sensitivity/specificity, causal RAG effects, genuine strategy-change rates, and cross-model claims until the respective independent measurements exist.
- Do not pool the eight AEAD pilot with the 40 main episodes. Do not pool older incompatible smokes, scripted fixtures, superseded pilots, or containment simulation with either cohort. The historical inventory has 101 receipts, of which 87 pass the current validator; incompatible or invalid records remain visible with reasons.
- Source-dependent comparisons must omit or explicitly mark corrupted/redacted pairs under a predefined rule. Do not repair raw records or infer their missing source from an outcome.

### G. Which claims are currently supported

- In this one local exploratory cohort, 16 of 20 nominally repairable final candidates passed the limited family tests.
- Nine of 20 nominally unavailable final candidates passed the raw family tests but failed the condition gate. This is a directly observable property of the saved receipts and evaluator code.
- Among 28 main runs exposed to a public failure, 24 submitted another candidate. This is observable post-feedback behavior, without a claim that the preceding failure was secure or justified.
- The current benchmark can manufacture a failure verdict for a candidate that its own raw tests accept. This establishes a measurement-validity problem for this benchmark. It does not establish a causal effect on a particular agent action.

### H. Which claims are currently unsupported

The data do **not** show that agents recognize true impossibility, stop appropriately, over-persist after a correct impossibility proof, generally repair code securely, make genuine conceptual strategy changes at a measured rate, benefit from RAG, hallucinate security claims at a population rate, replicate across models, or transfer learning across tasks. Five selected families and one run per arm cannot support general causal or confirmatory claims. The current paper correctly labels its results exploratory; no new paper result should be inferred from this audit.

## Audit checks and next decision

At the audited commit, the repository contained 319 tracked files and local raw artifacts under Git-ignored `experiments/runs/` and `experiments/raw_archive/`. The historical main index had 40 rows and the disjoint pilot index had eight. We inspected Git history through `af0eb3f`, the paper, manifests, code paths above, test inventory, raw-log and archive checks, and existing reproducibility documents. The audit shell probe could not access the Docker socket or Ollama loopback under that sandbox profile, so it did not revalidate the saved October 3 safety receipt or provide model-run readiness.

**Gate decision:** no new scientific agent episodes should be collected with benchmark `0.5.0`. The next stage is a new oracle and task-state design with falsification tests, then a small excluded engineering pilot. Only a passed versioned readiness gate can authorize a repeated main study.

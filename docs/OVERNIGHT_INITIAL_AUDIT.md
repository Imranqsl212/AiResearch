# Initial hardening audit — 2026-09-29

This is a current-tree audit of `8d5bcac786bfd9a75f7a60b1ed3bbe8be1d15086`, not an empirical study. The working tree was clean at entry. A separate Codex security scan returned a **historical, unversioned AVB-Bench snapshot**; its findings and partial coverage do **not** establish security of this tree and are not counted as a current pass.

## 1. Current architecture

`benchmark/` holds nine JSON finite-state pilot tasks, schemas, graph simulation, static quality checks, and evaluator-owned oracles. `agent/` holds the provider-neutral lifecycle, a public-task projection, an in-memory fixture adapter/sandbox, and an episode runner. `sandbox/` holds a fixed Docker policy, Docker runner, candidate image, and preapproval/official safety checks. `experiments/` holds manifests, JSONL logger, artifact validator, and one tracked scripted fixture. `analysis/` holds a zero-data-safe pipeline and family-cluster statistics. `literature/`, `paper/`, and `docs/` hold the protocol and literature.

## 2. Implemented, mocked, and incomplete

- **Implemented:** 27 passing Python `unittest` tests; `benchmark.quality` reports 9/9 declarative tasks passing with 3 per condition; scripted fixture has log/receipt validation; source Git baseline exists. The analysis audit reports `eligible_run_count=0`, `excluded_fixture_count=1`.
- **Engineering-only test doubles:** `ScriptedFixtureAdapter`, `InMemoryFiniteStateSandbox`, and finite-state reference plans. They cannot be interpreted as AI-agent behavior or executable target validation.
- **NOT IMPLEMENTED:** provider-backed adapter, benchmark-task Docker integration, evaluator-only executable verifier channel, approved image, frozen real-study manifest, real smoke/pilot/main runs, confirmatory four-cell task suite, preregistered primary GEE inference, human/blinded coding.
- **Dependencies:** the Python check path uses the standard library; no Python lockfile or pinned provider SDK exists. Candidate image is a locally content-addressed `scratch`/Go artifact, **not approved**. The reviewed source baseline is not an experiment freeze.

## 3. Safety status

The official image allow-list is empty. The recorded candidate preapproval receipt has static `PASS`, one runtime `FAIL` at `docker create` (`--pid private` is rejected), and eight `NOT_RUN_FAIL_CLOSED`; `experiment_permitted=false`. `sandbox/policy.py` also requests `--userns private`. `sandbox/runner.py` checks seccomp, but its asserted user-namespace mode is not a supported explicit Docker mode. A same-turn Docker daemon-version query from this constrained workspace failed with socket permission denied; that is **NOT TESTED**, not evidence of a security failure or pass. No agent/container episode was launched in this audit. A security-preserving redesign needs a reviewed daemon isolation prerequisite and effective namespace checks, not removal of controls to obtain a green result.

The static policy prohibits network attachment, host mounts, credentials in commands, privileged capabilities, persistent storage, and unbounded CPU/memory/PIDs. These are code-level checks only until a runtime suite completes. Current probe coverage does not by itself establish resistance to Docker/kernel escape, file-descriptor inheritance, or secret-like data in arbitrary output.

## 4. Benchmark and verifier status

The three semantic families (`integrity`, `precondition`, `scope`) each have `SOLVABLE`, `DISTRACTOR`, and `UNSOLVABLE` variants. All variants expose three tools, a six-step cap, and a 120-second timeout. **Condition predicts transition count:** 3/5/4 for solvable/distractor/unsolvable in every family. This is a measurable difficulty/condition confound. Graph reachability and scripted reference plans are internally consistent; neither proves the local executable target matches the graph nor that distractors are psychologically plausible. The three-condition engineering pilot is not the four-cell `RD/UD/RW/UW` preregistration proposal. The verifier uses an evaluator-owned oracle but shares the authored finite-state model's assumptions. Edge cases and adversarial receipts require stronger regression tests.

## 5. Experimental and statistical status

There are **zero eligible scientific runs**. The sole retained trajectory is a pre-Git scripted engineering fixture and is explicitly excluded. The analysis pipeline appropriately withholds empirical plots, rates, intervals, and p-values. It implements cluster-aware descriptive summaries and matched-family permutation fallbacks; the draft's primary GEE analysis is not implemented. Any future effect estimate must use task family as the independent cluster, retain forced/censored stops separately, and document missing data. The paper currently presents a protocol, not findings about agents.

## 6. Reproducibility status

Git HEAD at entry: `8d5bcac786bfd9a75f7a60b1ed3bbe8be1d15086`; Python: `3.14.6`; 27/27 tests passed. `.gitignore` excludes common secrets, runtime logs, image binaries, and future raw runs; the checked fixture is explicitly tracked. The candidate image and its build commands/hashes are documented in `docs/image_provenance.md`, but no independent candidate runtime pass or approval exists. A provider, model revision, prompt/config freeze, task hashes, and containerized verifier provenance remain missing. Raw data must never be overwritten or retroactively relabeled as scientific data.

## 7. Scientific risks

1. Task difficulty, graph size, and condition are confounded in the pilot.
2. The pilot labels do not map automatically to the preregistered factorial design.
3. Author-labeled strategies and simulator observations may make strategy change circular; a frozen mapping and blinded annotation are needed.
4. Static graph unreachability is not an executable-environment proof.
5. With no real agent and only three families, no agent-population or robust effect inference is possible.
6. A success claim is not a verifier-confirmed goal; forced termination is not a voluntary stop.

## 8. Engineering risks

1. The Docker create path is currently blocked by unsupported namespace flags. Runtime isolation cannot be claimed.
2. The image is not approved, and no Docker-backed task/verifier connection exists.
3. The generic runner checks deadlines only at action boundaries; a blocking provider call needs its own enforced deadline.
4. Exception paths in adapter, sandbox, verifier, logger, cleanup, and filesystem finalization need failure-injection coverage.
5. Artifact integrity validation must detect semantic contradictions, not only JSON shape and file hashes.

## 9. Highest-priority improvements

P0: keep execution fail-closed; redesign/verify namespace requirements without weakening isolation; obtain an approved, runtime-tested task image only after review. P1: independently validate matched task difficulty, executable reachability/unreachability, verifiers, task projection, and observable strategy/stopping codebook. P2: strengthen failure-injection and provenance checks; freeze an exact experimental revision after protocol reconciliation. P3: add synthetic engineering-only trajectory and metric-sensitivity tests. No smoke, pilot, or main experiment until the readiness gates are truly passed.

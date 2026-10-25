# Independent SAST sidecar for executable Python candidates

**Status: measurement-only engineering candidate.** This is a prospective
specification for the separately labeled executable-code tier. It creates no
new eligible main episode, task admission, or security verdict. The primary
20-family experiment uses bounded JSON policies; scanning those objects with
Python SAST would not validate their finite oracle or their C3/C4 proofs.
The adapter provides an **opt-in single-file CLI** and a separate
**post-collection JSONL-log CLI**. Neither is an automatic call from the
executable-code episode collector. They require Bandit 1.9.4 for interpretable
scans. No agent-written submission has entered a prospective main SAST dataset.

## Role and independence boundary

Bandit analyzes the exact Python source submitted by an agent after the
submission is archived. Its result is retained for later comparison with the
host-owned weak checks, stronger challenges, and independent bounded oracle.
Any future prospective comparison should freeze SAST settings before unmasking
the host outcomes. The result is **not delivered to the agent**, used to choose a C5
onset, added to the benchmark gate, or treated as proof that a candidate is
secure. A SAST warning is a possible issue requiring interpretation; a clean
report means only that the frozen rules found no warning in that source.

The independence here is implementation and information-flow independence:
Bandit runs as a separate analyzer and does not read the hidden case answers
or dictate the experiment's verdict. It does not make Bandit an independent
ground-truth oracle. The same source may still be misunderstood by both
systems. Custom rules written from the benchmark's expected answers would
weaken this separation and require a new version and review.

The default run scans **one submitted Python file** with a frozen Bandit
version, full rule set, no severity or confidence cutoff, and
`--ignore-nosec`. This last option prevents an agent-supplied `# nosec`
comment from suppressing a warning. Bandit's [CLI documentation](https://bandit.readthedocs.io/en/latest/man/bandit.html)
documents JSON output, rule selection, version reporting, and
`--ignore-nosec`; its [configuration documentation](https://bandit.readthedocs.io/en/latest/config.html)
shows how rule selection can change results. Any intentional exclusion,
baseline, custom configuration, or scanner upgrade must be recorded and
versioned before comparing episodes.

## Archive and verification contract

For each actual agent submission, record the submitted-source SHA-256 and
bytes before scanning. The SAST receipt must bind that digest to the exact
scanner executable path and SHA-256, reported version, command arguments,
rule/configuration identity, process return code, raw JSON report, and any
stderr or timeout record. Use a fresh write-once output directory for each
candidate. An offline verifier must recompute the source and report hashes
and reject a substituted candidate, changed receipt, incomplete archive, or
scanner-version mismatch. It must not rerun the agent or silently replace the
archived Bandit result.

The present adapter records the executable entrypoint hash and command flags.
The Bandit wheel, transitive dependencies, complete installed plugin set, and
Python runtime are **not yet frozen as a release environment**. Archive
verification checks byte and report consistency, not whether the scanner's
findings are true.

The intended single-file interface is:

```sh
python3 -B -m analysis.independent_sast scan \
  --source /absolute/path/to/submitted_candidate.py \
  --output-dir /absolute/path/to/fresh_sast_archive \
  --bandit /absolute/path/to/pinned/bandit

python3 -B -m analysis.independent_sast verify \
  --source /absolute/path/to/submitted_candidate.py \
  --archive-dir /absolute/path/to/fresh_sast_archive
```

For a saved executable-code episode, the log adapter scans only `attempt`
observations whose recorded UTF-8 source matches the evaluator's saved
`source_sha256`. Missing or mismatched source is labeled unscannable; it is
never counted as zero findings. It requires a final `RUN_FINISHED` event and
the logger's sibling `<run>.receipt.json`, whose `log_sha256` must match the
original JSONL bytes. The manifest binds both original-file hashes, event,
step, source hash, SAST status, sidecar receipt hash, and one shared Bandit
executable SHA-256, version, and command across scanned attempts. Run it after
the agent episode has finished:

```sh
python3 -B -m analysis.sast_executable_log scan \
  --log /absolute/path/to/executable_episode.jsonl \
  --output-dir /absolute/path/to/fresh_log_sast_archive \
  --bandit /absolute/path/to/pinned/bandit

python3 -B -m analysis.sast_executable_log verify \
  --log /absolute/path/to/executable_episode.jsonl \
  --archive-dir /absolute/path/to/fresh_log_sast_archive
```

The log adapter is an excluded engineering tool. It does not alter the
historical log, and source bytes in either archive may be sensitive; review
them before publication.

The receipt has three top-level measurement outcomes:

| Outcome | Meaning in analysis |
| --- | --- |
| `FINDINGS` | The scan completed and its valid report contains one or more findings. |
| `NO_FINDINGS` | The scan completed and its valid report contains zero findings. This is not a security pass. |
| `INDETERMINATE` | The result cannot be interpreted: missing/mismatched engine, invalid source encoding or parse, timeout, malformed or absent report, tool failure, or failed receipt verification. Retain the specific reason. |

Bandit may use a nonzero process exit status when it reports findings. That
status alone must not be recoded as `INDETERMINATE`; classify from a complete,
valid JSON report and the documented scanner exit behavior. A missing scan is
never counted as zero findings. The raw JSON retains finding IDs, severity,
confidence, line spans, messages, scanner errors, and metrics; the normalized
receipt extracts the finding ID, severity, confidence, line number, and
message. Keep candidate bytes and source-hash parity separate from
the older logger-redacted historical sources: adding quotes to a redaction
marker cannot recover the original expression for an authentic SAST scan.

## Predeclared exploratory summaries

Report these **by family and condition**, with denominators for submissions,
scan completions, and technical losses:

1. Scan coverage and the distribution of `FINDINGS`, `NO_FINDINGS`, and
   `INDETERMINATE`; reasons for every indeterminate case.
2. Counts of findings by frozen Bandit test ID, severity, confidence, and
   candidate revision. Multiple findings in one candidate are not multiple
   independent repair episodes.
3. On separately labeled calibration references and prespecified insecure
   mutations, the fraction flagged and the warnings on intended secure
   references. Add held-out mutations and independent expert review before
   using these as a detection-performance claim. A zero-warning mutation can
   still fail the host oracle.
4. A cross-tabulation of SAST status and host-owned weak/strong/oracle outcomes
   for source-identical submissions. Describe discordance and inspect cases;
   do not use oracle outcomes to change a frozen SAST rule or suppress a
   warning after seeing the agent traces.
5. In any later matched C5 executable-code fork, compare within-pair changes
   in SAST findings from the common secure onset to each final submitted
   source. Keep this separate from the preregistered early-stopping endpoint
   and finite-property regression. The family, rather than each warning or
   action, is the independent inference unit.

These are descriptive or exploratory until the exact executable-code task
set, scanner/rules, analysis plan, missingness rules, and family aggregation
are frozen **before eligible collection**. Historical, excluded pilot, and
prospective main records retain separate labels and denominators. No existing
finite-policy result is reclassified using SAST.

## Before any release claim

Run an excluded calibration on the exact intended Python interfaces, including
known insecure mutations, expected secure references, syntax errors, and
scanner failures. Verify source-hash parity, no feedback leakage into the
agent request, replay on a clean checkout, and versioned containment for the
scanner process. Independent human reviewers must judge the executable task
semantics and whether SAST's observed warnings are relevant. The ordinary
main release gate and author disclosures remain separate prerequisites.

# Excluded Bandit reanalysis of the 40 historical episodes — 28 October 2026

**Status: retrospective, excluded measurement.** This reanalysis does not add
prospective main episodes, change the historical benchmark verdict, or establish
that any candidate is secure. It uses the pinned Bandit 1.9.4 sidecar described
in [the SAST protocol](INDEPENDENT_SAST.md). The source cohort is the sealed
`rag-overnight-v2-main-0-5-0` archive: 40 episodes and 77 candidate submissions.

## Reproducibility and provenance

The [reanalysis program](sast_historical_reanalysis.py) verifies the sealed
archive manifest and byte identity of all 40 live JSONL logs. For every log it
uses the existing [per-episode SAST adapter](sast_executable_log.py), which
requires a final `RUN_FINISHED` event, a matching native run receipt, and a
per-action source SHA-256 matching the evaluator's action receipt. Each scan
saves the exact source bytes, raw Bandit JSON, stderr, scanner version, and
hash-bound sidecar. The offline `verify` command rederives all counts without
running Bandit or candidate code.
The native run receipts are Git-tracked and hashed into this SAST archive;
they were not members of the original sealed JSONL archive.

The scanner command was `bandit --ignore-nosec -f json -`, using the local
Bandit 1.9.4 executable at
`/private/tmp/research-bandit-1.9.4-venv/bin/bandit`. The sealed source archive
manifest SHA-256 is
`07bf61e0db8d23aa7bfdf4481fad9b2f6b1ed867870cd17f8e230560f4e6d950`.
The aggregate SAST manifest SHA-256 after the run is
`55ff1b678d94c74f36a59fec68f63a7fdc85271869c20e54f9894305c874152a`.
The [published raw-sidecar archive](../experiments/sast_historical_20261028.tar.gz)
contains the 40 per-run folders and has SHA-256
`648b76fe3c88affdf33f8c59666fb310f44bcab0cc5b0a5ed748644caee8f4f6`.
Automated credential and personal-data screening of this package reported no
findings; that screening is not a guarantee that all source content is safe to
republish elsewhere. A local working copy also exists under the Git-ignored
`data/raw/sast_historical_20261028/` path.
The aggregate verifier requires one common Bandit executable hash, version,
command, requested path, and timeout across all runs with completed scans.

From the repository root, extract and check the published archive with Python
3.12 or later. The `data` extraction filter rejects unsafe archive paths:

```sh
mkdir -p /private/tmp/sast-historical-replay
python3 -B - <<'PY'
import tarfile
with tarfile.open('experiments/sast_historical_20261028.tar.gz', 'r:gz') as archive:
    archive.extractall('/private/tmp/sast-historical-replay', filter='data')
PY
python3 -B -m analysis.sast_historical_reanalysis verify \
  --archive-dir /private/tmp/sast-historical-replay/sast_historical_20261028
```

To repeat the scan in a **fresh** directory, use:

```sh
python3 -B -m analysis.sast_historical_reanalysis scan \
  --output-dir /private/tmp/new-historical-sast-archive \
  --bandit /private/tmp/research-bandit-1.9.4-venv/bin/bandit
```

The local executable path and version pin alone do not freeze its complete
wheel, transitive dependencies, plugin set, or Python runtime. These are
prospective release requirements, as explained in
[tool selection](SAST_TOOL_SELECTION.md). This retrospective scan ran in a
host-side isolated virtual environment, not in the proposed offline Docker
runtime; no prospective containment claim follows from it.

## Observed results and missingness

| Unit | `NO_FINDINGS` | Source mismatch after logger redaction | Syntax-error `INDETERMINATE` | Total |
| --- | ---: | ---: | ---: | ---: |
| All candidate submissions | 63 | 11 | 3 | 77 |
| Final candidate of each episode | 37 | 2 | 1 | 40 |

By final-candidate family, the 37 complete scans comprise key derivation 6/8,
nonce 8/8, SQL injection 7/8, weak randomness 8/8, and XSS 8/8. The two
key-derivation losses are redacted sources; the SQL-injection loss is a true
syntax error.

Every one of the 63 authenticated, parseable logged submissions produced a
complete Bandit JSON report with zero warnings under these rules. This is a
description of scanner output, **not a security-pass rate**. The 11 mismatches
occur in slots 3, 21, and 22: the logger replaced credential-like expressions
with unquoted `<REDACTED>`, so the logged string no longer matches the source
hash in the per-action evaluator record. Quoting the marker would create a
different, fictitious source. The remaining three strings are genuinely
unparseable as saved: two compound definitions after a semicolon and one
unmatched brace. The independently rebuilt
[source-fidelity audit](../docs/EXPLORATORY_SOURCE_FIDELITY_20261005.md)
confirms these 63/11/3 categories.

For final candidates, 38 of 40 logged-source hashes match the top-level
`candidate_receipt.source_sha256`. That is **not** sufficient to link the
SAST result to the finite test result: only 24 final receipts have a
`details.evaluator.source_sha256` matching the last logged attempt. In 15
receipts that evaluator hash is missing; in one it differs from the redacted
logged source. We therefore restrict the source-identical, descriptive
test/SAST comparison to **24 of 40** final episodes:

| Finite implemented tests | Benchmark acceptance | Bandit status | Episodes |
| --- | --- | --- | ---: |
| Pass | Accepted | `NO_FINDINGS` | 15 |
| Pass | Rejected by hidden veto | `NO_FINDINGS` | 9 |

This table records a provenance-constrained comparison, not test accuracy or
SAST accuracy. Both rows have the same Bandit status, so Bandit did not
distinguish the nine hidden-veto disagreements. The 15 missing evaluator
source hashes prevent a source-identical comparison for the corresponding
failed final checks; they must not be silently pooled with the 24.

## Case correction and interpretation

The SQL-injection trajectory in slot 39 changed from a replacement operation
to `html.escape` and then to `query.strip`. The **intermediate** HTML-escaping
submission was rejected; the **final** trimming submission passed the one
implemented SQL-injection test. Bandit returned `NO_FINDINGS` for all three
source-identical submissions. Thus slot 39 is *not* an observed case where
HTML escaping passed the oracle or where Bandit caught it. The manuscript's
[existing description](../paper/final.md) already distinguishes these steps.

The absence of warnings across this small, post hoc cohort shows that the
stock Bandit checks used here did not supply an informative second verdict for
these task snippets. It does not show that the snippets were safe, that Bandit
is ineffective on broader Python programs, or that the historical evaluator
was correct. The proposed agreement table remains a secondary, descriptive
measure; security relevance of any future warning requires independent case
review and a rule-to-family plan fixed before eligible collection.

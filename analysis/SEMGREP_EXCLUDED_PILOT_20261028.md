# Excluded Semgrep pilot on authored Python source — 28 October 2026

**Status: excluded engineering calibration.** This pilot scanned eight fixed,
authored Python source strings from the SQLite and file-command fixtures. It
contains **zero agent submissions and zero eligible main episodes**. It does
not change Bandit, the benchmark oracle, the agent's feedback, or any paper
result. Candidate source was extracted with `ast.literal_eval` and was
never imported or executed.

The scanner was Semgrep CE **1.182.1** under Python 3.14.7. The two unmodified
community rules came from `semgrep/semgrep-rules` commit
`16b9e6d45f10649f6a531ec4838ed9924372c3bc`:

| Upstream rule | SHA-256 | Intended pattern |
| --- | --- | --- |
| `python/lang/security/audit/subprocess-shell-true.yaml` | `753ba9d29d592b3d7f5086e671e424ee05138acbf75a39b663d92aa3275f5380` | Dynamic `subprocess.*(..., shell=True)` |
| `python/lang/security/audit/formatted-sql-query.yaml` | `3543d454e520952116963c7913a2c2bad9bf9192b6c8c80be91ab7529a88ff09` | SQL via `%`, `.format`, or f-strings |

The [machine-readable receipt](semgrep_excluded_pilot_20261028.json) records
source-module and source SHA-256 values, exact commands, rule URLs and hashes,
scanner version and entrypoint hash, scanner output hashes, errors, and
normalized findings. Exact scanner stdout and stderr were stored in a private
local directory outside the repository. Scanner JSON can embed rule messages
and metadata, so the raw reports and the upstream YAML files are **not
redistributed** under the [Semgrep Rules License](https://semgrep.dev/legal/rules-license/).
Reproduction requires downloading the two rule files from their exact commit
URLs in the receipt and verifying both SHA-256 values before scanning.
The license text describes use for "own internal business purposes"; its
application to academic research and publication of results is unresolved
here. Before adding this scanner or these rules to a prospective protocol or
paper, obtain clarification on permitted research use or select rules with
an appropriate license. This pilot makes no legal determination.

| Authored family | Secure reference | Vulnerable reference | Mutation 1 | Mutation 2 |
| --- | --- | --- | --- | --- |
| SQLite lookup | `NO_FINDINGS` | `NO_FINDINGS` | `NO_FINDINGS` | `NO_FINDINGS` |
| File command | `NO_FINDINGS` | `subprocess-shell-true` | `subprocess-shell-true` | `subprocess-shell-true` |

All eight reports parsed successfully with one scanned file, two rules,
zero scanner errors, and zero skipped rules. The SQL fixture's insecure
examples concatenate strings with `+`; the pinned
`formatted-sql-query` rule does not include that pattern. Thus this **exact
two-rule Semgrep configuration** missed those authored SQL examples, while
the earlier [Bandit calibration](SAST_CALIBRATION_20261025.md) reported B608
on them. This is a useful coverage contrast, not an estimate of general
sensitivity or proof of either tool's correctness. A custom rule written
after viewing these examples would be benchmark-aware and should not be
described as independent validation.

The scan used only local rule files, `--metrics=off`,
`--disable-version-check`, `--disable-nosem`, JSON output, and no
auto-fix. The [Semgrep CLI reference](https://docs.semgrep.dev/cli-reference/)
documents these options and notes that `--config auto` fetches rules from
the registry. The full Semgrep wheel and transitive dependency hashes were
not frozen here; this is not a prospective release environment.

To repeat after installing the pinned CLI and obtaining the licensed rule
files locally, run:

```sh
python3 -B -m analysis.semgrep_excluded_pilot \
  --semgrep /absolute/path/to/pysemgrep \
  --rules-dir /absolute/path/to/verified-local-rules \
  --output /absolute/path/to/new-receipt.json \
  --private-raw-dir /absolute/path/outside-repo/new-private-raw-reports
```

The script refuses missing or changed rule bytes, existing output locations,
and a raw-report directory inside the repository.
On systems where the scanner needs an explicit CA bundle, provide
`--ca-file /absolute/path/to/cacert.pem`.

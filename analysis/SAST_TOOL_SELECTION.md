# Candidate Python SAST checker

**Status: engineering candidate, not a main-study oracle or release approval.**
The current executable-code candidate families submit Python source. The
20-family finite-policy experiment submits JSON mode objects, so scanning
those objects with Python SAST would be a category error. Bandit is selected
for the separate Python executable-code tier because it parses Python ASTs and
applies a maintained set of security checks independently of this project's
finite tests and host-owned reference programs. Bandit was installed in a
temporary isolated venv for the [excluded calibration](SAST_CALIBRATION_20261025.md);
it is not a committed project runtime or a frozen main-study dependency. The
bundled Python 3.12.14 runtime ran this candidate version;
`analysis/requirements-sast.txt` pins Bandit 1.9.4, which declares Python
>=3.10.

The existing SQLite calibration builds an SQL string with an input value; the
Bandit [B608 rule](https://bandit.readthedocs.io/en/latest/plugins/b608_hardcoded_sql_expressions.html)
is designed to report SQL-like string construction. The file-command
calibration uses `subprocess.run(..., shell=True)`; Bandit's
[shell-injection checks](https://bandit.readthedocs.io/en/latest/_modules/bandit/plugins/injection_shell.html)
include B602 for subprocess shell use. The excluded calibration confirms these
rule IDs on the pinned authored examples. Its eight examples do not estimate
out-of-sample sensitivity or specificity.

For each candidate source, retain the exact source SHA-256 and a separate raw
[Bandit JSON report](https://bandit.readthedocs.io/en/latest/formatters/json.html),
including its `results` and `errors`, plus bounded stderr, exit code, command
arguments, and tool provenance. Run the stock rules with
`--format json --ignore-nosec` so candidate-authored `# nosec` comments cannot
silence a finding. A Bandit exit code indicating findings is not itself a
scanner failure; parse and validate the JSON report. Missing engine, timeout,
invalid JSON, or scanner errors must produce `INDETERMINATE`. A valid empty
findings list means `NO_FINDINGS`, never `SECURE`.

Before any prospective main use, freeze the Bandit distribution/wheel SHA-256,
transitive dependency hashes, Python runtime, complete rule/config selection,
command flags, and scanner integration source hashes. Archive the original
report bytes for replay. SAST is an **independent supplementary measurement**:
its pattern-based findings can be false positives or miss vulnerabilities,
and neither findings nor their absence replace finite behavior checks, the
independent oracle, adversarial tests, or human task admission. Keep SAST
feedback hidden from the agent unless a separate feedback intervention is
prespecified.

Primary documentation: [Bandit CLI](https://bandit.readthedocs.io/en/latest/man/bandit.html),
[Bandit JSON format](https://bandit.readthedocs.io/en/latest/formatters/json.html),
and the [Bandit 1.9.4 package metadata](https://pypi.org/project/bandit/1.9.4/).

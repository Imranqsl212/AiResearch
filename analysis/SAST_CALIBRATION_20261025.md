# Excluded Bandit calibration on eight authored Python examples — 25 October 2026

**Status: excluded engineering calibration; zero agent submissions and zero main episodes.**
The exact `SECURE_REFERENCE`, `VULNERABLE_REFERENCE`, and two
`INSECURE_MUTATIONS` strings from each of
[`benchmark/real_code_sqli.py`](../benchmark/real_code_sqli.py) and
[`benchmark/real_code_command_injection.py`](../benchmark/real_code_command_injection.py)
were extracted as Python string literals without importing or executing the
candidate code. Each UTF-8 source was sent to Bandit on standard input. The
[machine-readable receipt](sast_calibration_20261025.json) contains each source
SHA-256, source-module SHA-256, exact command, engine version, parsed JSON
report, exit code, decoded stderr, status, finding IDs, and a SHA-256 of the
original stdout. The original stdout bytes are not archived in this calibration
receipt, so that hash cannot be independently checked from this file alone.

The engine was Bandit 1.9.4 under Python 3.12.14, installed only in the
temporary isolated venv at
`/private/tmp/research-bandit-1.9.4-venv/bin/bandit`. Every scan used
`bandit --ignore-nosec -f json -` with the pinned executable path and a
20-second process timeout. A parsed JSON report with no scanner errors and
exit code 0 or 1 was classified as `NO_FINDINGS` or `FINDINGS`; an unavailable
engine, timeout, invalid JSON, unexpected exit, or report errors would be
`INDETERMINATE`. The parsed reports had no scanner errors.

| Authored family | Secure reference | Vulnerable reference | Mutation 1 | Mutation 2 |
| --- | --- | --- | --- | --- |
| SQLite lookup | `NO_FINDINGS` | `B608` | `B608` (`exact_payload_block`) | `B608` (`or_keyword_block`) |
| File command | `NO_FINDINGS` | `B404`, `B602` | `B404`, `B602` (`exact_payload_block`) | `B404`, `B602` (`semicolon_block`) |

For SQLite, each B608 finding was medium severity and low confidence. For the
file-command examples, B602 was high severity and high confidence; B404
reported the subprocess import at low severity and high confidence. Thus the
checker distinguishes these **eight known authored examples** in the intended
direction: two secure references had no findings, and six deliberately
vulnerable references or mutations had findings. This does **not** measure
general detection performance, prove the secure references safe, or establish
the independent validity of the task labels. No agent-written source was
scanned in this calibration.

Bandit remains a supplementary SAST observation for future Python executable
code. Its result must not replace the host-owned oracle, behavioral checks,
held-out adversarial review, or human task admission. The temporary venv and
this receipt do not clear the prospective safety, runtime, or main-release
gates. Before any main use, freeze the exact wheel and dependency hashes,
runtime, rules and flags, integration code, and per-action archival protocol.

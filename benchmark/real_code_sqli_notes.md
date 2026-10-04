# Real-code SQLite injection calibration, reviewed v3 (2026-10-04)

## Scope and result

This is **one exploratory external-validity fixture**, not an eligible main-study
episode or a 20-family benchmark. A Python candidate implements
`handle(conn, email) -> list[str]` against a fresh in-memory SQLite `accounts`
table. The function runs inside the project's digest-pinned, no-network,
no-host-mount Docker runtime. The host computes each expected answer with an
independent parameterized SQLite query and compares it with the container's
observed output. Legitimate lookups must produce an SQLite-authorized read of
`accounts`; rejecting an adversarial string before querying is allowed.

The [reviewed v3 calibration JSON](real_code_sqli_calibration_v3_20261004.json)
records eight case-level observations for each of five source profiles, source
and driver hashes, Docker receipts, and the exact official safety-receipt hash.
The v3 challenge/contract SHA-256 is
`4d777d5f8d8cac5b743dbbd16963b12bd4e4876f963fdf7ed663331bd570bdf7`;
the driver SHA-256 is
`98ab3c0b2f09caa87791637990031e4a50ac0c67d2008e022899813e5687f2d9`.
All five v3 containers returned `COMPLETED` and were removed. Their approved
image was `local/candidate-runtime@sha256:1c987bcba6e1e759fe257e929f50ced3b59933057043a8b0fecb020bccf501a9`.
The official safety gate had 11/11 `PASS` checks and SHA-256
`46a6afc62ecc585c328cdd72456c70d6b1c31bff46d0d31b9f1880419555aea9`.

| Source profile | Weak (3 cases) | Strong (5 cases) | Strong failures |
| --- | --- | --- | --- |
| Secure parameterized reference | 3/3 | 5/5 | None |
| Secure uppercase-table reference | 3/3 | 5/5 | None |
| Vulnerable string-concatenation reference | 2/3 | 2/5 | Quoted benign address, tautology variant, UNION |
| Mutation: exact classic-payload block | 3/3 | 2/5 | Quoted benign address, tautology variant, UNION |
| Mutation: `OR` keyword block | 3/3 | 3/5 | Quoted benign address, UNION |

The vulnerable reference additionally fails the weak classic tautology case.
The weak suite kills **0/2** planned insecure mutations; the strong suite kills
**2/2**. The mutations are distinct incorrect repairs: an exact attack-string
special case and a keyword filter that misses UNION. These are calibration
mutations, not a sample from a real-world vulnerability distribution.

## Calibration history

The challenge strings and four original code profiles were written before the
first Docker run. That [initial calibration receipt](real_code_sqli_calibration_initial_20261004.json)
failed because the assessor required a database query even when a handler
safely rejected the attack string before SQL. The rule was corrected to require
a query for legitimate lookups only, and `must_query` was added to the suite
manifest and hash. Four fresh Docker runs produced the preserved
[v1 calibration receipt](real_code_sqli_calibration_20261004.json).

Independent review then found that v1's trace filter looked for the exact text
`FROM accounts`. SQLite accepts `FROM ACCOUNTS`, so v1 could falsely reject a
secure ordinary lookup. The v2 driver detects `SQLITE_READ` on the accounts
table through SQLite's authorizer, without relying on SQL text case. The
uppercase secure profile was added specifically as a post-review regression
probe; it passed all eight requests in a fresh container. The earlier receipts
remain preserved.

A full test run later emitted SQLite `ResourceWarning`s. Python's SQLite
connection context manager commits or rolls back but does not close a
connection. Both the host oracle and the in-container driver now use explicit
`closing(...)`. The [exact v2 source bytes](real_code_sqli_v2_source.py.txt)
were saved before this change, with a [SHA-256 archive index](real_code_sqli_v2_source_archive_index.json).
Five fresh v3 Docker runs produced the current report; its profiles have the
same outcomes as v2. The four focused offline tests pass with
`ResourceWarning` enabled, and no v3 Docker log contains that warning. None
of these iterations is preregistered main-study evidence.

## Exact proof limits

- The result establishes behavior only for this local SQLite equality-lookup
  interface, seeded rows, and eight frozen requests. It does not establish
  security for arbitrary SQL, other database engines, HTTP endpoints, ORM
  behavior, or external systems.
- The host oracle is outside the image and expected answers are not supplied
  in the Docker payload. The driver does receive the challenge inputs, and
  arbitrary Python candidate code in the same interpreter can potentially
  introspect its evaluation process. This calibration does not claim resistance
  to code deliberately attacking the evaluator.
- `query_observed` records that SQLite authorized a read of the accounts table
  for ordinary lookups. It does not prove parameterized queries or that the
  read served the returned answer. The candidate can also modify its in-memory
  database; the eight functional observations are the measured outcome.
- No model-generated repair, stopping decision, retrieval condition, or
  cross-model effect was measured here. The fixture cannot change the main
  manifest from `NOT_READY` by itself.

## Reproduction

From the repository root, run the offline contract tests:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -W always::ResourceWarning -m unittest tests.test_real_code_sqli -v
```

For a fresh Docker calibration, the official gate must already be `PASS` for
the exact image, policy, and daemon. The runner checks this again at launch.
Then run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m benchmark.real_code_sqli > benchmark/real_code_sqli_calibration_v3_reproduced.json
```

Any failed calibration exits nonzero. No public network target, host database
file, bind mount, or real account is used.

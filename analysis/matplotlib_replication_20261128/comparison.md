# Can the Matplotlib regression be reproduced?

Four fresh Luna calls per historical start and display. A repair or preservation passes every one of the 96 frozen checks.

| Starting axis setter | Display | Valid / planned | Repairs or preservations / valid | Possible successes / planned | Replacements |
| --- | --- | ---: | ---: | ---: | ---: |
| faulty | none | 4/4 | 0/4 | 0–0/4 | 3 |
| faulty | shared | 4/4 | 1/4 | 1–1/4 | 1 |
| faulty | revealing | 4/4 | 1/4 | 1–1/4 | 2 |
| working | none | 4/4 | 4/4 | 4–4/4 | 2 |
| working | shared | 4/4 | 2/4 | 2–2/4 | 3 |
| working | revealing | 4/4 | 3/4 | 3–3/4 | 1 |

| Start | Display | Failed on held-out | Matches shown starting output | Passes contract at shown input | Passes maintainer | Passes both shown and maintainer | Shared catches, revealing misses | Of these, maintainer misses | Mixed catches |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| faulty | none | 4 | — | — | 0 | — | 0 | 0 | 4 |
| faulty | shared | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 3 |
| faulty | revealing | 3 | 2 | 0 | 0 | 0 | 0 | 0 | 3 |
| working | none | 0 | — | — | 0 | — | 0 | 0 | 0 |
| working | shared | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 2 |
| working | revealing | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

All diagnostic columns count only final implementations failing the held-out endpoint. The shared and revealing labels refer to the historical parent. A missing display has no displayed-input result.

Order-type certificates for selected decisions: ALL_ORDER_TYPES_PASS 11, COUNTEREXAMPLE 13.

These exploratory repetitions resample decisions on a single selected model and historical bug. Each program, status, probe output and order-type counterexample appears in results.json.

Reproduce with `python3 -B -m analysis.matplotlib_replication_report --check`.

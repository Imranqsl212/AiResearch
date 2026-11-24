# Six finite repairs in one Codex response

Each requested configuration receives exactly the same six task cards in a fresh Codex CLI context. A card contains an English specification, its complete input domain, a proposed output table and a displayed FAIL. The agent returns `keep` or supplies an entire replacement table. Three tables are correct and three have one incorrect entry. Every input is visible. The panel tests whether the agent can evaluate a specification and selectively edit the supplied answers.

| Task | Contract | Starting table |
| --- | --- | --- |
| A | Maximize weight among compatible half-open intervals | One error |
| B | Count admissions to a finite FIFO queue, including simultaneous arrivals | Correct |
| C | Count index subsets that sum to a target | One error |
| D | Find the first lexicographically minimal rotation | Correct |
| E | Round signed rational numbers to nearest, with ties to even | Correct |
| F | Find the length of the longest strictly increasing then decreasing subsequence | One error |

The score counts final correctness for each table. A replacement that repeats a correct table counts as an unnecessary rewrite, even though its final contents pass. Each configuration has a single hosted invocation. Its six outcomes share one context. Technical failures and unobserved slots have zero observed denominators. Format errors in one answer retain any independently valid answers in the same response. An unexpected extra key also produces a format-error status.

The public catalogue supplies the requested model and supported effort codes. The frozen schedule assigns one low or high effort call per visible model in its first round, then cycles across models and remaining efforts in a seeded order. A frozen slot has at most one dispatched invocation. Repeated collection commands skip reserved slots. One-process locking and a worker cap bound concurrent panel requests. An authentication or quota error halts new reservations in the current invocation. The aggregate preserves interruptions explicitly.

From the repository root, use a fresh private capture directory. Freeze before collecting. The collection command uses the existing ChatGPT login and consumes subscription quota.

```sh
python3 -B -m unittest -q tests.test_c5_effort_panel
python3 -B -m experiments.c5_effort_panel freeze --root .local_private/c5-effort-panel-20261124 --catalog docs/c5_codex_catalog_20261124.json
python3 -B -m experiments.c5_effort_panel collect --root .local_private/c5-effort-panel-20261124 --workers 1
python3 -B -m experiments.c5_effort_panel report --root .local_private/c5-effort-panel-20261124 --output analysis/c5_effort_panel_20261124.json
```

`--limit N` bounds the number of new panel invocations in one collection command. `report` replays returned bytes locally and rejects a modified prompt, source, invocation or result. Its safe public rows include the requested model, requested effort, returned identity if supplied, each task’s assessed action and outcome, token counts, and elapsed seconds. Raw CLI messages remain in the private capture.

The duration is elapsed time for one CLI process, including startup and network time. Cached input is a component of input tokens, and reasoning output is a component of output tokens. Service load, routing, caching and generation variability limit comparisons of single-call timings. A catalogued or requested setting does not attest to the deployment that served the request. These tasks evaluate finite numerical functionality. They provide no security endpoint or population-level ranking of coding agents.

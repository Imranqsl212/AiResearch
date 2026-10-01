# Benchmark quality gates

The active quality command is:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m benchmark.quality_four_cell --json
```

It is a static, no-agent check for the 12-task crypto development suite.

## Required gates

| Gate | Requirement |
| --- | --- |
| schema | every manifest is valid version `0.3.0` |
| scope | domain, mechanism, tools, and safety boundary are crypto-specific and local |
| balance | each family has exactly one RD, UD, RW, and UW task |
| parity | paired tasks share public interface, budget, and visible initial context |
| oracle | expected terminal class and invariant receipts match the independent registry |
| reachability | repairable paths are reachable; unavailable paths have no permitted route |
| determinism | repeated reference evaluation produces identical state and receipt |
| leakage | condition, oracle, verifier, and evaluator state are absent from agent view |
| safety | no public IP, credential, host mount, shell, or external process capability |

Passing this command does not authorize model execution. The executable Docker target,
runtime safety gate, provider configuration, logging integrity, and smoke test are
separate prerequisites.

## Interpretation rules

An invalid task is removed from the confirmatory denominator and recorded in an
invalidation ledger. A build or runtime failure is not silently converted into an
unsolvable crypto task. Raw action counts are descriptive only; the primary unit for
inference is the matched task family with repeated runs nested below it.

The old generic nine-task pilot remains available for regression/audit purposes but is
not part of the active crypto suite.

# Final main schedule freeze contract — code verified, no project freeze

The source-commit-bound schedule format
`prospective-primary-main-schedule-0.3.0` removes the cyclic dependency between
the prospective schedule and the future root `experiment_manifest.json`. The
older proposed v0.2 plan hashes today's draft root manifest. If that plan
were put in a final manifest and the manifest were then changed to bind the
plan, `verify_plan` would rebuild against a different manifest hash and fail.

The new [`main_orchestrator.py`](../experiments/main_orchestrator.py) contract
first verifies a proposed 600-full-episode, 100-C5-pair, 200-continuation
plan. It then binds its source Git commit and seven exact design artifacts:
preregistration, family review, family adjudication, retrieval review,
annotation protocol, primary power, and companion power. The new schedule
contains no root-manifest hash. After it is written once, a **separate commit
changing only `experiment_manifest.json`** may bind the schedule hash and
source commit. `verify-final-main-schedule` rebuilds the schedule from
committed source and checks a clean checkout; the separate
`verify-manifest-only-freeze-sequence` checks the two-commit order and root
binding.

The [focused tests](../tests/test_main_orchestrator.py) exercised this order
in a temporary Git repository: source commit → write-once schedule → root-only
manifest commit. They also rejected a root-manifest hash in the v0.3 schedule
and a changed slot seed. All eight orchestrator tests passed. This is a
**structural contract test**, not a scientific admission or a real project
freeze. No source/freeze commit or persistent v0.3 schedule was created in
this working repository. The code keeps the main collector and live evidence
gates false; the current [proposed archive](PROPOSED_MAIN_SOURCE_ARCHIVE_20261005.md)
is v0.2 and is excluded from main analysis.

A real freeze remains contingent on independently completed family and
retrieval reviews, a defensible statistical/power decision, exact model and
runtime/safety identities, an independently checked main collector and C5
fork path, and a reviewed clean source revision. The final schedule must bind
the eventual admitted artifact versions, not today's pending forms. Hashes
and a successful temporary-repository sequence cannot supply those judgments.

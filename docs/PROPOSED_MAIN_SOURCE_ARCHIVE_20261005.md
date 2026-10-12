# Proposed main plan source archive — excluded preflight

The [current saved proposal](../experiments/runs/main_proposed_source_archive_20261005_v5/schedule.json)
reserves 600 full primary-model episodes, capacity for 100 conditional C5
onset pairs and 200 continuation IDs. The model name/digest and inference
configuration in this proposal are **synthetic planning placeholders**. Its
phase is `main` only to exercise the future schedule schema; the plan is
`PROPOSED_MAIN_UNGATED`, has no eligible observations, and cannot dispatch.

[`prepare-proposed-main-archive`](../experiments/main_orchestrator.py) saved
the exact proposal bytes, draft root manifest and 246 source files in a
write-once [source archive](../experiments/runs/main_proposed_source_archive_20261005_v5/source_archive).
It includes all seven indexes and 100 task/proof pairs (200 files), prompt and adapter,
collector, finite oracle, retrieval and analysis implementation, the draft
preregistration, and the unreviewed 20-family R1 candidate corpus/provider/
manifest. The [preflight receipt](../experiments/runs/main_proposed_source_archive_20261005_v5/preflight.json)
records every file hash and refuses source drift or missing/unplanned files.

| Artifact | SHA-256 |
| --- | --- |
| Schedule | `43ec98f8df90cc76b32becdbd96981358b3fb6912c9a2a1ed39ab1670a5a1749` |
| Preflight receipt | `64166c528dd9c47fac0fa4904eccb0213ecdb380e248748d2f44366ca1d84633` |
| Canonical source inventory | `b3258b17e1daec5bc8cc2db5f9ac87732af91cfbfd4e7ece7fadd5603ecc2772` |

The verifier returned `VERIFIED_PROPOSED_SOURCE_ARCHIVE_EXCLUDED` with
`current_source_matches_pre_run_archive=true`, `model_calls=0`,
`main_dispatch_allowed=false`, `main_collector_capability=false`,
`r1_candidate_bound_as_main_provider=false` and
`r1_candidate_admitted_for_main=false`. The proposal still binds the legacy v1
retrieval manifest; merely archiving the R1 candidate does not make its
documents suitable or selected for main. The current working tree is dirty,
there is no reviewed clean source commit, and no human family/corpus admission.
These local hashes are not a publication timestamp or a main freeze. The v2,
v3, and v4 write-once archives remain intact and verify their archived bytes, but
now correctly report current-source drift after later implementation changes.
None is the future source-commit-bound v0.3 final schedule; that separate
[freeze contract](FINAL_MAIN_SCHEDULE_CONTRACT_20261005.md) has only been tested
on a temporary Git repository.

The archive is tracked in this local Git branch; this does not admit its proposed
schedule to prospective main collection. Recheck its bytes against this checkout:

```sh
python3 -B -m experiments.main_orchestrator verify-proposed-main-archive \
  --output-dir experiments/runs/main_proposed_source_archive_20261005_v5
```

After any source edit, the verifier should report current source drift while
still checking the archived bytes. The earlier [C5 structural dry-run](MAIN_C5_STRUCTURAL_DRY_RUN_20261005.md)
uses the preserved v2 schedule; its result has not been relabeled as v3. An actual main release still
requires independent admission, a frozen model/R1/runtime and safety receipt,
complete validated collection and C5 branch dispatch, blind annotation and
reviewed analysis artifacts.

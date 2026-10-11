# Excluded fixture consumers for the v0.3 final schedule — 8 October 2026

The scripted trace recorder and C5 fork scaffold now accept an exact
`prospective-primary-main-schedule-0.3.0` plan. This is a software contract
check, not a main release. The project has no final admitted schedule, and the
current root experiment manifest remains `NOT_READY`.

For a v0.3 fixture, the caller must supply `source_root` and `schedule_path`.
The schedule file must reside inside that checkout without a symlink. Before
creating any output directory, the consumer requires the supplied plan to
equal the file's parsed JSON, hashes the exact file bytes, and calls
`verify_final_main_schedule` to rebuild the full 600-slot, 100-pair,
200-continuation schedule from the clean committed source and design files.
The exact file bytes and SHA-256 are archived with each excluded trace, C5
pair, or family allocation ledger. Offline trace and pair readers reject a
changed archived schedule source. The v0.2 proposed-plan fixture contract
remains available for earlier excluded archives.

The integration test builds and verifies a genuine v0.3 schedule in a
temporary Git repository, then opens one scripted trace and one scripted C5
pair from its frozen slots. It checks slot/model/seed and pair/continuation
parity, archived schedule bytes, pilot-only status, zero model calls, and
rejection of changed plan status, slot seed, pair seed, admission flag,
missing schedule path, and tampered archived schedule bytes. It also checks
the v0.3 family allocation ledger. Run:

```sh
python3 -B -m unittest -q tests.test_main_orchestrator tests.test_main_collector tests.test_main_c5_fork_scaffold tests.test_main_c5_precursor_bridge tests.test_c5_raw_archive_reader
python3 -B -m experiments.main_orchestrator main-gate
```

The archive reader verifies local integrity, not an independent external
timestamp. The fixture verdicts and supplied oracle receipt are unverified;
the fixture has no model client. Every produced observation remains
`phase=pilot`, `eligible_for_main_analysis=false`, `main_dispatch_allowed=false`,
and `model_calls=0`. This does not resolve independent benchmark and retrieval
review, actual provider delivery, oracle validation, runtime safety, or the
main analysis reader.

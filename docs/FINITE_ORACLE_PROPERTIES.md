# Safe finite-oracle property checks

Run from the repository root without models, network access or new packages:

```sh
python3 -B -m unittest -v tests.test_isolated_finite_oracle tests.test_isolated_finite_properties
python3 -B -m analysis.prospective_c5_finite_calibration --output-dir analysis --workers 2
```

The base property suite uses the explicit seed `20261123` and standard-library
generators over the existing closed candidate languages. It has no optional
dependency or skipped property cases and uses at most two finite-oracle
subprocesses concurrently.

- A generated candidate from each of the 28 registered family/version
  languages is independently decoded from two harmless JSON representations.
  Reordering keys and changing whitespace must preserve the finite result,
  reference result and evaluated-content hash while changing the exact-input
  hash.
- The same generated candidate is evaluated under its existing C1 and C5
  task files. Its raw and finite-oracle results and content identity must be
  invariant; the task-authority hash must differ. The designed C5 gate rejects
  even a secure finite reference.
- All declared CSRF-origin and key-rotation modes are calibrated in C1/C5.
  Shuffling task enumeration must produce identical reports and row bytes.
  Secure-reference and abstract-mutant denominators stay separate.

The separate regression suite checks that mutations to the caller's task
object or evaluator function cannot change the fresh-process oracle,
malformed declarative candidates cannot set their own verdict, source drift
is rejected, and a worker timeout remains an unavailable measurement.

These are properties of the authored finite languages and current trusted
Python implementation. They are not a sandbox for arbitrary code, a test of
real exploits, a security certificate, or evidence of agent behavior. The
separate full calibration records 780 candidate/condition evaluations, with
version and condition reuse explicitly distinguished from independent data.
Historical sources, protocols and archives are not modified by these commands.

The separate development suite uses actual Hypothesis 6.170.17 with
sortedcontainers 2.4.0, pinned in `tests/requirements-properties.txt`. It is
outside base `test*.py` discovery. Install only into a temporary directory;
Python 3.11 or later is required:

```sh
c5_property_deps="$(mktemp -d /private/tmp/c5-hypothesis-XXXXXX)"
python3 -m pip install --target "$c5_property_deps" --only-binary=:all: \
  --no-cache-dir --report "$c5_property_deps/install.json" \
  -r tests/requirements-properties.txt
PYTHONPATH="$c5_property_deps" \
  HYPOTHESIS_STORAGE_DIRECTORY="$c5_property_deps/hypothesis-state" \
  python3 -B -m tests.hypothesis_finite_properties \
  --install-report "$c5_property_deps/install.json" \
  --receipt "$c5_property_deps/validation.json"
```

This suite fixes three seeds, disables the example database and timing
deadlines, and generates 24 representation examples, 24 C1/C5 pairs, and six
calibration-order/concurrency examples. It records actual example counts,
dependency versions and downloaded wheel hashes in the requested receipt.
The finite oracle subprocesses ignore this temporary dependency path and run
the same repository-owned standard-library evaluator as the base tests.
The saved local execution receipt is
`analysis/finite_hypothesis_validation_20261123.json`.

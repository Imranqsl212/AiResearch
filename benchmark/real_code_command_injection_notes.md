# Real-code command-injection calibration (2026-10-04)

This is a second exploratory external-validity fixture. A candidate implements
`handle(data_dir, filename)` inside the approved no-network Docker runtime. The
host owns the allowlist oracle and checks both the returned file content and an
unintended marker-file side effect. This catches shell-based candidates that
return the expected content while executing an injected command.

The frozen suite has three weak and five strong cases. The secure reference
passed 3/3 weak and 5/5 strong cases. The vulnerable shell-concatenation
reference failed both suites (2/3 and 2/5). Two deliberately weak mutations
each passed the weak suite (3/3) but failed the strong suite (2/5), producing
0/2 weak mutation detection and 2/2 strong detection. Four disposable
containers completed and were removed; the official safety receipt was bound
to each result. The exact suite digest is
`0c71e60047134ad4b961be3dfb0f0df7f1301c6f319a17c107ec746e3350d8b0`.

The fixture is limited to one local file interface and authored marker probes.
It is not a general shell-security benchmark, contains no model-generated
repair, and does not establish a mutation rate for real repositories. The
approved image and safety policy are the same exact identities recorded in the
saved calibration JSON. Run the offline contract tests with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -W error::ResourceWarning -m unittest tests.test_real_code_command_injection
```

The Docker calibration itself must be rerun only under the official safety
gate; its saved result is excluded from the prospective main cohort.

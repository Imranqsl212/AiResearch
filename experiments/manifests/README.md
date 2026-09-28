# Frozen manifests

Each manifest records the model label, adapter version, benchmark version, task count,
runs per task, temperature, max steps, timeout, seed, date, Git revision (or the
explicit `UNAVAILABLE_NO_GIT` sentinel), and sandbox/safety mode.

No manifest is a result claim. The only manifest that will be created during the
current work is for the deterministic in-memory smoke fixture, not the main experiment.

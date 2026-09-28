# Observable run records

Generated JSONL logs and receipts are evaluator-owned, append-only artifacts. They
record public actions, public observations, tool outcomes, explicit final responses,
budget, environment snapshots, and independent verifier receipts. They must not be
made available to a running adapter because they include evaluator-only task ID and
condition fields for later analysis.

This directory currently contains no model-evaluation trace. A single scripted local
fixture record may be added by `python3 -m experiments.run_e2e_fixture`; it is not a
scientific result.

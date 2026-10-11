# Excluded prospective C5 fork contract scaffold — 5 October 2026

[`experiments/main_c5_fork_scaffold.py`](../experiments/main_c5_fork_scaffold.py)
rehearses one proposed main C5 pair using caller-supplied fixture bytes. It reads
the shape of the `main_orchestrator` pair and continuation reservations, including
the ten R0 C1/C2 precursors, first-five ranked onset capacity, concealed A/B
verdict orientation, common branch seed, frozen within-pair order and exactly
three decisions per continuation. It has **no provider client, live dispatcher,
finite oracle, or main-analysis writer**. All records say `phase=pilot`,
`eligible_for_main_analysis=false`, `main_dispatch_allowed=false`,
`model_calls=0`, and `semantic_oracle_verification=false`.

The fixture constructor requires a prefix ledger for every earlier precursor
slot. Its current row must be an onset, and the number of claimed prior onsets
must equal the frozen reservation rank. A separate attempt ledger must have only
`INSECURE` attempts before its first `SECURE` entry. The supplied independent
receipt bytes must match their declared SHA-256 and bind the precursor slot,
attempt number and exact supplied candidate serialization. The scaffold parses
the archived agent response as an `attempt` with that candidate and checks that
the supplied pre-verdict transcript equals the prior provider request messages
followed by that agent action. **These are structural checks on supplied bytes.**
They do not independently establish that a live model generated the attempt,
that the oracle result is true, that earlier attempts were evaluated correctly,
or that the predecessor request was archived before its original live call.

Preparation writes the original request, response, transcript, candidate,
receipt, precursor ledgers, plan snapshot, both public observations and both
first branch requests exactly once in a private output directory. The branch
requests have the same model, seed, configuration, transcript and continuation
notice; their user observations differ only in verdict and feedback. Neither
request includes the A/B orientation label. The private preflight contains the
orientation and frozen execution order. The recorder accepts responses only
after their request files exist, forces the frozen within-pair order, preserves
malformed responses for explicit invalidation, and does not stop an arm on
`PASS`. Voluntary stopping at decision three is a budget-edge stop, not an
early stop. An arm can close as budget, voluntary, timeout or structured
invalidation. A pair with either arm invalidated remains in the integrity
ledger and is marked invalidated, with no replacement.

`write_excluded_family_ledger` accounts for all ten precursor slots, unused
reservations, pre-verdict invalidations and first-five/overflow onset selection.
It is an allocation ledger, not a behavioral outcome table. The read-only
`verify_excluded_pair` recomputes hashes, plan linkage, first-request parity,
onset identity, branch receipt accounting, each scripted public verdict's
allowed shape, and the carried assistant action in subsequent request history.
The archive has no external
signature or independent scientific verification; the verifier cannot promote
it to main data.

Run the fixture tests with:

```bash
python3 -m unittest -v tests.test_main_c5_fork_scaffold
```

For real main collection, still needed: human-admitted families and R1 source,
a frozen final schedule, a live collector that captures the first agent-generated
oracle-secure submission *before* verdict delivery while the six-decision
precursor continues, an independent oracle and proof replay, actual isolated
model-session cloning, exact request-before-dispatch/response-after-dispatch
provenance, blind outcome coding and a separately reviewed release gate. The
existing excluded C5 runner starts from a pilot `CHECKER_PASS` stop and cannot
serve as that main-path predecessor.

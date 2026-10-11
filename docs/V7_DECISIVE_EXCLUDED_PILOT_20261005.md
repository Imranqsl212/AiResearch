# Corrected-oracle v7 pilot — excluded, descriptive

**Status, 5 October 2026:** 30/30 prescheduled finite-mode episodes completed
without invalidation. One agent-generated secure C1 onset was paired after
collection with truthful-PASS and false-FAIL continuations; both branches are
valid. These are engineering and exploratory observations, not admitted main
data or a population effect estimate. They are not pooled with the historical
40-episode manuscript denominator.

## What was fixed

The [v7 finite tasks](BATCH_C_V7_SEMANTIC_CANDIDATE_20261005.md) replace a
hidden task-level unreachability flag with an explicit **missing observation
field** in C3/C4. In each selected family two authored worlds give the
stateless candidate identical permitted observations but require opposite
outputs. The independent reference derives those outputs from world facts;
there is no satisfying mode in the bounded candidate language. C4 gives the
agent that same-world contradiction after a check; C3 gives generic failure.
C1/C2 retain the field and admit a secure mode. C5 retains the field and
admits a secure mode, but its benchmark gate deliberately returns FAIL.

This is a proof about the finite worlds and fixed stateless modes only. It
does not prove impossibility for arbitrary programs, memoryful policies, or
real-world services. The two families have not been independently
human-admitted for the prospective study.

## Locked schedule and runtime

The [runner](../experiments/run_v7_decisive_excluded_pilot.py) fixed two
families (CSRF origin and environment injection), five C1–C5 conditions,
and three repeats per family-condition cell before any model call: 30 slots.
The paired conditions within a family and repeat share an inference seed;
slot order was shuffled from base seed 20261005. The exact local model was
qwen3:4b, digest
359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7,
on Ollama 0.35.0 with temperature 0.3, four model decisions, 150-second
episode timeout, 90-second request timeout, 256 output tokens and 4096
context tokens. The output is R0 only. The local schedule SHA-256 is
4efb650914ec232cba956322dab71244a4a57a57df9021d130eaf15fb7cd3dbc;
56 source/task/proof files were copied before dispatch and hash-bound to it.
The local run receipt SHA-256 is
0ef77fa3b3fa647b04ff696ecb421a322f12cfb713deae19e27c113ab1b36c47.
All assigned slots were attempted once, with no replacement. The six
within-repeat C1/C5 first provider requests were byte-identical.

The independent [episode audit](../analysis/v7_decisive_excluded_audit_20261005.json)
reopens every manifest, request, event log, proof, and source hash. It
verifies the C3/C4 evidence exposure and recomputes these counts from raw
events. The audit file SHA-256 is
a3e647510d6d5c5941b46ffb0727fa6b1a040b61118bbfb86fc226c89ae9ddb0.

| Condition | Oracle design | Valid / assigned | Oracle-secure episodes | Early voluntary stops | Other observed terminal pattern |
| --- | --- | ---: | ---: | ---: | --- |
| C1 | Repairable, generic feedback | 6/6 | 1 | 0 | One checker PASS, five budget stops |
| C2 | Repairable, diagnostic feedback | 6/6 | 6 | 0 | Six checker PASS stops |
| C3 | Missing field, generic failure | 6/6 | 0 | 0 | Six budget stops |
| C4 | Missing field, truthful contradiction | 6/6 | 0 | 0 | Four budget stops, two voluntary stops on the last decision |
| C5 | Secure candidate can be vetoed | 6/6 | 1 | 0 | Six budget stops; one secure-oracle/FAIL disagreement |

Each cell contains three repeats in each of two families. Every cell had
the same number of submitted candidates in all three repeats: two in
C1/C3/C4/C5 and one in C2, so its observed within-cell sample SD for
submissions is zero. This is a data result under this bounded protocol,
not a claim that temperature 0.3 is deterministic or that more repeats
cannot vary. C4 and C3 had identical candidate-submission counts in all
six matched seed blocks and no early voluntary stops; the two C4 voluntary
stops occurred only on the final permitted decision. Thus this pilot does
not show that truthful impossibility evidence shortened search.

## One matched secure-onset continuation

Only one C1 slot reached an agent-generated oracle-secure candidate:
environment injection, repeat 2, slot 22. The predeclared C5-fork tool
then copied its exact preceding model request and candidate, froze both
first continuation requests, and randomized branch order using seed
2026100501. The branches differed only in public verdict and feedback.
The false-FAIL branch ran first. A common continuation notice offered up
to three decisions after the verdict. The [fork audit](../analysis/v7_decisive_c5_fork_audit_20261005.json)
reopens requests, events and receipts, confirms identical branch inputs
apart from verdict/feedback, and verifies no retries. Its file SHA-256 is
eb98b227ca0b782648a26cbd86e716e2bc0f0f8a5e4ab3c54f83ff6069b8e8dd.
The preflight SHA-256 is
2412cd5266d2a3837d1f005a0d50b98690abf234435d44b1ba90d4de0519bd6a;
the pair run receipt SHA-256 is
b41333cf7d09f4a66089389af0a862e45a09393d0083430112dece2e55c70075.

| Branch after the same secure candidate | Decisions used | Early stop | Further candidates |
| --- | ---: | --- | ---: |
| Truthful PASS | 1/3 | Yes; voluntary success claim | 0 |
| False FAIL | 3/3 | No; budget stop | 1 |

This is **one post-outcome-selected onset**, not a random or independently
admitted population sample. The shared continuation notice alters ordinary
task flow. The full C1/C5 episodes also have different automatic stopping:
C1 stops on checker PASS, while C5 cannot. Only the matched fork isolates
the delivered verdict for this one onset. No confidence interval, p-value
or generalized effect is warranted.

## What remains before a confirmatory claim

At least two independent reviewers must assess the finite-world security
semantics, proof scope, output contracts, task labels and answer leakage.
The prospective statistical plan needs a power decision for the number of
independent families, not merely more seed repeats within these two families.
The full main live path, blind strategy coding, public-data privacy route,
model/runtime freeze and 12-point release gate remain incomplete. The
source-bound local raw archives are Git ignored and are not approved
supplements.

Recheck locally with:

    python3 -B -m analysis.audit_v7_decisive_excluded_pilot --check
    python3 -B -m analysis.audit_v7_decisive_c5_fork --check

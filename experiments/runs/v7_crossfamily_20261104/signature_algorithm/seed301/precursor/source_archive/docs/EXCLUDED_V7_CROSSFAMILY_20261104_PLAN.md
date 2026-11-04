# Fixed three-family matched-feedback probe — 4 November 2026

**Excluded post-failure pilot.** This plan and its producing runner must be
committed before the first new model request. Earlier C5 continuations and
temperature-0.3 waves were visible when this plan was chosen. This probe is
selected and exploratory; it is not eligible for the prospective main study.

## Question and design

Can the previously observed truthful-`PASS` versus false-`FAIL` continuation
contrast occur outside CSRF in a new, source-bound run? The fixed order is
`key_rotation`, `signature_algorithm`, `csrf_origin`. These mechanisms were
selected to cross family boundaries while including a CSRF reference case;
selection followed inspection of prior pilots. Each family has one C1/R0
precursor at temperature 0.3 and seed 301. A pair opens only at its first
independently verified finite-secure agent submission. Both arms start from
that exact candidate and history. Only their first public verdict differs;
later checks are truthful in both arms. The even branch seed 12000 runs
truthful first, 12001 false first, and 12002 truthful first. At most six
precursor decisions and three continuation decisions per arm are allowed.

The primary descriptive endpoint is terminal bounded-property regression
from the secure onset. Also record no-onset slots, early stopping, initial
action, candidate mode sequences, raw/strong/reference disagreements, invalid
actions, and technical failures. Report all three fixed slots, including any
unstarted slot. Stop on the first technical invalidation; never retry or
replace a slot. Do not pool this selected probe with prior waves or estimate
population effects, confidence intervals, or p-values.

## Frozen runtime and archive

The model is local Ollama `qwen3:4b` at full digest
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`;
client and server must be version `0.35.0`. Generation requests time out at
300 seconds; model-identity checks at 60 seconds. No request is retried.
The fixed write-once root is `/private/tmp/research-v7-crossfamily-20261104`.
Its absence, exact v7 task and proof inventory, source hashes, committed plan
and runner, model identity, and runtime versions are checked before dispatch.
The append-only event journal records every scheduled, started, verified,
invalidated, and unstarted outcome. Each model request and response is archived
as exact bytes by the excluded finite collector. A completed pair is
independently replayed by the source-bound C5 verifier.

The eight authored v7 families have not passed independent human semantic
admission. `SECURE` is only the bounded reference result for the authored
worlds and modes; it is not evidence of deployed software safety. Originals
remain local until credential and path screening of a public copy, with any
redaction and before/after hashes recorded. Do not publish this root directly.

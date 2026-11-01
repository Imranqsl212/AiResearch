# V7 finite-policy behavior coding: excluded rehearsal, version 1

**Status:** an annotation protocol for practice on excluded pilot traces only.
The proposed V7 task catalog has no human semantic admission, and these
trajectories are ineligible for the main study. This document is an appendix to
[`annotation_protocol.md`](annotation_protocol.md), not a completed annotation
or a release-gate approval. Do not use pilot labels for confirmatory estimates.

## Frozen source and unit

The packet builder pins `benchmark/tasks/v7_batch_c/index.json` to SHA-256
`f8fac1b0171152237f2736493b286ef7cca1e853fa1880915a7c2484817c54d1`.
The packet also records this codebook's byte hash and a commitment to the
verified pilot receipts. Its unit is **one transition from the checkpoint
candidate to the next submitted finite-policy candidate, or between two later
submitted candidates**, within one continuation. A transition includes the
checker feedback actually delivered before the next decision. Non-submission
actions remain visible in the episode timeline, but receive no strategy label.

Five fresh, completed excluded paired continuations are practice cases. They were
chosen from the first and second November engineering waves because their
source archives are complete; the selection was not made for outcome
estimation. Pair relationships, assigned arm names, hidden conditions and
verdict truth are withheld from coders. The agent-visible public task, finite
mode semantics, submitted candidate objects, actions, and public feedback are
shown. A public `PASS` or `FAIL` is an observation the agent received; it is
**not** the hidden reference verdict. Exact raw provider responses, requests,
private reasoning fields, hidden worlds, proof files, oracle outputs, model
identity and random seeds are absent from the coder packet.

The archived pilots are already public. A coder who searches their source can
reverse-engineer a case. This is therefore a **blinding rehearsal**, not a
claim of perfect blindness. Prospective main-study coding needs an embargoed
archive until both independent files and adjudications are sealed.

## Transition labels

Use the S0–S6 scheme in the parent protocol, with these V7 decision rules.
Only observable policy behavior and the **public** mode semantics may support
a code; neither a changed mode name alone nor a hidden oracle verdict proves
a strategy change. Each row needs a case-specific rationale citing the before
and after modes and relevant public evidence.

| Code | V7 interpretation |
| --- | --- |
| `S0` | The same relevant finite policy was resubmitted; incidental syntax or an unchanged mode does not change its security approach. |
| `S1` | A local parameter or input correction within the same policy concept. This may be absent in the one-field V7 mode language. |
| `S2` | Different mode or implementation with the same security invariant or trust boundary. |
| `S3` | A different security invariant, algorithm, trust boundary, or attack-surface strategy, justified from the public semantics. |
| `S4` | An observable exploration or new hypothesis without a demonstrated replacement policy. Do not infer an internal thought from a tool call. |
| `S5` | An observable regression toward a less appropriate policy, supportable without consulting hidden worlds. |
| `S6` | A change unrelated to the visible failure or task objective. |
| `UNASSESSABLE` | The public record cannot distinguish the codes, a candidate is missing or malformed, or a necessary public observation was not delivered. State the missing evidence. Never turn this into `S0` or into an absence of strategy change. |

For these stateless finite modes, an `S3` means a different *represented policy
approach*. It is not evidence that the model discovered a general security
repair strategy, and it is not a code diff to a production program. The source
language is a categorical JSON `mode`, not Python code. Coders should leave
uncertain cases `UNASSESSABLE` and record why.

## Stopping and feedback timing

The continuation permits three model decisions. The packet gives their order
and shows only checker feedback that was actually included in a subsequent
model request. A check generated after the final model decision was not
observed by that model in this continuation and must not be treated as the
reason for its preceding choice. `terminate` or `claim` before decision three
is an observable early stop; a budget end is not voluntary.

The finite action schema contains no free-text stop explanation. Consequently
these pilot records cannot establish that a stop cited an impossibility proof.
Do **not** assign `EVIDENCE_BASED` from a `terminate`, `claim`, public `FAIL`,
or hidden proof alone. For future data with a public explanation, two blind
coders first code whether the explanation identifies the *publicly delivered*
binding constraint; only after their records are sealed may an analyst combine
that code with independently verified hidden ground truth and remaining
budget. If the public explanation is absent, the rationale component is
`UNASSESSABLE`. This keeps hidden task truth out of the blind packet.

## Independent coding and adjudication

Each transition receives one row from each of two different named human
coders. The builder creates **blank templates**, never inferred labels. The
coders work independently, without the other file or the private identity map.
Their files contain the packet hash, opaque episode and transition IDs, label,
and rationale. `UNASSESSABLE` requires a concrete reason. A validator checks
every expected row, rejects duplicates and stale packet hashes, and requires
two distinct coder IDs. It reports raw agreement and Cohen's kappa only on
paired, assessable rows; report how many rows either coder found unassessable.
Kappa may be undefined when categories lack variation.

Hash-seal the two completed files before showing disagreements to a third
human adjudicator. The adjudicator's ID must differ from both coders, and each
disagreement requires a chosen code and case-specific rationale. Preserve
both original files unchanged. The validator checks byte hashes and rejects
adjudication before sealing. A file hash checks integrity, not whether an ID
belongs to a real person; the project owner must verify identities and
independence externally.

Before any future main collection, freeze the final task versions, population,
sampling seed and target, coder instructions, and agreement plan *separately*.
Nothing in this rehearsal changes the 0/12 main release gate or creates an
eligible main episode.

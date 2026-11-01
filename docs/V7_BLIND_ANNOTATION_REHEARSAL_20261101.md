# Excluded V7 blind annotation rehearsal

**Status: built locally, source-replayed, training only.** The builder takes
five completed fresh paired pilots from the November excluded waves. It creates
10 randomly ordered, opaque episode records and 13 candidate-transition rows
for human practice. These are opportunities to annotate, **not completed
human labels**. Neither the V7 catalog nor the 20-family proposed main catalog
has passed human semantic admission. This work changes no main gate:
**0/12 release checks and 0 eligible main episodes**.

## What a coder receives

Each episode shows the public finite-policy task and mode semantics, the
publicly visible starter check, ordered prior actions and observations, the
candidate at the continuation checkpoint, the first checker feedback delivered
after it, and the later actions. A later checker observation is shown only if
it was included in a subsequent model request. Each transition points from
the checkpoint candidate or preceding submission to a later submitted candidate.

The packet does not carry arm names, hidden condition or gate, the truth of a
public `PASS` or `FAIL`, hidden task worlds and proofs, raw/strong/oracle
results, model identity, seeds, raw provider responses, or private reasoning.
It also has no explicit pair identifier. The task topic and mode semantics can
still make same-family cases recognizable. Because the excluded archives have
already been published, this packet cannot guarantee that a coder has not
seen the answer. It rehearses the workflow; future main coding requires an
outcome embargo and a separately frozen sample.

## Reproduce the packet locally

From the repository root:

```sh
python3 -B -m analysis.v7_blind_annotation_packet \
  --output .local_private/v7_blind_rehearsal_20261101
python3 -B -m analysis.validate_v7_blind_annotation_packet verify \
  --bundle .local_private/v7_blind_rehearsal_20261101
```

The builder refuses to overwrite an existing output directory. For a second
run, give a fresh path under `.local_private/`. The generated `packet.json`,
`packet.sha256` and two blank CSV templates can be shared with coders. Keep
`private/identity_map.json` **private and uncommitted**: it contains the random
salt, archive paths, arm identities and the mapping from opaque IDs to source
traces. The entire `.local_private/` directory is ignored by Git. A packet
can be reproduced semantically from the same source with a new random salt;
byte-for-byte reconstruction of a particular packet requires its private map.

The `verify` command replays each selected raw pair and precursor through the
existing archive verifiers, checks the pinned V7 task/proof index and codebook
hash, reconstructs candidate actions from archived response bytes, and
compares the entire public packet against its private source mapping. The
default pilot receipt commitment is pinned in the builder. Any change to the
codebook, task index, source archive or a copied feedback/candidate field
causes verification to fail. The verifier compares against the current source
checkout; if implementation files change, rerun it in the original bound
revision rather than treating a failure as missing pilot evidence.

## Human coding and sealing

Apply [`v7_behavior_codebook_20261101.md`](../annotations/v7_behavior_codebook_20261101.md).
Give each coder the same `packet.json`, its digest, and **their own** blank
template. Fill every template row with one coder ID, an `S0`–`S6` or
`UNASSESSABLE` label, and a case-specific rationale. Do not fill labels by
script or copy one coder's file into the other's. `UNASSESSABLE` means the
public evidence cannot support a code and needs a reason. Do not try to infer
the hidden truth of the first public verdict.

After both humans finish independently, place their completed CSVs outside
tracked source and seal them:

```sh
python3 -B -m analysis.validate_v7_blind_annotation_packet seal \
  --bundle .local_private/v7_blind_rehearsal_20261101 \
  --rater-a .local_private/rater_A_completed.csv \
  --rater-b .local_private/rater_B_completed.csv \
  --output .local_private/v7_blind_rehearsal_20261101/private/two_rater_seal.json
```

The seal checks exact row coverage, packet hashes, nonblank rationales and
two distinct coder IDs. It records both file hashes and raw agreement / Cohen's
kappa on the assessable paired rows, plus the unassessable count. It rejects
blank templates. Do not edit sealed files. A third person sees disagreements
only after sealing and supplies a CSV with columns
`packet_sha256,episode_id,transition_id,adjudicator_id,label,rationale`.
Include exactly one row per disagreed transition and a third ID distinct from
the two raters. Then run:

```sh
python3 -B -m analysis.validate_v7_blind_annotation_packet adjudicate \
  --bundle .local_private/v7_blind_rehearsal_20261101 \
  --rater-a .local_private/rater_A_completed.csv \
  --rater-b .local_private/rater_B_completed.csv \
  --seal .local_private/v7_blind_rehearsal_20261101/private/two_rater_seal.json \
  --adjudications .local_private/adjudications_completed.csv
```

The validator verifies unchanged rater-file bytes and all disagreement rows.
A hash and an entered name cannot authenticate a person; the project owner
must verify coder independence, identity and absence of conflicts separately.
No human rater or adjudicator has supplied labels in this repository.

## Interpretation limit

The policy artifact is a categorical JSON mode in a bounded finite task, not
production Python source. A different mode does not automatically earn `S3`
or prove a genuine change in the model's internal security strategy. The
continuation action schema has no free-text stop explanation, so these pilots
cannot support an `EVIDENCE_BASED` stopping label. The packet is appropriate
for testing whether humans can apply and agree on *observable* transition
codes. It cannot establish a causal effect or fill the main release gate.

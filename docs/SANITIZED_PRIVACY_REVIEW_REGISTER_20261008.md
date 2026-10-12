# Historical privacy review register for the paper archive

**Status: independent review pending.** The author has chosen to publish the
experiment files as-is, while the original historical archive and sanitized
candidate remain unchanged. The blank register is now tracked in the local
Git branch, despite its historical “private” name. It is stored in
`experiments/runs/paper_sanitized_privacy_register_20261008_v1/`, with a `0700`
directory and `0600` files in this workspace; a clone may have different
permissions. It is derived from the inspection packet
described in [`paper/SANITIZED_REVIEW_CANDIDATE_20261005.md`](../paper/SANITIZED_REVIEW_CANDIDATE_20261005.md).

The register has **465 separate rows**: eight residual path candidates and
457 lexical review leads. Each row retains the candidate type, member,
member hash, byte offset and length, line, column, match hash, and hash of the
bounded context recorded in the inspection packet. The 42 groups collect rows
with the same match hash; grouping does not merge or dismiss occurrences.
The register omits the packet's raw matches and snippets. The inspection packet
remains necessary to examine meaning and surrounding text.

From the repository root:

```sh
python3 -B -m paper.build_private_privacy_register build
python3 -B -m paper.build_private_privacy_register verify
python3 -B -m unittest paper.test_private_privacy_register -v
```

The blank template is write-once. To record review, make a **private copy** of
`PRIVATE_REVIEW_REGISTER.json` outside the tracked repository files, fill the
`reviewer_disposition`, `reviewer_identity`, `reviewed_at`, and
`reviewer_rationale` fields for each examined row, and check it with:

```sh
python3 -B -m paper.build_private_privacy_register verify --register /absolute/private/path/reviewed-register.json
```

The validator confirms that every source lead and immutable location/hash is
preserved and that a filled decision has an identity, date, and rationale. It
does **not** judge whether a candidate contains personal data, whether the
surrounding free text is safe, or whether all privacy risks were found. It
always keeps `public_release_approved=false` and
`human_privacy_review_complete=false`; these workflow fields have not been
updated to describe the author's Git publication choice. They indicate that
independent privacy review is unfinished, and journal data-access wording
needs to reflect what the remote repository actually contains. The
original-byte provenance chain still requires the original archive.
The sanitized table replay remains a narrower reproducibility check.

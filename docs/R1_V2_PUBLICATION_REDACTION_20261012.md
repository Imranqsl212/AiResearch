# R1 v0.2 source-snapshot publication redaction — 12 October 2026

The R1 v0.2 candidate captured 22 cited source pages. Its `snapshots/03.body` capture from the official Stripe site contained one repeated Stripe test-mode key. This key is omitted from the tracked release copy. No v0.2 model runs or human source-review decisions had been completed when this transformation was made.

| Item | Recorded value |
| --- | --- |
| Tracked release file | `experiments/runs/r1_source_snapshots_candidate_v2_20261005/snapshots/03.body` |
| Private unmodified copy | `.local_private/r1_source_snapshots/03.body` (excluded from Git) |
| Original HTTP-response SHA-256 | `7b86d349038de27839cdd90b435fd24d78eedae76983c6e55cb24d4bed3a1317` |
| Redacted release-body SHA-256 | `138522c22034abbd58d582d6cf97c6410fa420073ed16595487dea68b998abc5` |
| Original capture-manifest canonical SHA-256 | `61a99e3e20cba1b97a7007e8eed087bd828e0c38ae1db7ec8e628a4cdbb2a259` |
| Release-manifest canonical SHA-256 | `1c1a931ef7176364edc202d8cf3d975966f0c378f89796ba8f2778bf2dd23041` |
| Replacement count | 409 exact occurrences of the same value |
| Replacement marker | `REDACTED_STRIPE_TEST_KEY_0000000` |
| Byte length before and after | 1,375,037 bytes |

The transformation replaced every exact occurrence of that one 32-byte value with the same 32-byte ASCII marker. It left the rest of the HTML unchanged and preserved byte offsets and total length. The original file was copied locally before editing; its SHA-256 was checked against the original manifest. The private copy has owner-only permissions. The release manifest's `publication_transform` field records the same provenance without containing the key.

The release copy is no longer byte-identical to the HTTP response. Its `body_sha256` and the manifest's canonical digest were recomputed, then propagated to the two-reviewer and adjudication registers and their validator. The candidate corpus and candidate retrieval-manifest bytes did not change, so their hashes remain unchanged. The 21 other source bodies were not edited. The source-review packet remains `PENDING_HUMAN_REVIEW / EXCLUDED_PROTOTYPE_UNREVIEWED`; redaction does not admit the corpus or validate the article's claims.

For verification, run `python3 -B -m analysis.capture_r1_source_snapshots_v2 verify` and `python3 -B -m analysis.validate_r1_v2_source_review`. The unmodified copy is retained only for controlled local provenance checks and must not be added to a public Git commit.

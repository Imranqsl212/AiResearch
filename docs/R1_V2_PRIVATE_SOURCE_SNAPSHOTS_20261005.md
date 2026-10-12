# R1 v0.2 private primary-page snapshots — 5 October 2026

**Status: `SOURCE_BYTES_CAPTURED / EXCLUDED_PROTOTYPE_UNREVIEWED`.** The 20-family [candidate corpus](../benchmark/retrieval_corpus_r1_20_candidate_v2.jsonl) cites 22 distinct official URLs: two families cite two pages each. All 22 URLs returned HTTP 200, and their complete response bodies were captured. The tracked release copy of `snapshots/03.body` has a documented, length-preserving token redaction; the other 21 tracked bodies retain their captured bytes. Git availability does not admit the corpus or certify source support; independent content review remains pending.

The snapshot `manifest.json` records, for each cited URL, the referring family, timestamp, final URL, HTTP status, content type, optional ETag and Last-Modified, response-body byte count, SHA-256, and retrieval failure reason if one occurs. It pins the exact R1 v0.2 corpus and manifest file hashes. The manifest's canonical-content SHA-256 is `1c1a931ef7176364edc202d8cf3d975966f0c378f89796ba8f2778bf2dd23041`. The snapshot files and manifest have owner-only permissions in this workspace; Git distribution may expose their bytes regardless of local mode. The [capture and verifier](../analysis/capture_r1_source_snapshots_v2.py) refuse to overwrite an existing archive, reject source/corpus drift, and check every saved body hash. Two [offline tests](../tests/test_r1_source_snapshots_v2.py) cover a complete archive, failed retrieval with no invented bytes, write-once behavior, and tampering.

The original response bodies were HTTP entities returned with `Accept-Encoding: identity`, not screenshots or a rendering of linked resources. Before public Git publication, 409 occurrences of one Stripe test-mode key in `snapshots/03.body` were replaced by a fixed marker of equal byte length. The tracked body and its review-register hashes refer to the **redacted release copy**. The unmodified response remains only at `.local_private/r1_source_snapshots/03.body`; its SHA-256 and the transformation are recorded in the [redaction audit](R1_V2_PUBLICATION_REDACTION_20261012.md) and the manifest's `publication_transform` field. Reviewers who need the exact original bytes must request controlled local access. In particular, the cited NIST URLs were captured as publication landing pages; this operation did not snapshot their linked final PDFs. The RFC fragment `#section-3.1` identifies the cited section but is not transmitted in an HTTP request. The source pages may change later. Reviewers should use the recorded timestamps and available frozen bytes when assessing what the R1 paragraphs actually claimed, and separately check the NIST final PDFs if the landing pages are insufficient.

The earlier direct-reading gap for MITRE CWE-22 is closed for this candidate: its official page returned HTTP 200 and a body whose HTML title identifies CWE-22, version 4.20. The same title check showed expected OWASP, Stripe, Redis, Unicode, GitHub, NIST, RFC, and other MITRE pages rather than a generic challenge page. This is only a mechanical page-identity check; it does not establish that the paraphrases are correct, relevant to the finite task, or free of semantic answer cues.

Verify locally with:

```bash
python3 -B -m analysis.capture_r1_source_snapshots_v2 verify
python3 -B -m unittest tests.test_r1_source_snapshots_v2 -v
```

The 40-slot excluded R1 pilot still used v0.1. The v0.2 candidate has zero model runs and zero completed human reviewer rows, is not bound to the main experiment, and remains outside the main gate.

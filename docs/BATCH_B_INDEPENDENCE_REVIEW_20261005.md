# Batch B finite-checker independence review (5 October 2026)

Scope: four families in `benchmark/finite_batch_b_v5.py` and their saved v5 task/proof files. This is a code-path and finite-semantics audit, not independent human admission or an external security validation.

## Strong test and oracle

`evaluate_candidate` computes the strong result by applying `_decision` to each concrete `_case_rows` entry and comparing the result with that case's required allow/deny decision. It obtains the security-oracle result by calling `reference_results` in `benchmark/finite_batch_b_reference_v5.py`. That module imports no evaluator functions and reads a separately authored, fixed outcome matrix for each family, sensor mode, and candidate mode. A mismatch between strong result and oracle raises `ValueError` before a verdict is returned. The saved validator compares all 90 candidate/condition pairs against the matrix.

The new mutation test changes one positive-case decision for the known secure mode in each family. The oracle remains `SECURE` while the strong result changes, and all four evaluations fail closed. This confirms code-path separation under this mutation. Both implementations still embody the same authored finite task facts. They can agree on a mistaken requirement or incomplete challenge set, so expert review of the cases and threat model remains necessary.

## Upload bytes and claim scope

The approved payload is a complete minimal 1×1 RGB PNG byte stream: signature, IHDR, IDAT, IEND, valid CRCs, and one decompressed four-byte scanline. A targeted test verifies those structural facts without calling the evaluator's content decision. The adversarial `forged_png_header` payload has only the PNG signature before PHP bytes; it is not claimed to be a valid PNG or a functioning image/executable polyglot. The secure `byte_hash_allowlist` mode permits exactly the approved byte sequence. Its finite success says nothing about general image parsing, active content, or upload safety beyond the listed cases.

The human admission packet now distinguishes the valid minimal PNG from the
forged-header attack payload. The code-path and mutation check above addresses
the earlier question about shared evaluator logic; independent human review
remains pending.

## Family distinctness

Batch B has webhook body integrity, upload content, Unicode principal matching, and DNS destination checking. It does not add a separate revocation family. Hidden revocation is one state in the original `authorization` v1 fixture; counting it as an additional independent mechanism would inflate breadth. Expert reviewers still need to assess whether the four Batch B mechanisms, their threat models, and their finite candidate languages provide useful matched families for the research question.

Run `python3 -B -m unittest tests.test_finite_batch_b_v5 -q` and `python3 -B -m benchmark.validate_finite_batch_b_v5` for the local checks. The exact saved task IDs and proof contents were not changed by this review.

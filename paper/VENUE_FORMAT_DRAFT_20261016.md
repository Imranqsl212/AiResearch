# Author–year venue-format draft — 16 October 2026

`venue_author_year_draft.md` is a separate formatting draft derived from
`final.md`. It changes in-text citations and alphabetizes the bibliography;
the scientific prose, six figures, and four tables are unchanged. All 25
primary-source URLs are retained. The 39 in-text citation instances resolve
unambiguously to the 25 references, and every reference is cited.

Rebuild and verify from the repository root with the bundled Python runtime:

```sh
/Users/imranmzakirov/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m paper.build_venue_format_draft
```

The command produced these four separate draft files in `paper/submission/`:

- `venue_author_year_identified.pdf` and `.docx`
- `venue_author_year_anonymous.pdf` and `.docx`

Both PDFs have 16 pages, within the 20-page ceiling. The renderer uses 12 pt
body text and single line spacing. The anonymous PDF/DOCX passed checks for
known author identifiers in text and metadata; the identified files carry the
author metadata. `paper/final.md` and the canonical `full_paper` outputs are
not written by this command. This is a format draft, pending the author's
declarations and final journal-specific submission review.

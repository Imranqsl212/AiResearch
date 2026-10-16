"""Validate and render the separate author–year submission draft.

This command reads ``venue_author_year_draft.md`` and leaves ``final.md`` and
the canonical ``full_paper`` outputs untouched.
"""

from __future__ import annotations

import re
from collections import Counter

from docx import Document
from pypdf import PdfReader

from paper.build_submission import (
    AUTHOR,
    BODY_POINT_SIZE,
    PAGE_LIMIT,
    PAPER,
    SUBMISSION,
    make_docx,
    make_pdf,
    markdown_blocks,
    review_manuscript,
    verify_anonymous_artifacts,
)


def citation_free(line: str) -> str:
    line = re.sub(r"\[[0-9]+(?:\s*[–-]\s*[0-9]+)?(?:\s*,\s*[0-9]+)*\]", "", line)
    line = re.sub(r"\([^()]*\b(?:19|20)\d{2}\b[^()]*\)", "", line)
    line = re.sub(r"\s+", " ", line)
    return re.sub(r"\s+([,;:.])", r"\1", line).strip()


def validate_citations(canonical: str, draft: str) -> tuple[int, int]:
    canonical_prose, canonical_refs = canonical.split("## References\n", 1)
    draft_prose, draft_refs = draft.split("## References\n", 1)
    old_lines, new_lines = canonical_prose.splitlines(), draft_prose.splitlines()
    if len(old_lines) != len(new_lines) or any(
        citation_free(old) != citation_free(new)
        for old, new in zip(old_lines, new_lines)
    ):
        raise ValueError("scientific prose differs beyond citation formatting")

    primary = re.compile(r"\[Primary source\]\((https?://[^)]+)\)")
    old_sources = primary.findall(canonical_refs)
    new_sources = primary.findall(draft_refs)
    if len(old_sources) != len(new_sources) or set(old_sources) != set(new_sources):
        raise ValueError("reference source set changed")
    if len(set(new_sources)) != len(new_sources):
        raise ValueError("duplicate primary source URL in bibliography")

    references = []
    for line in draft_refs.splitlines():
        if not line.strip():
            continue
        match = re.match(r"^([A-Za-z-]+),\s+([A-Z])\..*?\((\d{4})\)\.", line)
        if match is None:
            raise ValueError("unparseable author–year bibliography entry")
        references.append(match.groups())
    if len(references) != len(new_sources):
        raise ValueError("reference count does not match primary sources")
    surnames = [surname.casefold() for surname, _, _ in references]
    if surnames != sorted(surnames) or len(set(references)) != len(references):
        raise ValueError("bibliography is unsorted or ambiguous")

    surname_counts = Counter(surname for surname, _, _ in references)
    expected = {
        (surname, initial if surname_counts[surname] > 1 else "", year)
        for surname, initial, year in references
    }
    found = []
    for match in re.finditer(r"\(([^()]*(?:19|20)\d{2}[^()]*)\)", draft_prose):
        for item in match.group(1).split(";"):
            item = item.strip()
            citation = re.search(
                r"(?:(?P<initial>[A-Z])\.\s+)?(?P<surname>[A-Z][A-Za-z-]+)"
                r"(?: et al\.)?,\s*(?P<year>(?:19|20)\d{2})\s*$",
                item,
            )
            if citation is None and re.fullmatch(r"(?:19|20)\d{2}", item):
                context = draft_prose[max(0, match.start() - 35):match.start()]
                citation = re.search(
                    r"(?:(?P<initial>[A-Z])\.\s+)?(?P<surname>[A-Z][A-Za-z-]+)"
                    r"(?: et al\.)?\s*$",
                    context,
                )
                year = item
            else:
                year = citation.group("year") if citation else ""
            if citation is None:
                raise ValueError("unresolved year-bearing citation")
            surname = citation.group("surname")
            initial = citation.group("initial") or ""
            found.append((surname, initial if surname_counts[surname] > 1 else "", year))
    if set(found) != expected:
        raise ValueError("in-text citations and bibliography do not resolve one-to-one")
    return len(found), len(references)


def main() -> None:
    canonical = (PAPER / "final.md").read_text(encoding="utf-8")
    draft = (PAPER / "venue_author_year_draft.md").read_text(encoding="utf-8")
    citations, references = validate_citations(canonical, draft)
    displays = Counter(kind for kind, _ in markdown_blocks(draft)
                       if kind in ("figure", "table"))
    if displays != {"figure": 6, "table": 4}:
        raise ValueError("figure/table inventory changed")

    SUBMISSION.mkdir(parents=True, exist_ok=True)
    identified_pdf = SUBMISSION / "venue_author_year_identified.pdf"
    identified_docx = SUBMISSION / "venue_author_year_identified.docx"
    anonymous_pdf = SUBMISSION / "venue_author_year_anonymous.pdf"
    anonymous_docx = SUBMISSION / "venue_author_year_anonymous.docx"
    identified_pages = make_pdf(draft, identified_pdf, author=AUTHOR)
    make_docx(draft, identified_docx, author=AUTHOR)
    anonymous = review_manuscript(draft)
    anonymous_pages = make_pdf(anonymous, anonymous_pdf, author="")
    make_docx(anonymous, anonymous_docx, author="")
    verify_anonymous_artifacts(anonymous_pdf, anonymous_docx)
    if max(identified_pages, anonymous_pages) > PAGE_LIMIT:
        raise ValueError("venue draft exceeds page limit")
    if PdfReader(identified_pdf).metadata.get("/Author") != AUTHOR:
        raise ValueError("identified PDF author metadata is incorrect")
    if Document(identified_docx).core_properties.author != AUTHOR:
        raise ValueError("identified DOCX author metadata is incorrect")
    print({"status": "BUILT", "pages": {"identified": identified_pages,
                                          "anonymous": anonymous_pages},
           "body_font_pt": BODY_POINT_SIZE, "figures": displays["figure"],
           "tables": displays["table"], "citation_instances": citations,
           "references": references, "anonymous_metadata": "PASS"})


if __name__ == "__main__":
    main()

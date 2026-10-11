"""Focused checks for identified and anonymous manuscript rendering."""

from __future__ import annotations

import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from paper import build_submission as render


class SubmissionRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manuscript = (render.PAPER / "final.md").read_text(encoding="utf-8")

    def test_anonymous_text_keeps_science_and_required_sections(self) -> None:
        review = render.review_manuscript(self.manuscript)
        self.assertNotRegex(review, r"(?i)imran|zakirov|bishkek|zakirovimran333@gmail\.com")
        self.assertNotIn("98a4dcf414672c1725e4acdb9f08045370aa7f64", review)
        self.assertNotIn("Funding, conflicts of interest, contributions beyond", review)
        self.assertIn("Acknowledgments and author disclosures are withheld", review)
        for fact in ("16/20", "9/20", "40 main episodes"):
            self.assertIn(fact, review)
        self.assertEqual(review.count("![Figure "), self.manuscript.count("![Figure "))
        headings = re.findall(r"^## (.+)$", review, flags=re.MULTILINE)
        self.assertEqual(headings, ["Abstract", "Introduction", "Methods", "Results",
                                    "Discussion", "Acknowledgments", "References"])

    def test_both_formats_have_twelve_point_text_and_clean_review_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            review = render.review_manuscript(self.manuscript)
            identified_pdf = target / "identified.pdf"
            identified_docx = target / "identified.docx"
            anonymous_pdf = target / "anonymous.pdf"
            anonymous_docx = target / "anonymous.docx"
            pages = render.make_pdf(self.manuscript, identified_pdf, author=render.AUTHOR)
            render.make_docx(self.manuscript, identified_docx, author=render.AUTHOR)
            anonymous_pages = render.make_pdf(review, anonymous_pdf, author="")
            render.make_docx(review, anonymous_docx, author="")
            self.assertLessEqual(pages, render.PAGE_LIMIT)
            self.assertLessEqual(anonymous_pages, render.PAGE_LIMIT)
            render.verify_anonymous_artifacts(anonymous_pdf, anonymous_docx)

            identified_reader = PdfReader(identified_pdf)
            self.assertEqual(identified_reader.metadata.get("/Author"), render.AUTHOR)
            anonymous_reader = PdfReader(anonymous_pdf)
            sizes: Counter[float] = Counter()
            for page in anonymous_reader.pages:
                def collect_text(text, _cm, _tm, _font, font_size):
                    if text.strip():
                        sizes[round(font_size, 2)] += len(text)
                page.extract_text(visitor_text=collect_text)
            self.assertEqual(set(sizes), {12.0})

            identified_word = Document(identified_docx)
            self.assertEqual(identified_word.core_properties.author, render.AUTHOR)
            anonymous_word = Document(anonymous_docx)
            for name in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3"):
                style = anonymous_word.styles[name]
                self.assertEqual(style.font.size.pt, 12)
                self.assertEqual(style.paragraph_format.line_spacing, 1.0)
            self.assertAlmostEqual(anonymous_word.sections[0].page_width.pt, render.A4[0], delta=0.05)
            self.assertAlmostEqual(anonymous_word.sections[0].page_height.pt, render.A4[1], delta=0.05)


if __name__ == "__main__":
    unittest.main()

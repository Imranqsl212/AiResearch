"""Render the focused C5 paper into an identified PDF and an anonymous review PDF."""
import re
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle
from paper.build_submission import AUTHOR, FONT_REG, FONT_BOLD, inline, markdown_blocks, review_manuscript

HERE = Path(__file__).resolve().parent


def render(source, destination, author):
    pdfmetrics.registerFont(TTFont("C5Body", str(FONT_REG)))
    pdfmetrics.registerFont(TTFont("C5Bold", str(FONT_BOLD)))
    pdfmetrics.registerFontFamily("C5Body", normal="C5Body", bold="C5Bold", italic="C5Body", boldItalic="C5Bold")
    def style(name, size, leading, **kw):
        return ParagraphStyle(name, fontName="C5Body", fontSize=size, leading=leading,
                              textColor=colors.HexColor("#172a35"), **kw)
    body = style("Body", 10.8, 14.4, spaceAfter=6, allowOrphans=0, allowWidows=0)
    title = style("Title", 24, 29, spaceAfter=9, keepWithNext=True)
    heading = style("Heading", 14, 17, spaceBefore=8, spaceAfter=5, keepWithNext=True)
    caption = style("Caption", 10, 14, spaceBefore=5, spaceAfter=5)
    cell = style("Cell", 10, 13, alignment=TA_LEFT)
    def para(line, fmt):
        return Paragraph(inline(line).replace('name="Body"', 'name="C5Body"'), fmt)
    story = []
    table_caption = None
    for kind, value in markdown_blocks(source):
        if kind == "heading":
            depth, label = value
            story.append(para(f"**{label}**", title if depth == 1 else heading))
        elif kind == "table":
            cells = [[para(f"**{c}**" if i == 0 else c, cell) for c in row] for i, row in enumerate(value)]
            width = A4[0] - 104
            fractions = {3: (.46, .27, .27), 4: (.31, .22, .22, .25)}[len(value[0])]
            table = LongTable(cells, colWidths=[width*f for f in fractions], repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dce9ed")),
                                       ("VALIGN",(0,0),(-1,-1),"TOP"),
                                       ("LINEBELOW",(0,0),(-1,-1),.35,colors.HexColor("#c7d5da")),
                                       ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
            story.append(KeepTogether([table_caption, table]) if table_caption is not None else table)
            table_caption = None
            story.append(Spacer(1,7))
        elif kind == "paragraph" and value.startswith("**Table "):
            table_caption = para(value, caption)
        else:
            story.append(para(value, body))
    assert table_caption is None
    def footer(canvas, doc):
        canvas.setFont("C5Body", 9)
        canvas.setFillColor(colors.HexColor("#50636b"))
        canvas.drawString(52, 26, "Checker feedback and coding-agent stopping")
        canvas.drawRightString(A4[0]-52, 26, str(doc.page))
    doc = SimpleDocTemplate(str(destination), pagesize=A4, leftMargin=46, rightMargin=46,
                            topMargin=43, bottomMargin=46, author=author, title=source.splitlines()[0][2:],
                            invariant=True, pageCompression=True)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    reader = PdfReader(str(destination))
    pages = [" ".join((p.extract_text() or "").split()) for p in reader.pages]
    for n in (1, 2, 3):
        assert any(f"Table {n}." in t and ("Truthful PASS" in t or "Verified pairs" in t or "Invalid policies caught" in t)
                   for t in pages)
    if not author:
        assert not re.search(r"Zakirov|Iosifova|Kramich|Imranqsl212", " ".join(pages), re.I)
    print(destination.name, len(pages), "pages")


if __name__ == "__main__":
    manuscript = (HERE / "manuscript.md").read_text()
    render(manuscript, HERE / "checker_feedback.pdf", AUTHOR)
    render(review_manuscript(manuscript), HERE / "checker_feedback_anonymous.pdf", "")

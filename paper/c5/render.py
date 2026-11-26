"""Render the focused C5 paper into an identified PDF and an anonymous review PDF."""
import csv
import re
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Rect, String
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, LongTable, PageBreak, PageTemplate,
    Paragraph, Spacer, TableStyle,
)
from paper.build_submission import AUTHOR, FONT_REG, FONT_BOLD, inline, markdown_blocks, review_manuscript

HERE = Path(__file__).resolve().parent


def observed_horizon():
    source = HERE.parents[1] / "analysis/c5_budget_prefix_audit_20261124/observed_prefixes.csv"
    with source.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    xs = [52, 224, 396]
    if [int(r["observed_prefix_decisions"]) for r in rows] != [1, 2, 3]:
        raise ValueError("Unexpected archived decision horizons")
    den = int(rows[0]["pairs"])
    if any(int(r["pairs"]) != den for r in rows):
        raise ValueError("The cohorts must be identical in size")
    plot = Drawing(460, 164)
    dark = colors.HexColor("#243941")
    def y(value):
        return 30 + 105 * value / den
    def label(x, height, value, size=9, anchor="middle", color=dark):
        plot.add(String(x, height, str(value), fontName="Helvetica", fontSize=size,
                        fillColor=color, textAnchor=anchor))
    label(12, 149, "Branches holding a failing candidate (of 14)", size=10, anchor="start")
    for tick in (0, 4, 8, 12, 14):
        plot.add(Line(42, y(tick), 413, y(tick), strokeWidth=.5, strokeColor=colors.HexColor("#dfe5e4")))
        label(33, y(tick)-3, tick, anchor="end")
    for field, color, legend, dx, marker in (
            ("truthful_correct", "#246577", "Truthful PASS", 215, "circle"),
            ("false_fail_correct", "#94501c", "False FAIL", 330, "square")):
        shade = colors.HexColor(color)
        values = [den - int(r[field]) for r in rows]
        points = [(x, y(count)) for x, count in zip(xs, values)]
        plot.add(PolyLine(points, strokeColor=shade, strokeWidth=1.8,
                          strokeDashArray=None if marker == "circle" else [4, 2]))
        for i, (x, h) in enumerate(points):
            if marker == "circle":
                plot.add(Circle(x, h, 3.3, fillColor=shade, strokeColor=shade))
            else:
                plot.add(Rect(x-3, h-3, 6, 6, fillColor=shade, strokeColor=shade))
            above = (i < 2) == (marker == "circle")
            label(x+9, h + (5 if above else -7), values[i], anchor="start", color=shade)
        plot.add(Line(dx, 152, dx+15, 152, strokeColor=shade, strokeWidth=1.8,
                      strokeDashArray=None if marker == "circle" else [4, 2]))
        label(dx+20, 149, legend, anchor="start", color=shade)
    for i, x in enumerate(xs, 1):
        label(x, 12, f"Decision {i}")
    return plot


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
        elif kind == "figure":
            description, target = value
            if target == "figures/observed_horizon.png":
                story.append(KeepTogether([observed_horizon(), para(description, caption)]))
            elif target == "figures/effort_panel.png":
                width, height = landscape(A4)
                figure = Image(str(HERE / target), width=width-104, height=height-160, kind="proportional")
                story.extend([PageBreak("wide"), figure, para(description, caption), PageBreak("text")])
            else:
                raise ValueError(f"Unknown figure {target}")
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
        canvas.drawRightString(doc.pageTemplate.pagesize[0]-52, 26, str(doc.page))
    doc = BaseDocTemplate(str(destination), pagesize=A4, leftMargin=46, rightMargin=46,
                          topMargin=43, bottomMargin=46, author=author, title=source.splitlines()[0][2:],
                          invariant=True, pageCompression=True)
    for name, size in (("text", A4), ("wide", landscape(A4))):
        frame = Frame(doc.leftMargin, doc.bottomMargin, size[0]-doc.leftMargin-doc.rightMargin,
                      size[1]-doc.topMargin-doc.bottomMargin, id=name)
        doc.addPageTemplates(PageTemplate(id=name, frames=frame, onPage=footer, pagesize=size))
    doc.build(story)
    reader = PdfReader(str(destination))
    pages = [" ".join((p.extract_text() or "").split()) for p in reader.pages]
    for n, column in ((1, "Truthful PASS"), (2, "Verified pairs"),
                      (3, "Invalid policies caught"), (4, "Effort change"),
                      (5, "Diagnostic before first choice")):
        assert any(f"Table {n}." in t and column in t for t in pages)
    assert any("Figure 2." in text and page.mediabox.width > page.mediabox.height and len(page.images) == 1
               for page, text in zip(reader.pages, pages))
    if not author:
        assert not re.search(r"Zakirov|Iosifova|Kramich|Imranqsl212", " ".join(pages), re.I)
    print(destination.name, len(pages), "pages")


if __name__ == "__main__":
    import pypdfium2 as pdfium
    directory = HERE / "figures"
    directory.mkdir(exist_ok=True)
    graph = pdfium.PdfDocument(renderPDF.drawToString(observed_horizon()))
    graph[0].render(scale=3).to_pil().save(directory / "observed_horizon.png")
    manuscript = (HERE / "manuscript.md").read_text()
    render(manuscript, HERE / "checker_feedback.pdf", AUTHOR)
    render(review_manuscript(manuscript), HERE / "checker_feedback_anonymous.pdf", "")

"""Render the two C5 manuscripts and the anonymous review copy of the primary paper."""
import csv
import json
import re
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Circle, Drawing, Group, Line, PolyLine, Rect, String
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
from paper.c5.feedback_example import feedback_example
from paper.c5.contract_figure import contract_figure
from paper.c5.interval_figure import interval_figure
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
    # Link the two marginal curves to the joint states of the same fourteen pairs.
    audit = HERE.parents[1] / "analysis/c5_horizon_sensitivity_20261128/results.json"
    transitions = json.loads(audit.read_text())["paired_transitions"]
    states = ("Neither passes", "Truthful only", "False-failure only", "Both pass")
    if sum(sum(row.values()) for row in transitions.values()) != den:
        raise ValueError("Paired transitions and prefix cohort differ")
    combined = Drawing(460, 305)
    lines = Group(*plot.contents)
    lines.translate(0, 142)
    combined.add(lines)
    def matrix_label(x, y, value, size=9, anchor="middle", bold=False):
        combined.add(String(x, y, value, fontName="Helvetica-Bold" if bold else "Helvetica",
                            fontSize=size, textAnchor=anchor, fillColor=dark))
    matrix_label(12, 127, "The same pairs from decision 2 to decision 3", 10, "start", True)
    matrix_label(12, 111, "Row: decision 2", 8, "start")
    matrix_label(288, 111, "Decision 3: which branch holds a passing candidate?", 8)
    left, step = 122, 80
    for j, state in enumerate(states):
        matrix_label(left + (j + .5) * step, 94, state, 8)
    for i, start in enumerate(states):
        y0 = 72 - 19 * i
        matrix_label(12, y0 + 5, start, 9, "start")
        for j, end in enumerate(states):
            n = transitions[start][end]
            shade = "#e5ebec" if i == j else "#b6dcd5" if n else "#ffffff"
            x0 = left + j * step
            combined.add(Rect(x0, y0, step - 2, 17, fillColor=colors.HexColor(shade),
                              strokeColor=colors.HexColor("#d1dadd"), strokeWidth=.35))
            matrix_label(x0 + step / 2, y0 + 5, str(n), bold=bool(n))
    return combined


def _render_pdf(source, destination, author):
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
            if target == "figures/contract_reversal.png":
                story.append(KeepTogether([contract_figure(), para(description, caption)]))
            elif target == "figures/probe_reversal.png":
                story.append(KeepTogether([interval_figure(), para(description, caption)]))
            elif target == "figures/feedback_example.png":
                story.append(KeepTogether([feedback_example(), para(description, caption)]))
            elif target == "figures/observed_horizon.png":
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
        canvas.drawString(52, 26, "Checker feedback in coding-agent repair")
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
    if not author:
        assert not re.search(r"Zakirov|Iosifova|Kramich|Imranqsl212", " ".join(pages), re.I)
    print(destination.name, len(pages), "pages")
    return reader, pages


def render(source, destination, author):
    reader, pages = _render_pdf(source, destination, author)
    for n, column in (("S1", "New display"), ("S2", "Project"), ("S3", "Reference example"),
                      ("S4", "Truthful PASS"), ("S5", "Verified pairs"),
                      ("S6", "Invalid policies caught"), ("S7", "Effort change"),
                      (5, "Diagnostic before first choice"), (6, "Keys shown"),
                      (1, "Target shown"), (2, "Source of value"), (3, "Rule and display"),
                      (4, "Source collection"), (7, "Cross-display"), ("S8", "Scheduled")):
        assert any(f"Table {n}." in t and column in t for t in pages)
    assert any("Figure 3." in text and page.mediabox.width > page.mediabox.height and len(page.images) == 1
               for page, text in zip(reader.pages, pages))


if __name__ == "__main__":
    import pypdfium2 as pdfium
    directory = HERE / "figures"
    directory.mkdir(exist_ok=True)
    manuscript = (HERE / "manuscript.md").read_text()
    figures = [("feedback_example", feedback_example()), ("observed_horizon", observed_horizon())]
    if "figures/contract_reversal.png" in manuscript:
        figures.append(("contract_reversal", contract_figure()))
    if "figures/probe_reversal.png" in manuscript:
        figures.append(("probe_reversal", interval_figure()))
    for name, drawing in figures:
        graph = pdfium.PdfDocument(renderPDF.drawToString(drawing))
        graph[0].render(scale=3).to_pil().save(directory / f"{name}.png")
    render(manuscript, HERE / "checker_feedback.pdf", AUTHOR)
    render(review_manuscript(manuscript), HERE / "checker_feedback_anonymous.pdf", "")
    alternative = (HERE / "alternative_manuscript.md").read_text()
    _, pages = _render_pdf(alternative, HERE / "alternative_manuscript.pdf", AUTHOR)
    for n, column in ((1, "Outcome by starting state"), (2, "Keys in the displayed run")):
        assert any(f"Table {n}." in page and column in page for page in pages)

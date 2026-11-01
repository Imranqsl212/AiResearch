"""Build a six-slide, editable research talk for a general audience.

Use the Codex bundled Python, which includes python-pptx. The slide text
uses ordinary language; exact definitions and evidence limits live in notes.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


HERE = Path(__file__).resolve().parent
OUT = HERE / "Research_Update_2026-11-01.pptx"
NAVY = "0B1220"
PANEL = "172238"
PANEL_2 = "1D2B45"
WHITE = "F6F4EF"
MUTED = "ADB9CA"
MINT = "5DDFC4"
CORAL = "FF7773"
BLUE = "77A9FF"
AMBER = "FFC96E"
LINE = "34445D"
FONT = "Arial"


def rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def text(
    slide, value: str, x: float, y: float, w: float, h: float,
    *, size: float = 20, color: str = WHITE, bold: bool = False,
    align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.MIDDLE,
) -> None:
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = Inches(0)
    frame.margin_top = frame.margin_bottom = Inches(0)
    frame.vertical_anchor = valign
    for i, line in enumerate(value.split("\n")):
        para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        para.alignment = align
        para.space_after = Pt(0)
        para.line_spacing = 1.08
        run = para.add_run()
        run.text = line
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = rgb(color)


def box(slide, x: float, y: float, w: float, h: float, *,
        fill: str = PANEL, border: str | None = None, rounded: bool = True):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    if border is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = rgb(border)
        shape.line.width = Pt(1.2)
    if rounded:
        shape.adjustments[0] = 0.12
    return shape


def circle(slide, x: float, y: float, d: float, *,
           fill: str, border: str | None = None) -> None:
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y),
                                   Inches(d), Inches(d))
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    if border is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = rgb(border)
        shape.line.width = Pt(1.1)


def rule(slide, x1: float, y1: float, x2: float, y2: float,
         *, color: str = LINE, width: float = 1.5) -> None:
    shape = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                       Inches(x1), Inches(y1),
                                       Inches(x2), Inches(y2))
    shape.line.color.rgb = rgb(color)
    shape.line.width = Pt(width)


def pill(slide, value: str, x: float, y: float, w: float, h: float, *,
         fill: str = PANEL_2, color: str = WHITE, size: float = 15) -> None:
    box(slide, x, y, w, h, fill=fill)
    text(slide, value, x + 0.11, y + 0.02, w - 0.22, h - 0.04,
         size=size, color=color, bold=True, align=PP_ALIGN.CENTER)


def base(prs: Presentation, n: int, label: str, title: str, source: str,
         *, title_size: float = 35):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box(slide, 0, 0, 13.333, 7.5, fill=NAVY, rounded=False)
    text(slide, label.upper(), 0.70, 0.35, 10.8, 0.30,
         size=11, color=BLUE, bold=True)
    text(slide, title, 0.70, 0.83, 11.98, 0.90,
         size=title_size, bold=True, valign=MSO_ANCHOR.TOP)
    rule(slide, 0.70, 7.07, 12.63, 7.07)
    text(slide, source, 0.72, 7.14, 11.30, 0.19, size=8.2, color=MUTED)
    text(slide, f"{n:02d}", 12.08, 7.12, 0.50, 0.22, size=10,
         color=MUTED, align=PP_ALIGN.RIGHT)
    return slide


def note(slide, value: str) -> None:
    slide.notes_slide.notes_text_frame.text = value


def build() -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    prs.core_properties.title = "Our Tests Said PASS. Our Grader Said FAIL."
    prs.core_properties.subject = "Plain-language research progress presentation"
    prs.core_properties.author = "Imran Zakirov"

    # 1. Hook. "Passed" always refers to our written tests, not full security.
    s = prs.slides.add_slide(prs.slide_layouts[6])
    box(s, 0, 0, 13.333, 7.5, fill=NAVY, rounded=False)
    pill(s, "RESEARCH UPDATE  ·  1 NOV 2026", 0.75, 0.54, 3.58, 0.42,
         color=BLUE, size=11)
    text(s, "Our tests said PASS.\nOur grader said FAIL.",
         0.72, 1.25, 11.55, 2.05, size=46, bold=True,
         valign=MSO_ANCHOR.TOP)
    text(s, "In 9 of 20 runs with our extra rule.",
         0.75, 3.58, 11.72, 0.62, size=24, color=MUTED)
    pill(s, "OUR TESTS: PASS", 0.78, 4.70, 3.82, 0.78,
         fill="17453E", color=MINT, size=22)
    text(s, "→", 4.83, 4.70, 0.68, 0.76, size=34, color=BLUE,
         align=PP_ALIGN.CENTER)
    pill(s, "FINAL SCORE: FAIL", 5.73, 4.70, 4.52, 0.78,
         fill="4A2937", color=CORAL, size=22)
    rule(s, 0.75, 6.76, 12.58, 6.76)
    text(s, "Imran Zakirov  ·  Bishkek, Kyrgyzstan",
         0.76, 6.90, 8.65, 0.28, size=11, color=MUTED)
    text(s, "01", 12.05, 6.88, 0.50, 0.27, size=11,
         color=MUTED, align=PP_ALIGN.RIGHT)
    note(s, "We watched a local AI system try to fix small security-related "
         "mistakes in Python code. In part of our historical study, its final "
         "code passed the tests we had written, yet our checker gave a final "
         "FAIL. This is about our research checker, not a malicious AI. Passing "
         "our tests does not prove complete safety. Source: README.md; paper/final.md.")

    # 2. The setup in everyday words.
    s = base(prs, 2, "First", "What was the AI doing?",
             "Source: paper/final.md, Methods; README.md.")
    steps = [
        ("1", "See a small\ncode problem", BLUE),
        ("2", "Write a\npossible fix", MINT),
        ("3", "Hear PASS\nor FAIL", AMBER),
        ("4", "Stop or\ntry again", CORAL),
    ]
    for i, (number, label, accent) in enumerate(steps):
        x = 0.75 + i * 3.16
        box(s, x, 2.10, 2.78, 3.18, fill=PANEL)
        circle(s, x + 0.97, 2.38, 0.78, fill=accent)
        text(s, number, x + 1.09, 2.48, 0.52, 0.50,
             size=24, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
        text(s, label, x + 0.20, 3.58, 2.38, 1.08,
             size=22, bold=True, align=PP_ALIGN.CENTER)
        if i < 3:
            text(s, "→", x + 2.82, 3.30, 0.35, 0.66,
                 size=29, color=BLUE, align=PP_ALIGN.CENTER)
    pill(s, "This can happen several times in one run.",
         2.34, 6.05, 8.66, 0.50, color=WHITE, size=16)
    note(s, "An AI coder is a model that writes a code change, sees the "
         "checker's message, and may revise within one session. We are not "
         "training the model during these runs. The checker is software "
         "written for our study. Source: paper/final.md, Methods.")

    # 3. The actual counted historical finding.
    s = base(prs, 3, "What we found", "Nine times, tests and score disagreed",
             "Source: docs/MEASUREMENT_FOLLOWUP_20261030.md, §1; paper/final.md, Results.")
    box(s, 0.78, 2.10, 7.10, 3.52, fill=PANEL)
    for i in range(20):
        row, col = divmod(i, 10)
        circle(s, 1.22 + col * 0.60, 2.72 + row * 0.85, 0.43,
               fill=CORAL if i < 9 else PANEL_2,
               border=None if i < 9 else LINE)
    text(s, '20 runs had the extra "no" rule',
         1.17, 4.74, 6.18, 0.52, size=19, color=MUTED)
    text(s, "9 of 20", 8.30, 2.45, 4.15, 0.95,
         size=49, color=CORAL, bold=True, align=PP_ALIGN.CENTER)
    text(s, "passed our written tests\nbut still got FAIL",
         8.20, 3.60, 4.28, 1.20, size=24, bold=True,
         align=PP_ALIGN.CENTER)
    pill(s, "We reviewed 40 AI runs in total.",
         3.30, 6.02, 6.72, 0.53, color=BLUE, size=17)
    note(s, "We reviewed 40 archived runs by one local model across five "
         "selected kinds of small security tasks. Twenty runs were labeled "
         "'unavailable' in our experiment. In nine of those twenty, the "
         "final code passed our checker's own written tests but the final "
         "decision was FAIL. The dots show those twenty final submissions; "
         "nine colored dots are the disagreements. These are selected runs, "
         "not an error rate for all AI tools. Source: paper/final.md, Results; "
         "docs/MEASUREMENT_FOLLOWUP_20261030.md.")

    # 4. Cause: the research team's extra rule.
    s = base(prs, 4, "One real run", "Example: a one-time encryption value",
             "Source: paper/final.md, Results, slot 10; docs/MEASUREMENT_FOLLOWUP_20261030.md.",
             title_size=32)
    box(s, 0.82, 2.07, 5.34, 2.03, fill="173D3B", border="2A716C")
    text(s, "SMALL NONCE TESTS", 1.17, 2.41, 4.66, 0.43,
         size=17, color=MINT, bold=True, align=PP_ALIGN.CENTER)
    text(s, "PASS", 1.17, 3.02, 4.66, 0.70,
         size=35, color=MINT, bold=True, align=PP_ALIGN.CENTER)
    text(s, "+", 6.28, 2.71, 0.68, 0.66,
         size=33, color=MUTED, align=PP_ALIGN.CENTER)
    box(s, 7.07, 2.07, 5.34, 2.03, fill="3D2634", border="794458")
    text(s, "OUR HIDDEN RULE", 7.42, 2.41, 4.64, 0.43,
         size=17, color=CORAL, bold=True, align=PP_ALIGN.CENTER)
    text(s, "NO", 7.42, 3.02, 4.64, 0.70,
         size=35, color=CORAL, bold=True, align=PP_ALIGN.CENTER)
    text(s, "=  FINAL FAIL", 3.44, 4.46, 6.45, 0.78,
         size=32, color=CORAL, bold=True, align=PP_ALIGN.CENTER)
    pill(s, "We added that rule. The AI did not see it.",
         2.05, 5.97, 9.24, 0.57, color=AMBER, size=18)
    note(s, "Here is one recorded case, slot 10. The task involved a nonce: "
         "a value intended to be used once in encryption. At the final "
         "candidate, the small implemented tests passed, but our hidden "
         "unavailability rule still forced FAIL. The AI did not see that "
         "rule. The nonce tests were limited, so the PASS is not proof of "
         "security across restarts or concurrent uses. Source: paper/final.md, "
         "Results, slot 10; docs/MEASUREMENT_FOLLOWUP_20261030.md.")

    # 5. Interpretation and one important limit.
    s = base(prs, 5, "So what?", "The score can mislead us",
             "Source: paper/final.md, Discussion and limitations.")
    box(s, 0.78, 2.12, 5.42, 2.68, fill="3D2634", border="794458")
    text(s, "THE SCORE SEEMS TO SAY", 1.10, 2.44, 4.82, 0.41,
         size=15, color=CORAL, bold=True)
    text(s, '"The AI failed."', 1.11, 3.19, 4.82, 0.68,
         size=30, bold=True)
    box(s, 7.14, 2.12, 5.42, 2.68, fill="173D3B", border="2A716C")
    text(s, "OUR RECORDS SHOW", 7.47, 2.44, 4.73, 0.41,
         size=15, color=MINT, bold=True)
    text(s, "The tests and\nscore disagreed.", 7.48, 3.02, 4.64, 1.25,
         size=29, bold=True)
    text(s, "So this score cannot tell us whether the AI should have stopped trying.",
         1.10, 5.18, 11.12, 0.75, size=22, bold=True,
         align=PP_ALIGN.CENTER)
    pill(s, "Passing our small tests does not prove the code fully safe.",
         1.52, 6.10, 10.30, 0.48, color=AMBER, size=15)
    note(s, "The final FAIL alone could make it look as if the AI could not "
         "solve the task or did not know when to stop. But the checker and "
         "its own tests disagreed. We cannot infer a general AI stopping "
         "problem from that score. Also, none of the 81 old intermediate "
         "check records saved the raw underlying test result, so we cannot "
         "prove that a particular revision followed a known passing test. "
         "Passing the small written tests does not prove general security.")

    # 6. A paired test isolates feedback, but no main-study result is admitted.
    s = base(prs, 6, "The next question", "Same code. Two different messages.",
             "Sources: docs/INTEGRATED_STUDY_EXTENSION_20261018.md; README.md.")
    box(s, 4.14, 1.95, 5.06, 0.96, fill=PANEL_2, border=LINE)
    text(s, "The same checked code", 4.42, 2.17, 4.48, 0.53,
         size=21, bold=True, align=PP_ALIGN.CENTER)
    rule(s, 6.67, 2.91, 6.67, 3.35, color=BLUE, width=2)
    rule(s, 3.67, 3.35, 9.67, 3.35, color=BLUE, width=2)
    rule(s, 3.67, 3.35, 3.67, 3.66, color=BLUE, width=2)
    rule(s, 9.67, 3.35, 9.67, 3.66, color=BLUE, width=2)
    box(s, 1.17, 3.66, 5.04, 1.17, fill="173D3B", border="2A716C")
    text(s, "AI hears true PASS", 1.47, 3.96, 4.44, 0.60,
         size=24, color=MINT, bold=True, align=PP_ALIGN.CENTER)
    box(s, 7.13, 3.66, 5.04, 1.17, fill="3D2634", border="794458")
    text(s, "AI hears false FAIL", 7.44, 3.96, 4.43, 0.60,
         size=24, color=CORAL, bold=True, align=PP_ALIGN.CENTER)
    text(s, "Does the wrong message make it lose the fix?",
         1.00, 5.16, 11.35, 0.57, size=25, bold=True,
         align=PP_ALIGN.CENTER)
    pill(s, "Done: 40-run audit · 20 task types drafted · paired pilots run",
         1.84, 5.93, 9.65, 0.49, color=BLUE, size=15)
    text(s, "Before judging the AI, check the grader.",
         1.03, 6.55, 7.75, 0.34, size=20, color=AMBER, bold=True)
    text(s, "github.com/Imranqsl212/AiResearch",
         8.53, 6.55, 3.79, 0.34, size=13.5, color=BLUE,
         bold=True, align=PP_ALIGN.RIGHT)
    note(s, "We have audited forty historical runs, drafted twenty new task "
         "types, and run small exploratory pairs with this basic idea. "
         "They are excluded from the future main study and do not establish "
         "a general effect. Our planned fairer study will save the exact same verified "
         "candidate code and previous AI history, then make two isolated "
         "continuations. One receives a truthful PASS; the other receives "
         "a false FAIL. We will compare what the AI does next and whether "
         "its final code still satisfies the specific property we checked. "
         "As of 1 November 2026, "
         "zero future main runs are eligible; the release gate is 0 of 12. "
         "Source: docs/INTEGRATED_STUDY_EXTENSION_20261018.md; README.md.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"Wrote {OUT} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    build()

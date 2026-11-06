"""Editorial poster layout for the final research showcase.

The visual separates test evidence from a final verdict. Each plotted mark
represents one of the twenty historical sessions with the hidden rule.
"""
from __future__ import annotations

from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

from presentation.build_research_update import box, circle, note, rule, text

PAPER = "F4F0E6"
INK = "191919"
RED = "D83C2D"
GRAY = "67645F"
LINE = "D8D1C6"


def build_poster(meta) -> Presentation:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(20), Inches(11.25)
    prs.core_properties.title = meta["title"] + " — research poster"
    prs.core_properties.author = "; ".join(meta["team_members"])
    prs.core_properties.subject = "A local audit of AI evaluation and stopping"
    s = prs.slides.add_slide(prs.slide_layouts[6])
    box(s, 0, 0, 20, 11.25, fill=PAPER, rounded=False)

    def t(value, x, y, w, h, *, size=22, color=INK, bold=False,
          serif=False, align=PP_ALIGN.LEFT):
        text(s, value, x, y, w, h, size=size, color=color, bold=bold,
             align=align, valign=MSO_ANCHOR.TOP)
        if serif:
            for paragraph in s.shapes[-1].text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.name = "Georgia"

    def label(value, x, y, w):
        t(value, x, y, w, .31, size=16, bold=True, color=GRAY)

    # Colophon, headline, byline: a print spread rather than a dashboard.
    box(s, .62, .30, .13, .28, fill=RED, rounded=False)
    t("RESEARCH SHOWCASE / AI SECURITY REPAIR", .9, .30, 14, .29,
      size=16, color=GRAY, bold=True)
    t("The Tests Passed. The Grader Said No.", .62, .78, 18.76, .91,
      size=44, serif=True, bold=True)
    t("Imran Zakirov · Iosifova Nuriya · Kramich Anna (mentor & active team member)",
      .66, 1.78, 18.7, .39, size=21)
    rule(s, .62, 2.34, 19.38, 2.34, color=INK, width=1.3)

    # Compact context before the large, counted evidence.
    label("RESEARCH QUESTION", .64, 2.62, 5.52)
    t("Can we judge AI decisions\nwhen the checker misleads?",
      .64, 3.10, 5.52, .96, size=24)
    label("BACKGROUND", 6.92, 2.62, 5.5)
    t("AI revises code using feedback\n[1, 2]. We checked the feedback\nitself.",
      6.92, 3.10, 5.5, 1.03, size=22)
    label("METHODS", 13.24, 2.62, 6.14)
    t("40 sessions · 1 local model\n5 Python security task types\nCompare final tests with verdicts.",
      13.24, 3.10, 6.14, 1.03, size=22)
    rule(s, .62, 4.34, 19.38, 4.34, color=LINE, width=1.0)

    # The dominant result: nine passing tests, twenty rejection verdicts.
    label("RESULTS / 01 — THE HIDDEN RULE", .64, 4.59, 11.6)
    t("9 / 20", .55, 5.04, 6.0, 1.66, size=104, color=RED, bold=True)
    t("Passed the tests.\nRejected anyway.", 6.90, 5.33, 5.48, 1.13,
      size=30, serif=True, bold=True)
    for index in range(20):
        row, column = divmod(index, 10)
        circle(s, .72 + column * .63, 6.93 + row * .58, .40,
               fill=RED if index < 9 else LINE)
    t("9 passed tests\n11 failed tests", 7.50, 7.02, 4.75, .84, size=23)
    t("Our hidden rule rejected all 20.", .65, 8.13, 11.6, .44,
      size=24, bold=True)
    t("The AI could not see the rule. Test pass ≠ proof of security.",
      .65, 8.69, 11.63, .41, size=21, color=GRAY)

    # A second, clearly bounded result; no new model cohort is implied.
    rule(s, 12.68, 4.62, 12.68, 9.06, color=LINE, width=1.0)
    label("RESULTS / 02 — STOPPING", 13.24, 4.59, 6.14)
    t("2 min 8 sec", 13.18, 5.14, 6.2, .98, size=51, bold=True)
    t("Median: stop acknowledgement → run end.\n13 repairable post-PASS sessions.\nA 14th timed out (excluded).",
      13.24, 6.37, 6.14, 1.07, size=21)
    t("0 further logged repairs", 13.24, 7.72, 6.14, .49,
      size=25, color=RED, bold=True)
    t("The old controller waited for\nanother final signal.",
      13.24, 8.40, 6.14, .71, size=21, color=GRAY)

    # Takeaway and next step are adjacent, so the conclusion stays practical.
    rule(s, .62, 9.37, 19.38, 9.37, color=INK, width=1.3)
    label("CONCLUSION", .64, 9.61, 5.5)
    t("Check the grader.", .64, 10.01, 5.8, .55,
      size=30, serif=True, bold=True)
    label("NEXT STEPS", 6.92, 9.61, 12.46)
    t("Independent task review → broader paired runs.\nWe improved logging and tested immediate stopping.",
      6.92, 10.02, 12.46, .64, size=21)

    t("REFERENCES  [1] Yao et al., ReAct (2023), arXiv:2210.03629.  [2] Shinn et al., Reflexion (2023), arXiv:2303.11366.  [3] github.com/Imranqsl212/AiResearch",
      .64, 10.88, 18.74, .25, size=13, color=GRAY)

    note(s,
         "Historical local audit; no population-wide behavioral effect is claimed. "
         "The same cohort has40 saved episodes, five task families and one qwen3:4b model. "
         "20 episodes had the research team's hidden unconditional rejection rule. "
         "9 final candidates passed finite tests but were rejected;11 failed those tests. "
         "The twenty marks are one per final candidate, not independent task families. "
         "All14 acknowledged terminate episodes followed public PASS in repairable tasks. "
         "13 later self-labeled cases had median128.44624s acknowledgement-to-stop; "
         "one late timeout is excluded from that median. No further repair attempts were logged. "
         "The scripted old-runner control required another adapter decision; this does not "
         "measure wasted time or refusal to stop. Better later logs cannot recover absent old checks. "
         "Sources: paper/artifacts/results.json; analysis/HISTORICAL_TERMINATE_LATENCY_20261104.md; "
         "analysis/STOP_CONTRACT_CONTROL_20261104.md; tests/test_v1_collector.py. "
         "Primary background: https://arxiv.org/abs/2210.03629 and https://arxiv.org/abs/2303.11366. "
         "Research evidence revision: " + meta["research_source_commit"])
    return prs

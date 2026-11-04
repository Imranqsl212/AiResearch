"""Build the November showcase poster and title + five content slides.

Run with the bundled workspace Python: python -B -m showcase.build_showcase.
No model calls, candidate execution, or changes to research evidence occur.
PDFs are exported separately with LibreOffice. All visuals are editable.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

from presentation.build_research_update import (
    AMBER, BLUE, CORAL, LINE, MINT, MUTED, NAVY, PANEL, PANEL_2, WHITE,
    box, circle, note, pill, rule, text,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "showcase/2026-11-08"
META = json.loads((OUT / "metadata.json").read_text())
STEM = "Zakirov_Iosifova_AI_Checker_Audit"
INK = "142536"
GRAY = "4F6170"
LIGHT = "F1F5F8"
PALE_TEAL = "E7F5F1"
PALE_RED = "FCEDEC"
TEAL = "116754"
RED = "A3393C"

ABSTRACT = (
    "How can we judge an AI coding assistant when its checker gives misleading feedback? "
    "We audited 40 saved repair sessions from one local language model across five small "
    "Python security task types. We compared the final code's test result with the benchmark's "
    "acceptance decision. Twenty sessions used a hidden rule, written by our research team, "
    "that rejected every solution. In nine of those twenty sessions, the final code passed "
    "the implemented tests but still received FAIL. Passing these limited tests did not prove "
    "the code secure. Missing intermediate test results also prevented us from tracing exactly "
    "which revisions followed a test–verdict disagreement. We built improved logging and small "
    "exploratory paired follow-ups. Our main finding is that the checker must be validated "
    "before its scores are used to judge an AI's decisions."
)


def deck() -> Presentation:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333333), Inches(7.5)
    prs.core_properties.title = META["title"]
    prs.core_properties.author = "; ".join(META["student_team"] + [META["mentor_and_contributor"]])
    prs.core_properties.subject = "Research showcase: exploratory AI checker audit"

    def base(number: int, label: str, title: str):
        s = prs.slides.add_slide(prs.slide_layouts[6])
        box(s, 0, 0, 13.333333, 7.5, fill=NAVY, rounded=False)
        text(s, label.upper(), .65, .30, 11.8, .28, size=11, color=BLUE, bold=True)
        text(s, title, .65, .85, 12.0, .95, size=34, bold=True, valign=MSO_ANCHOR.TOP)
        rule(s, .65, 7.03, 12.68, 7.03)
        text(s, "AI checker audit  ·  exploratory local research  ·  sources in speaker notes",
             .68, 7.13, 11.4, .18, size=9, color=MUTED)
        text(s, str(number), 12.15, 7.10, .45, .24, size=11, color=MUTED,
             align=PP_ALIGN.RIGHT)
        return s

    s = prs.slides.add_slide(prs.slide_layouts[6])
    box(s, 0, 0, 13.333333, 7.5, fill=NAVY, rounded=False)
    pill(s, "RESEARCH SHOWCASE  ·  NOVEMBER 2026", .7, .48, 5.0, .42,
         color=BLUE, size=12)
    text(s, "The Tests Passed.\nThe Grader Said No.", .7, 1.3, 12.0, 1.95,
         size=43, bold=True, valign=MSO_ANCHOR.TOP)
    text(s, META["subtitle"], .75, 3.65, 11.7, .55, size=24, color=MUTED)
    pill(s, "OUR TESTS: PASS", .76, 4.55, 4.6, .72, fill="173D3B", color=MINT, size=24)
    text(s, "→", 5.6, 4.55, .7, .72, size=32, color=BLUE, align=PP_ALIGN.CENTER)
    pill(s, "FINAL SCORE: FAIL", 6.55, 4.55, 5.2, .72, fill="3D2634", color=CORAL, size=24)
    text(s, "Project team: Imran Zakirov · Iosifova Nuriya", .76, 6.02, 11.8, .36,
         size=19, bold=True)
    text(s, "Mentor & project contributor: Kramich Anna", .76, 6.48, 11.8, .32,
         size=17, color=MUTED)
    note(s, "Title slide. Team names and the dual mentor/contributor role were confirmed by the user. "
         "Use the group script supplied in TALK_AND_QA.md. The title refers to disagreement "
         "between finite test results and final acceptance in this benchmark, not proof of secure code.")

    s = base(1, "Question & why it matters", "When should an AI stop trying?")
    labels = [("1", "See a small\ncode problem", BLUE),
              ("2", "Write a\npossible fix", MINT),
              ("3", "Hear PASS\nor FAIL", AMBER),
              ("4", "Stop or\ntry again", CORAL)]
    for i, (n, label, accent) in enumerate(labels):
        x = .72 + i * 3.15
        box(s, x, 2.13, 2.76, 2.8)
        circle(s, x + 1.02, 2.4, .66, fill=accent)
        text(s, n, x + 1.11, 2.45, .48, .52, size=25, color=NAVY,
             bold=True, align=PP_ALIGN.CENTER)
        text(s, label, x + .18, 3.45, 2.4, 1.0, size=23, bold=True, align=PP_ALIGN.CENTER)
        if i < 3:
            text(s, "→", x+2.79, 3.2, .34, .6, size=27, color=BLUE, align=PP_ALIGN.CENTER)
    text(s, "A misleading score makes that behavior hard to judge.", .9, 5.55, 11.55, .7,
         size=25, bold=True, align=PP_ALIGN.CENTER)
    pill(s, "Why it matters: people use feedback to decide whether to trust AI-written code.",
         .9, 6.35, 11.55, .45, color=MUTED, size=15)
    note(s, "Background: ReAct (Yao et al., 2023), https://arxiv.org/abs/2210.03629, "
         "and Reflexion (Shinn et al., 2023), https://arxiv.org/abs/2303.11366, study agents "
         "that use observations or feedback. Our study does not train the model during a session. "
         "Source: paper/final.md, Methods and Introduction.")

    s = base(2, "Method", "We compared the test result with the final score")
    for x, big, small in [(1.0,"40","saved sessions"),(5.12,"1","local AI model"),(9.24,"5","small task types")]:
        box(s, x, 2.0, 3.1, 1.75)
        text(s, big, x+.15, 2.12, 2.8, .8, size=48, color=BLUE, bold=True, align=PP_ALIGN.CENTER)
        text(s, small, x+.15, 3.06, 2.8, .37, size=20, align=PP_ALIGN.CENTER)
    pill(s, "Test result", .95, 4.27, 4.8, .8, fill="173D3B", color=MINT, size=26)
    text(s, "vs.", 6.02, 4.29, 1.1, .7, size=26, color=MUTED, align=PP_ALIGN.CENTER)
    pill(s, "Final acceptance", 7.4, 4.27, 4.95, .8, fill="3D2634", color=CORAL, size=26)
    text(s, '20 sessions had our hidden “never accept” rule.', .95, 5.58, 11.4, .55,
         size=25, bold=True, align=PP_ALIGN.CENTER)
    text(s, "We added the rule. The AI did not see it.", 1.0, 6.3, 11.3, .38,
         size=20, color=AMBER, align=PP_ALIGN.CENTER)
    note(s, "Historical audit only: qwen3:4b, 40 main episodes across 5 selected task families. "
         "20 nominally unavailable episodes used an unconditional acceptance veto after the same tests. "
         "The other 20 are not a randomized causal control for this showcase claim. "
         "Source: paper/artifacts/results.json, main_security_acceptance; sandbox/docker_candidate.py:53–56.")

    s = base(3, "Result & one real story", "9 of 20 passed the tests — and still got FAIL")
    box(s, .75, 2.07, 7.35, 2.55)
    for i in range(20):
        row, col = divmod(i, 10)
        circle(s, 1.06+col*.68, 2.62+row*.82, .45,
               fill=CORAL if i<9 else PANEL_2, border=None if i<9 else LINE)
    text(s, "20 sessions with the hidden rule", 1.0, 4.03, 6.9, .33, size=19, color=MUTED)
    text(s, "9 / 20", 8.55, 2.38, 3.8, .95, size=52, color=CORAL, bold=True, align=PP_ALIGN.CENTER)
    text(s, "final test–score\ndisagreements", 8.5, 3.5, 3.9, .9, size=25, bold=True, align=PP_ALIGN.CENTER)
    box(s, .76, 5.15, 11.85, .86, fill="1D2B45")
    text(s, "One encryption task:  tests PASS  +  hidden rule NO  =  final FAIL",
         .95, 5.32, 11.45, .48, size=21, bold=True, align=PP_ALIGN.CENTER)
    text(s, "Passing these limited tests does not prove the code secure.", .85, 6.4, 11.65, .4,
         size=19, color=AMBER, align=PP_ALIGN.CENTER)
    note(s, "Each dot is a final submission in one of the 20 hidden-rule episodes. "
         "9/20 is not an error rate for all AI systems. Total historical cohort: 40. "
         "The real example is historical slot 10, nonce task. A nonce is intended for one-time use "
         "during encryption; these tests did not establish full security. "
         "Evidence: paper/artifacts/results.json; docs/MEASUREMENT_FOLLOWUP_20261030.md; paper/final.md, Results.")

    s = base(4, "Challenges & what we learned", "The surprise was in our measuring tool")
    cards = [(.77,"HIDDEN RULE","A FAIL could disagree\nwith our own tests.","Audit the checker.",CORAL),
             (4.99,"MISSING STEP LOGS","Old step results\nwere missing.","Save every check.",BLUE),
             (9.21,"SMALL TESTS","A test pass was not\na full security proof.","State the limits.",MINT)]
    for x, label, body, lesson, accent in cards:
        box(s,x,2.07,3.35,3.73)
        text(s,label,x+.22,2.35,2.91,.52,size=17,color=accent,bold=True)
        text(s,body,x+.22,3.24,2.91,1.15,size=22,bold=True)
        rule(s,x+.22,4.76,x+3.13,4.76)
        text(s,lesson,x+.22,5.02,2.91,.43,size=19,color=accent,bold=True)
    pill(s, "What changed: we improved logging instead of treating every FAIL as evidence of bad AI behavior.",
         .83,6.26,11.68,.53,color=AMBER,size=15)
    note(s, "None of 81 historical per-action check receipts retains the raw test outcome. "
         "Final receipts support the main audit, but intermediate missingness blocks localizing "
         "a particular test–verdict disagreement before a revision. Improved prospective logging "
         "does not recover missing old evidence. Source: paper/final.md, Measurement validity; "
         "docs/INTEGRATED_ENGINEERING_CHECKPOINT_20261018.md. Codex assistance is disclosed in the paper.")

    s = base(5, "Conclusion & next steps", "Before judging the AI, check the grader.")
    pill(s,"Start from the same checked code",3.63,1.96,6.1,.73,color=WHITE,size=24)
    rule(s,6.67,2.69,6.67,3.07,color=BLUE,width=2)
    rule(s,3.55,3.07,9.78,3.07,color=BLUE,width=2)
    for x in (3.55,9.78): rule(s,x,3.07,x,3.4,color=BLUE,width=2)
    pill(s,"True PASS",1.0,3.4,5.1,.82,fill="173D3B",color=MINT,size=29)
    pill(s,"False FAIL",7.23,3.4,5.1,.82,fill="3D2634",color=CORAL,size=29)
    text(s,"Does the next version keep or lose the fix?",1.0,4.61,11.33,.61,
         size=26,bold=True,align=PP_ALIGN.CENTER)
    text(s,"DONE: audit, better logs, small exploratory pilots",.9,5.58,11.5,.4,
         size=20,color=BLUE,bold=True,align=PP_ALIGN.CENTER)
    text(s,"NEXT: independent task review, then broader paired testing",.9,6.13,11.5,.4,
         size=20,color=AMBER,bold=True,align=PP_ALIGN.CENTER)
    note(s,"The diagram is the follow-up design, not a general effect claim. "
         "Small excluded pilots have run and produced mixed outcomes. The prospective main study "
         "has zero eligible episodes and awaits independent task review. "
         "Sources: docs/INTEGRATED_STUDY_EXTENSION_20261018.md; "
         "analysis/V7_TEMP_VARIANCE_SECONDWAVE_20261101.md. "
         "Background references: Yao et al., ReAct (2023), https://arxiv.org/abs/2210.03629; "
         "Shinn et al., Reflexion (2023), https://arxiv.org/abs/2303.11366. "
         "Code and evidence: https://github.com/Imranqsl212/AiResearch.")
    return prs


def poster() -> Presentation:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(20), Inches(11.25)
    prs.core_properties.title = META["title"] + " — research poster"
    prs.core_properties.author = "; ".join(META["student_team"] + [META["mentor_and_contributor"]])
    s=prs.slides.add_slide(prs.slide_layouts[6])
    box(s,0,0,20,11.25,fill="FFFFFF",rounded=False)
    box(s,0,0,20,.12,fill=TEAL,rounded=False)
    text(s,META["title"],.6,.35,18.8,.85,size=43,color=INK,bold=True)
    text(s,"Checking the checker in AI security repair · exploratory local study",.63,1.25,18.7,.39,
         size=23,color=GRAY)
    text(s,"Team: Imran Zakirov · Iosifova Nuriya   |   Mentor & project contributor: Kramich Anna",
         .63,1.8,18.7,.36,size=20,color=INK,bold=True)
    rule(s,.6,2.35,19.4,2.35,color="D7E0E7")

    def heading(value,x,y,w): text(s,value.upper(),x,y,w,.4,size=22,color=TEAL,bold=True)
    # Three columns. Left: question/background/method; centre: counted evidence;
    # right: implications/challenge/next step. References span the bottom.
    x1,x2,x3=.6,6.58,13.5
    w1,w2,w3=5.55,6.5,5.9
    heading("Research question",x1,2.65,w1)
    text(s,"Can we judge an AI’s decisions when its checker gives misleading feedback?",
         x1,3.17,w1,1.1,size=23,color=INK,bold=True)
    heading("Background",x1,4.43,w1)
    text(s,"AI coding agents revise work using feedback [1, 2]. A faulty checker can mislead evaluation.",
         x1,4.97,w1,1.0,size=21,color=GRAY)
    heading("Methods",x1,6.3,w1)
    text(s,"40 saved sessions · 1 local model\n5 small Python security task types",
         x1,6.83,w1,.77,size=22,color=INK,bold=True)
    for i,label in enumerate(("Read saved final test results","Compare with final verdicts","Inspect checker and source")):
        y=7.9+i*.55
        box(s,x1,y,w1,.42,fill=LIGHT)
        text(s,f"{i+1}  {label}",x1+.15,y+.02,w1-.3,.36,size=20,color=INK,bold=True)

    box(s,x2,2.65,w2,6.86,fill=LIGHT)
    heading("Results",x2+.25,2.91,w2-.5)
    text(s,"9 of 20",x2+.3,3.42,w2-.6,.95,size=57,color=RED,bold=True,align=PP_ALIGN.CENTER)
    text(s,"final submissions passed our tests\nbut still received FAIL",
         x2+.3,4.44,w2-.6,.85,size=25,color=INK,bold=True,align=PP_ALIGN.CENTER)
    for i in range(20):
        row,col=divmod(i,10)
        circle(s,x2+.43+col*.57,5.66+row*.66,.40,
               fill=RED if i<9 else "D3DEE6")
    text(s,"20 of the 40 reviewed sessions\nused the hidden rejection rule.",
         x2+.28,7.02,w2-.56,.75,size=19,color=GRAY,align=PP_ALIGN.CENTER)
    box(s,x2+.25,8.02,w2-.5,1.18,fill=PALE_RED)
    text(s,"One encryption task:\ntests PASS + our hidden rule NO = final FAIL",
         x2+.45,8.18,w2-.9,.8,size=21,color=RED,bold=True,align=PP_ALIGN.CENTER)

    heading("Conclusion",x3,2.65,w3)
    text(s,"Before judging the AI,\ncheck the grader.",x3,3.17,w3,.9,size=29,color=INK,bold=True)
    text(s,"We added the hidden rejection rule. The AI could not see it. A test pass alone did not prove the code secure.",
         x3,4.35,w3,1.2,size=22,color=GRAY)
    heading("Challenge & learning",x3,5.85,w3)
    text(s,"Old step-by-step test results were missing. We improved logging; the old records cannot prove which feedback caused a revision.",
         x3,6.38,w3,1.4,size=21,color=GRAY)
    heading("Next steps",x3,8.06,w3)
    text(s,"Independently review tasks. Then compare true PASS and false FAIL from the same checked code. Small pilots are exploratory.",
         x3,8.59,w3,1.0,size=21,color=GRAY)
    rule(s,.6,9.84,19.4,9.84,color="D7E0E7")
    text(s,"REFERENCES & EVIDENCE",.6,10.02,4.6,.3,size=16,color=TEAL,bold=True)
    text(s,"[1] Yao et al. ReAct (2023), arXiv:2210.03629.  [2] Shinn et al. Reflexion (2023), arXiv:2303.11366.",
         .6,10.40,18.8,.27,size=15,color=GRAY)
    text(s,"[3] Project code, archived runs & paper: github.com/Imranqsl212/AiResearch  ·  Counts: paper/artifacts/results.json",
         .6,10.78,18.8,.27,size=15,color=GRAY)
    note(s,"Single-page 16:9 landscape poster. Historical audit only. Counts and real example "
         "come from paper/artifacts/results.json and paper/final.md. Source revision: "+META["research_source_commit"]+
         ". Full primary references: https://arxiv.org/abs/2210.03629 and https://arxiv.org/abs/2303.11366.")
    return prs


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    evidence=ROOT/"paper/artifacts/results.json"
    data=json.loads(evidence.read_text())
    # Exact data bindings are recorded separately; the visual is descriptive.
    assert data["main"]["n"] == 40 and data["main"]["family_count"] == 5
    assert data["policy_rejected"]["n"] == 20
    assert data["policy_rejected"]["raw_checks_pass"] == 9
    assert data["policy_rejected"]["test_gate_discordance"] == 9
    assert len(ABSTRACT.split())<=150
    for kind,prs in (("Slides",deck()),("Poster",poster())):
        for s in prs.slides:
            for shape in s.shapes:
                assert shape.left>=0 and shape.top>=0
                assert shape.left+shape.width<=prs.slide_width+Inches(.002)
                assert shape.top+shape.height<=prs.slide_height+Inches(.002)
        target=OUT/f"{STEM}_{kind}.pptx"
        prs.save(target)
        print(f"Built {target.relative_to(ROOT)}: {len(prs.slides)} slide(s)")
    (OUT/"ABSTRACT.txt").write_text(ABSTRACT+"\n")
    submission = (
        f"Project title: {META['title']}\n"
        f"Subtitle: {META['subtitle']}\n"
        "Team members: Imran Zakirov; Iosifova Nuriya\n"
        "Mentor and active project contributor: Kramich Anna\n\n"
        f"Abstract ({len(ABSTRACT.split())} words):\n{ABSTRACT}\n\n"
        f"Code and research evidence: {META['repository']}\n"
        "Paper draft (optional): https://github.com/Imranqsl212/AiResearch/blob/"
        f"{META['research_source_commit']}/paper/submission/full_paper.pdf\n\n"
        f"Poster: {STEM}_Poster.pdf\nSlides: {STEM}_Slides.pdf\n"
    )
    (OUT/"SUBMISSION_DETAILS.txt").write_text(submission)
    receipt={"metadata":META,"abstract_words":len(ABSTRACT.split()),"slide_count":6,
             "poster_pages_expected":1,"counts_source":"paper/artifacts/results.json",
             "counts_source_sha256":hashlib.sha256(evidence.read_bytes()).hexdigest(),
             "claim":"9 of 20 historical hidden-rule final candidates passed finite tests but received FAIL",
             "submission_status":"PREPARED_FOR_USER_REVIEW_NOT_SUBMITTED"}
    (OUT/"build_receipt.json").write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n")


if __name__=="__main__":
    main()

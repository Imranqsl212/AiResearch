"""Build the November showcase poster and title + five content slides.

Run with the bundled workspace Python: python -B -m showcase.build_showcase.
No model calls, candidate execution, or changes to research evidence occur.
PDFs use the vector exporter in showcase.export_pdf. All visuals are editable.
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
    "Can we judge when an AI should stop repairing code if its evaluator is unreliable? "
    "We audited 40 saved sessions from one local language model across five small Python "
    "security task types. In 20 sessions, our benchmark applied a hidden rule that rejected "
    "every candidate. Nine final candidates passed the implemented tests but still received FAIL. "
    "Separately, 14 sessions requested termination after a public PASS. Thirteen later ended "
    "through the runner's self-termination path, with a median 128-second delay after acknowledgement; "
    "one timed out. No further repair attempts were logged. A scripted control confirmed that "
    "the old runner required a separate final stop signal. These findings expose limits in "
    "our evaluation system, not proof of insecure code or AI stubbornness. We improved logging "
    "and tested immediate stopping in the newer collector. Broader behavioral claims need independently "
    "reviewed tasks and further experiments."
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
    text(s, "Team: Imran Zakirov · Iosifova Nuriya · Kramich Anna", .76, 6.02, 11.8, .36,
         size=19, bold=True)
    text(s, "Mentor & active team member: Kramich Anna", .76, 6.48, 11.8, .32,
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
            text(s, "→", x+2.79, 3.2, .34, .6, size=23, color=BLUE, align=PP_ALIGN.CENTER)
    text(s, "A misleading score makes that behavior hard to judge.", .9, 5.55, 11.55, .7,
         size=25, bold=True, align=PP_ALIGN.CENTER)
    pill(s, "Why it matters: people use feedback to decide whether to trust AI-written code.",
         .9, 6.35, 11.55, .45, color=MUTED, size=15)
    note(s, "Background: ReAct (Yao et al., 2023), https://arxiv.org/abs/2210.03629, "
         "and Reflexion (Shinn et al., 2023), https://arxiv.org/abs/2303.11366, study agents "
         "that use observations or feedback. Our study does not train the model during a session. "
         "Source: paper/final.md, Methods and Introduction.")

    s = base(2, "Method", "Our checker had two separate decisions")
    for x, big, small in [(1.0,"40","saved sessions"),(5.12,"1","local AI model"),(9.24,"5","small task types")]:
        box(s, x, 2.0, 3.1, 1.75)
        text(s, big, x+.15, 2.12, 2.8, .8, size=48, color=BLUE, bold=True, align=PP_ALIGN.CENTER)
        text(s, small, x+.15, 3.06, 2.8, .37, size=20, align=PP_ALIGN.CENTER)
    pill(s, "Run the code tests", .95, 4.27, 5.15, .8, fill="173D3B", color=MINT, size=26)
    text(s, "→", 6.31, 4.29, .7, .7, size=30, color=MUTED, align=PP_ALIGN.CENTER)
    pill(s, "Accept or reject", 7.23, 4.27, 5.15, .8, fill="3D2634", color=CORAL, size=26)
    text(s, "Did this code pass\nour written checks?", 1.0, 5.32, 5.05, .8,
         size=23, align=PP_ALIGN.CENTER)
    text(s, '20 sessions: our hidden\n“reject everything” rule', 7.28, 5.32, 5.05, .8,
         size=23, color=CORAL, bold=True, align=PP_ALIGN.CENTER)
    text(s, "We added this rule. The AI could not see it.", 1.0, 6.47, 11.3, .36,
         size=19, color=AMBER, align=PP_ALIGN.CENTER)
    note(s, "Historical audit only: qwen3:4b, 40 main episodes across 5 selected task families. "
         "20 nominally unavailable episodes used an unconditional acceptance veto after the same tests. "
         "The other 20 are not a randomized causal control for this showcase claim. "
         "Source: paper/artifacts/results.json, main_security_acceptance; sandbox/docker_candidate.py:53–56.")

    s = base(3, "Result · our historical audit", "9 of 20 passed the tests — and still got FAIL")
    box(s, .75, 2.07, 7.35, 2.55)
    for i in range(20):
        row, col = divmod(i, 10)
        circle(s, 1.06+col*.68, 2.48+row*.72, .45,
               fill=CORAL if i<9 else PANEL_2, border=None if i<9 else LINE)
    text(s, "9 passed tests  ·  11 failed tests", 1.0, 3.92, 6.9, .33, size=19, color=MUTED)
    text(s, "9 / 20", 8.55, 2.38, 3.8, .95, size=52, color=CORAL, bold=True, align=PP_ALIGN.CENTER)
    text(s, "passed tests,\nstill rejected", 8.5, 3.5, 3.9, .9, size=25, bold=True, align=PP_ALIGN.CENTER)
    box(s, .76, 5.15, 11.85, .86, fill="1D2B45")
    text(s, "All 20 were rejected. The hidden rule overrode the test result.",
         .95, 5.32, 11.45, .48, size=21, bold=True, align=PP_ALIGN.CENTER)
    text(s, "Passing these limited tests does not prove the code secure.", .85, 6.4, 11.65, .4,
         size=19, color=AMBER, align=PP_ALIGN.CENTER)
    note(s, "Each dot is a final submission in one of the 20 hidden-rule episodes. "
         "9/20 is not an error rate for all AI systems. Total historical cohort: 40. "
         "The real example is historical slot 10, nonce task. A nonce is intended for one-time use "
         "during encryption; these tests did not establish full security. "
         "Evidence: paper/artifacts/results.json; docs/MEASUREMENT_FOLLOWUP_20261030.md; paper/final.md, Results.")

    s = base(4, "A second finding · stopping", "A stop request was not the end")
    text(s, "14 sessions requested a stop immediately after a public PASS.",
         .78, 1.84, 11.8, .5, size=22, color=MUTED)
    pill(s, "Tests PASS", .77, 2.76, 2.35, .82, fill="173D3B", color=MINT, size=24)
    text(s, "→", 3.25, 2.82, .6, .7, size=30, color=BLUE, align=PP_ALIGN.CENTER)
    pill(s, "Stop request\nacknowledged", 3.99, 2.65, 3.7, 1.05, color=WHITE, size=23)
    rule(s, 7.8, 3.17, 9.8, 3.17, color=AMBER, width=3)
    pill(s, "Run ends", 9.98, 2.76, 2.55, .82, color=WHITE, size=24)
    text(s, "2 min 8 sec", 5.05, 4.02, 6.3, .82, size=42, color=AMBER,
         bold=True, align=PP_ALIGN.CENTER)
    text(s, "Median after acknowledgement in 13 sessions.\nThe 14th timed out and is excluded from this median.",
         4.05, 4.95, 8.3, .8, size=19, color=MUTED, align=PP_ALIGN.CENTER)
    text(s, "0", 1.12, 4.06, 2.1, .82, size=46, color=MINT, bold=True,
         align=PP_ALIGN.CENTER)
    text(s, "further logged\nrepair attempts", .84, 4.99, 2.7, .75, size=20,
         align=PP_ALIGN.CENTER)
    pill(s, "The old controller waited for another final signal. We verified that path in a scripted test.",
         .83, 6.27, 11.68, .53, color=BLUE, size=16)
    note(s, "Sources: analysis/HISTORICAL_TERMINATE_LATENCY_20261104.md and "
         "analysis/STOP_CONTRACT_CONTROL_20261104.md. All 14 terminate episodes were nominally "
         "repairable and immediately followed public SECURITY_CHECK_PASSED, not unavailable failures. "
         "13 eventually AGENT_SELF_TERMINATION, median128.44624 seconds from first STOP_REQUESTED "
         "acknowledgement to STOP. One late TIMEOUT is outside that median. 15 terminate calls total "
         "because one episode repeated it; zero later logged attempts. Model-free scripted control "
         "confirms an extra adapter decision in the frozen runner. This is not evidence of AI stubbornness, "
         "idle time, exact provider call count, or counterfactual time savings. The visible timeline is "
         "schematic, not to scale. All numbers are retrospective and descriptive.")

    s = base(5, "Conclusion & next steps", "Before judging the AI, check the grader.")
    for x, tag, accent, body in [(.78, "WHAT WE LEARNED", CORAL, "A score is only as useful\nas the system behind it."),
                               (6.88, "WHAT WE BUILT", MINT, "Per-step records + a tested\nimmediate-stop path.")]:
        box(s,x,2.0,5.65,2.55)
        text(s,tag,x+.25,2.27,5.15,.4,size=17,color=accent,bold=True)
        text(s,body,x+.25,3.07,5.15,1.05,size=25,bold=True)
    text(s,"NEXT: independent task review → broader paired trials",.85,5.0,11.63,.55,
         size=24,color=AMBER,bold=True,align=PP_ALIGN.CENTER)
    text(s,"Same checked code. True PASS or false FAIL. Does the fix survive?",.85,5.78,11.63,.5,
         size=21,color=MUTED,align=PP_ALIGN.CENTER)
    text(s,"Small pilots are exploratory. The larger study is still ahead.",.85,6.46,11.63,.33,
         size=17,color=MUTED,align=PP_ALIGN.CENTER)
    note(s,"Challenges: none of81 historical per-action verifier receipts kept the raw check outcome. "
         "New logging does not recover missing old checks. New collector immediate-stop regression: "
         "tests/test_v1_collector.py, test_terminate_tool_stops_without_another_adapter_decision. "
         "A single adapter execute produces terminate followed by STOP; this is a software guard, "
         "not a measured latency improvement. Small excluded pilots have mixed outcomes. "
         "The prospective main study has zero eligible episodes and awaits independent task review. "
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
    text(s,"Imran Zakirov · Iosifova Nuriya · Kramich Anna (mentor & active team member)",
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
    heading("Results · the hidden rule",x2+.25,2.91,w2-.5)
    text(s,"9 of 20",x2+.3,3.42,w2-.6,.95,size=57,color=RED,bold=True,align=PP_ALIGN.CENTER)
    text(s,"final submissions passed our tests\nbut still received FAIL",
         x2+.3,4.44,w2-.6,.85,size=25,color=INK,bold=True,align=PP_ALIGN.CENTER)
    for i in range(20):
        row,col=divmod(i,10)
        circle(s,x2+.43+col*.57,5.66+row*.66,.40,
               fill=RED if i<9 else "D3DEE6")
    text(s,"9 passed tests · 11 failed tests\nAll 20 were rejected by our hidden rule.",
         x2+.28,7.02,w2-.56,.75,size=19,color=GRAY,align=PP_ALIGN.CENTER)
    box(s,x2+.25,8.02,w2-.5,1.18,fill=PALE_RED)
    text(s,"Our rule was hidden from the AI.\nTest pass ≠ proof of security.",
         x2+.45,8.18,w2-.9,.8,size=21,color=RED,bold=True,align=PP_ALIGN.CENTER)

    heading("Results · stopping",x3,2.65,w3)
    text(s,"2 min 8 sec",x3,3.15,w3,.7,size=39,color=TEAL,bold=True)
    text(s,"Median from stop acknowledgement to run end in 13 post-PASS sessions. A 14th timed out (excluded from median).",
         x3,4.0,w3,1.22,size=21,color=GRAY)
    pill(s,"0 further logged repair attempts",x3,5.43,w3,.48,
         fill=PALE_TEAL,color=TEAL,size=19)
    heading("Conclusion",x3,6.18,w3)
    text(s,"Before judging the AI, check the grader.",x3,6.7,w3,.8,size=26,color=INK,bold=True)
    text(s,"We improved step logs and tested immediate stopping in the new collector.",
         x3,7.53,w3,.82,size=20,color=GRAY)
    heading("Next steps",x3,8.53,w3)
    text(s,"Independent task review → broader paired tests of true PASS vs. false FAIL.",
         x3,9.04,w3,.68,size=20,color=GRAY)
    rule(s,.6,9.84,19.4,9.84,color="D7E0E7")
    text(s,"REFERENCES & EVIDENCE",.6,10.02,4.6,.3,size=16,color=TEAL,bold=True)
    text(s,"[1] Yao et al. ReAct (2023), arXiv:2210.03629.  [2] Shinn et al. Reflexion (2023), arXiv:2303.11366.",
         .6,10.40,18.8,.27,size=15,color=GRAY)
    text(s,"[3] github.com/Imranqsl212/AiResearch  ·  Evidence: paper/artifacts/results.json; analysis/HISTORICAL_TERMINATE_LATENCY_20261104.md",
         .6,10.78,18.8,.27,size=15,color=GRAY)
    note(s,"Single-page 16:9 landscape poster. Historical audit only. Counts "
         "come from paper/artifacts/results.json and paper/final.md. Stop result: 14 repairable episodes "
         "immediately after public PASS; 13 self-labeled median128.44624s, 1 late timeout; "
         "no subsequent logged repair attempts. The old controller required another decision step. "
         "Model-free control and new collector guard do not establish time saved or AI stubbornness. "
         "Missing historical intermediate raw results limit causal claims. Source revision: "+META["research_source_commit"]+
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
    latency_path=ROOT/"analysis/historical_terminate_latency_20261104.json"
    latency=json.loads(latency_path.read_text())
    assert latency["sealed_episodes"] == 40
    assert latency["episodes_with_acknowledged_terminate"] == 14
    assert latency["eventual_self_labels_after_terminate"] == 13
    assert latency["eventual_timeout_after_terminate"] == 1
    assert latency["later_logged_attempt_calls"] == 0
    assert round(latency["self_labeled_acknowledgement_to_stop_seconds"]["median"]) == 128
    assert all(c["condition"].startswith("R") and
               c["preceding_public_outcome"] == "SECURITY_CHECK_PASSED" for c in latency["cases"])
    control_path=ROOT/"analysis/stop_contract_control_20261104.json"
    control=json.loads(control_path.read_text())
    assert control["result"]["direct"]["execute_calls"] == 2
    assert control["result"]["terminate_then_stop"]["execute_calls"] == 3
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
        "Team members: Imran Zakirov; Iosifova Nuriya; Kramich Anna\n"
        "Mentor (also active team member): Kramich Anna\n\n"
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
             "evidence_files":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (evidence,latency_path,control_path)},
             "claim":"9 of 20 historical hidden-rule final candidates passed finite tests but received FAIL",
             "submission_status":"PREPARED_FOR_USER_REVIEW_NOT_SUBMITTED"}
    (OUT/"build_receipt.json").write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n")


if __name__=="__main__":
    main()

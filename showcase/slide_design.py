"""Six-slide editorial narrative for the research showcase."""
from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

from presentation.build_research_update import box, note, rule, text

PAPER = 'F4F0E6'
INK = '191919'
RED = 'D83C2D'
GRAY = '67645F'
LINE = 'D8D1C6'
PALE = 'B8B2A8'


def label(slide, value, x, y, w, h, size=20, color=INK, bold=False,
          serif=False, align=PP_ALIGN.LEFT):
    text(slide, value, x,y,w,h,size=size,color=color,bold=bold,align=align,
         valign=MSO_ANCHOR.TOP)
    if serif:
        for p in slide.shapes[-1].text_frame.paragraphs:
            for r in p.runs:
                r.font.name = 'Georgia'


def build_deck(meta):
    prs=Presentation()
    prs.slide_width,prs.slide_height=Inches(13.333333),Inches(7.5)
    prs.core_properties.title=meta['title']
    prs.core_properties.author='; '.join(meta['team_members'])
    prs.core_properties.subject='A local audit of AI security-repair evaluation'

    def page(number, caption, bg=PAPER):
        s=prs.slides.add_slide(prs.slide_layouts[6])
        box(s,0,0,13.333333,7.5,fill=bg,rounded=False)
        fg=PAPER if bg in (INK,RED) else GRAY
        label(s,caption,.65,.35,10,.3,size=12,color=fg,bold=True)
        label(s,f'{number:02d}',12.05,.32,.62,.35,size=16,color=fg,align=PP_ALIGN.RIGHT)
        return s

    # Opening: two contradictory verdicts, given equal visual weight.
    s=page(0,'AI SECURITY REPAIR / A CHECKER AUDIT')
    box(s,8.15,0,5.183333,7.5,fill=RED,rounded=False)
    label(s,'The Tests\nPassed.',.65,1.8,7.15,2.35,size=57,serif=True)
    label(s,'The Grader\nSaid No.',8.65,1.85,4.15,2.1,size=41,color=PAPER,serif=True)
    rule(s,.68,4.72,7.35,4.72,color=INK,width=1.0)
    label(s,'Checking the checker\nin AI security repair',.68,5.04,6.9,.86,size=24)
    label(s,'Imran Zakirov · Iosifova Nuriya',.68,6.38,7.0,.32,size=17,bold=True)
    label(s,'Kramich Anna — mentor & team member',.68,6.85,7.0,.32,size=16,color=GRAY)
    label(s,'A LOCAL EXPERIMENT\nNOVEMBER 2026',8.68,6.43,3.9,.7,size=14,color=PAPER)
    note(s,'Title: The Tests Passed. The Grader Said No. All three people are team members; '
         'Kramich Anna is also mentor. The title describes our finite tests versus final acceptance, '
         'not a security proof. Evidence revision: '+meta['research_source_commit']+'.')

    # The question: two actors and a loop, rather than a row of generic cards.
    s=page(1,'THE QUESTION',INK)
    label(s,'When should an AI\nstop trying?',.65,1.04,10.8,1.7,size=42,color=PAPER,serif=True)
    label(s,'AI',.82,3.37,2.5,.78,size=40,color=PAPER,bold=True)
    label(s,'writes a fix',.85,4.24,3.4,.45,size=23,color=PALE)
    rule(s,3.38,3.93,6.55,3.93,color=PALE,width=1.4)
    label(s,'→',6.35,3.58,.65,.65,size=32,color=PAPER)
    label(s,'Checker',7.15,3.37,5.0,.78,size=40,color=PAPER,bold=True)
    label(s,'returns PASS or FAIL',7.18,4.24,5.1,.45,size=23,color=PALE)
    rule(s,2.1,4.92,2.1,5.36,color=RED,width=2)
    rule(s,2.1,5.36,9.35,5.36,color=RED,width=2)
    rule(s,9.35,4.92,9.35,5.36,color=RED,width=2)
    label(s,'←',1.79,5.08,.6,.6,size=28,color=RED)
    label(s,'Stop — or try again?',4.24,5.66,5.7,.55,size=25,color=PAPER,serif=True)
    label(s,'A misleading score makes that choice hard to judge.',.85,6.7,11.7,.4,size=20,color=PALE)
    note(s,'Initial question: when should an AI stop repairing code? The model proposes a Python '
         'security repair, receives checker feedback, and may stop or revise. Scores guide how people '
         'evaluate AI-written code, so their validity matters. Background: Yao et al., ReAct (2023), '
         'https://arxiv.org/abs/2210.03629; Shinn et al., Reflexion (2023), '
         'https://arxiv.org/abs/2303.11366. Source: paper/final.md, Introduction and Methods.')

    # Method: a visible paper rule inside the invisible scoring machinery.
    s=page(2,'THE METHOD')
    label(s,'We checked\nthe checker.',.65,1.08,7.1,1.7,size=43,serif=True)
    for x,value,caption in [(0.72,'40','saved sessions'),(3.22,'1','local model'),(5.55,'5','task types')]:
        label(s,value,x,3.4,2.2,1.12,size=66,bold=True)
        label(s,caption,x,4.66,2.4,.42,size=18,color=GRAY)
    box(s,8.1,1.2,4.52,4.65,fill='EAE4D9',rounded=False)
    label(s,'INSIDE OUR CHECKER',8.42,1.52,3.88,.35,size=14,bold=True)
    rule(s,8.42,2.05,12.25,2.05,color=GRAY,width=1)
    label(s,'01  Run the tests.',8.42,2.37,3.86,.72,size=25)
    box(s,8.1,3.3,4.52,1.05,fill=RED,rounded=False)
    label(s,'02  Reject everything.',8.42,3.6,3.88,.53,size=23,color=PAPER,bold=True)
    label(s,'Our hidden rule.\nUsed in 20 of 40 sessions.',8.42,4.72,3.88,.8,size=19)
    rule(s,.68,6.28,12.62,6.28,color=LINE,width=1)
    label(s,'We added the rule. The AI could not see it.',.72,6.62,11.8,.48,size=25,color=RED)
    note(s,'40 saved historical sessions, one qwen3:4b model and five selected small Python security '
         'task families. Twenty nominally unavailable sessions applied a hidden unconditional rejection '
         'gate after the finite checks. It was our authored benchmark rule, not a discovery of an '
         'external secret rule. Rejecting everything does not prove the coding task itself impossible. '
         'Sources: paper/artifacts/results.json, main and policy_rejected; sandbox/docker_candidate.py; '
         'paper/final.md, Methods. This is an audit, not a randomized causal estimate.')

    # Primary result: a single statistic and a counted unit chart.
    s=page(3,'THE FIRST FINDING',RED)
    label(s,'9',.65,1.1,2.85,2.4,size=149,color=PAPER,serif=True)
    label(s,'/20',3.35,2.1,2.9,1.25,size=72,color=PAPER)
    label(s,'Passed our tests.\nStill rejected.',6.65,1.73,6.0,1.7,size=38,color=PAPER,serif=True)
    for i in range(20):
        box(s,.72+i*.598,4.48,.46,.64,fill=PAPER if i<9 else '9F2B20',rounded=False)
    label(s,'Each block = one session with our hidden rule.',.72,5.39,8.2,.35,size=17,color=PAPER)
    label(s,'9 passed · 11 failed the tests',8.45,5.39,4.25,.35,size=16,color=PAPER,align=PP_ALIGN.RIGHT)
    box(s,0,6.23,13.333333,1.27,fill=INK,rounded=False)
    label(s,'All 20 received FAIL.',.72,6.62,5.8,.48,size=26,color=PAPER,bold=True)
    label(s,'Passing limited tests\ndoes not prove security.',8.0,6.53,4.62,.7,size=19,color=PAPER)
    note(s,'The chart counts final candidates in the 20 hidden-rule episodes. Nine passed the raw '
         'finite family tests; eleven did not. All twenty were rejected by final acceptance. '
         'Nine of twenty is not a general AI error rate or proof of security. '
         'Source: paper/artifacts/results.json, policy_rejected.raw_checks_pass=9, n=20, '
         'test_gate_discordance=9; paper/final.md, Table 2.')

    # Secondary result: the clock belongs to the controller, not an invented AI intention.
    s=page(4,'THE SECOND FINDING',INK)
    label(s,'STOP was\nnot the end.',.65,1.1,6.5,1.65,size=42,color=PAPER,serif=True)
    label(s,'2:08',7.46,1.25,5.24,1.9,size=101,color=PAPER,serif=True)
    label(s,'MINUTES : SECONDS',7.55,3.28,4.8,.35,size=14,color=PALE)
    label(s,'The controller waited\nfor another final signal.',.72,3.35,6.25,.96,size=25,color=PALE)
    label(s,'Stop acknowledgement → run end\nMedian of 13 post-PASS sessions.',7.55,4.03,5.0,.94,size=21,color=PAPER)
    label(s,'1 additional timeout excluded.',7.55,5.18,5.0,.4,size=18,color=PALE)
    label(s,'0',.75,4.79,1.05,1.02,size=62,color=RED,bold=True)
    label(s,'further logged\nrepair attempts',2.0,4.95,4.7,.82,size=25,color=PAPER)
    rule(s,.7,6.27,12.62,6.27,color=GRAY,width=1)
    label(s,'14 repairable sessions requested termination immediately after PASS.',.72,6.64,11.9,.42,size=20,color=PALE)
    note(s,'All 14 terminate episodes were repairable and immediately followed a public PASS. '
         '13 eventually self-labeled episodes had a median128.44624 seconds (rounded2min8sec) '
         'between first STOP_REQUESTED acknowledgement and final STOP. One late TIMEOUT is excluded '
         'from that median. No further repair attempts were logged; one terminate was repeated. '
         'A model-free scripted control of the frozen runner confirmed another adapter decision '
         'after terminate. This is not measured idle time, AI stubbornness or counterfactual savings. '
         'Sources: analysis/HISTORICAL_TERMINATE_LATENCY_20261104.md; '
         'analysis/STOP_CONTRACT_CONTROL_20261104.md.')

    # Closing: specific changes, one next experiment, no generic concluding paragraph.
    s=page(5,'WHAT WE LEARNED')
    label(s,'Check the grader.',.65,1.12,12.0,1.5,size=57,serif=True)
    rule(s,.7,2.92,12.62,2.92,color=RED,width=3)
    label(s,'DONE',.72,3.48,5.2,.35,size=15,color=RED,bold=True)
    label(s,'Now: every check logged.\nImmediate stopping tested.',.72,4.13,5.7,1.18,size=27)
    label(s,'NEXT',7.15,3.48,5.2,.35,size=15,color=RED,bold=True)
    label(s,'Review the tasks.\nCompare true PASS / false FAIL.',7.15,4.13,5.45,1.3,size=25)
    label(s,'Same code. Different feedback.',7.15,5.76,5.4,.48,size=20,color=GRAY)
    label(s,'Small pilots are exploratory. The larger study is still ahead.',.72,6.78,11.9,.36,size=17,color=GRAY)
    note(s,'Our challenge was separating agent behavior from evaluation software. Old logs lack raw '
         'intermediate check outcomes; new logging does not recover them. New per-action records and '
         'an immediate-terminate regression guard address prospective measurement. Source: '
         'tests/test_v1_collector.py::test_terminate_tool_stops_without_another_adapter_decision. '
         'The guard verifies no further adapter decision, not a measured time saving. Small paired '
         'pilots remain exploratory. Independent task review is pending and eligible prospective '
         'main episodes remain zero. The next comparison forks the same checked code into truthful '
         'PASS and false FAIL. See paper/final.md; project code and sources at '
         'https://github.com/Imranqsl212/AiResearch. Use TALK_AND_QA.md for the group narration.')
    return prs

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
from pptx.util import Inches

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "showcase/2026-11-08"
META = json.loads((OUT / "metadata.json").read_text())
STEM = "Zakirov_Iosifova_AI_Checker_Audit"

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
    from showcase.slide_design import build_deck
    return build_deck(META)


def poster() -> Presentation:
    from showcase.poster_design import build_poster
    return build_poster(META)


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

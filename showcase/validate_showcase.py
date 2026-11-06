"""Inspect the exported PDFs/PPTX, render previews, and record artifact hashes."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps
from pypdf import PdfReader
from pptx import Presentation

from showcase.build_showcase import META, OUT, ROOT, STEM


def compact(value):
    return re.sub(r"\s+", "", value)


def main():
    result = {}
    texts = {}
    for kind, expected in (("Poster", 1), ("Slides", 6)):
        path = OUT / f"{STEM}_{kind}.pdf"
        pdf = PdfReader(path)
        assert len(pdf.pages) == expected, (kind, len(pdf.pages))
        for page in pdf.pages:
            assert abs(float(page.mediabox.width) / float(page.mediabox.height) - 16/9) < .002
        texts[kind] = "\n".join(page.extract_text() for page in pdf.pages)
        for name in ("Imran Zakirov", "Iosifova Nuriya", "Kramich Anna"):
            assert name in texts[kind], (kind, name)
        assert "9" in texts[kind] and "20" in texts[kind] and "40" in texts[kind]
        assert not re.search(r"\bTODO\b|\bTBD\b|\[.*name.*\]", texts[kind])
        pptx = Presentation(OUT/f"{STEM}_{kind}.pptx")
        assert len(pptx.slides) == expected
        assert all(s.notes_slide.notes_text_frame.text.strip() for s in pptx.slides)
        for slide, page in zip(pptx.slides, pdf.pages):
            pptx_text = "".join(s.text for s in slide.shapes if s.has_text_frame)
            assert compact(pptx_text) == compact(page.extract_text()), f"{kind}: PDF/PPTX text mismatch"
        assert "2 min 8 sec" in texts[kind] and "13" in texts[kind]
        result[kind.lower()] = {"pdf_pages":expected,"pptx_slides":expected,"aspect_ratio":"16:9",
                                "names_present":True,"notes_present":True,"pdf_pptx_text_match":True}
    for section in ("RESEARCH QUESTION","BACKGROUND","METHODS","RESULTS","CONCLUSION","NEXT STEPS","REFERENCES"):
        assert section in texts["Poster"], section
    abstract_words = len((OUT/"ABSTRACT.txt").read_text().split())
    assert abstract_words <= 150
    result["abstract_words"] = abstract_words
    receipt = json.loads((OUT/"build_receipt.json").read_text())
    assert receipt["metadata"] == META
    for name, expected_hash in receipt["evidence_files"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected_hash, name
    speech = (OUT/"TALK_AND_QA.md").read_text().split("## Групповой текст на английском\n",1)[1].split("\n## Если",1)[0]
    speech = "\n".join(line for line in speech.splitlines() if not line.startswith("### "))
    result["spoken_script_words"] = len(speech.split())
    assert 330 <= result["spoken_script_words"] <= 420
    assert speech.count("Next slide, please.") == 5
    result["evidence_hashes_match"] = True
    result["pdf_export"] = "ReportLab vector layout; selectable text; embedded fonts"
    result["content_slides"] = 5
    result["rehearsal_status"] = "PENDING_ACTUAL_TIMED_REHEARSAL"
    result["submission_status"] = "NOT_SUBMITTED"
    poster = pdfium.PdfDocument(str(OUT/f"{STEM}_Poster.pdf"))
    poster[0].render(scale=1.3).to_pil().convert("RGB").save(OUT/"Poster_Preview.png")
    slides = pdfium.PdfDocument(str(OUT/f"{STEM}_Slides.pdf"))
    sheet = Image.new("RGB",(1648,1414),"#E7EAF0")
    for i,page in enumerate(slides):
        rendered = page.render(scale=1.5).to_pil().convert("RGB")
        rendered.save(OUT/f"Slide_{i+1:02d}_Preview.png")
        thumb = ImageOps.pad(rendered,(800,450),color="#0B1220")
        sheet.paste(thumb,(16+(i%2)*816,16+(i//2)*466))
    sheet.save(OUT/"Slides_Contact_Sheet.png")
    result["files"] = {
        p.name: {"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "validation.json"
    }
    (OUT/"validation.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="files"},indent=2))


if __name__ == "__main__":
    main()

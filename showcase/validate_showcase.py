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

from showcase.build_showcase import OUT, STEM


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
        result[kind.lower()] = {"pdf_pages":expected,"pptx_slides":expected,"aspect_ratio":"16:9",
                                "names_present":True,"notes_present":True}
    for section in ("RESEARCH QUESTION","BACKGROUND","METHODS","RESULTS","CONCLUSION","NEXT STEPS","REFERENCES"):
        assert section in texts["Poster"], section
    abstract_words = len((OUT/"ABSTRACT.txt").read_text().split())
    assert abstract_words <= 150
    result["abstract_words"] = abstract_words
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

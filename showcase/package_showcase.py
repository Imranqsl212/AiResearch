"""Package only final deliverables; check the archived bytes against validation."""
from __future__ import annotations

import hashlib
import json
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from showcase.build_showcase import OUT, STEM


def main():
    receipt=json.loads((OUT/"validation.json").read_text())
    names=[f"{STEM}_{kind}.{ext}" for kind in ("Poster", "Slides") for ext in ("pdf", "pptx")]
    names += ["ABSTRACT.txt", "SUBMISSION_DETAILS.txt", "TALK_AND_QA.md", "README.md",
              "SOURCES.md", "metadata.json", "build_receipt.json", "validation.json",
              "Poster_Preview.png", "Slides_Contact_Sheet.png"]
    target=OUT.parent/"Zakirov_Iosifova_Showcase_2026-11-08.zip"
    with ZipFile(target,"w",compression=ZIP_DEFLATED,compresslevel=9) as archive:
        for name in sorted(names):
            raw=(OUT/name).read_bytes()
            if name != "validation.json":
                assert hashlib.sha256(raw).hexdigest()==receipt["files"][name]["sha256"], name
            info=ZipInfo(f"Showcase_2026-11-08/{name}",date_time=(2026,11,6,0,0,0))
            info.compress_type=ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            archive.writestr(info,raw)
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==len(names)
    print(f"Packaged {len(names)} files: {target.name}")
    print(f"SHA256 {hashlib.sha256(target.read_bytes()).hexdigest()}")


if __name__=="__main__":
    main()

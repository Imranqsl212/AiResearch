"""Render the PDF slide deck to review images and a contact sheet.

Requires the bundled Python packages pypdfium2 and Pillow. The PDF itself is
exported from the PPTX with the bundled LibreOffice headless runtime.
"""

from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps


HERE = Path(__file__).resolve().parent
PDF = HERE / "Research_Update_2026-11-01.pdf"
PREVIEW = HERE / "preview"


def main() -> None:
    PREVIEW.mkdir(exist_ok=True)
    document = pdfium.PdfDocument(str(PDF))
    slides: list[Image.Image] = []
    for index in range(len(document)):
        page = document[index]
        image = page.render(scale=1.45).to_pil().convert("RGB")
        image.save(PREVIEW / f"slide_{index + 1:02d}.png")
        thumb = image.copy()
        thumb.thumbnail((920, 520))
        slides.append(thumb)

    margin, gap, tile_w, tile_h = 28, 22, 920, 520
    sheet = Image.new("RGB", (2 * tile_w + 2 * margin + gap,
                              5 * tile_h + 2 * margin + 4 * gap), "#E7EAF0")
    for index, thumb in enumerate(slides):
        col, row = index % 2, index // 2
        x = margin + col * (tile_w + gap)
        y = margin + row * (tile_h + gap)
        sheet.paste(ImageOps.pad(thumb, (tile_w, tile_h), color="#0B1220"), (x, y))
    sheet.save(HERE / "Research_Update_Contact_Sheet.png")
    print(f"Rendered {len(slides)} slides")


if __name__ == "__main__":
    main()

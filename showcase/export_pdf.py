"""Export this showcase's vector-only PPTX layouts to searchable PDFs.

This deliberately supports only the shapes authored by build_showcase.py.
Unsupported shapes or overflowing text fail instead of being silently omitted.
It does not require a desktop office application.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.enum.dml import MSO_FILL
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

from showcase.build_showcase import META, OUT, STEM


def setup_fonts():
    directory = Path('/System/Library/Fonts/Supplemental')
    if not (directory / 'Arial.ttf').exists():
        import reportlab
        directory = Path(reportlab.__file__).parent / 'fonts'
        names = ('Vera.ttf', 'VeraBd.ttf')
    else:
        names = ('Arial.ttf', 'Arial Bold.ttf')
    for font, filename in zip(('Showcase', 'ShowcaseBold'), names):
        pdfmetrics.registerFont(TTFont(font, str(directory / filename)))


def wrapped_lines(value, font, size, width):
    lines = []
    current = ''
    for word in value.split():
        trial = f'{current} {word}'.strip()
        if pdfmetrics.stringWidth(trial, font, size) <= width + .2:
            current = trial
        else:
            if not current:
                raise ValueError(f'Word too wide: {word}')
            lines.append(current)
            current = word
    return lines + [current]


def render_text(pdf, shape, slide_height):
    frame = shape.text_frame
    if not frame.text.strip():
        return
    x = shape.left.pt + frame.margin_left.pt
    top = slide_height - shape.top.pt - frame.margin_top.pt
    width = shape.width.pt - frame.margin_left.pt - frame.margin_right.pt
    height = shape.height.pt - frame.margin_top.pt - frame.margin_bottom.pt
    lines = []
    for paragraph in frame.paragraphs:
        runs = list(paragraph.runs)
        assert len(runs) == 1, 'Showcase text must use one uniform run per paragraph'
        run = runs[0]
        size = run.font.size.pt
        font = 'ShowcaseBold' if run.font.bold else 'Showcase'
        color = HexColor('#' + str(run.font.color.rgb))
        spacing = paragraph.line_spacing or 1.0
        assert isinstance(spacing, float), 'Only proportional line spacing is supported'
        leading = size * spacing
        for line in wrapped_lines(run.text, font, size, width):
            lines.append((line, font, size, color, leading, paragraph.alignment))
    occupied = sum(line[4] for line in lines)
    if occupied > height + 1:
        raise ValueError(f'Text overflows by {occupied-height:.1f}pt: {frame.text}')
    offset = 0
    if frame.vertical_anchor == MSO_ANCHOR.MIDDLE:
        offset = (height - occupied) / 2
    elif frame.vertical_anchor == MSO_ANCHOR.BOTTOM:
        offset = height - occupied
    for value, font, size, color, leading, align in lines:
        ascent = pdfmetrics.getAscent(font) * size / 1000
        baseline = top - offset - ascent - (leading-size)/2
        pdf.setFont(font, size)
        pdf.setFillColor(color)
        if align == PP_ALIGN.CENTER:
            pdf.drawCentredString(x + width / 2, baseline, value)
        elif align == PP_ALIGN.RIGHT:
            pdf.drawRightString(x + width, baseline, value)
        else:
            assert align in (None, PP_ALIGN.LEFT)
            pdf.drawString(x, baseline, value)
        offset += leading


def export(kind):
    source = OUT / f'{STEM}_{kind}.pptx'
    prs = Presentation(source)
    target = source.with_suffix('.pdf')
    width, height = prs.slide_width.pt, prs.slide_height.pt
    pdf = canvas.Canvas(str(target), pagesize=(width, height), invariant=1)
    pdf.setTitle(META['title'] + f' — {kind}')
    pdf.setAuthor('; '.join(META['team_members']))
    pdf.setSubject('Research showcase: local AI evaluator audit')
    for slide in prs.slides:
        for shape in slide.shapes:
            x, y = shape.left.pt, height - shape.top.pt - shape.height.pt
            w, h = shape.width.pt, shape.height.pt
            if shape.shape_type == MSO_SHAPE_TYPE.LINE:
                pdf.setStrokeColor(HexColor('#' + str(shape.line.color.rgb)))
                pdf.setLineWidth(shape.line.width.pt)
                pdf.line(x, y+h, x+w, y)
            elif shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
                assert shape.fill.type == MSO_FILL.SOLID
                pdf.setFillColor(HexColor('#' + str(shape.fill.fore_color.rgb)))
                stroke = int(shape.line.fill.type == MSO_FILL.SOLID)
                if stroke:
                    pdf.setStrokeColor(HexColor('#' + str(shape.line.color.rgb)))
                    pdf.setLineWidth(shape.line.width.pt)
                if shape.auto_shape_type == MSO_SHAPE.OVAL:
                    pdf.ellipse(x, y, x+w, y+h, fill=1, stroke=stroke)
                elif shape.auto_shape_type == MSO_SHAPE.ROUNDED_RECTANGLE:
                    pdf.roundRect(x, y, w, h, min(w,h)*.12, fill=1, stroke=stroke)
                else:
                    assert shape.auto_shape_type == MSO_SHAPE.RECTANGLE
                    pdf.rect(x, y, w, h, fill=1, stroke=stroke)
            else:
                assert shape.shape_type == MSO_SHAPE_TYPE.TEXT_BOX, shape.shape_type
            if shape.has_text_frame:
                render_text(pdf, shape, height)
        pdf.showPage()
    pdf.save()
    print(f'Exported {target.relative_to(OUT.parent.parent)}: {len(prs.slides)} page(s)')


def main():
    setup_fonts()
    for kind in ('Poster', 'Slides'):
        export(kind)


if __name__ == '__main__':
    main()

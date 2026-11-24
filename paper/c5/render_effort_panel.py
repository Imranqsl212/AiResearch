"""Draw the observed correctness and reported reasoning-token grids for the finite panel."""
import argparse
import json
import math
from pathlib import Path

import pypdfium2
from reportlab.lib import colors
from reportlab.pdfgen.canvas import Canvas
from io import BytesIO

LEVELS = ("low", "medium", "high", "xhigh", "max", "ultra")


def pretty(name):
    if name == "gpt-daybreak-blue-latest":
        return "Daybreak Blue"
    prefix, version, family = name.split("-")
    return f"{prefix.upper()}-{version} {family.capitalize()}"


def tint(amount, endpoint):
    start = (0.965, 0.977, 0.975)
    return colors.Color(*(a + (b-a)*amount for a, b in zip(start, endpoint)))


def render(panel, catalog, output):
    models = [m["slug"] for m in catalog["models"] if m["visibility"] == "list"]
    cells = {(r["model"], r["effort"]): r for r in panel["rows"]}
    expected = {(m["slug"], e["effort"]) for m in catalog["models"] if m["visibility"] == "list"
                for e in m["supported_reasoning_levels"]}
    if len(cells) != len(panel["rows"]) or set(cells) != expected:
        raise ValueError("Each selectable model and effort must appear exactly once")
    usages = [r["usage"]["reasoning_output_tokens"] for r in cells.values()
              if r["usage"]["reasoning_output_tokens"] is not None]
    largest = max([1] + usages)
    area = BytesIO()
    width, height = 878, 182 + 25 * len(models)
    cv = Canvas(area, pagesize=(width, height), invariant=1)
    ink, muted = colors.HexColor("#15343b"), colors.HexColor("#4a6269")
    def label(x, y, content, size=10, color=ink, bold=False, centered=False):
        cv.setFillColor(color)
        cv.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        if centered:
            cv.drawCentredString(x, y, content)
        else:
            cv.drawString(x, y, content)
    label(20, height-29, "Repair quality and reasoning tokens across effort settings", size=18, bold=True)
    label(20, height-47, "One hosted response per setting; six fixed tasks in a shared prompt. Each table has a unique correct output.", size=10, color=muted)
    cell_w, cell_h = 57, 22
    origins = (128, 514)
    label(origins[0], height-76, "Correct final tables", size=12, bold=True)
    label(origins[1], height-76, "Reported reasoning tokens", size=12, bold=True)
    for i, level in enumerate(LEVELS):
        for x in origins:
            label(x + (i+.5)*cell_w, height-94, level, centered=True, color=muted)
    for j, model in enumerate(models):
        y = height - 124 - 25*j
        label(20, y+8, pretty(model), bold=True)
        for i, level in enumerate(LEVELS):
            row = cells.get((model, level))
            for k, origin in enumerate(origins):
                x = origin + i*cell_w
                value, amount = None, 0
                if row is None:
                    mark = "n/a"
                elif k == 0 and row["valid_tasks"]:
                    total, value = row["valid_tasks"], row["correct"]
                    mark, amount = f"{value}/{total}", value/total
                elif k == 1 and row["usage"]["reasoning_output_tokens"] is not None:
                    value = row["usage"]["reasoning_output_tokens"]
                    mark, amount = f"{value:,}", math.log1p(value) / math.log1p(largest)
                else:
                    mark = "--"
                shade = tint(amount, ((.42,.73,.68),(.57,.71,.86))[k]) if value is not None else colors.HexColor("#efefef")
                cv.setFillColor(shade)
                cv.roundRect(x+1.5, y, cell_w-3, cell_h, 2.5, fill=1, stroke=0)
                label(x+cell_w/2, y+7.5, mark, size=9.5, color=ink if value is not None else muted, centered=True)
    label(20, 30, "Fractions use the number of scorable tasks. n/a = unsupported effort. -- = no observed value.", size=10, color=muted)
    label(20, 14, "Colour on the token panel uses a logarithmic scale. CLI usage reports reasoning tokens as part of output tokens.", size=9, color=muted)
    cv.showPage()
    cv.save()
    document = pypdfium2.PdfDocument(area.getvalue())
    try:
        document[0].render(scale=2).to_pil().save(output)
    finally:
        document.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(json.loads(args.panel.read_bytes()), json.loads(args.catalog.read_bytes()), args.output)

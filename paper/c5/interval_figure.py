"""Draw both diagnostic inputs for the same generated Matplotlib interval patch."""
import json

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, String
from reportlab.lib import colors

from analysis import production_patch_report as study


def figure_inputs():
    ledger = json.loads((study.DEFAULT / "results.json").read_bytes())
    key = ("matplotlib", "gpt-6-luna", "working", "revealing")
    record, = [r for r in ledger["rows"] if tuple(r[k] for k in ("task", "model", "start", "arm")) == key]
    if record["status"] != "OK" or record["action"] != "replace" or record["passes"]:
        raise ValueError("Expected the recorded working-start regression")
    run = study.evaluator("matplotlib", record["expression"])
    initial = json.loads((study.DEFAULT / "calibration.json").read_bytes())["matplotlib"]["starts"]["faulty"]["expression"]
    old_bug = study.evaluator("matplotlib", initial)
    data = []
    for arm in ("revealing", "shared"):
        args = study.PROBES["matplotlib"][arm]
        data.append((args, study.expected("matplotlib", args)["output"], old_bug(args)["output"], run(args)["output"]))
    return data


def interval_figure():
    values = figure_inputs()
    fig = Drawing(460, 170)
    ink = colors.HexColor("#1e343c")
    grey = colors.HexColor("#617379")
    teal = colors.HexColor("#226d70")
    rust = colors.HexColor("#994e33")
    def label(x, y, value, size=9, bold=False, fill=ink, align="start"):
        fig.add(String(x, y, value, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                       fillColor=fill, textAnchor=align))
    def position(column, v):
        return 141 + column * 170 + 12.3*v
    def segment(column, y, endpoints, color):
        first, end = (position(column, v) for v in endpoints)
        fig.add(Line(end+3, y, first, y, strokeColor=color, strokeWidth=2.1))
        fig.add(Circle(first, y, 2.6, fillColor=color, strokeColor=color))
        fig.add(Polygon([end, y, end+5, y+3, end+5, y-3], fillColor=color, strokeColor=color))
    label(6, 153, "A probe can lose its power after the edit", 12, True)
    for col, (args, expected, historical, generated) in enumerate(values):
        base = 136 + col*170
        label(base, 131, ("Contained span" if col == 0 else "Expanding span"), 10, True)
        label(base, 117, f"Old [{args[0]}, {args[1]}], add [{args[2]}, {args[3]}]", 8.5, fill=grey)
        for y, endpoints, color in ((95, expected, teal), (70, historical, rust), (45, generated, ink)):
            segment(col, y, endpoints, color)
        fig.add(Line(position(col,0), 28, position(col,10), 28, strokeColor=grey, strokeWidth=.5))
        for tick in (0,2,5,8,10):
            x = position(col,tick)
            fig.add(Line(x,25,x,31,strokeColor=grey,strokeWidth=.5))
            label(x,14,str(tick),7.5,fill=grey,align="middle")
    for y, title, shade in ((92,"Required interval",teal),(67,"Historical defect",rust),(42,"Generated regression",ink)):
        label(6,y,title,9.2,True,shade)
    return fig

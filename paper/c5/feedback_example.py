"""Draw two observed histories from the released choices and execution records."""
from ast import literal_eval
import json
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors

ANALYSIS = Path(__file__).resolve().parents[2] / "analysis"


def load(study, part):
    return json.loads((ANALYSIS / study / f"{part}.json").read_bytes())


def feedback_example():
    formatter = "pprint_display_20261128"
    variants = load(formatter, "calibration")["variants"]
    history = "gpt-6-luna_cpython_correct_r1_early"
    choices = {r["arm"]: r for r in load(formatter, "results")["rows"] if r["parent_id"] == history}
    labels = {"p3": "Keep text order", "p5": "Use numeric order"}
    left = []
    for arm in ("none", "shared", "revealing"):
        row = choices[arm]
        if row["status"] != "OK" or row["before_variant"] != "p3":
            raise ValueError("Unexpected formatter checkpoint")
        keys = [] if arm == "none" else list(literal_eval(variants["p3"]["outputs"][arm]))
        observed = "No new output" if not keys else f"Prints {keys[0]} then {keys[1]}"
        left.append((observed, labels[row["after_variant"]]))

    reference = "reference_example_20261128"
    choices = {r["arm"]: r for r in load(reference, "results")["rows"] if r["block"] == "gpt-6-luna_round_A"}
    examples = load(reference, "calibration")["round"]["shown"]
    right = []
    for arm, shown in (("none", None), ("shared", examples[0]), ("target_a", examples[1]), ("target_b", examples[1])):
        row = choices[arm]
        if row["status"] != "OK" or row["start"] != "A":
            raise ValueError("Unexpected rounding checkpoint")
        shown_label = "No example" if shown is None else f"{shown[0]} must give {shown[2 if arm == 'target_b' else 1]}"
        right.append((shown_label, {"A": "Keep ties down", "B": "Use ties up"}[row["after"]]))

    figure = Drawing(460, 142)
    ink, accent, rule = (colors.HexColor(h) for h in ("#203840", "#225e69", "#cad6d7"))
    def label(x, y, txt, size=9, bold=False, shade=ink):
        figure.add(String(x, y, txt, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size, fillColor=shade))

    for x, title, desc, rows in (
        (0, "Actual output", "Starting formatter sorts keys as text.", left),
        (236, "Required output", "Starting rule rounds exact ties down.", right),
    ):
        figure.add(Rect(x, 0, 224, 140, fillColor=colors.HexColor("#f7f9f8"), strokeColor=rule, strokeWidth=.55))
        label(x + 8, 121, title, 12, True)
        label(x + 8, 105, desc)
        label(x + 8, 84, "Evidence shown", 8, True, accent)
        label(x + 118, 84, "Program chosen", 8, True, accent)
        for i, (shown, chosen) in enumerate(rows):
            y = 65 - i * 17
            figure.add(Line(x + 8, y + 11, x + 216, y + 11, strokeColor=rule, strokeWidth=.5))
            label(x + 8, y, shown)
            label(x + 118, y, chosen)
    return figure

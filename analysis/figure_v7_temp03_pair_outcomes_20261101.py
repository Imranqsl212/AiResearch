"""Render two separate excluded temperature-0.3 outcome grids from verified JSON.

Default invocation writes nothing. ``--write`` first replays both saved reports
through their source-bound analyzers, then writes one fixed PNG. The figure is
descriptive: it never pools the sequential waves or computes inferential rates.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from analysis import v7_temp_variance_20261101 as v1
from analysis import v7_temp_variance_secondwave_20261101 as v2


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "analysis/figures/v7_temp03_pair_outcomes_20261101.png"
CATEGORIES = (
    "FALSE_ONLY", "TRUTH_ONLY", "BOTH", "NEITHER",
    "NO_ONSET", "TECHNICAL", "UNSTARTED", "INDETERMINATE",
)
STYLE = {
    "FALSE_ONLY": ("F only", "False-FAIL only", "#BE4F59", "#FFFFFF"),
    "TRUTH_ONLY": ("T only", "Truthful-PASS only", "#3975AD", "#FFFFFF"),
    "BOTH": ("Both", "Both arms", "#8264A3", "#FFFFFF"),
    "NEITHER": ("Neither", "Neither arm", "#3E967F", "#FFFFFF"),
    "NO_ONSET": ("No onset", "No secure onset", "#B9C0C7", "#18232E"),
    "TECHNICAL": ("Tech", "Technical invalidation", "#D7A34D", "#18232E"),
    "UNSTARTED": ("Not run", "Not started", "#F4F6F8", "#4E5A66"),
    "INDETERMINATE": ("Unknown", "Indeterminate endpoint", "#687A89", "#FFFFFF"),
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def category(slot: dict[str, Any]) -> str:
    """Map one scheduled slot without converting missingness into a result."""
    status = slot.get("status")
    if status == "NOT_RUN_AFTER_STOP":
        _require(slot.get("pair") is None and slot.get("precursor") is None,
                 "unstarted slot contains an outcome")
        return "UNSTARTED"
    if status in {"PRECURSOR_INVALIDATED", "PAIR_INVALIDATED",
                  "POST_PRECURSOR_INVALIDATED"}:
        _require(slot.get("pair") is None,
                 "technically invalidated slot contains a verified pair")
        return "TECHNICAL"
    if status == "NOT_RUN_NO_ONSET":
        _require(slot.get("pair") is None and slot.get("precursor") is not None,
                 "no-onset slot has a pair or lacks its precursor")
        return "NO_ONSET"
    _require(status == "COMPLETED_EXCLUDED_C5_PAIR",
             f"unknown scheduled-slot status: {status}")
    pair = slot.get("pair")
    _require(isinstance(pair, dict) and isinstance(pair.get("arms"), dict),
             "verified pair is missing arm endpoints")
    arms = pair["arms"]
    _require(set(arms) == {"TRUTHFUL_PASS", "FALSE_FAIL"},
             "paired arm identities differ")
    truth = arms["TRUTHFUL_PASS"].get("terminal_finite_property_regression")
    false = arms["FALSE_FAIL"].get("terminal_finite_property_regression")
    _require((truth is None or type(truth) is int and truth in (0, 1))
             and (false is None or type(false) is int and false in (0, 1)),
             "paired endpoint is neither 0, 1, nor null")
    if truth is None or false is None:
        return "INDETERMINATE"
    if false == 1 and truth == 0:
        return "FALSE_ONLY"
    if truth == 1 and false == 0:
        return "TRUTH_ONLY"
    if truth == 1 and false == 1:
        return "BOTH"
    return "NEITHER"


def grid(report: dict[str, Any], schedule: list[dict[str, Any]],
         expected_schema: str) -> list[list[str]]:
    """Account for every prescheduled family/seed exactly once."""
    _require(report.get("schema_version") == expected_schema
             and report.get("eligible_for_main_analysis") is False
             and report.get("dispatch_status") in {"WAVE_COMPLETE", "WAVE_STOPPED"},
             "figure input is not the expected excluded wave")
    slots = report.get("slots")
    _require(isinstance(slots, list) and len(slots) == len(schedule) == 32,
             "figure input does not contain all 32 scheduled slots")
    _require(report.get("overall", {}).get("scheduled_precursors") == 32,
             "report denominator differs from fixed schedule")
    by_id: dict[str, dict[str, Any]] = {}
    for slot in slots:
        _require(isinstance(slot, dict) and isinstance(slot.get("slot_id"), str),
                 "malformed figure slot")
        slot_id = slot["slot_id"]
        _require(slot_id not in by_id, f"duplicate figure slot: {slot_id}")
        by_id[slot_id] = slot
    _require(set(by_id) == {row["slot_id"] for row in schedule},
             "figure slots differ from frozen schedule")
    matrix = []
    for family in v1.FAMILIES:
        row_categories = []
        for fixed in schedule:
            if fixed["family"] != family:
                continue
            slot = by_id[fixed["slot_id"]]
            _require(slot.get("family") == family
                     and slot.get("precursor_seed") == fixed["precursor_seed"]
                     and slot.get("branch_seed") == fixed["branch_seed"],
                     f"figure slot metadata differs: {fixed['slot_id']}")
            row_categories.append(category(slot))
        _require(len(row_categories) == 4, f"figure family lacks four seeds: {family}")
        matrix.append(row_categories)
    _require(sum(len(row) for row in matrix) == 32,
             "figure failed to account for the full wave")
    return matrix


def _verified_report(module: Any, path: Path) -> dict[str, Any]:
    _require(path.is_file() and not path.is_symlink(),
             f"verified report missing: {path}")
    saved = path.read_text(encoding="utf-8")
    replay = module.build_report()
    expected = json.dumps(replay, indent=2, sort_keys=True,
                          ensure_ascii=False) + "\n"
    _require(saved == expected,
             f"saved report differs from source-bound archive replay: {path}")
    return replay


def build_figure_data(v1_report: Path = v1.OUTPUT,
                      v2_report: Path = v2.OUTPUT) -> dict[str, Any]:
    """Fail before any drawing when either independently verified report is absent."""
    for path in (v1_report, v2_report):
        _require(path.is_file() and not path.is_symlink(),
                 f"verified report missing: {path}")
    _require(v1_report.resolve() == v1.OUTPUT.resolve()
             and v2_report.resolve() == v2.OUTPUT.resolve(),
             "figure requires the two fixed repository reports")
    first = _verified_report(v1, v1_report)
    second = _verified_report(v2, v2_report)
    left = grid(first, v1.fixed_schedule(),
                "excluded-v7-temp03-four-seed-20261101-1")
    right = grid(second, v2.fixed_schedule(),
                 "excluded-v7-temp03-secondwave-20261101-1")
    return {
        "families": list(v1.FAMILIES),
        "waves": [
            {"label": "Wave 1: excluded", "seeds": list(v1.SEEDS),
             "dispatch_status": first["dispatch_status"], "matrix": left},
            {"label": "Wave 2: post-failure excluded", "seeds": list(v2.SEEDS),
             "dispatch_status": second["dispatch_status"], "matrix": right},
        ],
    }


def render_png(data: dict[str, Any], path: Path = OUTPUT) -> None:
    """Draw a categorical grid with Pillow; one wave per panel, no pooled bars."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required to draw this figure; use the paper-render Python"
        ) from exc
    width, height = 2500, 1450
    image = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    font = {size: ImageFont.load_default(size=size) for size in (22, 24, 26, 28, 30, 34, 49)}
    draw.text((80, 64), "Paired terminal finite-reference outcomes",
              font=font[49], fill="#142332")
    draw.text((80, 135), "Eight authored task families x four seeds per separate excluded wave; temperature 0.3",
              font=font[28], fill="#415162")
    panel_xs = (55, 1290)
    grid_y, row_height, cell_width = 350, 75, 145
    for panel_x, wave in zip(panel_xs, data["waves"]):
        draw.rounded_rectangle((panel_x, 205, panel_x + 1155, 980), radius=18,
                               fill="#FAFBFC", outline="#B8C2CB", width=3)
        title = wave["label"]
        draw.text((panel_x + 35, 227), title, font=font[34], fill="#142332")
        counts = Counter(cell for row in wave["matrix"] for cell in row)
        paired = sum(counts[key] for key in CATEGORIES[:4]) + counts["INDETERMINATE"]
        summary = (f"{wave['dispatch_status'].replace('_', ' ').title()}  |  "
                   f"{paired}/32 paired  |  {counts['NO_ONSET']} no onset  |  "
                   f"{counts['TECHNICAL']} technical  |  {counts['UNSTARTED']} unstarted")
        draw.text((panel_x + 35, 285), summary, font=font[22], fill="#415162")
        grid_x = panel_x + 390
        for column, seed in enumerate(wave["seeds"]):
            draw.text((grid_x + column * cell_width + cell_width / 2, 325),
                      str(seed), font=font[26], fill="#263846", anchor="mm")
        for row_index, family in enumerate(data["families"]):
            y = grid_y + row_index * row_height
            draw.text((grid_x - 18, y + row_height / 2), family,
                      font=font[24], fill="#263846", anchor="rm")
            for column, key in enumerate(wave["matrix"][row_index]):
                label, _, background, foreground = STYLE[key]
                x = grid_x + column * cell_width
                draw.rectangle((x + 3, y + 3, x + cell_width - 4,
                                y + row_height - 4), fill=background,
                               outline="#9AA8B5", width=2)
                draw.text((x + cell_width / 2, y + row_height / 2), label,
                          font=font[22], fill=foreground, anchor="mm")
    draw.text((80, 1020), "Legend: terminal bounded-property regression",
              font=font[30], fill="#142332")
    legend_xs = (80, 680, 1280, 1880)
    for index, key in enumerate(CATEGORIES):
        row, column = divmod(index, 4)
        y = 1080 + row * 80
        x = legend_xs[column]
        _, label, background, _ = STYLE[key]
        draw.rectangle((x, y, x + 40, y + 40), fill=background,
                       outline="#8A98A4", width=2)
        draw.text((x + 54, y + 20), label, font=font[26], fill="#263846",
                  anchor="lm")
    draw.text((80, 1280),
              "Regression = final active candidate fails the independent bounded finite reference after a verified secure onset.",
              font=font[24], fill="#415162")
    draw.text((80, 1320),
              "Wave 2 was planned after Wave 1 stopped technically. Cells are descriptive; waves are not pooled.",
              font=font[24], fill="#415162")
    draw.text((80, 1360),
              "Finite-reference agreement is not a general security guarantee. Both waves are excluded from the main study.",
              font=font[24], fill="#415162")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="verify both saved reports and write the fixed PNG")
    args = parser.parse_args()
    if not args.write:
        parser.print_help()
        return
    data = build_figure_data()
    render_png(data)
    print(f"Wrote {OUTPUT.relative_to(ROOT)} from two separately verified reports")


if __name__ == "__main__":
    main()

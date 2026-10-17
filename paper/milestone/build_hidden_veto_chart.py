"""Build a descriptive chart from the archived historical result summary.

Run from any directory::

    python3 paper/milestone/build_hidden_veto_chart.py

The SVG uses only Python's standard library. ImageMagick is used for the PNG.
No confidence intervals are drawn: the five historical families were selected,
with one observation per task cell.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "paper/artifacts/results.json"
DEFAULT_SVG = Path(__file__).with_name("hidden_veto_results.svg")
DEFAULT_PNG = Path(__file__).with_name("hidden_veto_results.png")


def load_counts(path: Path) -> list[dict[str, int | str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    main = data["main"]
    groups = [
        ("Repairable (R)", data["repairable"]),
        ("Policy rejected (U)", data["policy_rejected"]),
    ]
    rows: list[dict[str, int | str]] = []
    for label, group in groups:
        n = group["n"]
        raw = group["raw_checks_pass"]
        accepted = group["accepted"]
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in (n, raw, accepted)):
            raise ValueError(f"Non-integer summary for {label}")
        if not 0 <= accepted <= raw <= n:
            raise ValueError(f"Invalid count ordering for {label}")
        rows.append({"label": label, "n": n, "raw": raw, "accepted": accepted})
    if [row["n"] for row in rows] != [20, 20] or main["n"] != 40:
        raise ValueError("This chart is defined for the 40-episode historical cohort")
    if sum(int(row["raw"]) for row in rows) != main["raw_checks_pass"]:
        raise ValueError("Raw-pass group totals disagree with main summary")
    if sum(int(row["accepted"]) for row in rows) != main["accepted"]:
        raise ValueError("Acceptance group totals disagree with main summary")
    if rows[1]["raw"] - rows[1]["accepted"] != main["hidden_policy_veto"]:
        raise ValueError("U raw-pass/acceptance gap disagrees with hidden-veto count")
    return rows


def render_svg(rows: list[dict[str, int | str]]) -> str:
    top, baseline, maximum = 190, 585, 20
    plot_height = baseline - top
    x_by_group = ((285, 440), (785, 940))
    colors = ("#173a60", "#218d91")
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="800" viewBox="0 0 1300 800" role="img" aria-labelledby="title desc">',
        '<title id="title">Historical finite tests and final acceptance</title>',
        '<desc id="desc">Grouped bars for 20 repairable and 20 policy-rejected episodes. Raw family tests passed for 16 and 9 respectively; final acceptance was 16 and 0. The policy-rejected group had a hidden veto.</desc>',
        '<rect width="1300" height="800" fill="#ffffff"/>',
        '<rect width="1300" height="12" fill="#173a60"/>',
        '<g font-family="Arial,Helvetica,sans-serif" fill="#172536">',
        '<text x="120" y="70" font-size="35" font-weight="700">When finite tests pass but the gate rejects</text>',
        '<text x="120" y="105" font-size="21" fill="#536578">Historical main cohort · 40 episodes · descriptive counts</text>',
        f'<rect x="120" y="133" width="22" height="22" fill="{colors[0]}"/>',
        '<text x="154" y="151" font-size="19">Raw family finite tests passed</text>',
        f'<rect x="520" y="133" width="22" height="22" fill="{colors[1]}"/>',
        '<text x="554" y="151" font-size="19">Final benchmark accepted</text>',
    ]
    for tick in range(0, maximum + 1, 5):
        y = baseline - plot_height * tick / maximum
        parts.append(f'<line x1="165" y1="{y:.1f}" x2="1120" y2="{y:.1f}" stroke="#dce4eb" stroke-width="1.5"/>')
        parts.append(f'<text x="147" y="{y + 6:.1f}" font-size="18" text-anchor="end" fill="#536578">{tick}</text>')
    parts.append('<text x="52" y="400" font-size="18" transform="rotate(-90 52 400)">Episodes (out of 20 per group)</text>')
    for i, row in enumerate(rows):
        n = int(row["n"])
        for j, field in enumerate(("raw", "accepted")):
            value = int(row[field])
            x = x_by_group[i][j]
            height = plot_height * value / maximum
            y = baseline - height
            if value:
                parts.append(f'<rect x="{x}" y="{y:.1f}" width="116" height="{height:.1f}" fill="{colors[j]}"/>')
            else:
                parts.append(f'<line x1="{x}" y1="{baseline - 2}" x2="{x + 116}" y2="{baseline - 2}" stroke="{colors[j]}" stroke-width="4"/>')
            label_y = max(top + 22, y - 13) if value else baseline - 17
            parts.append(f'<text x="{x + 58}" y="{label_y:.1f}" font-size="24" font-weight="700" text-anchor="middle">{value}/{n}</text>')
        center = sum(x_by_group[i]) / 2 + 58
        parts.append(f'<text x="{center:.1f}" y="631" font-size="23" font-weight="700" text-anchor="middle">{row["label"]}</text>')
        parts.append(f'<text x="{center:.1f}" y="659" font-size="18" text-anchor="middle" fill="#536578">n = {n} episodes</text>')
    parts.extend(
        [
            '<rect x="120" y="695" width="1060" height="61" rx="8" fill="#edf3f6"/>',
            '<text x="138" y="719" font-size="17" font-weight="700">Interpretation limit</text>',
            '<text x="138" y="743" font-size="16">Finite family tests are limited; the U gate applied a hidden policy veto after those tests.</text>',
            '<text x="120" y="784" font-size="14" fill="#64748b">Source: paper/artifacts/results.json · Historical exploratory cohort · No inferential intervals</text>',
            '</g></svg>',
        ]
    )
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--svg", type=Path, default=DEFAULT_SVG)
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG)
    args = parser.parse_args()
    rows = load_counts(args.input)
    args.svg.parent.mkdir(parents=True, exist_ok=True)
    args.svg.write_text(render_svg(rows), encoding="utf-8")
    magick = shutil.which("magick")
    if not magick:
        raise RuntimeError("ImageMagick 'magick' is required to render the PNG")
    args.png.parent.mkdir(parents=True, exist_ok=True)
    font_options: list[str] = []
    for font in (
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if font.is_file():
            font_options = ["-font", str(font)]
            break
    subprocess.run(
        [magick, *font_options, "-background", "white", "-density", "120", str(args.svg), "-strip", str(args.png)],
        check=True,
    )
    print(f"Wrote {args.svg} and {args.png}")


if __name__ == "__main__":
    main()

"""Small dependency-free SVG renderers for data-backed analysis figures."""

from __future__ import annotations

import html
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


PALETTE = ("#2C7FB8", "#7FCDBB", "#FEC44F", "#F03B20", "#756BB1", "#636363")


def _fmt(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "NA"
    return f"{value:.{digits}f}"


def _svg_document(width: int, height: int, body: Iterable[str]) -> str:
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
            '<rect width="100%" height="100%" fill="white"/>',
            '<style>text{font-family:Arial,sans-serif;fill:#18212f}.title{font-size:18px;font-weight:700}.subtitle{font-size:12px;fill:#4b5563}.axis{font-size:12px}.tick{font-size:11px;fill:#4b5563}.label{font-size:11px}</style>',
            *body,
            "</svg>",
        ]
    )


def _write(path: Path, body: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_svg_document(900, 560, body), encoding="utf-8")


def bar_chart(
    path: Path,
    *,
    title: str,
    y_label: str,
    rows: Sequence[Mapping[str, Any]],
    sample_note: str,
    proportion: bool,
) -> None:
    """Render condition bars with family-cluster bootstrap intervals."""

    available = [row for row in rows if isinstance(row.get("estimate"), (int, float))]
    if not available:
        raise ValueError("bar_chart requires at least one numeric summary")
    left, right, top, bottom = 105, 55, 95, 100
    plot_width, plot_height = 900 - left - right, 560 - top - bottom
    maximum = 1.0 if proportion else max(
        float(row.get("ci_high") or row["estimate"]) for row in available
    )
    maximum = max(maximum, 1.0 if proportion else 0.1)
    body = [
        f'<text x="{left}" y="35" class="title">{html.escape(title)}</text>',
        f'<text x="{left}" y="56" class="subtitle">{html.escape(sample_note)}; error bars = 95% task-family cluster bootstrap CI</text>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#27364a"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#27364a"/>',
        f'<text x="20" y="{top + plot_height / 2}" class="axis" transform="rotate(-90 20 {top + plot_height / 2})">{html.escape(y_label)}</text>',
        f'<text x="{left + plot_width / 2}" y="530" class="axis">Condition</text>',
    ]
    for tick in range(6):
        value = maximum * tick / 5
        y = top + plot_height * (1 - value / maximum)
        body.extend(
            [
                f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#e5e7eb"/>',
                f'<text x="{left - 10}" y="{y + 4:.1f}" class="tick" text-anchor="end">{_fmt(value * 100 if proportion else value, 0 if proportion else 2)}{"%" if proportion else ""}</text>',
            ]
        )
    spacing = plot_width / len(available)
    bar_width = min(80, spacing * 0.55)
    for index, row in enumerate(available):
        estimate = float(row["estimate"])
        lower = float(row.get("ci_low") if row.get("ci_low") is not None else estimate)
        upper = float(row.get("ci_high") if row.get("ci_high") is not None else estimate)
        center = left + spacing * (index + 0.5)
        height = plot_height * estimate / maximum
        y = top + plot_height - height
        color = PALETTE[index % len(PALETTE)]
        body.extend(
            [
                f'<rect x="{center - bar_width / 2:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{height:.1f}" fill="{color}"/>',
                f'<line x1="{center:.1f}" y1="{top + plot_height * (1 - lower / maximum):.1f}" x2="{center:.1f}" y2="{top + plot_height * (1 - upper / maximum):.1f}" stroke="#111827" stroke-width="2"/>',
                f'<line x1="{center - 6:.1f}" y1="{top + plot_height * (1 - lower / maximum):.1f}" x2="{center + 6:.1f}" y2="{top + plot_height * (1 - lower / maximum):.1f}" stroke="#111827"/>',
                f'<line x1="{center - 6:.1f}" y1="{top + plot_height * (1 - upper / maximum):.1f}" x2="{center + 6:.1f}" y2="{top + plot_height * (1 - upper / maximum):.1f}" stroke="#111827"/>',
                f'<text x="{center:.1f}" y="{top + plot_height + 22}" class="label" text-anchor="middle">{html.escape(str(row["condition"]))}</text>',
                f'<text x="{center:.1f}" y="{max(80, y - 8):.1f}" class="label" text-anchor="middle">{_fmt(estimate * 100 if proportion else estimate, 1)}{"%" if proportion else ""}</text>',
            ]
        )
    _write(path, body)


def grouped_bar_chart(
    path: Path,
    *,
    title: str,
    y_label: str,
    rows: Sequence[Mapping[str, Any]],
    sample_note: str,
) -> None:
    """Render two or more rate series by condition with cluster intervals."""

    available = [row for row in rows if isinstance(row.get("estimate"), (int, float))]
    if not available:
        raise ValueError("grouped_bar_chart requires at least one numeric summary")
    conditions = sorted({str(row["condition"]) for row in available})
    series = sorted({str(row["series"]) for row in available})
    by_key = {(str(row["condition"]), str(row["series"])): row for row in available}
    left, right, top, bottom = 105, 55, 95, 115
    plot_width, plot_height = 900 - left - right, 560 - top - bottom
    body = [
        f'<text x="{left}" y="35" class="title">{html.escape(title)}</text>',
        f'<text x="{left}" y="56" class="subtitle">{html.escape(sample_note)}; error bars = 95% task-family cluster bootstrap CI</text>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#27364a"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#27364a"/>',
        f'<text x="20" y="{top + plot_height / 2}" class="axis" transform="rotate(-90 20 {top + plot_height / 2})">{html.escape(y_label)}</text>',
        f'<text x="{left + plot_width / 2}" y="520" class="axis">Condition</text>',
    ]
    for tick in range(6):
        y = top + plot_height * (1 - tick / 5)
        body.extend(
            [
                f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#e5e7eb"/>',
                f'<text x="{left - 10}" y="{y + 4:.1f}" class="tick" text-anchor="end">{tick * 20}%</text>',
            ]
        )
    condition_spacing = plot_width / len(conditions)
    series_width = min(45, condition_spacing * 0.65 / len(series))
    for condition_index, condition in enumerate(conditions):
        center = left + condition_spacing * (condition_index + 0.5)
        for series_index, name in enumerate(series):
            row = by_key.get((condition, name))
            if row is None:
                continue
            estimate = float(row["estimate"])
            lower = float(row.get("ci_low") if row.get("ci_low") is not None else estimate)
            upper = float(row.get("ci_high") if row.get("ci_high") is not None else estimate)
            x = center + (series_index - (len(series) - 1) / 2) * (series_width + 4)
            height = plot_height * estimate
            y = top + plot_height - height
            color = PALETTE[series_index % len(PALETTE)]
            body.extend(
                [
                    f'<rect x="{x - series_width / 2:.1f}" y="{y:.1f}" width="{series_width:.1f}" height="{height:.1f}" fill="{color}"/>',
                    f'<line x1="{x:.1f}" y1="{top + plot_height * (1 - lower):.1f}" x2="{x:.1f}" y2="{top + plot_height * (1 - upper):.1f}" stroke="#111827" stroke-width="2"/>',
                ]
            )
        body.append(
            f'<text x="{center:.1f}" y="{top + plot_height + 22}" class="label" text-anchor="middle">{html.escape(condition)}</text>'
        )
    for index, name in enumerate(series):
        x = left + index * 260
        body.extend(
            [
                f'<rect x="{x}" y="540" width="10" height="10" fill="{PALETTE[index % len(PALETTE)]}"/>',
                f'<text x="{x + 15}" y="550" class="tick">{html.escape(name)}</text>',
            ]
        )
    _write(path, body)


def stacked_stopping_chart(
    path: Path,
    *,
    rows: Sequence[Mapping[str, Any]],
    sample_note: str,
) -> None:
    """Render stopping classes as condition-level proportions, with counts as labels."""

    by_condition: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_condition[str(row.get("condition", "UNKNOWN"))][str(row.get("terminal_class", "UNKNOWN"))] += 1
    if not by_condition:
        raise ValueError("stacked_stopping_chart requires terminal-class rows")
    classes = sorted({label for counter in by_condition.values() for label in counter})
    left, right, top, bottom = 105, 55, 95, 120
    plot_width, plot_height = 900 - left - right, 560 - top - bottom
    conditions = sorted(by_condition)
    body = [
        '<text x="105" y="35" class="title">Stopping behavior by condition</text>',
        f'<text x="105" y="56" class="subtitle">{html.escape(sample_note)}; segments are run proportions, descriptive only</text>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#27364a"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#27364a"/>',
        f'<text x="20" y="{top + plot_height / 2}" class="axis" transform="rotate(-90 20 {top + plot_height / 2})">Runs (%)</text>',
        f'<text x="{left + plot_width / 2}" y="515" class="axis">Condition</text>',
    ]
    for tick in range(6):
        y = top + plot_height * (1 - tick / 5)
        body.extend(
            [
                f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#e5e7eb"/>',
                f'<text x="{left - 10}" y="{y + 4:.1f}" class="tick" text-anchor="end">{tick * 20}%</text>',
            ]
        )
    spacing = plot_width / len(conditions)
    bar_width = min(100, spacing * 0.55)
    for index, condition in enumerate(conditions):
        counter = by_condition[condition]
        total = sum(counter.values())
        center = left + spacing * (index + 0.5)
        cumulative = 0.0
        for class_index, terminal_class in enumerate(classes):
            proportion = counter[terminal_class] / total
            height = proportion * plot_height
            y = top + plot_height - cumulative * plot_height - height
            body.append(
                f'<rect x="{center - bar_width / 2:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{height:.1f}" fill="{PALETTE[class_index % len(PALETTE)]}"><title>{html.escape(terminal_class)}: {counter[terminal_class]}/{total}</title></rect>'
            )
            cumulative += proportion
        body.append(
            f'<text x="{center:.1f}" y="{top + plot_height + 22}" class="label" text-anchor="middle">{html.escape(condition)} (n={total})</text>'
        )
    for index, terminal_class in enumerate(classes):
        x = left + (index % 3) * 245
        y = 535 + (index // 3) * 16
        body.extend(
            [
                f'<rect x="{x}" y="{y - 10}" width="10" height="10" fill="{PALETTE[index % len(PALETTE)]}"/>',
                f'<text x="{x + 15}" y="{y}" class="tick">{html.escape(terminal_class)}</text>',
            ]
        )
    _write(path, body)


def strategy_transition_graph(
    path: Path,
    *,
    edges: Sequence[tuple[str, str]],
    sample_note: str,
) -> None:
    """Render observed strategy transitions; nodes are not latent beliefs."""

    counts = Counter(edges)
    nodes = sorted({node for edge in counts for node in edge})
    if not nodes:
        raise ValueError("strategy_transition_graph requires at least one structured edge")
    center_x, center_y, radius = 450, 290, 180
    positions = {
        node: (
            center_x + radius * math.cos(2 * math.pi * index / len(nodes) - math.pi / 2),
            center_y + radius * math.sin(2 * math.pi * index / len(nodes) - math.pi / 2),
        )
        for index, node in enumerate(nodes)
    }
    body = [
        '<text x="105" y="35" class="title">Observed strategy transition graph</text>',
        f'<text x="105" y="56" class="subtitle">{html.escape(sample_note)}; nodes = structured strategy classes, edges = transition counts</text>',
        '<text x="105" y="530" class="axis">Source strategy class → destination strategy class (count-labelled directed edges)</text>',
    ]
    for (source, destination), count in sorted(counts.items()):
        x1, y1 = positions[source]
        x2, y2 = positions[destination]
        if source == destination:
            continue
        midpoint_x, midpoint_y = (x1 + x2) / 2, (y1 + y2) / 2
        body.extend(
            [
                f'<path d="M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}" stroke="#64748b" stroke-width="{min(6, 1 + count)}" fill="none" marker-end="url(#arrow)"/>',
                f'<text x="{midpoint_x:.1f}" y="{midpoint_y:.1f}" class="label" text-anchor="middle">{count}</text>',
            ]
        )
    body.insert(1, '<defs><marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#64748b"/></marker></defs>')
    for index, node in enumerate(nodes):
        x, y = positions[node]
        body.extend(
            [
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="42" fill="{PALETTE[index % len(PALETTE)]}" stroke="#1f2937"/>',
                f'<text x="{x:.1f}" y="{y + 4:.1f}" class="label" text-anchor="middle">{html.escape(node[:18])}</text>',
            ]
        )
    _write(path, body)


def representative_trajectory_chart(
    path: Path,
    *,
    trajectories: Sequence[Mapping[str, Any]],
    sample_note: str,
) -> None:
    """Render deterministic representative trajectories as action-index lanes."""

    if not trajectories:
        raise ValueError("representative_trajectory_chart requires trajectories")
    left, right, top, bottom = 220, 55, 95, 80
    plot_width, plot_height = 900 - left - right, 560 - top - bottom
    max_actions = max(int(item.get("logical_actions", 0)) for item in trajectories) or 1
    row_height = plot_height / len(trajectories)
    body = [
        '<text x="220" y="35" class="title">Representative observable trajectories</text>',
        f'<text x="220" y="56" class="subtitle">{html.escape(sample_note)}; each lane spans logical action count to terminal event</text>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#27364a"/>',
        f'<text x="{left + plot_width / 2}" y="530" class="axis">Logical action index (count)</text>',
        '<text x="20" y="300" class="axis" transform="rotate(-90 20 300)">Representative trajectory (deterministic stratified selection)</text>',
    ]
    for tick in range(0, max_actions + 1):
        if max_actions > 14 and tick % max(1, math.ceil(max_actions / 12)):
            continue
        x = left + plot_width * tick / max_actions
        body.extend(
            [
                f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#e5e7eb"/>',
                f'<text x="{x:.1f}" y="{top + plot_height + 20}" class="tick" text-anchor="middle">{tick}</text>',
            ]
        )
    for index, row in enumerate(trajectories):
        y = top + row_height * (index + 0.5)
        count = int(row.get("logical_actions", 0))
        x2 = left + plot_width * count / max_actions
        color = PALETTE[index % len(PALETTE)]
        label = f'{row.get("condition", "?")} · {row.get("trajectory_class", "?")} · {row.get("run_id", "?")}'
        body.extend(
            [
                f'<line x1="{left}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="7"/>',
                f'<circle cx="{x2:.1f}" cy="{y:.1f}" r="6" fill="{color}"/>',
                f'<text x="{left - 10}" y="{y + 4:.1f}" class="tick" text-anchor="end">{html.escape(label[:40])}</text>',
            ]
        )
    _write(path, body)

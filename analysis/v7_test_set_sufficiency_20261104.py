"""Exhaustive, source-bound test-set audit of the authored v7 candidate language.

This enumerates all documented modes and every nonempty subset of the three
(or two) authored worlds. It does not execute a model, establish real-world
security, or admit these tasks to the prospective main study.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

from benchmark.finite_batch_c_reference_v7 import reference_results
from benchmark.finite_batch_c_v7 import FAMILIES, candidate_space, decision
from benchmark.validate_finite_batch_c_v7 import ROOT as TASK_ROOT, validate


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "analysis/v7_test_set_sufficiency_20261104.json"
FIGURE = ROOT / "figures/v7_checker_stage_cascade_20261104.svg"
VERSION = "excluded-v7-exhaustive-test-set-sufficiency-v1"
CONDITIONS = ("C1", "C3", "C5")


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def _load_task(family: str, condition: str) -> tuple[dict[str, Any], str]:
    path = TASK_ROOT / f"fc7-{family}-{condition.lower()}.task.json"
    raw = path.read_bytes()
    task = json.loads(raw)
    if task.get("family") != family or task.get("condition") != condition:
        raise ValueError(f"unexpected task identity: {path}")
    return task, hashlib.sha256(raw).hexdigest()


def _passes(task: dict[str, Any], candidate: dict[str, str], indices: tuple[int, ...]) -> bool:
    return all(decision(task, candidate, task["worlds"][i]) ==
               task["worlds"][i]["required_output"] for i in indices)


def task_report(family: str, condition: str) -> dict[str, Any]:
    task, task_sha = _load_task(family, condition)
    candidates = list(candidate_space(task))
    worlds = task["worlds"]
    all_indices = tuple(range(len(worlds)))
    modes = []
    for candidate in candidates:
        raw, strong, oracle, gate = reference_results(task, candidate)
        local_raw = _passes(task, candidate, (0,))
        local_strong = _passes(task, candidate, all_indices)
        if (raw == "PASS") != local_raw or (strong == "PASS") != local_strong:
            raise ValueError(f"independent and local checker disagree: {task['task_id']}")
        if (oracle == "SECURE") != local_strong:
            raise ValueError(f"oracle and full-world checker disagree: {task['task_id']}")
        if (gate == "PASS") != (local_strong and task["gate_mode"] == "normal"):
            raise ValueError(f"gate and checker disagree: {task['task_id']}")
        modes.append({"mode": candidate["mode"], "raw_pass": local_raw,
                      "full_pass": local_strong, "gate_pass": gate == "PASS",
                      "passing_world_ids": [w["case_id"] for i, w in enumerate(worlds)
                                            if _passes(task, candidate, (i,))]})

    full = tuple(m["full_pass"] for m in modes)
    sufficient: list[tuple[int, ...]] = []
    subset_rows = []
    for width in range(1, len(worlds) + 1):
        for indices in itertools.combinations(all_indices, width):
            verdicts = tuple(_passes(task, candidate, indices) for candidate in candidates)
            matches = verdicts == full
            subset_rows.append({"case_ids": [worlds[i]["case_id"] for i in indices],
                                "accepted_modes": [modes[i]["mode"] for i, value
                                                   in enumerate(verdicts) if value],
                                "preserves_full_classification": matches})
            if matches and (not sufficient or len(indices) == len(sufficient[0])):
                sufficient.append(indices)
    if not sufficient:
        raise ValueError(f"no sufficient test set: {task['task_id']}")
    first = [m for m in modes if m["raw_pass"]]
    return {
        "family": family, "condition": condition,
        "task_id": task["task_id"], "task_sha256": task_sha,
        "world_count": len(worlds), "candidate_mode_count": len(candidates),
        "full_secure_mode_count": sum(full),
        "raw_pass_count": len(first),
        "raw_false_positive_count": sum(m["raw_pass"] and not m["full_pass"] for m in modes),
        "raw_false_positive_modes": [m["mode"] for m in modes
                                     if m["raw_pass"] and not m["full_pass"]],
        "raw_false_negative_count": sum(not m["raw_pass"] and m["full_pass"] for m in modes),
        "minimal_sufficient_world_count": len(sufficient[0]),
        "minimal_sufficient_sets": [[worlds[i]["case_id"] for i in indices]
                                    for indices in sufficient],
        "modes": modes, "subsets": subset_rows,
    }


def build_report() -> dict[str, Any]:
    admission = validate()
    if admission["status"] != "STRUCTURAL_PRE_REVIEW_ONLY_NOT_HUMAN_ADMITTED":
        raise ValueError("unexpected task-admission status")
    rows = [task_report(family, condition) for family in sorted(FAMILIES)
            for condition in CONDITIONS]
    return {
        "version": VERSION,
        "status": "EXCLUDED_AUTHORED_TEST_SET_AUDIT",
        "eligible_for_main_analysis": False,
        "human_semantic_admission": "PENDING",
        "task_index_sha256": admission["index_sha256"],
        "condition_order": list(CONDITIONS),
        "task_count": len(rows),
        "candidate_mode_evaluations": sum(r["candidate_mode_count"] for r in rows),
        "raw_false_positive_mode_evaluations": sum(r["raw_false_positive_count"] for r in rows),
        "rows": rows,
    }


def render_figure(report: dict[str, Any]) -> bytes:
    """Vector chart of counts, explicitly denominated in authored mode cards."""
    colors = {"raw": "#da9a18", "full": "#26789d", "gate": "#4d8a64"}
    labels = {"C1": "Repairable", "C3": "Hidden input", "C5": "Hidden veto"}
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="570" viewBox="0 0 1100 570">',
        '<rect width="1100" height="570" fill="#fff"/>',
        '<text x="46" y="42" font-family="Arial,sans-serif" font-size="27" font-weight="700" fill="#172f3f">Three layers of benchmark decisions</text>',
        '<text x="46" y="69" font-family="Arial,sans-serif" font-size="15" fill="#4a5d67">Exhaustive authored mode cards, not model trials; 26 modes per condition</text>',
    ]
    for group, condition in enumerate(CONDITIONS):
        rows = [r for r in report["rows"] if r["condition"] == condition]
        counts = (sum(r["raw_pass_count"] for r in rows),
                  sum(r["full_secure_mode_count"] for r in rows),
                  sum(sum(m["gate_pass"] for m in r["modes"]) for r in rows))
        top = 118 + group * 145
        parts.append(f'<text x="46" y="{top + 22}" font-family="Arial,sans-serif" font-size="21" font-weight="700" fill="#172f3f">{condition}: {labels[condition]}</text>')
        for i, (stage, count) in enumerate(zip(("raw", "full", "gate"), counts)):
            x = 292 + i * 270
            width = round(185 * count / 26)
            parts.extend((
                f'<text x="{x}" y="{top - 7}" font-family="Arial,sans-serif" font-size="16" fill="#354f60">{("First test", "All worlds", "Final verdict")[i]}</text>',
                f'<rect x="{x}" y="{top + 14}" width="185" height="30" rx="4" fill="#edf1f2"/>',
                f'<rect x="{x}" y="{top + 14}" width="{width}" height="30" rx="4" fill="{colors[stage]}"/>',
                f'<text x="{x + 193}" y="{top + 38}" font-family="Arial,sans-serif" font-size="22" font-weight="700" fill="#172f3f">{count}</text>',
            ))
            if i < 2:
                parts.append(f'<text x="{x + 240}" y="{top + 38}" font-family="Arial,sans-serif" font-size="22" fill="#78909c">→</text>')
        if group < 2:
            parts.append(f'<line x1="46" x2="1054" y1="{top + 100}" y2="{top + 100}" stroke="#dae2e6"/>')
    parts.extend((
        '<text x="46" y="552" font-family="Arial,sans-serif" font-size="14" fill="#4a5d67">C1 and C5 share the same tests; C5 vetoes every secure mode after testing. C3 withholds a needed input.</text>',
        '</svg>',
    ))
    return ("\n".join(parts) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--write", action="store_true")
    choice.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    raw = _canonical(report)
    if args.write:
        OUTPUT.write_bytes(raw)
        FIGURE.write_bytes(render_figure(report))
    else:
        if OUTPUT.read_bytes() != raw:
            raise ValueError("saved test-set audit differs from current source-bound recount")
        if FIGURE.read_bytes() != render_figure(report):
            raise ValueError("saved stage-cascade figure differs from source-bound recount")
    print(json.dumps({key: report[key] for key in
                      ("task_count", "candidate_mode_evaluations",
                       "raw_false_positive_mode_evaluations")}, sort_keys=True))


if __name__ == "__main__":
    main()

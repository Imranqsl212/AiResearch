"""Estimate excess cross-condition disagreement over within-prompt repeat disagreement."""
import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent / "replicate_display_20261128"
PARENT = "pprint_display_20261128"
ASSIGNMENTS = ("none1", "none2", "shared1", "shared2")
ENDPOINTS = ("source", "function")


def bound_json(path, digest):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError(f"Bound file changed: {path.name}")
    return json.loads(raw)


def verify_inputs(plan, parent, calibration, data):
    if plan.get("eligible_for_main_analysis") is not False or data.get("eligible_for_main_analysis") is not False:
        raise ValueError("Missing exploratory status")
    scores = {}
    for code, variant in calibration["variants"].items():
        checks = variant["checks"]
        if len(checks) != 10 or len({c["probe"] for c in checks}) != 10:
            raise ValueError("Incorrect hold-out roster")
        for c in checks:
            if (type(c["bindings_preserved"]) is not bool or (c["comparable_keys_sorted"] is not None
                    and type(c["comparable_keys_sorted"]) is not bool)
                    or c["passed"] is not (c["bindings_preserved"] and c["comparable_keys_sorted"] is not False)):
                raise ValueError("Inconsistent functional components")
        score = all(c["passed"] for c in checks)
        if variant["correct"] is not score:
            raise ValueError("Inconsistent functional score")
        scores[code] = score
    if len(scores) != 4 or sum(scores.values()) != 2:
        raise ValueError("Expected four source choices, two passing")
    originals = {b["parent_id"]: b for b in parent["blocks"]}
    blocks = {b["parent_id"]: b for b in plan["blocks"]}
    if len(originals) != 16 or len(plan["blocks"]) != 16 or blocks.keys() != originals.keys():
        raise ValueError("Starting roster differs from archived histories")
    for bid, block in blocks.items():
        if any(block[k] != v for k, v in originals[bid].items()) or sorted(block["assignments"]) != sorted(ASSIGNMENTS):
            raise ValueError("Archived history, options, or repetitions differ")
        if set(block["options"].values()) != set(scores) or block["before_correct"] is not scores[block["before_variant"]]:
            raise ValueError("Incorrect option menu or starting grade")
    rows = data["rows"]
    if len(rows) != 64 or {(r["parent_id"], r["assignment"]) for r in rows} != set(product(blocks, ASSIGNMENTS)):
        raise ValueError("Each assignment needs a separate status")
    for row in rows:
        b = blocks[row["parent_id"]]
        arm = row["assignment"][:-1]
        if (row["arm"] != arm or row["prompt_sha256"] != b["prompt_sha256"][arm] or row["model"] != b["model"]
                or row["history_sha256"] != b["history_sha256"] or row["before_variant"] != b["before_variant"]
                or row["before_correct"] is not b["before_correct"]):
            raise ValueError("Observed assignment differs")
        if row["status"] != "OK":
            if not row["status"] or any(row[k] is not None for k in ("choice", "after_variant", "after_correct")):
                raise ValueError("Missing selection has a final grade")
            continue
        choice = row["choice"]
        selected = b["before_variant"] if choice == "keep" else b["options"].get(choice)
        if (selected is None or (choice != "keep" and selected == b["before_variant"])
                or selected != row["after_variant"] or row["after_correct"] is not scores[selected]):
            raise ValueError("Recorded selection or grade differs")
    return blocks, scores


def disagreement(values):
    """Return raw cross (four comparisons) and within (two comparisons) counts."""
    a1, a2, b1, b2 = values
    cross = sum(a != b for a, b in product((a1, a2), (b1, b2)))
    within = int(a1 != a2) + int(b1 != b2)
    return cross, within, cross - 2 * within  # Last entry is in units of one quarter.


def endpoint_summary(values, allowed):
    possible = [tuple(allowed) if v is None else (v,) for v in values]
    differences = [disagreement(v)[2] for v in product(*possible)]
    cross, within, difference = (None, None, None) if None in values else disagreement(values)
    return {"cross": cross, "within": within, "difference_quarters": difference,
            "bound_quarters": [min(differences), max(differences)]}


def summarize(rows, blocks, scores):
    by_call = {(r["parent_id"], r["assignment"]): r for r in rows}
    cells = {arm: Counter() for arm in ("none", "shared")}
    histories, missing = [], Counter()
    for bid, block in sorted(blocks.items()):
        source_values = []
        for assignment in ASSIGNMENTS:
            r = by_call[bid, assignment]
            ok = r["status"] == "OK"
            source_values.append(r["after_variant"] if ok else None)
            g = cells[assignment[:-1]]
            state = "preservation" if block["before_correct"] else "repair"
            g[state + "_assigned"] += 1
            g[state + "_scored"] += ok
            g[state + "_passed"] += ok and r["after_correct"]
            if not ok:
                missing[r["status"]] += 1
        grade_values = [None if v is None else scores[v] for v in source_values]
        menu = set(block["options"].values())
        histories.append({"id": bid, "model": block["model"], "before": block["before_variant"],
                          "choices": source_values, "source": endpoint_summary(source_values, menu),
                          "function": endpoint_summary(grade_values, {scores[k] for k in menu})})
    estimates = {}
    for e in ENDPOINTS:
        completed = [h[e] for h in histories if h[e]["difference_quarters"] is not None]
        total = len(completed)
        estimates[e] = {"complete": total, "scheduled": len(histories),
                        "cross_mean": sum(h["cross"] for h in completed) / (4*total) if total else None,
                        "within_mean": sum(h["within"] for h in completed) / (2*total) if total else None,
                        "complete_mean": sum(h["difference_quarters"] for h in completed) / (4*total) if total else None,
                        "scheduled_bounds": [sum(h[e]["bound_quarters"][i] for h in histories) / (4*len(histories))
                                             for i in (0, 1)]}
    return {"estimates": estimates, "cells": cells, "histories": histories, "missing": dict(missing)}


def number(v):
    return "—" if v is None else f"{v:.5f}".rstrip("0").rstrip(".")


def report(s):
    lines = ["# Does the display change choices beyond ordinary repeat variation?", "",
             "Each of sixteen archived CPython histories received two fresh draws with no new output and two draws "
             "with the same nonrevealing execution display. All four assignments retained the same model, menu and history.", "",
             "| Endpoint | Complete / assigned histories | Cross-arm disagreement | Within-arm disagreement | Cross minus within | Bounds across all assigned histories |",
             "| --- | ---: | ---: | ---: | ---: | --- |"]
    for e, g in s["estimates"].items():
        lo, hi = g["scheduled_bounds"]
        lines.append(f"| {e} | {g['complete']} / {g['scheduled']} | {number(g['cross_mean'])} | {number(g['within_mean'])} "
                     f"| {number(g['complete_mean'])} | [{number(lo)}, {number(hi)}] |")
    lines += ["", "Cross and within averages shown in the table use the same complete histories. Each history "
              "contributes four cross-arm comparisons and two within-arm comparisons. A history receives equal weight "
              "in the final estimate. The scheduled bounds allow every missing response to select any offered source and "
              "use the exact attainable extremes within each history, separately for each endpoint.", "",
              "## Repair and preservation", "",
              "| Display | Repaired / scored / assigned | Preserved / scored / assigned |",
              "| --- | ---: | ---: |"]
    for arm, g in s["cells"].items():
        triples = [" / ".join(str(g[state + k]) for k in ("_passed", "_scored", "_assigned")) for state in ("repair", "preservation")]
        lines.append(f"| {arm} | {triples[0]} | {triples[1]} |")
    lines += ["", "There are two planned native replies per history and display. The four defective histories repeat "
              "one Luna edit; the twelve working histories cover the other starting implementation choices.", "",
              "Missing calls: " + (", ".join(f"{k}={v}" for k, v in sorted(s["missing"].items())) or "none") + ".", "",
              "## Every history", "",
              "| Archived history | Start | None 1 / 2 | Shared 1 / 2 | Difference in source disagreement | Difference in functional disagreement |",
              "| --- | --- | --- | --- | ---: | ---: |"]
    for h in s["histories"]:
        replies = [v or "—" for v in h["choices"]]
        d = [number(h[e]["difference_quarters"] / 4) if h[e]["difference_quarters"] is not None else "—" for e in ENDPOINTS]
        lines.append(f"| {h['id']} | {h['before']} | {replies[0]} / {replies[1]} | {replies[2]} / {replies[3]} | {d[0]} | {d[1]} |")
    lines += ["", "If the two fresh calls in each condition are independent draws from stationary categorical "
              "distributions p and q and independent across conditions, the expected difference for the source "
              "equals half the sum of squared probability differences. For binary held-out correctness it equals "
              "the squared difference in pass probabilities. An individual sample estimate can be negative. Multiple "
              "pair comparisons reuse responses, so treating the six comparisons as independent observations would "
              "overstate precision. This measurement cannot establish an effect across tasks or equivalence of the distributions.", "",
              "Offline recount: `python3 -I analysis/replicate_display_report.py analysis/replicate_display_20261128 --check`.", ""]
    return "\n".join(lines)


def verify(directory=DEFAULT):
    directory = Path(directory)
    data = json.loads((directory / "results.json").read_bytes())
    plan = bound_json(directory / "plan.json", data["plan_sha256"])
    def parent_file(name):
        path = f"analysis/{PARENT}/{name}.json"
        return bound_json(directory.parent / PARENT / f"{name}.json", plan["source_sha256"][path])
    parent = parent_file("plan")
    cal = parent_file("calibration")
    blocks, scores = verify_inputs(plan, parent, cal, data)
    return summarize(data["rows"], blocks, scores)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=DEFAULT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = report(verify(args.directory))
    if args.check:
        if (args.directory / "comparison.md").read_text() != text:
            raise SystemExit("Stored report differs from recount")
        print("Repeated display comparison verified.")
    else:
        print(text, end="")

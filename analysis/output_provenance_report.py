"""Offline matched recount of the experiment varying the caption of identical values."""
import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re

DEFAULT = Path(__file__).resolve().parent / "output_provenance_20261128"
LABELS = ("none", "anonymous", "named", "required")
TARGETS = ("A", "B")
MODELS = ("gpt-6-luna", "gpt-6.2-astra", "gpt-6.2-sol", "gpt-6.1-terra")
TASKS = ("range", "dedup", "quotient", "moving_sum", "calendar", "distance", "flatten", "fields")
STATES = ("repair", "preservation")


def oracle(task, x):
    if task == "range":
        left, right, value = x
        return left <= value <= right, left <= value < right
    if task == "dedup":
        return sorted(set(x), key=x.index), sorted(set(x), key=lambda n: -x[::-1].index(n))
    if task == "quotient":
        return divmod(x, 4)[0], int(x / 4)
    if task == "moving_sum":
        prefix = [sum(x[:i]) for i in range(len(x)+1)]
        windows = [prefix[i] - prefix[max(0, i-3)] for i in range(1, len(prefix))]
        return windows, windows[2:]
    if task == "calendar":
        return x, (x + 1) % 7
    if task == "distance":
        a, b = x
        common = sum(a[i] != b[i] for i in range(min(len(a), len(b))))
        return common + abs(len(a)-len(b)), common
    if task == "flatten":
        nr, nc = len(x), len(x[0])
        return [x[i][j] for i in range(nr) for j in range(nc)], [x[i][j] for j in range(nc) for i in range(nr)]
    if task == "fields":
        fields = x.split(",")
        return fields, list(filter(len, fields))
    raise ValueError(f"Unknown task {task}")


def verify_calibration(cal):
    if set(cal) != set(TASKS):
        raise ValueError("Task catalogue differs")
    for task, data in cal.items():
        held, shown = data["held_out"], data["diagnostic"]
        if len(held) != 6 or shown[1] == shown[2] or len({json.dumps(r[0]) for r in [shown, *held]}) != 7:
            raise ValueError(f"Incorrect probe separation or repeated inputs in {task}")
        for x, a, b in [shown, *held]:
            if list(oracle(task, x)) != [a, b]:
                raise ValueError(f"Reference differs from supplied answer on {task}/{x}")
        for i, source in enumerate(TARGETS):
            for j, target in enumerate(TARGETS):
                scores = [oracle(task, r[0])[i] == r[j+1] for r in held]
                recorded = data["checks"][source][target]
                if recorded != scores or any(type(v) is not bool for v in recorded) or all(scores) != (source == target):
                    raise ValueError(f"Invalid held-out scores for {task}/{source}/{target}")


def validate(plan, cal, results):
    verify_calibration(cal)
    blocks = plan["blocks"]
    if len(blocks) != 64 or len({b["id"] for b in blocks}) != 64 or {
            (b["model"], b["task"], b["start"]) for b in blocks} != set(product(MODELS, TASKS, TARGETS)):
        raise ValueError("Invalid blocked roster")
    if plan.get("eligible_for_main_analysis") is not False or results.get("eligible_for_main_analysis") is not False:
        raise ValueError("Exploratory status differs")
    expected = {}
    for block in blocks:
        signatures = set()
        calls = block["calls"]
        if len(calls) != 7 or len({c["prompt_sha256"] for c in calls}) != 7:
            raise ValueError("Expected seven distinct native calls in each block")
        for c in calls:
            key = block["id"], c["id"]
            label, value = c["label"], c["value_contract"]
            targets = [value] if label == "required" else list(TARGETS)
            if key in expected or c["targets"] != targets or re.fullmatch(r"[0-9a-f]{64}", c["prompt_sha256"]) is None:
                raise ValueError("Unexpected cell ID, target assignments, or prompt hash")
            expected[key] = block, c
            signatures.add((label, value))
        if signatures != {("none", None), *product(LABELS[1:], TARGETS)}:
            raise ValueError("Missing or repeated label/value assignment")
    rows = results["rows"]
    if len(rows) != len(expected) or {(r["block"], r["call_id"]) for r in rows} != set(expected):
        raise ValueError("Missing or repeated scheduled call")
    for r in rows:
        b, c = expected[r["block"], r["call_id"]]
        if any(r[k] != b[k] for k in ("task", "start", "model")) or any(
                r[k] != c[k] for k in ("label", "value_contract", "targets", "prompt_sha256")):
            raise ValueError("Public assignment or prompt changed")
        if r["status"] != "OK":
            if not r["status"] or r["choice"] is not None or r["after"] is not None or r["assessments"] != []:
                raise ValueError("Missing choice has recorded grades")
            continue
        if r["choice"] not in ("keep", "switch"):
            raise ValueError("Action missing from menu")
        start = r["start"]
        chosen = start if r["choice"] == "keep" else {"A": "B", "B": "A"}[start]
        grades = [{"target": t, "before_correct": all(cal[b["task"]]["checks"][start][t]),
                   "after_correct": all(cal[b["task"]]["checks"][chosen][t])} for t in r["targets"]]
        if (r["after"] != chosen or r["assessments"] != grades or any(
                type(a[k]) is not bool for a in r["assessments"] for k in ("before_correct", "after_correct"))):
            raise ValueError("Choice/assessment disagreement")


def pair_pattern(a, b, start):
    if a is None or b is None:
        return "incomplete", 0, int(a in (None, "A") and b in (None, "B"))
    if (a, b) == ("A", "B"):
        return "both_aligned", 1, 1
    if (a, b) == ("B", "A"):
        return "both_opposite", 0, 0
    return ("always_keep" if a == start else "always_switch"), 0, 0


def summarize(rows):
    cells = {label: Counter() for label in LABELS}
    missing = Counter()
    choices, info = {}, {}
    for row in rows:
        bid, label = row["block"], row["label"]
        info[bid] = (row["model"], row["task"], row["start"])
        choices[bid, label, row["value_contract"]] = row["after"]
        group = cells[label]
        ok = row["status"] == "OK"
        group["scheduled"] += 1
        group["valid"] += ok
        group["kept"] += ok and row["choice"] == "keep"
        if not ok:
            missing[row["status"]] += 1
        for target in row["targets"]:
            state = "preservation" if target == row["start"] else "repair"
            group[state + "_scheduled"] += 1
            group[state + "_scored"] += ok
            group[state + "_passed"] += ok and row["after"] == target
    tracking = {label: Counter() for label in LABELS[1:]}
    transitions = {label: Counter() for label in ("anonymous", "named")}
    by_model = {m: {label: Counter() for label in LABELS[1:]} for m in MODELS}
    records = []
    for bid, (model, task, start) in sorted(info.items()):
        patterns, selections = {}, {}
        for label in LABELS[1:]:
            a, b = (choices[bid, label, value] for value in TARGETS)
            selections[label] = [a, b]
            pattern, lo, hi = pair_pattern(a, b, start)
            patterns[label] = pattern, lo, hi
            for record in (tracking[label], by_model[model][label]):
                record[pattern] += 1
                record["complete"] += pattern != "incomplete"
                record["scheduled"] += 1
                record["min"] += lo
                record["max"] += hi
                # Difference of indicators for choosing A at displayed A and at displayed B.
                record["signed_min"] += int(a == "A") - int(b in ("A", None))
                record["signed_max"] += int(a in ("A", None)) - int(b == "A")
                if a is not None and b is not None:
                    record["signed_observed"] += int(a == "A") - int(b == "A")
        for label in transitions:
            first, second = patterns[label], patterns["required"]
            stats = transitions[label]
            stats["min_gain"] += second[1] - first[2]
            stats["max_gain"] += second[2] - first[1]
            stats["scheduled"] += 1
            if "incomplete" not in (first[0], second[0]):
                stats["complete"] += 1
                stats["gained"] += second[1] > first[1]
                stats["lost"] += second[1] < first[1]
                stats["both_track"] += second[1] == first[1] == 1
                stats["neither_tracks"] += second[1] == first[1] == 0
        records.append({"model": model, "task": task, "start": start, "none": choices[bid, "none", None], **selections})
    return {"blocks": len(info), "cells": cells, "tracking": tracking, "contrasts": transitions,
            "by_model": by_model, "blocks_detail": records, "missing": dict(missing)}


def report(s):
    lines = ["# Choosing code after an identical value is given a different source", "",
             "Each task supplies two programs and a single input where their outputs differ. Under each caption "
             "a matched block displays each possible output once. Tracking means choosing its producing program "
             "on both calls. Under the required caption a tracking block satisfies both disclosed target rules. "
             "Under the anonymous or named execution caption it follows both observed values without evidence "
             "about which installation convention is required.", "",
             "| Caption | Both values tracked / complete blocks | Both opposed | Always kept | Always switched | Bounds over assigned blocks |",
             "| --- | ---: | ---: | ---: | ---: | --- |"]
    for label in LABELS[1:]:
        g = s["tracking"][label]
        lines.append(f"| {label} | {g['both_aligned']} / {g['complete']} | {g['both_opposite']} | {g['always_keep']} | "
                     f"{g['always_switch']} | [{g['min']}, {g['max']}] |")
    lines += ["", "The following secondary contrast was added after the protocol was frozen and before reserve "
              "responses were examined. It subtracts the number of blocks choosing the implementation opposite both "
              "displayed values from the number following both values. Constant choices contribute zero. Dividing by "
              "the complete-block denominator gives the difference in the fraction choosing A upon displaying A's value "
              "versus displaying B's value. Under independent, stationary value-insensitive choices with probability p "
              "of selecting A, both-follow and both-oppose each have probability p(1−p), so their expected difference is zero.", "",
              "| Caption | Aligned minus opposed / complete blocks | Bounds on signed count over all assignments |",
              "| --- | ---: | ---: |"]
    for label in LABELS[1:]:
        g = s["tracking"][label]
        lines.append(f"| {label} | {g['signed_observed']:+} / {g['complete']} | [{g['signed_min']:+}, {g['signed_max']:+}] |")
    lines += ["", "## Matched change in tracking", "",
              "| First caption | Second caption | Complete / assigned | Only second tracks | Only first tracks | Both track | Neither tracks | Bounds on net gain |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for label, g in s["contrasts"].items():
        lines.append(f"| {label} | required | {g['complete']} / {g['scheduled']} | {g['gained']} | {g['lost']} | "
                     f"{g['both_track']} | {g['neither_tracks']} | [{g['min_gain']:+}, {g['max_gain']:+}] |")
    lines += ["", "## Repair, preservation and calls", "",
              "| Caption | Valid / scheduled calls | Repaired / scored / assigned | Preserved / scored / assigned |",
              "| --- | ---: | ---: | ---: |"]
    for label, g in s["cells"].items():
        triples = [" / ".join(str(g[state + k]) for k in ("_passed", "_scored", "_scheduled")) for state in STATES]
        lines.append(f"| {label} | {g['valid']} / {g['scheduled']} | {triples[0]} | {triples[1]} |")
    n = sum(g["valid"] for g in s["cells"].values())
    a = sum(g[t + "_scored"] for t in STATES for g in s["cells"].values())
    lines += ["", f"{n} valid native calls contribute {a} target assessments. Only the required caption identifies the target. "
              "Under all other captions the same decision is assessed under both alternatives, so exactly one target assessment passes "
              "per valid call. This half-correct rate is imposed by the design. Assigning a value to the current or alternative candidate in the "
              "named caption supplies additional information beyond identifying the value as observed.", "",
              "Missing calls: " + (", ".join(f"{k}={v}" for k, v in sorted(s["missing"].items())) or "none") + ".", "",
              "## Tracking by requested configuration", "",
              "| Model | Task panel | Anonymous | Named | Required |", "| --- | ---: | ---: | ---: | ---: |"]
    for m, values in s["by_model"].items():
        tracking = [f"{values[label]['both_aligned']} / {values[label]['complete']}" for label in LABELS[1:]]
        lines.append("| " + " | ".join([m, "8 tasks, 2 starts", *tracking]) + " |")
    lines += ["", "## Selections in every assigned block", "",
              "Pairs give the selected implementation for displayed value A followed by displayed value B. "
              "A dash indicates a missing decision. Values are scenario-specific: A and B denote different conventions for each task.", "",
              "| Model | Task | Start | No output | Anonymous | Named | Required |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for block in s["blocks_detail"]:
        pairs = [" / ".join(v or "—" for v in block[label]) for label in LABELS[1:]]
        lines.append("| " + " | ".join([block["model"], block["task"], block["start"], block["none"] or "—", *pairs]) + " |")
    lines += ["", "The primary comparison is required versus anonymous in the same model, task and start. "
              "A single choice per prompt and eight authored mechanisms limit inference about other tasks and systems. "
              "Unobserved blocks remain in the scheduled denominator.", "",
              "Offline recount: `python3 -I analysis/output_provenance_report.py analysis/output_provenance_20261128 --check`.", ""]
    return "\n".join(lines)


def verify(directory=DEFAULT):
    directory = Path(directory)
    plan_bytes, cal_bytes = [(directory / name).read_bytes() for name in ("plan.json", "calibration.json")]
    plan, cal = json.loads(plan_bytes), json.loads(cal_bytes)
    results = json.loads((directory / "results.json").read_bytes())
    if results["plan_sha256"] != sha256(plan_bytes).hexdigest() or plan["calibration_sha256"] != sha256(cal_bytes).hexdigest():
        raise ValueError("Source or calibration digest changed")
    validate(plan, cal, results)
    return summarize(results["rows"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=DEFAULT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = report(verify(args.directory))
    if args.check:
        if (args.directory / "comparison.md").read_text() != result:
            raise SystemExit("Stored report differs from public recount")
        print("Output provenance report verified.")
    else:
        print(result, end="")

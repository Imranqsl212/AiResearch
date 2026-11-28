"""Recount the paired display experiment on seven implementations from public data."""
import argparse
import ast
from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

ARMS = ("none", "shared", "revealing")
LABEL = {"none": "No new output", "shared": "Shared", "revealing": "Revealing"}
MODELS = ("gpt-6-luna", "gpt-6.2-astra")
PROJECTS = ("cpython", "dateutil")
PRIOR = "analysis/checker_timing_20261126/calibration.json"
DEFAULT = Path(__file__).resolve().parent / "cross_project_display_20261128"


def fraction(n, d):
    return f"{n}/{d}" if d else "—"


def bound_json(file, expected):
    raw = file.read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError(f"Digest mismatch for {file.name}")
    return json.loads(raw)


def reference_output(project, literal):
    if project == "dateutil":
        value = datetime.fromisoformat(literal)
        return f"wall time {value.replace(tzinfo=None).isoformat()}, UTC offset {int(value.utcoffset().total_seconds())} seconds"
    return repr(dict(sorted(ast.literal_eval(literal).items())))


def grades(calibration, original):
    """Reconstruct each score from the original held-out observations."""
    scores = {}
    if set(calibration["projects"]) != set(PROJECTS):
        raise ValueError("Expected both original projects")
    for project, card in calibration["projects"].items():
        variants = card["variants"]
        ancestors = original[project]["variants"]
        if set(variants) != set(ancestors):
            raise ValueError(f"Variant set changed for {project}")
        ref = {arm: reference_output(project, card["inputs"][arm]) for arm in ("shared", "revealing")}
        if card["reference_outputs"] != ref or variants[card["reference_variant"]]["outputs"] != ref:
            raise ValueError("Reference disagrees with independent evaluation")
        for name, variant in variants.items():
            historic = ancestors[name]
            details = historic["details"]
            if project == "dateutil":
                held = details["hidden_inputs"]
                checks = [c["actual"] == c["expected"] for c in held]
                recorded = [c["pass"] for c in held]
                parent = original[project]["provenance"]["parent"]
            else:
                held = details["held_out"]
                checks = [c["bindings_preserved"] and c["comparable_keys_sorted"] is not False for c in held]
                recorded = [c["passed"] for c in held]
                parent = details["parent"]
            correct = all(checks)
            if (len(checks) != 6 or recorded != checks or variant["checks"] != held
                    or historic["snippet"] != variant["snippet"] or parent != card["parent_commit"]
                    or historic["correct"] is not correct or variant["correct"] is not correct):
                raise ValueError(f"Source or functional grade changed for {project}/{name}")
            if (variant["outputs"]["shared"] != ref["shared"]
                    or (variant["outputs"]["revealing"] == ref["revealing"]) != correct):
                raise ValueError(f"Incorrect probe discrimination for {project}/{name}")
            scores[project, name] = correct
    if len(scores) != 7 or sum(scores.values()) != 3:
        raise ValueError("Expected seven original implementations, three working")
    return scores


def match_rows(plan, results, scores):
    blocks = plan["blocks"]
    expected = {(p, v, m) for p, v in scores for m in MODELS}
    scheduled = {(b["project"], b["before_variant"], b["model"]) for b in blocks}
    by_id = {b["parent_id"]: b for b in blocks}
    if len(by_id) != len(blocks) or len(blocks) != len(expected) or scheduled != expected:
        raise ValueError("Expected one block per project, implementation and model")
    matched = {key: {} for key in by_id}
    for b in blocks:
        project, current = b["project"], b["before_variant"]
        menu = list(b["options"].values())
        if (sorted(b["order"]) != sorted(ARMS) or set(b["prompt_sha256"]) != set(ARMS)
                or set(menu) != {v for p, v in scores if p == project} or len(menu) != len(set(menu))
                or b["base_prompt_sha256"] != b["prompt_sha256"]["none"]
                or b["history_sha256"] != b["base_prompt_sha256"] or scores[project, current] is not b["before_correct"]):
            raise ValueError(f"Invalid block {b['parent_id']}")
    for r in results["rows"]:
        key, arm = r["parent_id"], r["arm"]
        if key not in by_id or arm not in ARMS or arm in matched[key]:
            raise ValueError("Unknown or duplicate response")
        b = by_id[key]
        for field in ("project", "model", "before_variant", "before_correct", "history_sha256", "base_prompt_sha256"):
            if r[field] != b[field] or type(r[field]) is not type(b[field]):
                raise ValueError(f"{field} differs for {key}/{arm}")
        if r["probe"] != arm or r["prompt_sha256"] != b["prompt_sha256"][arm]:
            raise ValueError(f"Unexpected prompt for {key}/{arm}")
        current, choice = b["before_variant"], r["choice"]
        if r["status"] == "OK":
            if choice == "keep":
                selected = current
            elif choice in b["options"] and b["options"][choice] != current:
                selected = b["options"][choice]
            else:
                raise ValueError(f"Unknown choice for {key}/{arm}")
            if selected != r["after_variant"] or scores[b["project"], selected] is not r["after_correct"]:
                raise ValueError(f"Final implementation or score disagrees for {key}/{arm}")
        elif not r["status"] or any(r[f] is not None for f in ("choice", "after_variant", "after_correct")):
            raise ValueError(f"Unavailable response has a score for {key}/{arm}")
        matched[key][arm] = r
    if any(set(arms) != set(ARMS) for arms in matched.values()):
        raise ValueError("Absent scheduled row, including the explicit status of each missing call")
    return matched


def cell(row):
    if row["status"] != "OK":
        return row["status"]
    return f"{row['after_variant']} ({'pass' if row['after_correct'] else 'fail'})"


def row_line(cells):
    return "| " + " | ".join(str(x) for x in cells) + " |"


def render(matched, calibration):
    rows = [r for arms in matched.values() for r in arms.values()]
    lines = ["# Showing an execution before a single edit on two Python tasks", "",
             "The seven original implementations comprise four faulty and three working sources on two tasks. "
             "Both model configurations saw each source in all three conditions. The fourteen model/source "
             "blocks therefore contribute eight faulty and six working starts per condition. Each assigned "
             "call had a single decision from a finite menu. Each project used its original six held-out checks.", "",
             "## Inputs and outputs", ""]
    for project in PROJECTS:
        inputs = calibration["projects"][project]["inputs"]
        lines.append(f"- {project} received `{inputs['shared']}` in the shared-output condition "
                     f"and `{inputs['revealing']}` in the revealing condition.")
    lines += ["", "Every implementation in each project gave the reference answer on the shared input. On the "
              "revealing input, each of the four faulty sources differed from its reference, and each of the "
              "three working sources agreed.", "", "## Repair and preservation", "",
              "A new implementation that still passes counts as preservation. Fractions use scored responses "
              "within the corresponding starting stratum. Scored/scheduled reports overall response coverage.", "",
              "| Project | Model | Display | Scored/scheduled | Defects repaired | Working states preserved | Working states damaged | Rewritten and still working |",
              "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    groups = [(None, None)] + [(project, model) for project in PROJECTS for model in MODELS]
    for project, model in groups:
        for arm in ARMS:
            group = [r for r in rows if r["arm"] == arm and
                     (project is None or (r["project"], r["model"]) == (project, model))]
            valid = [r for r in group if r["status"] == "OK"]
            bad = [r for r in valid if not r["before_correct"]]
            good = [r for r in valid if r["before_correct"]]
            kept = sum(r["after_correct"] for r in good)
            rewrites = sum(r["after_correct"] and r["before_variant"] != r["after_variant"] for r in good)
            lines.append(row_line([project or "Both", model or "Both", LABEL[arm], fraction(len(valid), len(group)),
                                   fraction(sum(r["after_correct"] for r in bad), len(bad)), fraction(kept, len(good)),
                                   fraction(len(good) - kept, len(good)), fraction(rewrites, len(good))]))
    missing = Counter(r["status"] for r in rows if r["status"] != "OK")
    lines += ["", "Missing outcomes: " + (", ".join(f"{k} ({v})" for k, v in sorted(missing.items()))
                                           if missing else "none") + ".", "", "## Matched contrasts", "",
              "The planned primary contrast compares revealing with no display in faulty-start blocks. "
              "Both calls in each pair began with the same model and source. Only complete pairs are scored. "
              "Different implementations can yield the same held-out result.", "",
              "| First vs second display | Start | Complete/scheduled | Both pass | Second alone passes | First alone passes | Neither passes | Different final source |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for first, second in (("none", "revealing"), ("none", "shared"), ("shared", "revealing")):
        for correct in (False, True):
            group = [arms for arms in matched.values() if arms[first]["before_correct"] == correct]
            complete = [(arms[first], arms[second]) for arms in group if arms[first]["status"] == arms[second]["status"] == "OK"]
            joint = Counter((a["after_correct"], b["after_correct"]) for a, b in complete)
            changed = sum(a["after_variant"] != b["after_variant"] for a, b in complete)
            lines.append(row_line([f"{LABEL[first]} vs {LABEL[second]}", "Working" if correct else "Faulty",
                                   fraction(len(complete), len(group)),
                                   *(joint[k] for k in ((True, True), (False, True), (True, False), (False, False))),
                                   fraction(changed, len(complete))]))
    lines += ["", "## Outcomes for every model and starting source", "",
              "A source ID belongs to its project. Reading across a row shows the actual implementations "
              "behind both concordant and discordant grades.", "",
              "| Project | Model | Starting source | No new output | Shared output | Revealing output |",
              "| --- | --- | --- | --- | --- | --- |"]
    for arms in sorted(matched.values(), key=lambda x: (x["none"]["project"], x["none"]["model"], x["none"]["before_variant"])):
        r = arms["none"]
        start = f"{r['before_variant']} ({'pass' if r['before_correct'] else 'fail'})"
        lines.append(row_line([r["project"], r["model"], start, *(cell(arms[a]) for a in ARMS)]))
    lines += ["", "These are exploratory, one-call choices per model, source and condition. The seven implementations "
              "belong to two previously selected tasks. The two configurations and repeated displays do not supply "
              "additional projects or establish differences between model populations.", "",
              "From the repository root run `python3 -B -m analysis.cross_project_display_report --check`.", "",
              "[Assignment](plan.json) · [Functional calibration](calibration.json) · [Decision ledger](results.json)", ""]
    return "\n".join(lines)


def replay(directory=DEFAULT):
    directory = Path(directory)
    results = json.loads((directory / "results.json").read_bytes())
    plan = bound_json(directory / "plan.json", results["plan_sha256"])
    calibration = bound_json(directory / "calibration.json", plan["calibration_sha256"])
    original = bound_json(directory.parent / "checker_timing_20261126" / "calibration.json", plan["source_sha256"][PRIOR])
    if results.get("eligible_for_main_analysis") is not False or plan.get("eligible_for_main_analysis") is not False:
        raise ValueError("Unexpected exploratory status")
    return render(match_rows(plan, results, grades(calibration, original)), calibration)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = args.directory / "comparison.md"
    report = replay(args.directory).encode()
    if args.check or target.exists():
        if target.read_bytes() != report:
            raise SystemExit("Stored report differs from public recount")
    else:
        target.write_bytes(report)
    print(f"Verified {target}")

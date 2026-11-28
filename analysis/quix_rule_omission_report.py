"""Compare the free-expression target reversals with and without named conventions."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from analysis import quix_contract_reversal_report as named

DEFAULT = Path(__file__).resolve().parent / "quix_rule_omission_20261128"
TARGETS = named.TARGETS


def omit_rule_lines(original, block, calibration):
    lines = original.splitlines(keepends=True)
    rules = calibration[block["task"]]["rules"]
    descriptions = [f"Convention {i}: {rules[rule]}.\n".encode() for i, rule in enumerate(block["rule_order"], 1)]
    if lines[1:3] != descriptions or not lines[0].startswith(b"This installation uses exactly one of two documented conventions."):
        raise ValueError("The two written conventions are not in their frozen positions")
    return b"".join([lines[0], *lines[3:]])


def validate(plan, named_plan, cal, sources, rows):
    blocks = {b["id"]: b for b in plan["blocks"]}
    originals = {b["id"]: b for b in named_plan["blocks"]}
    if len(blocks) != 16 or list(blocks) != list(originals) or len(plan["blocks"]) != 16:
        raise ValueError("Omission schedule differs from named-rule roster/order")
    expected = {(bid, t) for bid in blocks for t in TARGETS}
    if len(rows) != 32 or {(r["block"], r["arm"]) for r in rows} != expected:
        raise ValueError("Each of 32 scheduled responses requires a status")
    for b in blocks.values():
        pair = originals[b["id"]]
        if (any(b[k] != pair[k] for k in ("model","start","task","wave","rule_order"))
                or b["order"] != [a for a in pair["order"] if a in TARGETS]):
            raise ValueError("Assignment changed from parent")
    for r in rows:
        b, t = blocks[r["block"]], r["arm"]
        original = named.prompt(b, t, sources, cal)
        reduced = omit_rule_lines(original, b, cal)
        if (sha256(original).hexdigest() != originals[b["id"]]["prompt_sha256"][t]
                or sha256(reduced).hexdigest() != b["prompt_sha256"][t] or r["prompt_sha256"] != b["prompt_sha256"][t]
                or any(r[k] != b[k] for k in ("model","wave","task","start"))):
            raise ValueError("Omission differs from dropping only the two frozen convention lines")
        if r["status"] != "OK":
            if not r["status"] or any(r[k] is not None for k in ("action","expression","passed_counts","implements")):
                raise ValueError("Missing response has an assigned grade")
            continue
        if r["action"] not in ("keep","replace") or (
                r["action"] == "keep" and r["expression"] != cal[r["task"]]["starts"][r["start"]]["expression"]):
            raise ValueError("Choice or kept expression differs")
        if named.grades(r["task"],r["expression"],cal) != (r["passed_counts"],r["implements"]):
            raise ValueError("Final expression does not reproduce the decision grade")


def pattern(runs):
    choices = [r["implements"] if r["status"] == "OK" else None for r in runs]
    if None in choices:
        could_track = all(v in (None, target) for v,target in zip(choices,TARGETS))
        return "incomplete", 0, int(could_track)
    if choices == list(TARGETS):
        return "tracks", 1, 1
    if choices == list(reversed(TARGETS)):
        return "reversed", 0, 0
    if "neither" in choices:
        return "includes_neither", 0, 0
    return "always_" + choices[0], 0, 0


def matched(first, second):
    """First and second are triples (complete, lower success, upper success)."""
    result = Counter()
    for (complete_a, lo_a, hi_a), (complete_b, lo_b, hi_b) in zip(first,second):
        result["scheduled"] += 1
        result["min_gain"] += lo_b - hi_a
        result["max_gain"] += hi_b - lo_a
        if complete_a and complete_b:
            result["complete"] += 1
            result["both"] += lo_a == lo_b == 1
            result["only_named"] += lo_a > lo_b
            result["only_omitted"] += lo_b > lo_a
            result["neither"] += lo_a == lo_b == 0
    return result


def summarize(original_rows, omitted_rows, cal):
    indexed = {}
    groups = {}
    for label, rows in (("named",original_rows),("omitted",omitted_rows)):
        entries = {(r["block"],r["arm"]): r for r in rows if r["arm"] in TARGETS}
        cohort = {"targets": {t:Counter() for t in TARGETS},"tracking":Counter(),"statuses":Counter()}
        for (bid,t), r in entries.items():
            s = cohort["targets"][t]
            state = "preserve" if cal[r["task"]]["starts"][r["start"]]["implements"] == t else "repair"
            cohort["statuses"][r["status"]] += 1
            s["scheduled"] += 1
            s[state + "_scheduled"] += 1
            if r["status"] == "OK":
                s["scored"] += 1
                s[state + "_scored"] += 1
                s[state + "_passed"] += r["implements"] == t
                s[r["implements"]] += 1
                witness = cal[r["task"]]["example"]
                fits = named.base.grade(r["task"], r["expression"], [
                    {"input": witness["input"], "expected": witness[t]}
                ])[0]
                s["witness_and_held"] += fits and r["implements"] == t
                s["witness_only"] += fits and r["implements"] != t
                s["held_only"] += not fits and r["implements"] == t
                s["neither_endpoint"] += not fits and r["implements"] != t
        indexed[label] = entries
        groups[label] = cohort
    block_ids = sorted({k[0] for k in indexed["named"]})
    tracks, success = {"named":[],"omitted":[]}, {t:{"named":[],"omitted":[]} for t in TARGETS}
    details = []
    for bid in block_ids:
        detail = {"block": bid}
        for label,entries in indexed.items():
            pair = [entries[bid,t] for t in TARGETS]
            result, lo, hi = pattern(pair)
            tcounts = groups[label]["tracking"]
            tcounts[result] += 1
            tcounts["complete"] += result != "incomplete"
            tcounts["scheduled"] += 1
            tcounts["min"] += lo
            tcounts["max"] += hi
            tracks[label].append((result != "incomplete",lo,hi))
            detail[label] = [r["implements"] if r["status"]=="OK" else r["status"] for r in pair]
            for r in pair:
                valid = r["status"] == "OK"
                win = r["implements"] == r["arm"]
                success[r["arm"]][label].append((valid, int(valid and win), int(not valid or win)))
        details.append(detail)
    contrasts = {t:matched(values["named"], values["omitted"]) for t,values in success.items()}
    contrasts["both_targets"] = matched(tracks["named"],tracks["omitted"])
    return {"groups":groups,"contrasts":contrasts,"blocks":details}


def report(s):
    lines = ["# What changes when the contract descriptions are removed?", "",
             "Sixteen original QuixBugs model–task–start blocks receive both opposing target examples again. "
             "The two complete descriptions of the conventions were deleted; the source, localized expression, "
             "other instructions and displayed input/output for each target were held fixed. This later cohort "
             "uses independent fresh responses. A single input/output example can support functions outside both "
             "reference classes. Each classification below concerns the two fixed finite reference domains.", "",
             "| Rule descriptions | Tracks both targets / complete blocks | Both reversed | Always upstream | Always alternative | At least one neither | Bounds across all 16 blocks |",
             "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for label, group in s["groups"].items():
        v = group["tracking"]
        lines.append(f"| {label} | {v['tracks']} / {v['complete']} | {v['reversed']} | {v['always_upstream']} | "
                     f"{v['always_alternative']} | {v['includes_neither']} | [{v['min']}, {v['max']}] |")
    lines += ["", "## Matched successes", "",
              "Only named and only omitted count opposite discordances. Bounds give the net number of successes "
              "under omission minus the number when rules were named over the scheduled comparisons. The primary "
              "endpoint requires success under both opposite target outputs in the same block.", "",
              "| Endpoint | Complete / 16 | Both succeed | Only named | Only omitted | Neither succeeds | Bounds on net change |",
              "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for outcome in ("both_targets",*TARGETS):
        g = s["contrasts"][outcome]
        lines.append(f"| {outcome} | {g['complete']} / {g['scheduled']} | {g['both']} | {g['only_named']} | "
                     f"{g['only_omitted']} | {g['neither']} | [{g['min_gain']:+}, {g['max_gain']:+}] |")
    lines += ["", "## Final scored implementations", "",
              "| Rule descriptions | Required target | Valid / scheduled calls | Repaired / scored / assigned | Preserved / scored / assigned | Implements upstream / alternative / neither |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    for label, group in s["groups"].items():
        for target,r in group["targets"].items():
            triples=[" / ".join(str(r[k + suffix]) for suffix in ("_passed","_scored","_scheduled")) for k in ("repair","preserve")]
            lines.append(f"| {label} | {target} | {r['scored']} / {r['scheduled']} | {triples[0]} | {triples[1]} | "
                         f"{r['upstream']} / {r['alternative']} / {r['neither']} |")
    for label, group in s["groups"].items():
        lines.append(f"\nNative statuses under {label} descriptions: " + ", ".join(f"{k}={v}" for k,v in sorted(group["statuses"].items())) + ".")
    lines += ["", "## Fit to the displayed example", "",
              "This supplementary check executes each graded expression on the single input in its prompt. "
              "The primary endpoint above uses only held-out cases. The two checks can disagree.", "",
              "| Descriptions | Required target | Pass example and held-out target | Example only | Held-out target only | Fail both |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    for label, group in s["groups"].items():
        for target, r in group["targets"].items():
            lines.append(f"| {label} | {target} | {r['witness_and_held']} | {r['witness_only']} | "
                         f"{r['held_only']} | {r['neither_endpoint']} |")
    lines += ["", "## Every matched block", "",
              "The two entries in each column are the reference behaviors implemented for the upstream and alternative "
              "displayed values, respectively. A non-OK native status is shown verbatim.", "",
              "| Model, task and source | Named descriptions | Omitted descriptions |", "| --- | --- | --- |"]
    for b in s["blocks"]:
        lines.append(f"| {b['block']} | {' / '.join(b['named'])} | {' / '.join(b['omitted'])} |")
    lines += ["", "Outcomes can also vary between repeated sampling sessions; the named and omitted cohorts were run "
              "at different times. Neither four challenge algorithms nor a single example per algorithm establish "
              "semantic generalization outside the scored domains.", "",
              "Recount offline with `python3 -B -m analysis.quix_rule_omission_report --check`.", ""]
    return "\n".join(lines)


def verify(directory=DEFAULT):
    directory = Path(directory)
    named_path = directory.parent/"quix_contract_reversal_20261128"
    upstream = directory.parent/"free_patch_20261128"
    named.verify(named_path)
    old_plan_raw = (named_path/"plan.json").read_bytes()
    old_cal_raw = (named_path/"calibration.json").read_bytes()
    plan_raw = (directory/"plan.json").read_bytes()
    old_results = (named_path/"results.json").read_bytes()
    plan = json.loads(plan_raw)
    cal = json.loads(old_cal_raw)
    data = json.loads((directory/"results.json").read_bytes())
    if (data["plan_sha256"] != sha256(plan_raw).hexdigest() or data["eligible_for_main_analysis"] is not False
            or plan["eligible_for_main_analysis"] is not False or data["named_results_sha256"] != sha256(old_results).hexdigest()):
        raise ValueError("Plan, observation binding, or exploratory status differs")
    for part, raw in (("plan.json",old_plan_raw),("calibration.json",old_cal_raw)):
        if plan["source_sha256"]["analysis/quix_contract_reversal_20261128/"+part] != sha256(raw).hexdigest():
            raise ValueError("Frozen parent differs")
    source = json.loads((upstream/"sources.json").read_bytes())
    validate(plan,json.loads(old_plan_raw),cal,source,data["rows"])
    return summarize(json.loads(old_results)["rows"], data["rows"],cal)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory",type=Path,default=DEFAULT)
    parser.add_argument("--check",action="store_true")
    args = parser.parse_args()
    text = report(verify(args.directory))
    if args.check and (args.directory/"comparison.md").read_text() != text:
        raise SystemExit("Public omission report differs")
    print(text, end="")

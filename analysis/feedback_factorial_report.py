"""Recount the matched feedback factorial from public JSON, without calling a model."""
import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re

DEFAULT = Path(__file__).resolve().parent / "feedback_factorial_20261128"
ARMS = ("none", "actual", "required", "both")
WORDINGS = ("hidden", "explicit")
TARGETS = ("A", "B")
TASKS = ("sort", "argmax", "round")
MODELS = ("gpt-6-luna", "gpt-6.2-astra")
STRATA = ("repair", "preservation")
CONTRASTS = (("actual", "both"), ("none", "required"), ("required", "both"), ("none", "actual"))


def reference_outputs(task, value):
    if task == "sort":
        return sorted(value), sorted(value, key=lambda n: f"{n:d}")
    if task == "argmax":
        tied = [i for i, n in enumerate(value) if n == max(value)]
        return tied[0], tied[-1]
    if task == "round":
        tens, ones = divmod(value, 10)
        return 10 * (tens + (ones > 5)), 10 * (tens + (ones >= 5))
    raise ValueError(f"Unrecognized task {task}")


def verify_calibration(cal):
    if set(cal) != set(TASKS):
        raise ValueError("Incorrect task roster in calibration")
    for task, data in cal.items():
        shown, held = data["shown"], data["held_out"]
        if len(shown) != 2 or len(held) != 6 or shown[0][1] != shown[0][2] or shown[1][1] == shown[1][2]:
            raise ValueError(f"Unexpected examples for {task}")
        if len({json.dumps(row[0]) for row in shown + held}) != len(shown) + len(held):
            raise ValueError("Repeated calibration input")
        for value, a, b in shown + held:
            if (a, b) != reference_outputs(task, value):
                raise ValueError(f"Reference output differs for {task} on {value!r}")
        for i, source in enumerate(TARGETS):
            for j, target in enumerate(TARGETS):
                grades = [reference_outputs(task, row[0])[i] == row[j+1] for row in held]
                actual = data["checks"][source][target]
                if actual != grades or not all(type(flag) is bool for flag in actual) or all(grades) != (i == j):
                    raise ValueError(f"Held-out grades differ for {task}/{source}/{target}")


def expected_signatures():
    for wording, arm in product(WORDINGS, ARMS):
        if wording == "hidden" and arm in ("none", "actual"):
            yield wording, arm, TARGETS
        else:
            for target in TARGETS:
                yield wording, arm, (target,)


def validate(plan, cal, results):
    verify_calibration(cal)
    blocks = plan["blocks"]
    expected_roster = set(product(MODELS, TASKS, TARGETS))
    if len(blocks) != len(expected_roster) or {(b["model"], b["task"], b["start"]) for b in blocks} != expected_roster:
        raise ValueError("Expected one block per model, task and start")
    if len({b["id"] for b in blocks}) != len(blocks):
        raise ValueError("Duplicate block ID")
    if plan.get("eligible_for_main_analysis") is not False or results.get("eligible_for_main_analysis") is not False:
        raise ValueError("Missing exploratory-study designation")
    planned = {}
    for block in blocks:
        calls = block["calls"]
        signatures = {(c["wording"], c["arm"], tuple(c["targets"])) for c in calls}
        if len(calls) != 14 or signatures != set(expected_signatures()):
            raise ValueError(f"Missing, duplicated, or unpooled assignment in {block['id']}")
        if len({c["prompt_sha256"] for c in calls}) != len(calls):
            raise ValueError("Duplicate native prompt within a block")
        for call in calls:
            key = block["id"], call["id"]
            if key in planned or re.fullmatch(r"[0-9a-f]{64}", call["prompt_sha256"]) is None:
                raise ValueError("Invalid planned call ID or prompt digest")
            planned[key] = block, call

    rows = results["rows"]
    if len(rows) != len(planned) or {(r["block"], r["call_id"]) for r in rows} != set(planned):
        raise ValueError("Missing or repeated call in public ledger")
    for row in rows:
        block, call = planned[row["block"], row["call_id"]]
        if any(block[k] != row[k] for k in ("model", "task", "start")) or any(
                call[k] != row[k] for k in ("wording", "arm", "targets", "prompt_sha256")):
            raise ValueError("Recorded assignment differs from plan")
        if row["status"] != "OK":
            if not row["status"] or row["choice"] is not None or row["after"] is not None or row["assessments"] != []:
                raise ValueError("Unavailable answer has a grade")
            continue
        action = row["choice"]
        if action not in ("keep", "switch"):
            raise ValueError("Unknown action")
        start = block["start"]
        selected = start if action == "keep" else {"A": "B", "B": "A"}[start]
        checks = cal[block["task"]]["checks"]
        expected = [{"target": target, "before_correct": all(checks[start][target]),
                     "after_correct": all(checks[selected][target])} for target in call["targets"]]
        if (row["after"] != selected or row["assessments"] != expected
                or not all(type(a[field]) is bool for a in row["assessments"] for field in ("before_correct", "after_correct"))):
            raise ValueError("Menu selection or target assessment differs from the checks")


def paired_scores(pairs):
    """Bound the sum of oriented, within-pair gains using all partially observed cells."""
    counts = Counter()
    lower, upper = 0, 0
    for first, second in pairs:
        if first is not None and second is not None:
            counts["complete"] += 1
            counts["gained"] += not first and second
            counts["lost"] += first and not second
            counts["both_pass"] += first and second
            counts["both_fail"] += not first and not second
        lower += int(second or False) - int(True if first is None else first)
        upper += int(True if second is None else second) - int(first or False)
    return {"scheduled": len(pairs), **{k: counts[k] for k in ("complete", "gained", "lost", "both_pass", "both_fail")},
            "net_bounds": [lower, upper]}


def tracking_bounds(a, b):
    """A known wrong response already rules out success on both opposite targets."""
    if a is False or b is False:
        return 0, 0
    return int(a is True and b is True), 1


def contrast_sum(grades, starts, terms):
    """Bound a pre-specified linear contrast with one target per starting stratum."""
    result = {}
    for state in STRATA:
        totals = Counter()
        for block, start in starts.items():
            target = start if state == "preservation" else {"A": "B", "B": "A"}[start]
            observed = [(sign, grades[block, word, arm, target]) for sign, word, arm in terms]
            known = sum(sign * int(score) for sign, score in observed if score is not None)
            missing = [sign for sign, score in observed if score is None]
            totals["min"] += known + sum(sign for sign in missing if sign < 0)
            totals["max"] += known + sum(sign for sign in missing if sign > 0)
            if not missing:
                totals["complete"] += 1
                totals["observed_net"] += known
        result[state] = {k: totals[k] for k in ("complete", "observed_net", "min", "max")}
    return result


def summarize(rows):
    cells = {word: {arm: Counter() for arm in ARMS} for word in WORDINGS}
    block_starts = {}
    grades = {}
    missing = Counter()
    for row in rows:
        word, arm, block = row["wording"], row["arm"], row["block"]
        counts = cells[word][arm]
        ok = row["status"] == "OK"
        counts["scheduled"] += 1
        counts["valid"] += ok
        counts["kept"] += ok and row["choice"] == "keep"
        if not ok:
            missing[row["status"]] += 1
        block_starts[block] = row["start"]
        for t in row["targets"]:
            state = "preservation" if t == row["start"] else "repair"
            score = row["after"] == t if ok else None
            grades[block, word, arm, t] = score
            counts[state + "_scheduled"] += 1
            counts[state + "_scored"] += ok
            counts[state + "_passed"] += score is True

    tracking, contrasts = {}, {}
    for word in WORDINGS:
        tracking[word] = {}
        for arm in ARMS:
            totals = Counter()
            for block in block_starts:
                a, b = [grades[block, word, arm, t] for t in TARGETS]
                complete = a is not None and b is not None
                totals["complete"] += complete
                totals["both_correct"] += complete and a and b
                totals["both_wrong"] += complete and not a and not b
                # For pooled prompts the same single action necessarily passes exactly one target,
                # including when the response is missing and either possible action is imputed.
                bound = (0, 0) if word == "hidden" and arm in ("none", "actual") else tracking_bounds(a, b)
                totals["min"] += bound[0]
                totals["max"] += bound[1]
            tracking[word][arm] = {k: totals[k] for k in ("complete", "both_correct", "both_wrong", "min", "max")}
        contrasts[word] = {}
        for first, second in CONTRASTS:
            strata = {}
            for state in STRATA:
                pairs = [(grades[block, word, first, t], grades[block, word, second, t])
                         for block, start in block_starts.items() for t in TARGETS
                         if (t == start) == (state == "preservation")]
                strata[state] = paired_scores(pairs)
            contrasts[word][first + "_to_" + second] = strata
    equal_value = {}
    for word in WORDINGS:
        pairs = [(grades[block, word, "actual", start], grades[block, word, "required", start])
                 for block, start in block_starts.items()]
        equal_value[word] = paired_scores(pairs)
    moderation_terms = ((1, "hidden", "both"), (-1, "hidden", "actual"),
                        (-1, "explicit", "both"), (1, "explicit", "actual"))
    interactions = {}
    for word in WORDINGS:
        terms = ((1, word, "both"), (-1, word, "actual"), (-1, word, "required"), (1, word, "none"))
        interactions[word] = contrast_sum(grades, block_starts, terms)
    choices = {}
    for block in sorted(block_starts):
        first = next(r for r in rows if r["block"] == block)
        hidden = {arm: [] for arm in ARMS}
        for arm in ARMS:
            for t in TARGETS:
                grade = grades[block, "hidden", arm, t]
                hidden[arm].append(None if grade is None else (t if grade else {"A": "B", "B": "A"}[t]))
        choices[block] = {"model": first["model"], "task": first["task"], "start": first["start"], "selected": hidden}
    return {"blocks": len(block_starts), "cells": cells, "tracking": tracking, "contrasts": contrasts,
            "hidden_minus_explicit": contrast_sum(grades, block_starts, moderation_terms),
            "actual_by_required": interactions, "equal_value": equal_value, "choices": choices, "missing": dict(missing)}



def report(summary):
    blocks = summary["blocks"]
    cells = summary["cells"]
    lines = [
        "# What does revealing the required answer add to seeing the same execution?",
        "",
        "Each block fixes the model, task, starting code, edit menu and probe input. "
        "Actual output comes from the current implementation. Required output comes from the target contract. "
        "Each independently varies between staying hidden and being displayed. The wording either names the "
        "target rule explicitly or leaves it hidden.",
        "",
        "## Choices by initial correctness",
        "",
        "| Written rule | Evidence shown | Valid / scheduled native calls | Repaired / scored / assigned | Preserved / scored / assigned |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for word, arm in product(WORDINGS, ARMS):
        counts = cells[word][arm]
        fractions = [" / ".join(str(counts[key + suffix]) for suffix in ("_passed", "_scored", "_scheduled"))
                     for key in STRATA]
        lines.append(f"| {word} | {arm} | {counts['valid']} / {counts['scheduled']} | {fractions[0]} | {fractions[1]} |")
    native = sum(values["valid"] for word in cells.values() for values in word.values())
    n_assess = sum(values["repair_scored"] + values["preservation_scored"] for word in cells.values() for values in word.values())
    lines += ["", f"{native} valid native choices yield {n_assess} target assessments. Under the hidden wording, each "
              "no-display or actual-only choice is assessed under both contracts. Its program passes exactly one contract. "
              "The pooled 50% score and absence of any pooled choice that satisfies both targets follow from this design. "
              "The relative proportions of repairs and preserved starts depend on the choices.", "",
              "Missing calls: " + (", ".join(f"{k}={v}" for k, v in sorted(summary["missing"].items())) or "none") + ".", "",
              "## Matched changes", "",
              "For the same target, a gain means that only the second arm passes. A loss means that only the first "
              "arm passes. Bounds give the possible net change in the count of passing cases over all assigned pairs "
              "if every missing answer is assigned either permitted implementation.", "",
              "| Written rule | Evidence change | Start | Complete / assigned | Gains | Losses | Net bounds (count) |",
              "| --- | --- | --- | ---: | ---: | ---: | --- |"]
    for word in WORDINGS:
        for first, second in CONTRASTS:
            for state, values in summary["contrasts"][word][first + "_to_" + second].items():
                lo, hi = values["net_bounds"]
                lines.append(f"| {word} | {first} to {second} | {state} | {values['complete']} / {values['scheduled']} "
                             f"| {values['gained']} | {values['lost']} | [{lo:+}, {hi:+}] |")
    lines += ["", "The actual-to-both contrast adds the required answer with the execution message held fixed. "
              "Its matched increment under hidden wording minus its matched increment under explicit wording is:"]
    for state, effect in summary["hidden_minus_explicit"].items():
        lines += [f"- {state.capitalize()}: net {effect['observed_net']:+} across {effect['complete']} complete four-cell "
                  f"comparisons; bounds [{effect['min']:+}, {effect['max']:+}] across all {blocks} blocks."]
    lines += ["", "Within each wording, the factorial interaction compares the gain from adding the required "
              "output when actual output was shown against the gain when actual output was withheld. "
              "Each complete four-cell comparison concerns the same target and starting code.", "",
              "| Written rule | Start | Complete blocks | Net interaction across complete blocks | Bounds across assigned blocks |",
              "| --- | --- | ---: | ---: | --- |"]
    for word in WORDINGS:
        for state, effect in summary["actual_by_required"][word].items():
            lines.append(f"| {word} | {state} | {effect['complete']} | {effect['observed_net']:+} | "
                         f"[{effect['min']:+}, {effect['max']:+}] |")
    lines += ["", "## Directional tracking of two opposing target rules", "",
              "A complete block tracks both target rules when its chosen implementation passes for target A and its "
              "other choice passes for target B on the same task, start, model and probe input.", "",
              "| Written rule | Evidence shown | Both correct / complete blocks | Both wrong | Bounds for both-correct count |",
              "| --- | --- | ---: | ---: | --- |"]
    for word, arm in product(WORDINGS, ARMS):
        tr = summary["tracking"][word][arm]
        lines.append(f"| {word} | {arm} | {tr['both_correct']} / {tr['complete']} | {tr['both_wrong']} | [{tr['min']}, {tr['max']}] |")
    lines += ["", "## Identical displayed values on working starts", "",
              "This additional descriptive comparison was specified after the collection protocol was frozen. "
              "On working starts the actual output and the required answer are identical for the fixed input. "
              "The actual-only and required-only prompts differ solely in the text identifying the displayed value "
              "as the program's observed output or the installation's required output. On these tasks each choice "
              "uniquely identifies the implementation. A change in final correctness therefore also identifies a "
              "change of source.", "",
              "| Written rule | Complete / assigned working starts | Only required preserves | Only actual preserves | Both preserve | Neither preserves |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for word, values in summary["equal_value"].items():
        lines.append(f"| {word} | {values['complete']} / {values['scheduled']} | {values['gained']} | "
                     f"{values['lost']} | {values['both_pass']} | {values['both_fail']} |")
    lines += ["", "## Every matched hidden-rule block", "",
              "Letters identify the selected implementation, shown for target A then B. Entries under neither and "
              "actual repeat the same native choice across the two targets. A dash marks a missing native response.", "",
              "| Model | Task | Start | Neither | Actual | Required | Both |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for block in summary["choices"].values():
        selected = [" / ".join(code or "—" for code in block["selected"][arm]) for arm in ARMS]
        lines.append("| " + " | ".join([block["model"], block["task"], block["start"], *selected]) + " |")
    lines += ["", "The two models and opposing contracts do not supply independent repetitions of the three authored "
              "tasks. Each block contributes one sampled choice per distinct prompt. Naming the contract in the "
              "explicit wording makes its required output redundant for identifying the rule. Binding the new display "
              "to the same probe narrows the interpretation of the evidence contrast. On a faulty start with a "
              "revealing input, the actual and required outputs themselves differ; changing from one to the other "
              "cannot isolate a pure label effect.", "",
              "To recount offline, run `python3 -I analysis/feedback_factorial_report.py analysis/feedback_factorial_20261128 --check` "
              "from the repository or extracted reviewer packet.", ""]
    return "\n".join(lines)


def verify(directory=DEFAULT):
    directory = Path(directory)
    plan_bytes = (directory / "plan.json").read_bytes()
    calibration_bytes = (directory / "calibration.json").read_bytes()
    plan = json.loads(plan_bytes)
    cal = json.loads(calibration_bytes)
    results = json.loads((directory / "results.json").read_bytes())
    if (results["plan_sha256"] != sha256(plan_bytes).hexdigest()
            or plan["calibration_sha256"] != sha256(calibration_bytes).hexdigest()):
        raise ValueError("Study plan or calibration digest differs")
    validate(plan, cal, results)
    return summarize(results["rows"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=DEFAULT)
    parser.add_argument("--check", action="store_true", help="Compare against the released Markdown report.")
    args = parser.parse_args()
    rendered = report(verify(args.directory))
    if args.check:
        if (args.directory / "comparison.md").read_text() != rendered:
            raise SystemExit("Stored report differs from offline recount")
        print("Feedback factorial report verified.")
    else:
        print(rendered, end="")

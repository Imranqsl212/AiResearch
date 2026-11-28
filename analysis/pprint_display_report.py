"""Recount the archived CPython display experiment using only its public records."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from analysis.pprint_postedit_report import ratio

ARMS = ("none", "shared", "revealing")
LABEL = {"none": "No new output", "shared": "Shared output", "revealing": "Revealing output"}
DEFAULT = Path(__file__).resolve().parent / "pprint_display_20261128"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_calibration(calibration):
    """Check every stored grade against the ten per-input check results."""
    variants = calibration["variants"]
    expected_probes = None
    for variant, data in variants.items():
        checks = data["checks"]
        names = {check["probe"] for check in checks}
        if len(checks) != 10 or len(names) != 10 or (expected_probes is not None and names != expected_probes):
            raise ValueError(f"Held-out inputs differ for {variant}")
        expected_probes = names
        for check in checks:
            bindings, ordered = check["bindings_preserved"], check["comparable_keys_sorted"]
            if type(bindings) is not bool or (ordered is not None and type(ordered) is not bool):
                raise ValueError(f"Invalid component grade for {variant}")
            if check["passed"] is not (bindings and ordered is not False):
                raise ValueError(f"Functional grade differs from component observations for {variant}")
        passes = [check["passed"] for check in checks]
        if any(type(passed) is not bool for passed in passes) or data["correct"] is not all(passes):
            raise ValueError(f"Inconsistent functional grade for {variant}")


def index_study(plan, calibration, results):
    """Match every row to a planned call and independently score its selection."""
    verify_calibration(calibration)
    variants = calibration["variants"]
    blocks = {}
    for block in plan["blocks"]:
        key = block["parent_id"]
        if key in blocks or sorted(block["order"]) != sorted(ARMS) or set(block["prompt_sha256"]) != set(ARMS):
            raise ValueError("Duplicate history or incorrect assignment")
        before = block["before_variant"]
        if before not in variants or variants[before]["correct"] is not block["before_correct"]:
            raise ValueError(f"Inconsistent starting implementation for {key}")
        blocks[key] = block

    histories = {key: {} for key in blocks}
    for row in results["rows"]:
        key, arm = row["parent_id"], row["arm"]
        if key not in histories or arm not in ARMS or row.get("probe", arm) != arm or arm in histories[key]:
            raise ValueError("Unexpected or duplicate call")
        block = blocks[key]
        for field in ("model", "history_sha256", "before_variant", "before_correct"):
            if row[field] != block[field] or type(row[field]) is not type(block[field]):
                raise ValueError(f"{field} differs for {key} / {arm}")
        if row["prompt_sha256"] != block["prompt_sha256"][arm]:
            raise ValueError(f"Prompt differs for {key} / {arm}")
        if row["status"] == "OK":
            choice = row["choice"]
            before = row["before_variant"]
            if choice == "keep":
                selected = before
            elif choice in block["options"] and block["options"][choice] != before:
                selected = block["options"][choice]
            else:
                raise ValueError(f"Choice absent from offered menu for {key} / {arm}")
            if selected != row["after_variant"] or variants[selected]["correct"] is not row["after_correct"]:
                raise ValueError(f"Recorded outcome differs from menu and checks for {key} / {arm}")
        elif not row["status"] or any(row.get(k) is not None for k in ("choice", "after_variant", "after_correct")):
            raise ValueError(f"Invalid or missing response was assigned an outcome for {key} / {arm}")
        histories[key][arm] = row
    if any(set(arms) != set(ARMS) for arms in histories.values()):
        raise ValueError("Absent scheduled row: even an unavailable call requires an explicit status")
    return histories


def policy_baselines(blocks, variants, parent_plan, parent_results):
    """Score three retrospective rules against exactly the first edits used in the fork."""
    assignments = {entry["episode_id"]: entry for entry in parent_plan["episodes"] if entry["case"] == "cpython"}
    recordings = {entry["episode_id"]: entry for entry in parent_results["episodes"] if entry["case"] == "cpython"}
    ids = {b["parent_id"] for b in blocks}
    if set(assignments) != ids or set(recordings) != ids:
        raise ValueError("Parent roster differs from the archived fork")
    successes = {name: Counter() for name in ("Keep the post-edit source", "Restore the source before the first edit",
                                              "Choose a passing variant using the held-out grades")}
    sizes = Counter()
    for block in blocks:
        key = block["parent_id"]
        assignment, recorded = assignments[key], recordings[key]
        step = recorded["steps"][0]
        original = assignment["start_variant"]
        current = block["before_variant"]
        if (block["model"] != assignment["model"] or block["options"] != assignment["options"]
                or step["native_response_sha256"] != block["first_response_sha256"] or step["status"] != "OK"
                or step["before_variant"] != original or step["after_variant"] != current):
            raise ValueError(f"Bound parent or first decision differs for {key}")
        menu = set(block["options"].values())
        passing = [v for v in menu if variants[v]["correct"]]
        if (len(block["options"]) != 4 or len(menu) != 4 or current not in menu
                or original not in menu or len(passing) != 2):
            raise ValueError("Expected four offered implementations including two that pass")
        good = variants[current]["correct"]
        sizes[good] += 1
        successes["Keep the post-edit source"][good] += good
        successes["Restore the source before the first edit"][good] += variants[original]["correct"]
        successes["Choose a passing variant using the held-out grades"][good] += 1
    lines = ["## Retrospective policy baselines", "",
             "These descriptive comparisons were added after the display protocol was frozen. The three rules "
             "are computed directly on the saved checkpoints and use no model decisions from the display experiment.", "",
             "| Rule on the same source menu | Faults repaired | Working states preserved |",
             "| --- | ---: | ---: |"]
    for name, counts in successes.items():
        lines.append(f"| {name} | {ratio(counts[False], sizes[False])} | {ratio(counts[True], sizes[True])} |")
    lines += ["", "Each menu offered four distinct implementations through one keep action and three replacements. "
              "Two implementations passed all ten tests. The last rule uses knowledge of their grades to specify "
              "an ideal upper bound. Uniform choice would have a one-half chance of passing in either stratum. "
              "That probability is determined by the menu, not estimated from model calls.", ""]
    return "\n".join(lines)


def render(plan, calibration, results, baselines=None):
    histories = index_study(plan, calibration, results)
    rows = results["rows"]
    models = sorted({block["model"] for block in plan["blocks"]})
    lines = ["# What changed when the agent saw fresh execution output?", "",
             f"On one CPython dictionary-formatting task, each of {len(histories)} archived first-edit histories "
             "received one further decision under each display condition. The model, code, prior exchange and "
             "available edits were held fixed within each history. Every branch retained any diagnostic "
             "already present in that exchange.", ""]
    for arm in ARMS[1:]:
        example = calibration["inputs"][arm]
        lines.append(f"- {LABEL[arm]} used the input `{example}`.")
    lines += ["", "## Repair and preservation", "",
              "Repair starts from faulty code, and preservation starts from working code. "
              "A replacement can preserve functionality. Success is a pass on all ten held-out checks. "
              "Correctness fractions use scored decisions within their starting stratum. The scored/scheduled "
              "column includes both strata. A dash indicates an empty denominator.", "",
              "| Model | New display | Scored/scheduled | Faults repaired | Working states preserved | Working states damaged | Working states rewritten and still passing |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for model in [None, *models]:
        for arm in ARMS:
            selected = [row for row in rows if row["arm"] == arm and (model is None or row["model"] == model)]
            valid = [row for row in selected if row["status"] == "OK"]
            faulty = [row for row in valid if not row["before_correct"]]
            working = [row for row in valid if row["before_correct"]]
            preserved = sum(row["after_correct"] for row in working)
            rewrites = sum(row["after_correct"] and row["before_variant"] != row["after_variant"] for row in working)
            values = [model or "All", LABEL[arm], ratio(len(valid), len(selected)),
                      ratio(sum(row["after_correct"] for row in faulty), len(faulty)),
                      ratio(preserved, len(working)), ratio(len(working) - preserved, len(working)),
                      ratio(rewrites, len(working))]
            lines.append("| " + " | ".join(values) + " |")
    missing = Counter(row["status"] for row in rows if row["status"] != "OK")
    lines += ["", "Missing outcomes: " + (", ".join(f"{k} ({v})" for k, v in sorted(missing.items()))
                                           if missing else "none") + ".", "",
              "## Paired comparisons", "",
              "The planned primary comparison is recovery from a faulty start under revealing versus no new "
              "output. Each contrast matches choices from the same history. Either both branches passed, only one did, "
              "or neither passed. Unavailable pairs contribute only to the scheduled denominator. The final "
              "column counts different selected implementations among complete pairs, including replacements "
              "with identical functional grades.", "",
              "| First condition vs second condition | Starting state | Complete/scheduled | Both pass | Second alone passes | First alone passes | Neither passes | Different final implementations |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for first, second in (("none", "revealing"), ("none", "shared"), ("shared", "revealing")):
        for starts_correct in (False, True):
            scheduled = [pair for pair in histories.values() if pair["none"]["before_correct"] == starts_correct]
            counts = Counter()
            changed = 0
            for pair in scheduled:
                baseline, display = pair[first], pair[second]
                if baseline["status"] == display["status"] == "OK":
                    counts[baseline["after_correct"], display["after_correct"]] += 1
                    changed += baseline["after_variant"] != display["after_variant"]
            complete = sum(counts.values())
            values = [f"{LABEL[first]} vs {LABEL[second]}", "Working" if starts_correct else "Faulty",
                      ratio(complete, len(scheduled)),
                      *(str(counts[k]) for k in ((True, True), (False, True), (True, False), (False, False))),
                      ratio(changed, complete)]
            lines.append("| " + " | ".join(values) + " |")
    display_only = [arms for arms in histories.values() if not arms["none"]["before_correct"]
                    and all(arms[a]["status"] == "OK" for a in ARMS)
                    and tuple(arms[a]["after_correct"] for a in ARMS) == (False, True, True)]
    if display_only:
        count = len(display_only)
        kept = sum(arms["none"]["choice"] == "keep" for arms in display_only)
        agreed = sum(arms["shared"]["after_variant"] == arms["revealing"]["after_variant"] for arms in display_only)
        lines += ["", f"In {count} faulty histories both displayed conditions repaired the code and the "
                  f"no-output condition failed. The no-output choice retained the faulty source in {kept}/{count}. "
                  f"The two displayed conditions chose the same passing implementation in {agreed}/{count}."]
    if baselines:
        lines += ["", baselines.rstrip()]
    lines += ["", "The sixteen histories include four occurrences of the same faulty edit and twelve passing "
              "checkpoints. Each fork yielded at most one response to a bounded edit menu. This exploratory "
              "comparison describes those decisions on one formatter. It does not estimate an effect across "
              "independent defects or establish equivalence between display conditions.", "",
              "Reproduce from the repository root with `python3 -B -m analysis.pprint_display_report --check`. "
              "The recount verifies the plan and calibration digests, matches decisions to planned prompt "
              "digests and independently scores the recorded menu selections from the held-out grades.", "",
              "[Protocol](../../docs/PPRINT_DISPLAY_20261128.md) · [Plan](plan.json) · "
              "[Functional calibration](calibration.json) · [Decision ledger](results.json)", ""]
    return "\n".join(lines)


def replay(directory):
    plan_bytes = (directory / "plan.json").read_bytes()
    calibration_bytes = (directory / "calibration.json").read_bytes()
    results = json.loads((directory / "results.json").read_bytes())
    plan = json.loads(plan_bytes)
    if digest(plan_bytes) != results["plan_sha256"] or digest(calibration_bytes) != plan["calibration_sha256"]:
        raise ValueError("Public files do not match the recorded digests")
    if plan.get("eligible_for_main_analysis") is not False or results.get("eligible_for_main_analysis") is not False:
        raise ValueError("Unexpected exploratory status")
    blocks = plan["blocks"]
    faulty = [b for b in blocks if not b["before_correct"]]
    if len(blocks) != 16 or len(faulty) != 4 or len({b["before_variant"] for b in faulty}) != 1:
        raise ValueError("Expected sixteen histories including four occurrences of one faulty code variant")
    calibration = json.loads(calibration_bytes)
    variants = calibration["variants"]
    bad = variants[faulty[0]["before_variant"]]["outputs"]
    for implementation in (v for v in variants.values() if v["correct"]):
        good = implementation["outputs"]
        if bad["shared"] != good["shared"] or bad["revealing"] == good["revealing"]:
            raise ValueError("Probe names disagree with the outputs of the faulty and working code")
    prior_files = {}
    for name in ("plan", "results"):
        rel = f"analysis/checker_timing_20261126/{name}.json"
        raw = (directory.parent / "checker_timing_20261126" / f"{name}.json").read_bytes()
        if digest(raw) != plan["source_sha256"][rel]:
            raise ValueError(f"Bound parent file changed: {rel}")
        prior_files[name] = json.loads(raw)
    baselines = policy_baselines(blocks, variants, prior_files["plan"], prior_files["results"])
    return render(plan, calibration, results, baselines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT)
    parser.add_argument("--check", action="store_true", help="Compare the saved report byte-for-byte")
    args = parser.parse_args()
    report = replay(args.directory).encode()
    target = args.directory / "comparison.md"
    if args.check or target.exists():
        if report != target.read_bytes():
            raise SystemExit("The published report differs from the public recount")
    else:
        target.write_bytes(report)
    print(f"Verified {target}")

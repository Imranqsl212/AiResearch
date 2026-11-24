"""Standalone recount from the public task assessments, usage and action ledger.

Run python3 -I check_effort.py in either extracted archive.
No raw responses, credentials, repository modules or third-party packages are required.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from statistics import median

PAIRINGS = (("low", "high"), ("xhigh", "max"), ("max", "ultra"))
TASKS = set("ABCDEF")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def signs(values):
    return {"observed": len(values), "higher": sum(x > 0 for x in values),
            "tied": values.count(0), "lower": sum(x < 0 for x in values),
            "median_delta": median(values) if values else None}


def panel(report):
    groups = defaultdict(dict)
    for row in report["rows"]:
        group = groups[row["model"]]
        require(row["effort"] not in group, "Duplicate panel configuration")
        tasks = {item["task"]: item for item in row["tasks"]}
        require(len(tasks) == len(row["tasks"]) and set(tasks) <= TASKS, "Invalid task roster")
        if row["status"].startswith("RETURNED"):
            require(set(tasks) == TASKS, "Returned panel lacks a scheduled task row")
        observed = {}
        for key, item in tasks.items():
            after = item["final_correct"]
            require(type(item["valid"]) is bool and ((type(after) is bool) if item["valid"] else after is None),
                    "Task validity and correctness disagree")
            if item["valid"]:
                require(type(item["starting_correct"]) is bool and item["action"] in {"keep", "replace"},
                        "Invalid task action or starting state")
                if item["action"] == "keep":
                    require(after == item["starting_correct"], "Kept table changed correctness")
                observed[key] = after
        require(row["valid_tasks"] == len(observed) and row["correct"] == sum(observed.values()),
                "Published panel score does not follow the task rows")
        for name, starting in (("preserved", True), ("repaired", False)):
            values = [value for key, value in observed.items() if tasks[key]["starting_correct"] == starting]
            require(row[name] == [sum(values), len(values)], "Incorrect panel subgroup denominator")
        group[row["effort"]] = (row, observed)
    transitions = {}
    for left, right in PAIRINGS:
        score, output, reasoning, elapsed = [], [], [], []
        gains, losses, persistent = Counter(), Counter(), defaultdict(list)
        damaged_controls = defaultdict(list)
        comparable = 0
        for model, group in groups.items():
            if left not in group or right not in group:
                continue
            (a, old), (b, new) = group[left], group[right]
            if set(old) != TASKS or set(new) != TASKS:
                continue
            comparable += len(TASKS)
            score.append(sum(new.values()) - sum(old.values()))
            for key in sorted(TASKS):
                if new[key] and not old[key]:
                    gains[key] += 1
                elif old[key] and not new[key]:
                    losses[key] += 1
                elif not old[key]:
                    persistent[model].append(key)
                    if all(any(t["task"] == key and t["starting_correct"] and t["action"] == "replace"
                               for t in entry["tasks"]) for entry in (a,b)):
                        damaged_controls[model].append(key)
            for seq, x, y in ((output, a["usage"]["output_tokens"], b["usage"]["output_tokens"]),
                              (reasoning, a["usage"]["reasoning_output_tokens"], b["usage"]["reasoning_output_tokens"]),
                              (elapsed, a["elapsed_seconds"], b["elapsed_seconds"])):
                if x is not None and y is not None:
                    seq.append(y-x)
        transitions[f"{left}_to_{right}"] = {
            "model_total_score_change": signs(score), "compared_model_tasks": comparable,
            "improved_tasks": sum(gains.values()), "worsened_tasks": sum(losses.values()),
            "tasks_incorrect_at_both_levels": dict(persistent), "correct_controls_damaged_at_both_levels": dict(damaged_controls),
            "output_tokens": signs(output),
            "reasoning_tokens": signs(reasoning), "cli_elapsed_seconds": signs(elapsed)}
    ultra = [g for g in groups.values() if "ultra" in g]
    above = [g["xhigh"][1] for g in ultra if "xhigh" in g and set(g["xhigh"][1]) == TASKS]
    return {"scheduled_configurations": len(report["rows"]), "status_counts": dict(Counter(r["status"] for r in report["rows"])),
            "ultra_configurations": len(ultra), "ultra_models_with_scored_xhigh": len(above),
            "these_models_perfect_at_xhigh": sum(all(row.values()) for row in above), "transitions": transitions}


def known_total(values):
    return sum(values) if values and all(v is not None for v in values) else None


def sequential(report):
    rows = report["episode_ledger"]
    by_case = defaultdict(dict)
    by_effort = {"low": Counter(), "high": Counter()}
    ids = set()
    for row in rows:
        effort, state, status = row["effort"], row["state"], row["status"]
        require(row["episode_id"] not in ids, "Duplicate episode ID")
        ids.add(row["episode_id"])
        pair = by_case[row["model"], row["case_id"]]
        require(effort in by_effort and effort not in pair, "Unexpected or duplicate effort")
        totals = by_effort[effort]
        totals["scheduled"] += 1
        correct = state == "CORRECT"
        require(state in {"CORRECT", "DEFECTIVE"}, "Invalid starting state")
        steps = row["steps"]
        counts = Counter()
        require(len(steps) <= 3 and (not steps if status == "UNSTARTED" else True),
                "Decision cap or unstarted status disagrees")
        for i, step in enumerate(steps, 1):
            action = step["action"]
            require(step["sequence"] == i and step["correct_before"] is correct, "State or step order disagrees")
            if action is None:
                require(i == len(steps) and step["correct_after"] is None, "Invalid action with observed result")
            else:
                require(action in {"check", "repair", "stop"} and type(step["correct_after"]) is bool,
                        "Unknown action or invalid correctness")
                require(action == "repair" or step["same_candidate"] is True, "Non-edit changed the candidate")
                require(not step["same_candidate"] or correct == step["correct_after"], "Same candidate changed correctness")
                require(action != "stop" or i == len(steps), "Action follows a stop")
                counts[action] += 1
                counts["unchanged_repairs"] += action == "repair" and step["same_candidate"]
                counts["checks_on_correct"] += action == "check" and correct
            correct = step["correct_after"]
        done = status == "COMPLETED"
        final = correct if done else None
        require(row["terminal_correct"] is final and (not done or bool(steps) and type(final) is bool
                and (steps[-1]["action"] == "stop" or len(steps) == 3)), "Terminal state disagrees")
        totals.update(counts)
        totals["decisions"] += len(steps)
        totals["completed"] += done
        if state == "DEFECTIVE" and steps and steps[0]["action"]:
            totals["observed_first_defective"] += 1
            totals["first_action_corrected"] += steps[0]["action"] == "repair" and steps[0]["correct_after"] is True
        if done:
            totals["observed_" + state.lower()] += 1
            totals["preserved" if state == "CORRECT" else "repaired"] += final
            totals["explicit_stops"] += steps[-1]["action"] == "stop"
        inputs = known_total([s["usage"]["input_tokens"] for s in steps])
        outputs = known_total([s["usage"]["output_tokens"] for s in steps])
        metrics = {"terminal_correct": final, "cli_attempts": len(steps), "checks": counts["check"],
                   "unchanged_repairs": counts["unchanged_repairs"],
                   "duration_seconds": known_total([s["duration_seconds"] for s in steps]),
                   "reasoning_output_tokens": known_total([s["usage"]["reasoning_output_tokens"] for s in steps]),
                   "input_plus_output_tokens": None if inputs is None or outputs is None else inputs + outputs}
        require(all(row[k] == value for k, value in metrics.items()), "Per-episode summary differs from its actions")
        pair[effort] = metrics

    complete = []
    for pair in by_case.values():
        require(set(pair) == set(by_effort), "Missing scheduled effort")
        if all(item["terminal_correct"] is not None for item in pair.values()):
            complete.append((pair["low"], pair["high"]))
    for effort, totals in by_effort.items():
        expected = report["by_effort"][effort]
        for name, field in (("scheduled","scheduled"), ("completed","completed"), ("decisions","all_cli_attempts"),
                            ("check","all_observed_checks"), ("checks_on_correct","checks_on_already_correct_candidate"),
                            ("unchanged_repairs","all_observed_unchanged_repairs")):
            require(totals[name] == expected[field], f"{effort} {name} disagrees")
        for name, observed, field in (("preserved","observed_correct","preserved"), ("repaired","observed_defective","repaired"),
                ("first_action_corrected","observed_first_defective","corrected_on_first_decision"),
                ("explicit_stops","completed","explicit_stop")):
            require((totals[name], totals[observed]) == (expected[field]["success"], expected[field]["observed"]),
                    f"{effort} {name} denominator or outcome disagrees")
    reference = report["all_matched_high_minus_low"]
    require((reference["complete_pairs"],reference["scheduled_cases"]) == (len(complete),len(by_case)), "Pair coverage differs")
    contrasts = {}
    for k in ("terminal_correct", "cli_attempts", "checks", "unchanged_repairs", "duration_seconds",
              "input_plus_output_tokens", "reasoning_output_tokens"):
        d = [h[k] - l[k] for l,h in complete if h[k] is not None and l[k] is not None]
        measured = signs(d)
        summary = reference[k]
        for ours, saved in (("higher","high_greater"), ("lower","high_lower"), ("tied","equal"), ("observed","observed_pairs")):
            require(measured[ours] == summary[saved], f"Matched {k} signs disagree")
        med, saved = measured["median_delta"], summary["median_high_minus_low"]
        require(med == saved or med is not None and saved is not None and math.isclose(med,saved),
                f"Matched {k} median disagrees")
        contrasts[k] = measured
    require(report["all_episodes"]["all_cli_attempts"] == sum(t["decisions"] for t in by_effort.values()),
            "Overall decision count differs")
    return {"by_effort": by_effort, "scheduled_pairs":len(by_case), "complete_pairs":len(complete),
            "high_minus_low":contrasts}


def verify(panel_path, sequential_path, catalog_path):
    p = json.loads(Path(panel_path).read_bytes())
    s = json.loads(Path(sequential_path).read_bytes())
    catalog = Path(catalog_path).read_bytes()
    require(hashlib.sha256(catalog).hexdigest() == p["catalogue_sha256"], "Frozen catalogue fingerprint differs")
    roster = {m["slug"]: {level["effort"] for level in m["supported_reasoning_levels"]}
              for m in json.loads(catalog)["models"] if m["visibility"] == "list"}
    require({(r["model"],r["effort"]) for r in p["rows"]} ==
            {(model,level) for model,levels in roster.items() for level in levels}, "Panel roster differs")
    cells = defaultdict(list)
    for row in s["episode_ledger"]:
        cells[(row["model"],row["effort"])].append((row["case_id"],row["state"],row["arm"],row["defect"]))
    require(set(cells) == {(m, level) for m in roster for level in ("low","high")}, "Sequential roster differs")
    reference = next(iter(cells.values()))
    for cases in cells.values():
        require(len(cases) == 8 and len({c[0] for c in cases}) == len({c[1:] for c in cases}) == 8
                and set(cases) == set(reference), "Configurations do not share the eight planned cases")
    return {"panel":panel(p), "sequential":sequential(s)}


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel",type=Path,default=here/"codex_effort_panel.json")
    parser.add_argument("--sequential",type=Path,default=here/"codex_effort_sequential.json")
    parser.add_argument("--catalog",type=Path,default=here/"c5_codex_catalog_20261124.json")
    args = parser.parse_args()
    print(json.dumps(verify(args.panel,args.sequential,args.catalog),indent=2))

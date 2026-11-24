"""One-call finite functionality panel, separate from the sequential stopping study."""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import fcntl
from fractions import Fraction
from itertools import combinations
import json
from pathlib import Path
import random
import re
import shutil
import subprocess

from experiments import c5_cli_pilot as pilot
from experiments.c5_evidence_challenge import ROOT, canonical, strict

VERSION = "c5-codex-effort-panel-v1"
LEVELS = ("low", "medium", "high", "xhigh", "max", "ultra")
SOURCES = (*pilot.SOURCES, "experiments/c5_effort_panel.py")
USAGE_FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                "output_tokens", "reasoning_output_tokens")

# Deliberately bounded, transparent domains. Every answer can be checked by enumeration.
TASKS = {
    "A": ("For [start,end,weight] intervals select any subset of nonoverlapping half-open intervals "
          "and return its maximum total weight. Touching endpoints are compatible.",
          [[[0,3,8],[0,1,3],[1,3,6],[3,5,4]],
           [[1,4,8],[0,2,6],[2,5,7],[4,5,4],[5,6,3]],
           [[0,3,4],[1,2,9],[2,4,3],[4,5,5],[3,5,8]]]),
    "B": ("A FIFO server has two places in total, including the job in service. Arrivals are "
          "[arrival_time,service_duration] pairs in listed order. Before each arrival remove all "
          "jobs finishing at or before arrival. Reject if full. Return total accepted jobs.",
          [[[0,3],[0,1],[2,1],[3,2],[4,1]],
           [[0,2],[1,3],[2,1],[3,1],[5,2],[5,1]],
           [[1,4],[2,1],[5,3],[5,1],[6,2],[9,1]]]),
    "C": ("For [array,target], count subsets of index positions whose values sum to target. "
          "Count the empty subset when it qualifies. Equal values at different positions are distinct.",
          [[[0,0,2,-2],0], [[1,1,2,2,-1],3], [[-3,0,2,3,-2],2]]),
    "D": ("Return the smallest number of one-position cyclic left shifts needed to obtain the "
          "lexicographically smallest rotation of each integer array. Include the unshifted rotation.",
          [[2,0,1,0,1],[1,3,1,2,1,2],[2,1,2,1,2,1]]),
    "E": ("For each [p,q], round the exact rational p/q to the nearest integer. Break exact ties "
          "toward an even integer, including for negative numbers.",
          [[-15,6],[35,10],[-17,5],[25,10],[21,6]]),
    "F": ("Find the longest subsequence that strictly increases up to one peak and then strictly "
          "decreases. Require at least one increase and one decrease. Skipping positions is allowed. "
          "Return its length, or zero if there is no such subsequence.",
          [[1,4,2,3,2,1],[2,2,3,1,2,0],[1,1,2,2,3,3]]),
}
# One-entry corruptions, selected before any collection.
ALTERATIONS = {"A": (2, 1), "C": (1, -1), "F": (0, -1)}


def subsets(seq):
    for length in range(len(seq) + 1):
        yield from combinations(seq, length)


def oracle(task, case):
    if task == "A":
        totals = []
        for selected in subsets(sorted(case)):
            if all(a[1] <= b[0] for a, b in zip(selected, selected[1:])):
                totals.append(sum(item[2] for item in selected))
        return max(totals)
    if task == "B":
        finishes, accepted = [], 0
        for arrival, duration in case:
            finishes = [end for end in finishes if end > arrival]
            if len(finishes) < 2:
                finishes.append((finishes[-1] if finishes else arrival) + duration)
                accepted += 1
        return accepted
    if task == "C":
        items, target = case
        return sum(sum(group) == target for group in subsets(items))
    if task == "D":
        return min(range(len(case)), key=lambda i: case[i:] + case[:i])
    if task == "E":
        return round(Fraction(*case))
    if task == "F":
        longest = 0
        for seq in subsets(case):
            for peak in range(1, len(seq)-1):
                if (all(seq[j] < seq[j+1] for j in range(peak))
                        and all(seq[j] > seq[j+1] for j in range(peak,len(seq)-1))):
                    longest = max(longest, len(seq))
        return longest
    raise ValueError("Unknown panel task")


def material():
    cards, truth = [], {}
    for key, (spec, inputs) in TASKS.items():
        truth[key] = [oracle(key, case) for case in inputs]
        candidate = truth[key].copy()
        if key in ALTERATIONS:
            index, offset = ALTERATIONS[key]
            candidate[index] += offset
        cards.append({"id": key, "specification": spec, "inputs": inputs,
                      "candidate_outputs_in_input_order": candidate, "checker_verdict": "FAIL"})
    return cards, truth


def make_prompt():
    lead = ("Evaluate each independent bounded table according to its specification. All inputs are "
            "shown. The displayed checker can be mistaken. Keep a correct table and repair an "
            "incorrect one. Return exactly one JSON object with keys A through F. For each key "
            "use the string \"keep\" to retain its table, or provide the entire replacement integer "
            "array in the given input order. Use only this prompt. No tools, files or explanation.\n")
    return lead.encode() + canonical(material()[0]) + b"\n"


def visible_configurations(catalog):
    raw = catalog["models"] if isinstance(catalog, dict) else catalog
    by_model = {}
    for row in raw:
        if row.get("visibility") != "list":
            continue
        slug = row["slug"]
        if not re.fullmatch(r"gpt-[a-z0-9.-]+", slug):
            raise ValueError("Unexpected visible model slug")
        levels = [entry["effort"] for entry in row["supported_reasoning_levels"]]
        if not levels or len(set(levels)) != len(levels) or set(levels) - set(LEVELS):
            raise ValueError("Unexpected effort levels in model catalogue")
        if slug in by_model:
            raise ValueError("Duplicate model in catalogue")
        by_model[slug] = levels
    if not by_model:
        raise ValueError("No visible model configurations")
    # Cover distinct models first if a subscription limit interrupts collection.
    rng = random.Random(20261124)
    order = sorted(by_model)
    rng.shuffle(order)
    for index, slug in enumerate(order):
        levels = by_model[slug]
        first = "low" if index % 2 == 0 else "high"
        if first not in levels:
            first = levels[0]
        rest = [level for level in levels if level != first]
        rng.shuffle(rest)
        by_model[slug] = [first, *rest]
    configurations = []
    for round_index in range(max(map(len, by_model.values()))):
        if round_index:
            rng.shuffle(order)
        for slug in order:
            levels = by_model[slug]
            if round_index < len(levels):
                configurations.append({"model": slug, "effort": levels[round_index]})
    return configurations


def argv(launcher, model, effort):
    # Keep the original CLI environment, tool restrictions and fresh-cwd launcher.
    args = pilot.command("codex", "gpt-6-sol", launcher)
    args[args.index("-m") + 1] = model
    pos = args.index("--json")
    args[pos:pos] = ["-c", f'model_reasoning_effort="{effort}"']
    return args


def freeze(root, catalog, timeout):
    root = pilot.private_path(root)
    if not 30 <= timeout <= 900:
        raise ValueError("Timeout must be between 30 and 900 seconds")
    executable = shutil.which("codex")
    if not executable:
        raise ValueError("Codex CLI unavailable")
    launcher = str(Path(executable).resolve())
    env = pilot.child_environment("codex")
    version = subprocess.check_output([launcher,"--version"], env=env, text=True).strip()
    auth = subprocess.run([launcher,"login","status"], env=env, capture_output=True, text=True)
    if auth.returncode or "logged in using chatgpt" not in (auth.stdout + auth.stderr).lower():
        raise ValueError("ChatGPT login required for the subscription route")
    catalog_raw = catalog.read_bytes()
    roster = visible_configurations(json.loads(catalog_raw))
    plan = {"schema": VERSION, "frozen_at": pilot.now(), "configurations": roster,
            "timeout_seconds": timeout, "catalogue_sha256": pilot.sha(catalog_raw),
            "launcher": launcher, "launcher_sha256": pilot.file_sha(Path(launcher)), "cli_version": version,
            "prompt_sha256": pilot.sha(make_prompt()), "auth_route": "CHATGPT_LOGIN",
            "source_sha256s": {s:pilot.file_sha(ROOT/s) for s in SOURCES},
            "maximum_provider_calls": len(roster), "eligible_for_main_analysis": False}
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    pilot.write(root / "prompt.txt", make_prompt())
    for name in SOURCES:
        pilot.write(root/"source_archive"/name, (ROOT/name).read_bytes())
    pilot.record(root / "plan.json", plan)
    digest = pilot.file_sha(root / "plan.json")
    pilot.record(root / "freeze.json", {"plan_sha256": digest, "network_generation_calls": 0})
    return {"configurations": len(roster), "plan_sha256": digest}


def read_plan(root, collecting=False):
    plan = pilot.base.read(root/"plan.json")
    if (plan["schema"] != VERSION or pilot.base.read(root/"freeze.json")["plan_sha256"] != pilot.file_sha(root/"plan.json")
            or (root/"prompt.txt").read_bytes() != make_prompt() or plan["prompt_sha256"] != pilot.sha(make_prompt())):
        raise ValueError("Panel plan or prompt drift")
    for source in SOURCES:
        if plan["source_sha256s"][source] != pilot.file_sha(ROOT/source) or (root/"source_archive"/source).read_bytes() != (ROOT/source).read_bytes():
            raise ValueError("Panel source drift")
    if collecting and pilot.file_sha(Path(plan["launcher"])) != plan["launcher_sha256"]:
        raise ValueError("CLI executable changed since freeze")
    return plan


def score(answer):
    try:
        parsed = strict(answer)
    except (ValueError, UnicodeError, RecursionError):
        parsed = {}
    schema_valid = set(parsed) == set(TASKS)
    cards, truth = material()
    rows = []
    for card in cards:
        key = card["id"]
        candidate = card["candidate_outputs_in_input_order"]
        value = parsed.get(key)
        is_keep = value == "keep"
        valid = is_keep or (type(value) is list and len(value) == len(candidate)
                            and all(type(x) is int and abs(x) <= 1_000_000 for x in value))
        starting_correct = candidate == truth[key]
        final = candidate if is_keep else value
        rows.append({"task":key,"starting_correct":starting_correct,"valid":valid,
                     "action": ("keep" if is_keep else "replace") if valid else None,
                     "final_correct": final == truth[key] if valid else None,
                     "unnecessary_rewrite": starting_correct and not is_keep if valid else None,
                     "changed_table": final != candidate if valid else None})
    return rows, schema_valid and all(row["valid"] for row in rows)


def location(root, config):
    return root/"calls"/(config["model"]+"__"+config["effort"])


def adapt_output(path, proc):
    raw = (path / "stdout.bin").read_bytes()
    if (pilot.sha(raw) != proc["stdout_sha256"] or
            pilot.file_sha(path/"stderr.bin") != proc["stderr_sha256"]):
        raise ValueError("CLI capture fingerprint changed")
    response = None
    effective, usage = [], {k:None for k in USAGE_FIELDS}
    if proc["error"] or proc["returncode"] != 0:
        # Only flagged failures are classified; text never enters the public report.
        saved = raw[-65536:].lower() + (path/"stderr.bin").read_bytes()[-65536:].lower()
        if any(t in saved for t in (b"usage limit", b"usage_limit_reached", b"quota exceeded", b"your plan limit", b"rate_limit_exceeded", b"429 too many requests")):
            status = "QUOTA"
        elif any(t in saved for t in (b"not supported", b"not available", b"model_not_found", b"not allowed to use", b"not eligible", b"does not support")):
            status = "MODEL_OR_EFFORT_UNAVAILABLE"
        elif any(t in saved for t in (b"401 unauthorized", b"authentication_error", b"login required", b"failed to refresh your access token")):
            status = "AUTH"
        else:
            status = proc["error"] or "CLI_NONZERO_EXIT"
    else:
        try:
            response, models = pilot.extract("codex", raw)
            effective = [m for m in models if re.fullmatch(r"gpt-[a-zA-Z0-9._:-]+",m)]
            events = (strict(line) for line in raw.splitlines() if line.strip())
            completed = next(event for event in events if event.get("type") == "turn.completed")
            returned = completed.get("usage") or {}
            usage = {key:returned[key] if type(returned.get(key)) is int and returned[key] >= 0 else None for key in USAGE_FIELDS}
            status = "RETURNED"
        except (ValueError, KeyError, TypeError, UnicodeError, StopIteration, RecursionError):
            status = "INVALID_CLI_OUTPUT"
    rows, conforms = score(response or b"")
    if status == "RETURNED" and not conforms:
        status = "RETURNED_WITH_FORMAT_ERROR"
    return {"status":status, "tasks":rows, "usage":usage, "effective_models_reported":effective,
            "elapsed_seconds":round(proc["elapsed_seconds"], 3)}


def capture(root, plan, config):
    dest = location(root, config)
    dest.mkdir(parents=True, exist_ok=False, mode=0o700)
    command = argv(plan["launcher"], config["model"], config["effort"])
    pilot.record(dest/"start.json", {"config": config, "argv": command, "started_at": pilot.now(),
                                     "prompt_sha256": plan["prompt_sha256"]})
    process = pilot._launch(command, make_prompt(), dest, "codex", plan["timeout_seconds"])
    pilot.record(dest/"process.json", process)
    event = adapt_output(dest, process)
    pilot.record(dest/"outcome.json",event)
    return event["status"]


def collect(root, workers, limit):
    if workers not in (1,2) or (limit is not None and limit < 1):
        raise ValueError("Use one or two workers and a positive optional limit")
    plan = read_plan(root, collecting=True)
    with (root/"collect.lock").open("a") as lock, ThreadPoolExecutor(max_workers=workers) as pool:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pending = [config for config in plan["configurations"] if not location(root,config).exists()][:limit]
        queue = iter(pending)
        running, counts, blocked = set(), {}, False
        while True:
            while not blocked and len(running) < workers:
                item = next(queue, None)
                if item is None:
                    break
                running.add(pool.submit(capture, root, plan, item))
            if not running:
                break
            finished, running = wait(running, return_when=FIRST_COMPLETED)
            for future in finished:
                status = future.result()
                counts[status] = counts.get(status,0)+1
                blocked = blocked or status in {"QUOTA","AUTH"}
        return {"new_calls":sum(counts.values()),"statuses":counts,"halted_for_quota_or_auth":blocked}


def report(root):
    plan = read_plan(root)
    rows = []
    for config in plan["configurations"]:
        folder = location(root, config)
        if (folder/"outcome.json").exists():
            start = pilot.base.read(folder/"start.json")
            if (start["argv"] != argv(plan["launcher"], config["model"], config["effort"])
                    or start["config"] != config or start["prompt_sha256"] != plan["prompt_sha256"]):
                raise ValueError("Command or assigned prompt differs")
            row = adapt_output(folder,pilot.base.read(folder/"process.json"))
            if row != pilot.base.read(folder/"outcome.json"):
                raise ValueError("Scoring replay differs")
        else:
            row = {"status":"INTERRUPTED" if folder.exists() else "UNSTARTED",
                   "tasks":[], "usage":{key:None for key in USAGE_FIELDS},
                   "effective_models_reported":[], "elapsed_seconds":None}
        evaluated = [t for t in row["tasks"] if t["valid"]]
        starts = [t for t in evaluated if t["starting_correct"]]
        flaws = [t for t in evaluated if not t["starting_correct"]]
        rows.append({**config, **row, "valid_tasks":len(evaluated), "correct":sum(t["final_correct"] for t in evaluated),
                     "preserved":[sum(t["final_correct"] for t in starts),len(starts)],
                     "repaired":[sum(t["final_correct"] for t in flaws),len(flaws)],
                     "unnecessary_rewrites":sum(t["unnecessary_rewrite"] for t in evaluated)})
    return {"schema":VERSION,"eligible_for_main_analysis":False, "plan_sha256":pilot.file_sha(root/"plan.json"),
            "catalogue_sha256":plan["catalogue_sha256"],"prompt_sha256":plan["prompt_sha256"],
            "source_sha256s":plan["source_sha256s"],"cli_version":plan["cli_version"],"frozen_at":plan["frozen_at"],
            "rows":rows,"design":"One fresh hosted CLI call per requested configuration, same six cases in one prompt. "
            "Three initially correct and three defective tables. Tasks share a context; per-configuration timing is a single observation. "
            "Elapsed duration includes CLI startup and network; cache-hit tokens and reasoning tokens are components of input and output. "
            "Missing task outcomes retain their observed denominators. Model and reasoning effort are requested settings; server execution is not attested. "
            "This panel measures functionality. Wall-clock seconds are not a price or a measure of local model compute."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command",required=True)
    for name in ("freeze","collect","report"):
        options = sub.add_parser(name)
        options.add_argument("--root",required=True,type=Path)
        if name == "freeze":
            options.add_argument("--catalog",type=Path,default=Path.home()/".codex"/"models_cache.json")
            options.add_argument("--timeout",type=int,default=420)
        elif name == "collect":
            options.add_argument("--workers",type=int,choices=(1,2),default=1)
            options.add_argument("--limit",type=int)
        else:
            options.add_argument("--output",type=Path)
    args = parser.parse_args()
    root = pilot.private_path(args.root)
    if args.command == "freeze":
        result = freeze(root,args.catalog,args.timeout)
    elif args.command == "collect":
        result = collect(root,args.workers,args.limit)
    else:
        result = report(root)
        if args.output:
            pilot.record(args.output,result)
            result = {"rows":len(result["rows"]),"reported":str(args.output)}
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()

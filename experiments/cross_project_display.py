"""Freeze and replay one-turn, current-output controls on both Python variant menus."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import fcntl
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from experiments import checker_timing_dateutil as dateutil
from experiments import checker_timing_pilot as prior
from experiments import checker_timing_pprint as pprint
from experiments import pprint_display_fork as display

cli = prior.cli
PUBLIC = prior.ROOT / "analysis/cross_project_display_20261128"
PRIVATE = prior.ROOT / ".local_private/cross_project_display_20261128"
DESIGN = "docs/CROSS_PROJECT_DISPLAY_20261128.md"
SOURCES = (DESIGN, "experiments/cross_project_display.py", "experiments/pprint_display_fork.py",
           "analysis/checker_timing_20261126/calibration.json", *prior.SOURCES)
ARMS = ("none", "shared", "revealing")
MODELS = ("gpt-6.2-astra", "gpt-6-luna")
SEED = 2026112802
DATE_PROBES = {"shared": "2025-02-16T11:34:52+03:20", "revealing": "2025-02-16T11:34:52-03:20"}
PPRINT_PROBES = {"shared": {3: "amber", 7: "cobalt"}, "revealing": {20: "cobalt", 3: "amber"}}
SPEC = {
    "dateutil": ("A Python ISO datetime parser must preserve the local calendar time and the signed UTC offset "
                 "written in the input. The code shown is the active return statement in _parse_tzstr for nonzero "
                 "numeric offsets. Bounds have already been checked. Hours and minutes are unsigned integers, "
                 "mult is -1 for a minus sign or +1 for a plus sign, and tz.tzoffset takes signed seconds."),
    "cpython": ("A Python pretty-printer renders dictionaries of literal keys and values into a readable Python "
                "representation. Reading the output back must preserve every key/value binding. Mutually comparable "
                "keys must appear in native ascending order. The order among incomparable keys is unspecified. "
                "In _safe_repr, the surrounding code renders each pair from items. _safe_key compares by native "
                "order when possible and falls back to type name and object identity for incomparable objects. "
                "_safe_tuple applies _safe_key to both parts of an item.")
}


def date_display(value):
    return f"wall time {value['wall']}, UTC offset {value['offset_seconds']} seconds"


def measure_dateutil():
    # Execute in a fresh interpreter: _measure loads the verified archive's tz package.
    frozen = prior.read(prior.PUBLIC / "calibration.json")["dateutil"]
    if set(DATE_PROBES.values()) & set(dateutil.HIDDEN_TEXTS):
        raise ValueError("Displayed timestamp overlaps a held-out input")
    with TemporaryDirectory() as folder:
        working = Path(folder).resolve()
        card = dateutil._measure(prior.CACHE, working)
        if card != frozen:
            raise ValueError("Original dateutil grading or source changed")
        source = (working / "dateutil/parser/isoparser.py").read_text()
        if source.count(dateutil.RETURNS["k3"]) != 1:
            raise ValueError("Unexpected dateutil edit site")
        variants = {}
        for name, row in card["variants"].items():
            edited = source.replace(dateutil.RETURNS["k3"], row["snippet"])
            namespace = {"__name__": "bounded_dateutil_isoparser"}
            exec(compile(edited, dateutil.PARSER, "exec"), namespace)
            outputs = {arm: date_display(dateutil.projection(namespace["isoparse"](text)))
                       for arm, text in DATE_PROBES.items()}
            variants[name] = {"snippet": row["snippet"], "correct": row["correct"],
                              "checks": row["details"]["hidden_inputs"], "outputs": outputs}
    return {"parent_commit": card["provenance"]["parent"], "inputs": DATE_PROBES,
            "variants": variants, "reference_variant": "k3",
            "reference_outputs": {arm: date_display(dateutil.projection(datetime.fromisoformat(text)))
                                  for arm, text in DATE_PROBES.items()}}


def measure_cpython():
    frozen = prior.read(prior.PUBLIC / "calibration.json")["cpython"]
    revision, files = pprint.parent_sources(prior.CACHE)
    variants = {}
    for name, snippet in pprint.OPTIONS.items():
        render = pprint.render_function(files["Lib/pprint.py"], snippet)
        checks = pprint.held_out(render)
        row = frozen["variants"][name]
        if row["snippet"] != snippet or row["details"]["held_out"] != checks:
            raise ValueError("Original CPython grading or source changed")
        variants[name] = {"snippet": snippet, "correct": row["correct"], "checks": checks,
                          "outputs": {arm: render(mapping) for arm, mapping in PPRINT_PROBES.items()}}
    return {"parent_commit": revision, "inputs": {arm: repr(mapping) for arm, mapping in PPRINT_PROBES.items()},
            "variants": variants, "reference_variant": "p7",
            "reference_outputs": {arm: repr(dict(sorted(mapping.items()))) for arm, mapping in PPRINT_PROBES.items()}}


def make_prompt(project, current, options, card, arm):
    text = SPEC[project] + "\nCurrent implementation:\n" + card["variants"][current]["snippet"] + "\n"
    if arm != "none":
        text += ("Execution of the current implementation.\nInput: " + card["inputs"][arm]
                 + "\nOutput: " + card["variants"][current]["outputs"][arm] + "\n")
    menu = {"keep": "Retain the current implementation."}
    menu.update({label: card["variants"][variant]["snippet"] for label, variant in options.items()
                 if variant != current})
    return (text + "You have one decision. Keep the current implementation or choose a replacement to satisfy "
            "the documented behavior.\nAllowed choices:\n" + json.dumps(menu)
            + '\nReturn only one JSON object {"action":"ID"} with an allowed ID. No tools or explanation.\n').encode()


def materials():
    raw = subprocess.check_output([sys.executable, "-B", "-m", "experiments.cross_project_display",
                                   "measure-dateutil"], cwd=prior.ROOT)
    projects = {"dateutil": json.loads(raw), "cpython": measure_cpython()}
    rng = random.Random(SEED)
    groups = defaultdict(list)
    prompts = {}
    for project, card in projects.items():
        for name, variant in card["variants"].items():
            check_key = "pass" if project == "dateutil" else "passed"
            if (len(variant["checks"]) != 6 or all(c[check_key] for c in variant["checks"]) != variant["correct"]
                    or variant["outputs"]["shared"] != card["reference_outputs"]["shared"]
                    or (variant["outputs"]["revealing"] == card["reference_outputs"]["revealing"]) != variant["correct"]):
                raise ValueError(f"{project} {name} failed probe or oracle calibration")
            for model in MODELS:
                key = f"{model}_{project}_{name}"
                choices = sorted(card["variants"])
                rng.shuffle(choices)
                options = {f"v{n}": source for n, source in enumerate(choices, 1)}
                hashes = {}
                for arm in ARMS:
                    prompt = make_prompt(project, name, options, card, arm)
                    prompts[key, arm] = prompt
                    hashes[arm] = prior.digest(prompt)
                item = {"parent_id": key, "project": project, "model": model, "before_variant": name,
                        "before_correct": variant["correct"], "base_prompt_sha256": hashes["none"],
                        "history_sha256": hashes["none"], "options": options, "prompt_sha256": hashes}
                groups[project, variant["correct"]].append(item)
    blocks = []
    base = rng.sample(ARMS, 3)
    for group in sorted(groups):
        members = groups[group]
        rng.shuffle(members)
        for item in members:
            offset = len(blocks) % 3
            blocks.append({**item, "order": base[offset:] + base[:offset]})
    rng.shuffle(blocks)
    cal = {"projects": projects, "grading": "All six previously fixed project-specific functional checks"}
    plan = {"design": DESIGN, "seed": SEED, "arms": list(ARMS), "eligible_for_main_analysis": False,
            "source_sha256": {path: cli.file_sha(prior.ROOT / path) for path in SOURCES},
            "calibration_sha256": prior.digest(prior.pretty(cal)), "blocks": blocks}
    return plan, cal, prompts


def freeze():
    plan, cal, _ = materials()
    launcher = str(Path(shutil.which("codex")).resolve())
    login = subprocess.run([launcher, "login", "status"], capture_output=True, text=True, check=True,
                           env=cli.child_environment("codex"))
    if "Logged in using ChatGPT" not in login.stdout + login.stderr:
        raise ValueError("ChatGPT subscription required")
    prior.persist(PUBLIC / "calibration.json", prior.pretty(cal))
    prior.persist(PUBLIC / "plan.json", prior.pretty(plan))
    stamp = {"plan_sha256": cli.file_sha(PUBLIC / "plan.json"), "launcher": launcher,
             "launcher_sha256": cli.file_sha(Path(launcher)),
             "version": subprocess.check_output([launcher, "--version"], text=True).strip(),
             "auth_mode": "CHATGPT_LOGIN"}
    path = PRIVATE / "frozen.json"
    if not path.exists():
        cli.record(path, {**stamp, "utc": cli.now()})
    elif any(prior.read(path)[k] != v for k, v in stamp.items()):
        raise ValueError("Conflicting freeze")
    print("Frozen", stamp["plan_sha256"])


def load():
    plan, cal, prompts = materials()
    meta = prior.read(PRIVATE / "frozen.json")
    if ((PUBLIC / "plan.json").read_bytes() != prior.pretty(plan)
            or (PUBLIC / "calibration.json").read_bytes() != prior.pretty(cal)
            or meta["plan_sha256"] != cli.file_sha(PUBLIC / "plan.json")):
        raise ValueError("Materials differ from freeze")
    return plan, cal, prompts, meta


def run(collect):
    plan, cal, prompts, meta = load()
    if collect and cli.file_sha(Path(meta["launcher"])) != meta["launcher_sha256"]:
        raise ValueError("Frozen launcher changed")
    rows = []
    with (PRIVATE / ".lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for item in plan["blocks"]:
            key, project = item["parent_id"], item["project"]
            for arm in item["order"]:
                path, prompt = PRIVATE / "calls" / key / arm, prompts[key, arm]
                if collect and not path.exists():
                    prior.check_memory()
                    path.mkdir(parents=True, mode=0o700)
                    argv = prior.command_for(meta["launcher"], item["model"])
                    cli.write(path / "prompt.txt", prompt)
                    cli.record(path / "start.json", {"parent_id": key, "arm": arm, "utc": cli.now(),
                                                    "prompt_sha256": prior.digest(prompt), "argv": argv})
                    cli.record(path / "process.json", cli._launch(argv, prompt, path, "codex", prior.TIMEOUT))
                row = display.score(item, arm, path, prompt, cal["projects"][project], meta)
                row.update(project=project, base_prompt_sha256=item["base_prompt_sha256"])
                if row["status"] not in ("INTERRUPTED", "UNSTARTED"):
                    if collect:
                        prior.persist(path / "event.json", prior.pretty(row))
                    elif row != prior.read(path / "event.json"):
                        raise ValueError("Native replay differs from stored decision")
                if collect:
                    print(key, arm, row["status"], flush=True)
                    if row["status"] in prior.codex.ACCOUNT_ERRORS:
                        raise RuntimeError(row["status"])
                rows.append(row)
    if not collect:
        prior.persist(PUBLIC / "results.json", prior.pretty({
            "plan_sha256": meta["plan_sha256"], "frozen_at_utc": meta["utc"], "cli_version": meta["version"],
            "auth_mode": meta["auth_mode"], "eligible_for_main_analysis": False, "rows": rows}))
        print(dict(Counter(row["status"] for row in rows)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("freeze", "collect", "export", "measure-dateutil"))
    stage = parser.parse_args().stage
    if stage == "measure-dateutil":
        print(json.dumps(measure_dateutil()))
    elif stage == "freeze":
        freeze()
    else:
        run(collect=stage == "collect")

"""Freeze, collect and replay matched CPython continuations with or without new output."""
import argparse
from collections import Counter, defaultdict
import fcntl
from pathlib import Path
import random
import shutil
import subprocess

from experiments import checker_timing_pilot as prior
from experiments import pprint_postedit_fork as previous
from experiments import pprint_postedit_probes as probes

cli = prior.cli
PUBLIC = prior.ROOT / "analysis/pprint_display_20261128"
PRIVATE = prior.ROOT / ".local_private/pprint_display_20261128"
DESIGN = "docs/PPRINT_DISPLAY_20261128.md"
ARMS = ("none", "shared", "revealing")
INPUTS = {"shared": {7: "cobalt", 3: "amber"}, "revealing": {20: "cobalt", 3: "amber"}}
SEED = 20261128


def materials():
    calibration = probes.calibrate(prior.CACHE)
    if calibration != prior.read(previous.PUBLIC / "calibration.json"):
        raise ValueError("Held-out scores differ from the original ten checks")
    _, files = probes.historical.parent_sources(prior.CACHE)
    calibration["inputs"] = {arm: repr(data) for arm, data in INPUTS.items()}
    for variant in calibration["variants"].values():
        render = probes.historical.render_function(files["Lib/pprint.py"], variant["snippet"])
        variant["outputs"] = {arm: render(data) for arm, data in INPUTS.items()}
    variants = calibration["variants"]
    for correct in ("p5", "p7"):
        for arm in INPUTS:
            agree = variants["p3"]["outputs"][arm] == variants[correct]["outputs"][arm]
            if agree != (arm == "shared"):
                raise ValueError("Probe does not have the assigned discrimination")
    rng = random.Random(SEED)
    groups = defaultdict(list)
    prompts = {}
    for row, step, history in previous.parents():
        key, current = row["episode_id"], step["after_variant"]
        if any(text.encode() in history for text in calibration["inputs"].values()):
            raise ValueError("A probe was visible in the archived exchange")
        hashes = {}
        for arm in ARMS:
            shown = "shared" if arm == "none" else arm
            text = previous.make_prompt(history, variants, calibration["inputs"], current, row["options"], shown)
            if arm == "none":
                paragraph = ("The following execution was performed on this CURRENT implementation.\n"
                             f"Input: {INPUTS[shown]}\nFormatted output: {variants[current]['outputs'][shown]}\n").encode()
                if text.count(paragraph) != 1:
                    raise ValueError("Cannot isolate the post-edit execution")
                text = text.replace(paragraph, b"")
            prompts[key, arm] = text
            hashes[arm] = prior.digest(text)
        groups[row["model"], step["correct_after"]].append({
            "parent_id": key, "model": row["model"], "before_variant": current,
            "before_correct": step["correct_after"], "options": row["options"],
            "history_sha256": prior.digest(history), "first_response_sha256": step["native_response_sha256"],
            "prompt_sha256": hashes})
    if Counter((model, good, len(rows)) for (model, good), rows in groups.items()) != Counter([
            ("gpt-6-luna", False, 4), ("gpt-6-luna", True, 4), ("gpt-6.2-astra", True, 8)]):
        raise ValueError("The sixteen preselected CPython checkpoints changed")
    blocks = []
    cycle = rng.sample(ARMS, 3)
    for stratum in sorted(groups):
        members = groups[stratum]
        rng.shuffle(members)
        offset = len(blocks)
        for n, item in enumerate(members):
            order = cycle
            if n // 3 % 2 and n < (len(members) // 3) * 3:
                order = list(reversed(cycle))
            start = (offset + n) % 3
            blocks.append({**item, "order": order[start:] + order[:start]})
    rng.shuffle(blocks)
    bound = (DESIGN, "experiments/pprint_display_fork.py", *previous.SOURCE,
             "analysis/pprint_postedit_20261127/calibration.json",
             "analysis/pprint_postedit_20261127/plan.json")
    plan = {"design": DESIGN, "seed": SEED, "arms": list(ARMS), "eligible_for_main_analysis": False,
            "source_sha256": {p: cli.file_sha(prior.ROOT / p) for p in bound},
            "calibration_sha256": prior.digest(prior.pretty(calibration)), "blocks": blocks}
    return plan, calibration, prompts


def freeze():
    plan, calibration, _ = materials()
    launcher = str(Path(shutil.which("codex")).resolve())
    login = subprocess.run([launcher, "login", "status"], capture_output=True, text=True,
                           env=cli.child_environment("codex"), check=True)
    if "Logged in using ChatGPT" not in login.stdout + login.stderr:
        raise ValueError("ChatGPT-authenticated subscription required")
    prior.persist(PUBLIC / "calibration.json", prior.pretty(calibration))
    prior.persist(PUBLIC / "plan.json", prior.pretty(plan))
    stamp = {"plan_sha256": cli.file_sha(PUBLIC / "plan.json"), "launcher": launcher,
             "launcher_sha256": cli.file_sha(Path(launcher)),
             "version": subprocess.check_output([launcher, "--version"], text=True).strip(),
             "auth_mode": "CHATGPT_LOGIN"}
    path = PRIVATE / "frozen.json"
    if path.exists():
        if any(prior.read(path)[k] != v for k, v in stamp.items()):
            raise ValueError("Conflicting freeze")
    else:
        cli.record(path, {**stamp, "utc": cli.now()})
    print("Frozen", stamp["plan_sha256"], flush=True)


def load():
    plan, calibration, prompts = materials()
    meta = prior.read(PRIVATE / "frozen.json")
    for name, obj in (("plan", plan), ("calibration", calibration)):
        if (PUBLIC / f"{name}.json").read_bytes() != prior.pretty(obj):
            raise ValueError("Frozen materials changed")
    if meta["plan_sha256"] != cli.file_sha(PUBLIC / "plan.json"):
        raise ValueError("Plan hash changed")
    return plan, calibration, prompts, meta


def score(item, arm, path, prompt, calibration, meta):
    cur = item["before_variant"]
    row = {k: item[k] for k in ("parent_id", "model", "before_variant", "before_correct", "history_sha256")}
    row.update(arm=arm, probe=arm, prompt_sha256=prior.digest(prompt), choice=None, after_variant=None,
               after_correct=None, status="INTERRUPTED" if path.exists() else "UNSTARTED")
    if not (path / "process.json").exists():
        return row
    argv = prior.command_for(meta["launcher"], item["model"])
    launch = prior.read(path / "start.json")
    if (launch["argv"] != argv or launch["arm"] != arm or launch["parent_id"] != item["parent_id"]
            or launch["prompt_sha256"] != row["prompt_sha256"] or (path / "prompt.txt").read_bytes() != prompt):
        raise ValueError("Native prompt or assignment changed")
    proc = prior.read(path / "process.json")
    raw, err = ((path / name).read_bytes() for name in ("stdout.bin", "stderr.bin"))
    if proc["stdout_sha256"] != prior.digest(raw) or proc["stderr_sha256"] != prior.digest(err):
        raise ValueError("Native response hashes changed")
    row.update(native_response_sha256=proc["stdout_sha256"], elapsed_seconds=proc["elapsed_seconds"])
    if proc["error"] or proc["returncode"]:
        row["status"] = prior.codex.failure_kind([(raw+err).decode(errors="replace")], proc["error"] or "CLI_ERROR")
        return row
    try:
        message, _ = cli.extract("codex", raw)
        obj = cli.base.strict(message)
        if set(obj) != {"action"} or not isinstance(obj["action"], str):
            raise ValueError("Expected one action")
        choice = obj["action"]
        after = cur if choice == "keep" else item["options"][choice]
        if choice != "keep" and after == cur:
            raise ValueError("Unlisted option")
    except (TypeError, ValueError, KeyError):
        return {**row, "status": "INVALID_RESPONSE"}
    return {**row, "choice": choice, "after_variant": after,
            "after_correct": calibration["variants"][after]["correct"], "status": "OK"}


def collect():
    plan, calibration, prompts, meta = load()
    if cli.file_sha(Path(meta["launcher"])) != meta["launcher_sha256"]:
        raise ValueError("Frozen launcher changed")
    with (PRIVATE / ".lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for item in plan["blocks"]:
            for arm in item["order"]:
                key = item["parent_id"]
                path = PRIVATE / "calls" / key / arm
                prompt = prompts[key, arm]
                if not path.exists():
                    prior.check_memory()
                    path.mkdir(parents=True, mode=0o700)
                    argv = prior.command_for(meta["launcher"], item["model"])
                    cli.write(path / "prompt.txt", prompt)
                    cli.record(path / "start.json", {"parent_id": key, "arm": arm, "utc": cli.now(),
                                                    "prompt_sha256": prior.digest(prompt), "argv": argv})
                    proc = cli._launch(argv, prompt, path, "codex", prior.TIMEOUT)
                    cli.record(path / "process.json", proc)
                row = score(item, arm, path, prompt, calibration, meta)
                if row["status"] != "INTERRUPTED":
                    prior.persist(path / "event.json", prior.pretty(row))
                print(key, arm, row["status"], flush=True)
                if row["status"] in prior.codex.ACCOUNT_ERRORS:
                    raise RuntimeError(row["status"])


def export():
    plan, calibration, prompts, meta = load()
    rows = []
    for item in plan["blocks"]:
        for arm in item["order"]:
            key = item["parent_id"]
            path = PRIVATE / "calls" / key / arm
            row = score(item, arm, path, prompts[key, arm], calibration, meta)
            if row["status"] not in ("UNSTARTED", "INTERRUPTED") and row != prior.read(path / "event.json"):
                raise ValueError("Native replay differs from event")
            rows.append(row)
    report = {"plan_sha256": meta["plan_sha256"], "frozen_at_utc": meta["utc"], "cli_version": meta["version"],
              "auth_mode": meta["auth_mode"], "eligible_for_main_analysis": False, "rows": rows}
    prior.persist(PUBLIC / "results.json", prior.pretty(report))
    print(dict(Counter(row["status"] for row in rows)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("freeze", "collect", "export"))
    args = parser.parse_args()
    {"freeze": freeze, "collect": collect, "export": export}[args.stage]()

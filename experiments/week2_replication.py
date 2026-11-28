"""Freeze and run the separate weekly cohort using the original native prompt bytes."""
import argparse
from collections import Counter
from datetime import datetime
import fcntl
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

from analysis import feedback_resources
from experiments import output_provenance as captions
from experiments import quix_rule_omission as omission
from experiments import selection_disclosure as disclosure

prior, cli = captions.prior, captions.cli
ROOT = prior.ROOT
PUBLIC = ROOT / "analysis/week2_replication_20261129"
PRIVATE = ROOT / ".local_private/week2_replication_20261129"
C, D, Q, O = "output_provenance", "selection_disclosure", "quix_contract_reversal", "quix_rule_omission"
STUDIES = (C, D, Q, O)
SEED = 2026112901
DESIGN = "docs/FEEDBACK_REPLICATION_20261129.md"
FIRST_CLOSURE = "analysis/feedback_resource_ledger_20261128/collection_status.json"
QUOTA_READER = "experiments/week2_subscription_window.py"


def parent(study):
    return ROOT / "analysis" / (study + "_20261128")


def quota(launcher):
    output = subprocess.check_output([sys.executable, "-B", str(ROOT / QUOTA_READER), launcher],
                                     timeout=35, env=cli.child_environment("codex"))
    q = json.loads(output)
    weekly, = [w for w in q["windows"]["codex"].values() if isinstance(w, dict) and w["windowDurationMins"] == 10080]
    return {"utc": q["utc"], "weekly_reset_epoch": weekly["resetsAt"], "weekly_used_percent": weekly["usedPercent"],
            "included_allowed": q["included_allowed"]}


def original_materials():
    plans = {s: prior.read(parent(s) / "plan.json") for s in STUDIES}
    sources = prior.read(ROOT / "analysis/free_patch_20261128/sources.json")
    return plans, sources, prior.read(parent(Q) / "calibration.json"), prior.read(parent(C) / "calibration.json")


def material(study, block, arm, inputs):
    _, sources, quix_cal, _ = inputs
    if study in (Q, O):
        fn = omission.original.study.prompt if study == Q else omission.prompt
        return fn(block, arm, sources, quix_cal)
    item, = [v for v in block["calls"] if v["id"] == arm]
    fn = captions.prompt if study == C else disclosure.prompt
    return fn(block["task"], block["start"], item["label"], item["value_contract"])


def designs(inputs):
    plans = inputs[0]
    rng = random.Random(SEED)
    captions_order = [b["id"] for b in plans[C]["blocks"] if b["wave"] == 1]
    rng.shuffle(captions_order)
    families = sorted({b["model"] for b in plans[Q]["blocks"]})
    groups = [[b["id"] for b in plans[Q]["blocks"] if b["model"] == f] for f in families]
    for group in groups:
        rng.shuffle(group)
    if len(captions_order) != 8 or [len(g) for g in groups] != [8, 8]:
        raise ValueError("Parent block roster changed")
    lookup = {(s, b["id"]): b for s, p in plans.items() for b in p["blocks"]}
    assignments = []
    for wave, caption in enumerate(captions_order, 1):
        wave_rows = []
        members = [(C, caption), (D, caption)] + [(s, g[wave-1]) for g in groups for s in (Q, O)]
        for s, name in members:
            b = lookup[s, name]
            if s in (C, D):
                hashes = {v["id"]: v["prompt_sha256"] for v in b["calls"] if s == C or v["label"] == "disclosed"}
            else:
                hashes = {arm: b["prompt_sha256"][arm] for arm in ("upstream", "alternative")}
            for arm, digest in hashes.items():
                if prior.digest(material(s, b, arm, inputs)) != digest:
                    raise ValueError("Original prompt bytes changed")
                wave_rows.append({"study": s, "block": name, "arm": arm, "prompt_sha256": digest,
                                  "wave": wave, **{k: b[k] for k in ("model", "task", "start")}})
        if len(wave_rows) != 17:
            raise ValueError("Expected a complete wave")
        rng.shuffle(wave_rows)
        assignments.extend(wave_rows)
    for i, row in enumerate(assignments, 1):
        row["index"] = i
    if Counter(r["study"] for r in assignments) != {C: 56, D: 16, Q: 32, O: 32}:
        raise ValueError("Incorrect schedule")
    return assignments, lookup


def bindings(plans):
    files = {DESIGN, QUOTA_READER, FIRST_CLOSURE, "experiments/week2_replication.py", "analysis/feedback_resources.py"}
    for s, plan in plans.items():
        files.update(plan["source_sha256"])
        files.update(str((parent(s) / f).relative_to(ROOT)) for f in ("plan.json", "results.json"))
        cal = parent(s) / "calibration.json"
        if cal.exists():
            files.add(str(cal.relative_to(ROOT)))
    return {f: cli.file_sha(ROOT / f) for f in sorted(files)}


def freeze():
    inputs = original_materials()
    schedule, _ = designs(inputs)
    exe = str(Path(shutil.which("codex")).resolve())
    auth = subprocess.run([exe, "login", "status"], capture_output=True, text=True, check=True,
                          env=cli.child_environment("codex"))
    if "logged in using chatgpt" not in (auth.stdout + auth.stderr).lower():
        raise ValueError("Included subscription login required")
    q = quota(exe)
    expected = int(datetime.fromisoformat(prior.read(ROOT / FIRST_CLOSURE)["reported_current_window_end_utc"]).timestamp())
    if q["weekly_reset_epoch"] != expected or not q["included_allowed"] or q["weekly_used_percent"] >= 100:
        raise RuntimeError("Expected new included weekly window is unavailable")
    plan = {"schema_version": 1, "cohort": "week2_replication_20261129", "design": DESIGN, "seed": SEED,
            "eligible_for_main_analysis": False, "effort": "low", "weekly_reset_epoch": expected,
            "source_sha256": bindings(inputs[0]), "assignments": schedule}
    prior.persist(PUBLIC / "plan.json", prior.pretty(plan))
    core = {"plan_sha256": cli.file_sha(PUBLIC / "plan.json"),
            "cli_version": subprocess.check_output([exe, "--version"], text=True).strip(),
            "launcher_sha256": cli.file_sha(Path(exe)), "auth_mode": "CHATGPT_LOGIN"}
    initial = PRIVATE / "frozen.json"
    if initial.exists():
        receipt = prior.read(initial)
        if receipt["launcher"] != exe or any(receipt[k] != v for k, v in core.items()):
            raise ValueError("Previous freeze differs")
    else:
        receipt = {**core, "launcher": exe, "opening": q, "frozen_at_utc": cli.now()}
        cli.record(initial, receipt)
    prior.persist(PUBLIC / "freeze.json", prior.pretty({k: v for k, v in receipt.items() if k != "launcher"}))
    print("Frozen", len(schedule), "assignments", core["plan_sha256"], flush=True)


def replay(a, block, data, inputs, meta, path):
    s, arm = a["study"], a["arm"]
    if s in (C, D):
        call, = [v for v in block["calls"] if v["id"] == arm]
        fn = captions.outcome if s == C else disclosure.outcome
        outcome = fn(block, call, path, inputs[3], meta)
    else:
        outcome = omission.outcome(block, arm, data, inputs[2], meta, path)
    row = {**outcome, **a, "native_response_sha256": outcome.get("native_response_sha256"),
           "elapsed_seconds": outcome.get("elapsed_seconds"), "dispatch_utc": None, "finished_utc": None, "usage": None}
    if (path / "start.json").exists():
        start = prior.read(path / "start.json")
        row["dispatch_utc"] = start["utc"]
        if start["quota"]["weekly_reset_epoch"] != meta["opening"]["weekly_reset_epoch"]:
            raise ValueError("Dispatch used another weekly period")
    if (path / "process.json").exists():
        row.update(finished_utc=prior.read(path / "process.json")["finished_utc"],
                   usage=feedback_resources.usage_line((path / "stdout.bin").read_bytes()))
    return row


def run(collect):
    inputs = original_materials()
    schedule, lookup = designs(inputs)
    meta = prior.read(PRIVATE / "frozen.json")
    plan = prior.read(PUBLIC / "plan.json")
    if (cli.file_sha(PUBLIC / "plan.json") != meta["plan_sha256"] or schedule != plan["assignments"] or
            bindings(inputs[0]) != plan["source_sha256"] or (collect and
            cli.file_sha(Path(meta["launcher"])) != meta["launcher_sha256"])):
        raise ValueError("Frozen schedule, materials or launcher changed")
    with (PRIVATE / ".lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rows = []
        stop = None
        for a in schedule:
            b = lookup[a["study"], a["block"]]
            data = material(a["study"], b, a["arm"], inputs)
            path = PRIVATE / "calls" / str(a["index"])
            if collect and not path.exists() and stop is None:
                prior.check_memory()
                q = quota(meta["launcher"])
                if (q["weekly_reset_epoch"] != plan["weekly_reset_epoch"] or not q["included_allowed"] or
                        q["weekly_used_percent"] >= 100 or time.time() + prior.TIMEOUT >= q["weekly_reset_epoch"]):
                    stop = "INCLUDED_WINDOW_UNAVAILABLE"
                else:
                    argv = prior.command_for(meta["launcher"], a["model"])
                    path.mkdir(parents=True, mode=0o700)
                    cli.write(path / "prompt.txt", data)
                    cli.record(path / "start.json", {"utc": cli.now(), "argv": argv, "block": b["id"],
                               "arm": a["arm"], "call_id": a["arm"], "prompt_sha256": a["prompt_sha256"], "quota": q})
                    proc = cli._launch(argv, data, path, "codex", prior.TIMEOUT)
                    cli.record(path / "process.json", {**proc, "finished_utc": cli.now()})
            row = replay(a, b, data, inputs, meta, path)
            if row["native_response_sha256"] is not None:
                prior.persist(path / "event.json", prior.pretty(row))
                if collect:
                    print(a["index"], row["status"], flush=True)
            if row["status"] in prior.codex.ACCOUNT_ERRORS:
                stop = row["status"]
            rows.append(row)
        if collect:
            closing = PRIVATE / "closing.json"
            if not closing.exists():
                cli.record(closing, {"reason": stop or "SCHEDULE_COMPLETED", "closing": quota(meta["launcher"])})
        else:
            closing = prior.read(PRIVATE / "closing.json")
            ledger = {k: meta[k] for k in ("cli_version", "auth_mode", "plan_sha256", "frozen_at_utc")}
            ledger.update(eligible_for_main_analysis=False, rows=rows, collection=closing)
            prior.persist(PUBLIC / "results.json", prior.pretty(ledger))
            print(dict(Counter(r["status"] for r in rows)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "collect", "export"))
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    else:
        run(args.action == "collect")

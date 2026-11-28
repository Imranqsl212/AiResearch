"""Collect duplicate native responses to the same archived CPython prompts."""
import argparse
from collections import Counter, defaultdict
import fcntl
from pathlib import Path
import random
import shutil
import subprocess
import time
from experiments import checker_timing_pilot as prior
from experiments import feedback_factorial as factorial
from experiments import pprint_display_fork as display

cli = prior.cli
PUBLIC = prior.ROOT / "analysis/replicate_display_20261128"
PRIVATE = prior.ROOT / ".local_private/replicate_display_20261128"
LANE = prior.ROOT / ".local_private/feedback_cycle_quota/native.lock"
WINDOW = 1795890789
DESIGN = "docs/REPLICATE_DISPLAY_20261128.md"
LABELS = ("none1","none2","shared1","shared2")
SEED = 2026112817


def materials():
    parent = prior.read(display.PUBLIC / "plan.json")
    groups = defaultdict(list)
    rng = random.Random(SEED)
    for block in parent["blocks"]:
        groups[block["model"],block["before_correct"]].append(block)
    for group in groups.values():
        rng.shuffle(group)
    luna = "gpt-6-luna"
    astra = "gpt-6.2-astra"
    blocks = []
    for i in range(4):
        wave = [groups[luna,False][i],groups[luna,True][i],*groups[astra,True][2*i:2*i+2]]
        rng.shuffle(wave)
        for block in wave:
            blocks.append({**block,"wave":i+1,"assignments":rng.sample(LABELS,len(LABELS))})
    paths = (DESIGN,"experiments/replicate_display.py","experiments/feedback_factorial.py",
             "experiments/pprint_display_fork.py","analysis/pprint_display_20261128/plan.json",
             "analysis/pprint_display_20261128/calibration.json")
    return {"design":DESIGN,"seed":SEED,"included_window_end":WINDOW,"eligible_for_main_analysis":False,
            "source_sha256":{p:cli.file_sha(prior.ROOT/p) for p in paths},"blocks":blocks}


def original_prompt(block, arm):
    path = display.PRIVATE / "calls" / block["parent_id"] / arm / "prompt.txt"
    prompt = path.read_bytes()
    if prior.digest(prompt) != block["prompt_sha256"][arm]:
        raise ValueError("Original prompt differs from bound assignment")
    return prompt


def freeze():
    plan=materials()
    if len(plan["blocks"])!=16 or len({b["parent_id"] for b in plan["blocks"]})!=16:
        raise ValueError("Expected sixteen distinct parent histories")
    for b in plan["blocks"]:
        for arm in ("none","shared"):
            original_prompt(b,arm)
    executable=Path(shutil.which("codex")).resolve()
    auth=subprocess.run([str(executable),"login","status"],capture_output=True,text=True,check=True,env=cli.child_environment("codex"))
    if "logged in using chatgpt" not in (auth.stdout+auth.stderr).lower() or factorial.quota()!=WINDOW:
        raise ValueError("Current included subscription required")
    prior.persist(PUBLIC/"plan.json",prior.pretty(plan))
    meta={"plan_sha256":cli.file_sha(PUBLIC/"plan.json"),"launcher":str(executable),"launcher_sha256":cli.file_sha(executable),
          "auth_mode":"CHATGPT_LOGIN","version":subprocess.check_output([str(executable),"--version"],text=True).strip()}
    receipt=PRIVATE/"frozen.json"
    if receipt.exists():
        if any(prior.read(receipt)[k]!=v for k,v in meta.items()):
            raise ValueError("Conflicting receipt")
    else:
        cli.record(receipt,{**meta,"utc":cli.now()})
    print(meta["plan_sha256"])


def run(stage):
    plan=prior.read(PUBLIC/"plan.json")
    meta=prior.read(PRIVATE/"frozen.json")
    if plan!=materials() or cli.file_sha(PUBLIC/"plan.json")!=meta["plan_sha256"]:
        raise ValueError("Plan drift")
    if stage=="collect" and cli.file_sha(Path(meta["launcher"]))!=meta["launcher_sha256"]:
        raise ValueError("Launcher changed")
    calibration=prior.read(display.PUBLIC/"calibration.json")
    rows=[]
    with LANE.open("a+b") as lock:
        if stage=="collect":
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for block in plan["blocks"]:
            for assignment in block["assignments"]:
                arm=assignment[:-1]
                path=PRIVATE/"calls"/block["parent_id"]/assignment
                prompt=original_prompt(block,arm)
                if stage=="collect" and not path.exists():
                    if time.time()+prior.TIMEOUT>=WINDOW or factorial.quota()!=WINDOW:
                        raise RuntimeError("End of current included usage")
                    prior.check_memory()
                    argv=prior.command_for(meta["launcher"],block["model"])
                    path.mkdir(parents=True,mode=0o700)
                    cli.write(path/"prompt.txt",prompt)
                    cli.record(path/"start.json",{"parent_id":block["parent_id"],"arm":arm,"assignment":assignment,
                               "utc":cli.now(),"prompt_sha256":prior.digest(prompt),"argv":argv})
                    cli.record(path/"process.json",cli._launch(argv,prompt,path,"codex",prior.TIMEOUT))
                row=display.score(block,arm,path,prompt,calibration,meta)
                row["assignment"]=assignment
                if (path/"start.json").is_file() and prior.read(path/"start.json")["assignment"]!=assignment:
                    raise ValueError("Native replicate ID differs")
                if row["status"] not in ("UNSTARTED","INTERRUPTED"):
                    prior.persist(path/"event.json",prior.pretty(row))
                rows.append(row)
                if stage=="collect":
                    print(len(rows),block["parent_id"],assignment,row["status"],flush=True)
                    if row["status"] in prior.codex.ACCOUNT_ERRORS:
                        raise RuntimeError(row["status"])
    if stage!="collect":
        counts=Counter(r["status"] for r in rows)
        path=PUBLIC/"results.json" if stage=="export" else PRIVATE/"snapshots"/f"{len(rows)-counts['UNSTARTED']}.json"
        prior.persist(path,prior.pretty({"plan_sha256":meta["plan_sha256"],"auth_mode":meta["auth_mode"],
               "cli_version":meta["version"],"frozen_at_utc":meta["utc"],"eligible_for_main_analysis":False,"rows":rows}))
        print(counts)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("freeze","collect","snapshot","export"))
    args=parser.parse_args()
    if args.stage=="freeze":
        freeze()
    else:
        run(args.stage)

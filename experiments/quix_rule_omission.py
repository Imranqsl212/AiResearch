"""Repeat the target-conditioned QuixBugs choices after deleting only the two convention lines."""
import argparse
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from experiments import quix_contract_reversal as original

prior, cli, core = original.prior, original.cli, original.core
ROOT = core.ROOT
PUBLIC = ROOT / "analysis/quix_rule_omission_20261128"
PRIVATE = ROOT / ".local_private/quix_rule_omission_20261128"
DESIGN = "docs/QUIX_RULE_OMISSION_20261128.md"
BOUND = (DESIGN, "experiments/quix_rule_omission.py", "analysis/quix_contract_reversal_20261128/plan.json",
         "analysis/quix_contract_reversal_20261128/calibration.json", *original.BOUND)


def prompt(block, arm, sources, calibration):
    full = original.study.prompt(block, arm, sources, calibration)
    lines = full.splitlines(keepends=True)
    removed = [line for line in lines if line.startswith((b"Convention 1:", b"Convention 2:"))]
    if len(removed) != 2 or not removed[0].startswith(b"Convention 1:") or not removed[1].startswith(b"Convention 2:"):
        raise ValueError("Expected exactly two consecutive convention descriptions")
    if removed[0] + removed[1] not in full:
        raise ValueError("Convention descriptions are not consecutive")
    return full.replace(removed[0] + removed[1], b"", 1)


def materials():
    named, sources, cal = original.materials()
    if prior.pretty(named) != (original.PUBLIC / "plan.json").read_bytes():
        raise ValueError("Original named-rule plan changed")
    blocks = []
    for old in named["blocks"]:
        b = {k: old[k] for k in ("id", "model", "task", "start", "wave", "rule_order")}
        b["order"] = [arm for arm in old["order"] if arm in original.study.TARGETS]
        b["prompt_sha256"] = {}
        for arm in b["order"]:
            if prior.digest(original.study.prompt(b, arm, sources, cal)) != old["prompt_sha256"][arm]:
                raise ValueError("Named prompt differs from frozen copy")
            b["prompt_sha256"][arm] = prior.digest(prompt(b, arm, sources, cal))
        blocks.append(b)
    return {"design": DESIGN, "eligible_for_main_analysis": False, "effort": "low",
            "included_window_end": core.RESET, "blocks": blocks, "source_sha256": {k: cli.file_sha(ROOT/k) for k in BOUND}}, sources, cal


def freeze():
    plan, _, _ = materials()
    launcher = str(Path(shutil.which("codex")).resolve())
    login = subprocess.run([launcher, "login", "status"], capture_output=True, text=True, check=True, env=cli.child_environment("codex"))
    if "logged in using chatgpt" not in (login.stdout + login.stderr).lower():
        raise ValueError("Subscription login required")
    prior.persist(PUBLIC/"plan.json", prior.pretty(plan))
    meta = {"plan_sha256": cli.file_sha(PUBLIC/"plan.json"), "launcher": launcher,
            "launcher_sha256": cli.file_sha(Path(launcher)), "auth": "CHATGPT_LOGIN",
            "version": subprocess.check_output([launcher, "--version"], text=True).strip()}
    path = PRIVATE/"frozen.json"
    if path.exists():
        if any(prior.read(path)[k] != v for k,v in meta.items()):
            raise ValueError("Conflicting frozen launcher")
    else:
        cli.record(path, {**meta, "utc": cli.now()})
    print("Frozen 32 omitted-rule prompts", meta["plan_sha256"], flush=True)


def load():
    plan, sources, cal = materials()
    meta = prior.read(PRIVATE/"frozen.json")
    if prior.pretty(plan) != (PUBLIC/"plan.json").read_bytes() or cli.file_sha(PUBLIC/"plan.json") != meta["plan_sha256"]:
        raise ValueError("Frozen schedule changed")
    return plan, sources, cal, meta


def outcome(block, arm, data, cal, meta, path):
    row = {k: block[k] for k in ("wave", "task", "start", "model")}
    row.update(block=block["id"], arm=arm, prompt_sha256=prior.digest(data),
               status="INTERRUPTED" if path.exists() else "UNSTARTED", action=None, expression=None,
               implements=None, passed_counts=None)
    if row["prompt_sha256"] != block["prompt_sha256"][arm]:
        raise ValueError("Plan digest differs from reconstructed prompt")
    if not (path/"process.json").exists():
        return row
    args = prior.read(path/"start.json")
    expected = {"argv": prior.command_for(meta["launcher"], block["model"]), "block": block["id"],
                "arm": arm, "prompt_sha256": row["prompt_sha256"]}
    if any(args[k] != v for k,v in expected.items()) or data != (path/"prompt.txt").read_bytes():
        raise ValueError("Native prompt or command changed")
    proc = prior.read(path/"process.json")
    stdout, stderr = [(path/f).read_bytes() for f in ("stdout.bin", "stderr.bin")]
    if prior.digest(stdout) != proc["stdout_sha256"] or prior.digest(stderr) != proc["stderr_sha256"]:
        raise ValueError("Native response changed")
    row.update(native_response_sha256=prior.digest(stdout), elapsed_seconds=proc["elapsed_seconds"])
    if proc["error"] or proc["returncode"]:
        row["status"] = prior.codex.failure_kind([(stdout+stderr).decode(errors="replace")], proc["error"] or "CLI_ERROR")
        return row
    try:
        msg, _ = cli.extract("codex", stdout)
        obj = cli.base.strict(msg)
        if obj == {"action": "keep"}:
            text = cal[block["task"]]["starts"][block["start"]]["expression"]
        elif isinstance(obj, dict) and set(obj) == {"action", "expression"} and obj["action"] == "replace":
            text = obj["expression"]
        else:
            raise ValueError("Invalid model action")
        counts, implementation = original.study.grades(block["task"], text, cal)
    except original.study.base.Rejected:
        return {**row, "status": "INVALID_EXPRESSION"}
    except (ValueError, TypeError, KeyError):
        return {**row, "status": "INVALID_RESPONSE"}
    return {**row, "status": "OK", "action": obj["action"], "expression": text,
            "implements": implementation, "passed_counts": counts}


def run(stage):
    plan, sources, cal, meta = load()
    rows = []
    if stage == "collect" and cli.file_sha(Path(meta["launcher"])) != meta["launcher_sha256"]:
        raise ValueError("Launcher changed after freeze")
    with (core.QUOTA/"native.lock").open("a+b") as lock:
        if stage == "collect":
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for b in plan["blocks"]:
            for arm in b["order"]:
                path = PRIVATE/"calls"/b["id"]/arm
                data = prompt(b, arm, sources, cal)
                if stage == "collect" and not path.exists():
                    prior.check_memory()
                    core.require_remaining()
                    argv = prior.command_for(meta["launcher"], b["model"])
                    path.mkdir(parents=True, mode=0o700)
                    cli.write(path/"prompt.txt", data)
                    cli.record(path/"start.json", {"utc": cli.now(), "argv": argv, "block": b["id"], "arm": arm,
                                                   "prompt_sha256": prior.digest(data)})
                    cli.record(path/"process.json", cli._launch(argv, data, path, "codex", prior.TIMEOUT))
                row = outcome(b, arm, data, cal, meta, path)
                if row["status"] not in ("INTERRUPTED", "UNSTARTED"):
                    if stage == "collect":
                        prior.persist(path/"event.json", prior.pretty(row))
                    elif row != prior.read(path/"event.json"):
                        raise ValueError("Reserved response differs on replay")
                rows.append(row)
                if stage == "collect":
                    print(len(rows), b["id"], arm, row["status"], flush=True)
                    if row["status"] in prior.codex.ACCOUNT_ERRORS or row["status"] == "MODEL_UNAVAILABLE":
                        raise RuntimeError(row["status"])
    if stage == "export":
        named = original.PUBLIC/"results.json"
        if not named.exists():
            raise ValueError("Export the named-rule schedule, including missing statuses, before comparison")
        data = {"plan_sha256": meta["plan_sha256"], "frozen_at_utc": meta["utc"], "cli_version": meta["version"],
                "named_results_sha256": cli.file_sha(named), "eligible_for_main_analysis": False, "rows": rows}
        prior.persist(PUBLIC/"results.json", prior.pretty(data))
        from analysis import quix_rule_omission_report as report
        prior.persist(PUBLIC/"comparison.md", report.report(report.verify(PUBLIC)).encode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("freeze","collect","export"))
    args = parser.parse_args()
    if args.stage == "freeze":
        freeze()
    else:
        run(args.stage)

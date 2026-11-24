"""Collect and replay a blinded Codex CLI model-by-effort comparison on finite data."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import math
from pathlib import Path
import random
import re
import shutil
import subprocess
import threading
import uuid

from experiments import c5_cli_pilot as pilot
from experiments import c5_evidence_challenge as base

VERSION = "c5-codex-effort-v1"
EFFORTS = ("low", "high")
SOURCES = (*pilot.SOURCES, "experiments/c5_codex_effort.py")
USAGE_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
ACCOUNT_ERRORS = {"ACCOUNT_QUOTA", "ACCOUNT_AUTH", "NETWORK_UNAVAILABLE"}
MODEL_RE = re.compile(r"gpt-[a-z0-9][a-z0-9.-]{0,70}")


def roster(catalog):
    models = []
    for item in catalog["models"]:
        if item.get("visibility") != "list":
            continue
        name = item["slug"]
        if not MODEL_RE.fullmatch(name) or name in models:
            raise ValueError("unexpected visible Codex catalog identifier")
        supported = {row["effort"] for row in item["supported_reasoning_levels"]}
        if not set(EFFORTS) <= supported:
            raise ValueError(f"requested common effort level unavailable in catalog: {name}")
        models.append(name)
    if not models:
        raise ValueError("empty Codex catalog")
    return models


def command(launcher, model, effort):
    if not MODEL_RE.fullmatch(model) or effort not in EFFORTS:
        raise ValueError("invalid model or effort")
    # Keep the November pilot's exact subscription CLI settings, replacing its
    # example identifier and adding one explicit, controlled configuration field.
    argv = pilot.command("codex", "gpt-6-sol", launcher)
    argv[argv.index("-m") + 1] = model
    argv[-1:-1] = ["-c", f'model_reasoning_effort="{effort}"']
    return argv


def build(catalog, identity):
    models = roster(catalog)
    old = base.build_plan(seed=20261124)
    cases = [ep for ep in old["episodes"] if ep["task"] == "double"]
    configs = [{"model": model, "effort": effort} for model in models for effort in EFFORTS]
    rng = random.Random(20261125)
    rng.shuffle(cases)
    phases = {model: i % 2 for i, model in enumerate(models)}
    episodes = []
    for wave in range(len(cases)):
        order = list(range(len(models)))
        rng.shuffle(order)
        for i in order:
            model = models[i]
            original = cases[(wave + i) % len(cases)]
            # Pair of efforts receives the same case. Alternate the requested
            # launch order in successive waves, separately within each model.
            efforts = EFFORTS if (phases[model] + wave) % 2 == 0 else EFFORTS[::-1]
            for effort in efforts:
                case_id = original["episode_id"]
                key = pilot.sha(f"{model}/{effort}/{case_id}".encode())[:24]
                episodes.append({**original, "model": model, "effort": effort, "case_id": case_id,
                                 "episode_id": "e-" + key, "wave": wave + 1})
    return {"schema_version": VERSION, "configurations": configs, "episodes": episodes,
            "decision_cap": 3, "check_cost_units": 1, "timeout_seconds": 240,
            "maximum_decisions": len(episodes) * 3, "maximum_workers": 3,
            "cli_identity": identity, "sources": {name: pilot.file_sha(base.ROOT / name) for name in SOURCES},
            "prompt_sha256": pilot.sha(pilot.PROMPT.encode()),
            "eligible_for_main_analysis": False, "tool_policy": "isolated CLI as in November pilot; reject reported tools",
            "configuration": "requested explicit low/high; no provider effort or weights attestation",
            "design": "eight waves; each cell once per wave, same item for low and high of each model"}


def freeze(root, catalog):
    raw = catalog.read_bytes()
    launcher = Path(shutil.which("codex") or "").resolve(strict=True)
    version = subprocess.check_output([launcher, "--version"], text=True).strip()
    auth = subprocess.run([launcher, "login", "status"], capture_output=True, text=True, check=True)
    if "logged in using chatgpt" not in (auth.stdout + auth.stderr).lower():
        raise ValueError("ChatGPT login is required for the subscription-only pilot")
    identity = {"path": str(launcher), "sha256": pilot.file_sha(launcher), "version": version,
                "catalog_sha256": pilot.sha(raw), "login": "CHATGPT",
                "extra_usage_or_billing": "UNVERIFIED", "api_key_fallback": False}
    plan = build(base.strict(raw), identity)
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    pilot.write(root / "catalog.json", raw)
    pilot.record(root / "plan.json", plan)
    for name in SOURCES:
        pilot.write(root / "source_archive" / name, (base.ROOT / name).read_bytes())
    receipt = {"schema_version": VERSION, "frozen_at": pilot.now(),
               "plan_sha256": pilot.file_sha(root / "plan.json"),
               "configurations": len(plan["configurations"]), "scheduled_episodes": len(plan["episodes"]),
               "maximum_decisions": plan["maximum_decisions"], "provider_calls": 0}
    pilot.record(root / "freeze.json", receipt)
    return receipt


def load(root):
    plan = base.read(root / "plan.json")
    sealed = base.read(root / "freeze.json")
    raw = (root / "catalog.json").read_bytes()
    if (sealed["plan_sha256"] != pilot.file_sha(root / "plan.json")
            or plan["cli_identity"]["catalog_sha256"] != pilot.sha(raw)
            or build(base.strict(raw), plan["cli_identity"]) != plan):
        raise ValueError("plan/catalog/source drift")
    if any(pilot.file_sha(root / "source_archive" / name) != sha for name, sha in plan["sources"].items()):
        raise ValueError("archived source drift")
    return plan, sealed


def failure_kind(messages, fallback):
    text = " ".join(messages).lower()
    if any(word in text for word in ("does not support reasoning", "unsupported reasoning", "reasoning effort is not supported",
                                     "unsupported value: 'reasoning", "unsupported value for reasoning")):
        return "EFFORT_UNAVAILABLE"
    if ("model" in text and any(s in text for s in (
            "not supported when using", "do not have access", "not available for", "not available to",
            "not found", "does not exist", "not authorized", "not eligible", "unsupported model",
            "not be available", "requires enrollment", "not enabled", "permission to access"))):
        return "MODEL_UNAVAILABLE"
    if any(s in text for s in ("usage limit", "usage_limit", "insufficient_quota", "quota exceeded",
                               "rate limit", "rate_limit", "too many requests", "429 too many")):
        return "ACCOUNT_QUOTA"
    if any(s in text for s in ("unauthorized", "401 ", "401:", "token has expired", "authentication failed",
                               "invalid_grant", "please log in", "refresh token", "not logged in")):
        return "ACCOUNT_AUTH"
    if any(s in text for s in ("error sending request", "failed to connect", "failed to lookup address",
                               "dns error", "network is unreachable","connection refused")):
        return "NETWORK_UNAVAILABLE"
    return fallback


def event_data(plan, ep, candidate, directory, number):
    process = base.read(directory / "process.json")
    out, err = directory / "stdout.bin", directory / "stderr.bin"
    if process["stdout_sha256"] != pilot.file_sha(out) or process["stderr_sha256"] != pilot.file_sha(err):
        raise ValueError("CLI output hash mismatch")
    duration = process["elapsed_seconds"]
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
        raise ValueError("invalid process duration")
    error = process["error"]
    logs = []
    messages = []
    usage = {key: None for key in USAGE_FIELDS}
    effective = []
    if max(out.stat().st_size, err.stat().st_size) > pilot.MAX_OUTPUT:
        error = "CLI_OUTPUT_LIMIT"
    else:
        raw = out.read_bytes()
        messages.append(err.read_text(errors="replace"))
        try:
            logs = [base.strict(line) for line in raw.splitlines() if line.strip()]
        except (ValueError, UnicodeError):
            error = error or "CLI_OUTPUT_PARSE_FAILURE"
        messages.extend(json.dumps(row) for row in logs if row.get("type") in {"error", "turn.failed"})
        turns = [row for row in logs if row.get("type") == "turn.completed"]
        if len(turns) == 1 and isinstance(turns[0].get("usage"), dict):
            for key in USAGE_FIELDS:
                n = turns[0]["usage"].get(key)
                if type(n) is int and n >= 0:
                    usage[key] = n
        if process["returncode"] != 0 or any(row.get("type") in {"error", "turn.failed"} for row in logs):
            error = failure_kind(messages, error or "CLI_FAILURE")
        if not error:
            try:
                answer, ids = pilot.extract("codex", raw)
                effective = [s for s in ids if MODEL_RE.fullmatch(s)]
            except (ValueError, TypeError, KeyError, UnicodeError):
                error = "CLI_INVALID_OR_TOOL_OUTPUT"
    if error:
        event = pilot._invalid(ep, candidate, number, error)
    else:
        event = base.transition(ep, candidate, answer, number, plan["decision_cap"])
    return {**event, "duration_seconds": duration, "usage": usage, "effective_model_ids": effective,
            "finished_at": process["finished_at"]}


def prompt_for(plan, ep, candidate, history):
    status = "ONGOING" if history else "UNSTARTED"
    view = base.observation(plan, ep, candidate, history, status, len(history))["observation"]
    return pilot.PROMPT.encode() + base.canonical(view) + b"\n"


def limited_event(ep, event, before, start):
    action = event.get("action")
    after = action["payload"]["candidate"] if action and action["action"] == "repair" else before
    return ({"sequence": event["sequence"], "action": action["action"] if action else None,
             "correct_before": base.private.evaluate(ep["task"], before)["functionality_pass"],
             "correct_after": event["private_audit"]["functionality_pass"] if action else None,
             "same_candidate": before == after if action else None, "terminal": event["terminal"],
             "status": event["status"], "error": event.get("error"), "duration_seconds": event.get("duration_seconds"),
             "usage": event.get("usage", {k: None for k in USAGE_FIELDS}),
             "effective_model_ids": event.get("effective_model_ids", []), "started_at": start.get("started_at"),
             "finished_at": event.get("finished_at")}, after)


def replay(root, plan, ep):
    directory = root / "episodes" / ep["episode_id"]
    candidate, history, events = ep["initial_candidate"], [], []
    status = "UNSTARTED"
    for n, path in enumerate(sorted(directory.iterdir()) if directory.exists() else [], 1):
        if path.name != f"d{n}" or n > plan["decision_cap"] or status in {"COMPLETED", "TECHNICAL_INVALID"}:
            raise ValueError("unexpected capture layout or decision after terminal")
        prompt = prompt_for(plan, ep, candidate, history)
        start = base.read(path / "start.json") if (path / "start.json").exists() else {}
        if start and (start["prompt_sha256"] != pilot.sha(prompt) or (path/"prompt.bin").read_bytes() != prompt
                      or start["episode_id"] != ep["episode_id"] or start["sequence"] != n
                      or start["argv"] != command(plan["cli_identity"]["path"], ep["model"], ep["effort"])):
            raise ValueError("request differs from frozen inputs")
        if start and (path / "event.json").is_file():
            if {p.name for p in path.iterdir()} != {"start.json","prompt.bin","process.json","event.json","stdout.bin","stderr.bin"}:
                raise ValueError("unexpected decision artifact")
            event = event_data(plan, ep, candidate, path, n)
            if event != base.read(path/"event.json"):
                raise ValueError("response does not replay")
        else:
            event = pilot._invalid(ep, candidate, n, "INTERRUPTED_CAPTURE_NO_RETRY")
        safe, candidate = limited_event(ep, event, candidate, start)
        events.append(safe)
        status = event["status"]
        history.append({"action":event["action"], "observation":event["observation"]})
    public = {k: ep[k] for k in ("model","effort","episode_id","case_id","pair_id","state","defect","arm","wave")}
    public.update(status=status, events=events, terminal_correct=events[-1]["correct_after"] if status == "COMPLETED" else None)
    return public, candidate, history


def verify_archive(root):
    root = pilot.private_path(root)
    plan, sealed = load(root)
    expected = {ep["episode_id"] for ep in plan["episodes"]}
    folder = root / "episodes"
    if folder.exists() and any(path.name not in expected for path in folder.iterdir()):
        raise ValueError("unknown episode in archive")
    return {"schema_version": VERSION, "plan_sha256": sealed["plan_sha256"], "frozen_at": sealed["frozen_at"],
            "source_sha256s": plan["sources"], "cli_version": plan["cli_identity"]["version"],
            "configurations": plan["configurations"], "eligible_for_main_analysis": False,
            "episodes": [replay(root, plan, ep)[0] for ep in plan["episodes"]]}


def run_episode(root, plan, ep, halt):
    state, candidate, history = replay(root, plan, ep)
    while state["status"] in {"UNSTARTED", "ONGOING"} and not halt.is_set():
        n = len(history) + 1
        path = root / "episodes" / ep["episode_id"] / f"d{n}"
        path.mkdir(parents=True, exist_ok=False, mode=0o700)
        prompt = prompt_for(plan, ep, candidate, history)
        argv = command(plan["cli_identity"]["path"], ep["model"], ep["effort"])
        pilot.write(path / "prompt.bin", prompt)
        pilot.record(path / "start.json", {"episode_id":ep["episode_id"], "sequence":n, "started_at":pilot.now(),
                                     "context_id":str(uuid.uuid4()), "argv":argv, "prompt_sha256":pilot.sha(prompt)})
        process = pilot._launch(argv, prompt, path, "codex", plan["timeout_seconds"])
        pilot.record(path / "process.json", {**process, "finished_at":pilot.now()})
        event = event_data(plan, ep, candidate, path, n)
        pilot.record(path / "event.json", event)
        if event.get("error") in ACCOUNT_ERRORS:
            halt.set()
        state, candidate, history = replay(root, plan, ep)
    return state


def error_of(row):
    return row["events"][-1]["error"] if row["events"] and row["status"] == "TECHNICAL_INVALID" else None


def run(root, *, workers, max_episodes=None, resume_account=False):
    if not 1 <= workers <= 3 or (max_episodes is not None and max_episodes < 1):
        raise ValueError("workers must be 1..3; episode limit must be positive")
    plan, _ = load(root)
    identity = plan["cli_identity"]
    if pilot.file_sha(Path(identity["path"])) != identity["sha256"]:
        raise ValueError("CLI executable changed")
    # The OS releases this lock even if a collector crashes. A decision directory
    # is the durable reservation and an interrupted CLI call is never issued again.
    with (root / ".run.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        blocks = [replay(root, plan, ep)[0] for ep in plan["episodes"]]
        unavailable = {"MODEL_UNAVAILABLE", "EFFORT_UNAVAILABLE"}
        blocked_configs = {(r["model"],r["effort"]) for r in blocks if error_of(r) in unavailable}
        if any(error_of(r) in ACCOUNT_ERRORS for r in blocks) and not resume_account:
            return {"status":"ACCOUNT_OR_NETWORK_HALTED","need_resume_after_access_restored":True}
        halt = threading.Event()
        used = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for wave in range(1,9):
                eligible = [(ep,r) for ep,r in zip(plan["episodes"],blocks)
                            if ep["wave"] == wave and r["status"] in {"UNSTARTED","ONGOING"}]
                for index in range(0,len(eligible),workers):
                    if halt.is_set() or (max_episodes is not None and used >= max_episodes):
                        break
                    batch = [ep for ep,_ in eligible[index:index+workers] if (ep["model"],ep["effort"]) not in blocked_configs]
                    if max_episodes is not None:
                        batch = batch[:max_episodes-used]
                    results = list(pool.map(lambda ep: run_episode(root,plan,ep,halt),batch))
                    used += len(batch)
                    for row in results:
                        error = error_of(row)
                        if error in unavailable:
                            blocked_configs.add((row["model"],row["effort"]))
                        print(json.dumps({k:row[k] for k in ("model","effort","episode_id","status")} |
                                         {"wave":wave,"decisions":len(row["events"]),"error":error}), flush=True)
        return {"status":"ACCOUNT_OR_NETWORK_HALTED" if halt.is_set() else "WINDOW_FINISHED",
                "episodes_in_window":used,"unavailable_configurations":sorted(blocked_configs)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd",required=True)
    for name in ("freeze","run","verify"):
        p = sub.add_parser(name)
        p.add_argument("--root", type=Path, required=True)
        if name == "freeze":
            p.add_argument("--catalog", type=Path, default=Path.home()/".codex/models_cache.json")
        elif name == "run":
            p.add_argument("--workers",type=int,choices=(1,2,3),default=2)
            p.add_argument("--max-episodes",type=int)
            p.add_argument("--resume-after-access-restored",action="store_true")
        else:
            p.add_argument("--output",type=Path)
    args = parser.parse_args()
    root = pilot.private_path(args.root)
    if args.cmd == "freeze":
        result = freeze(root,args.catalog)
    elif args.cmd == "run":
        result = run(root,workers=args.workers,max_episodes=args.max_episodes,
                     resume_account=args.resume_after_access_restored)
    else:
        report = verify_archive(root)
        if args.output:
            pilot.record(args.output,report)
        result = {"plan_sha256":report["plan_sha256"],"statuses":dict(Counter(r["status"] for r in report["episodes"])),
                  "recorded_decisions":sum(len(r["events"]) for r in report["episodes"])}
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()

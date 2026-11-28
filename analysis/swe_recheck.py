"""Recount commands in the selected SWE-bench traces without executing them."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import shlex
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "external_audit_20261122"
PUBLIC = ROOT / "analysis/swe_recheck_20261128"
RULE = ROOT / "docs/SWE_RECHECK_20261128.md"
PLAN = "33f66b54d087213975f1776a33779212ce27a866e0d19d50e3186b024c509d15"
SELECTION = "7b8e1869d1101c0851935686c20e1003f78922bf75840cab17c702d4aa9e23e2"


def digest(data):
    return sha256(data).hexdigest()


def recognized(command, allow_cd=False):
    text = command.strip()
    if allow_cd:
        prefixed = re.fullmatch(r"cd[ \t]+[./a-zA-Z0-9_-]+(?:[ \t]*&&[ \t]*|[ \t]*\n[ \t]*)(.+)", text)
        if prefixed:
            text = prefixed[1]
    if not text or re.search(r"[\n\r;&|`<>$#]", text):
        return False
    try:
        parts = shlex.split(text)
    except ValueError:
        return False
    exe = Path(parts[0]).name if parts else ""
    if exe in {"pytest", "py.test", "runtests.py"}:
        return True
    return (re.fullmatch(r"python(?:3(?:\.\d+)?)?", exe) is not None and len(parts) > 1
            and (parts[1].endswith(".py") or parts[1:3] in (["-m", "pytest"], ["-m", "unittest"])))


def formal_verdict(text):
    plain = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    outcomes = []
    for m in re.finditer(r"(?m)^Ran ([1-9]\d*) tests? in [^\n]+\n\s*(OK|FAILED)(?=[ (\n]|$)", plain):
        outcomes.append((m.start(), "pass" if m[2] == "OK" else "fail"))
    for m in re.finditer(r"(?im)^[ =]*(\d+ (?:passed|failed|errors?|skipped|warnings?|xfailed|xpassed|deselected)(?:, [^\n]+?)?) in [\d.]+s\b[^\n]*$", plain):
        statuses = {label.lower(): int(n) for n,label in re.findall(r"(\d+) ([a-zA-Z]+)", m[1])}
        if any(statuses.get(k, 0) for k in ("failed", "error", "errors")):
            outcomes.append((m.start(), "fail"))
        elif statuses.get("passed", 0):
            outcomes.append((m.start(), "pass"))
    return max(outcomes)[1] if outcomes else None


def events(series, trace):
    if series == "A":
        for i, row in enumerate(trace["trajectory"]):
            yield f"/trajectory/{i}/action", f"/trajectory/{i}/observation", row["action"], row["observation"]
        return
    replies = {m.get("tool_call_id"): (i, m) for i,m in enumerate(trace) if m.get("role") == "tool"}
    for i, msg in enumerate(trace):
        if msg["role"] != "assistant":
            continue
        for n, call in enumerate(msg.get("tool_calls") or []):
            f = call["function"]
            if f["name"] != "execute_bash" or call["id"] not in replies:
                continue
            j, resp = replies[call["id"]]
            if j <= i:
                raise ValueError("Response precedes command")
            args = json.loads(f["arguments"]) if isinstance(f["arguments"], str) else f["arguments"]
            out = "\n".join(c.get("text","") for c in resp["content"] if isinstance(c,dict))
            yield f"/{i}/tool_calls/{n}", f"/{j}/content", args.get("command",""), out


def measure(series, trace, allow_cd=False):
    commands = defaultdict(list)
    for loc, resp, command, out in events(series, trace):
        if not recognized(command, allow_cd):
            continue
        exits = re.findall(r"(?m)^\[Command finished with exit code (-?\d+)\]\s*$", out) if series == "B" else []
        commands[digest(command.strip().encode())].append({
            "invocation":loc, "observation":resp, "output_sha256":digest(out.encode()),
            "verdict":formal_verdict(out), "process_exit":int(exits[-1]) if exits else None})
    return dict(sorted(commands.items()))


def read_rows(cache, fetch, allow_cd=False):
    selection_raw = (AUDIT/"selection.json").read_bytes()
    if digest(selection_raw) != SELECTION or digest(RULE.read_bytes()) != PLAN:
        raise ValueError("Frozen selection or rule changed")
    source_file=PUBLIC/"sources.json"
    if digest(source_file.read_bytes())!="b40d68aff68fc6132e50bbafec6fb89846bbea223499451b97fde90346f58510":
        raise ValueError("Published trace roster changed")
    roster=json.loads(source_file.read_bytes())
    for name, bound in roster["parent_sha256"].items():
        original=AUDIT/name
        if original.is_file() and digest(original.read_bytes())!=bound:
            raise ValueError(f"Earlier trace evidence differs for {name}")
    sources=roster["rows"]
    pinned = [(s["series"], s["instance_id"]) for s in json.loads(selection_raw)["slots"]]
    if len(pinned) != 20 or set(pinned) != {(r["series"], r["instance_id"]) for r in sources} or len(sources) != len(pinned):
        raise ValueError("Unexpected roster")
    endpoints = {(r["series"],r["instance_id"]):r["benchmark_resolved"] for r in sources}
    rows = []
    for r in sources:
        row = {k:r[k] for k in ("series","instance_id","available","trace_url")}
        row.update(trace_sha256=r.get("raw_sha256"),commands=None)
        if row["available"]:
            path = cache / (row["trace_sha256"]+".json")
            if path.is_file():
                raw = path.read_bytes()
            elif fetch:
                with urlopen(row["trace_url"],timeout=40) as response:
                    raw = response.read(64*1024*1024+1)
            else:
                raise FileNotFoundError(path)
            if len(raw)>64*1024*1024 or digest(raw) != row["trace_sha256"]:
                raise ValueError("Unexpected trace file")
            row["commands"] = measure(row["series"],json.loads(raw),allow_cd)
        rows.append(row)
    for row in rows:
        row["benchmark_resolved"] = endpoints[row["series"],row["instance_id"]]
    result={"protocol_sha256":PLAN,"selection_sha256":SELECTION,"rows":rows}
    if allow_cd:
        path=ROOT/"docs/SWE_RECHECK_WRAPPER_SENSITIVITY_20261128.md"
        result["sensitivity_sha256"]=digest(path.read_bytes())
        if result["sensitivity_sha256"]!="18d6945454ea25b13cbb3330f40aa868da9a256e6f55978682000ec5438eb975":
            raise ValueError("Changed post-hoc sensitivity rule")
    return result


def flags(row):
    repeats = [calls for calls in (row["commands"] or {}).values() if len(calls)>=2]
    ends = [(calls[0],calls[-1]) for calls in repeats]
    return {"available":row["available"], "any_command":bool(row["commands"]), "repeat":bool(repeats),
            "suite_pair":any(a["verdict"] and b["verdict"] for a,b in ends),
            "suite_recovery":any((a["verdict"],b["verdict"])==("fail","pass") for a,b in ends),
            "exit_recovery":any(a["process_exit"] not in (None,0) and b["process_exit"]==0 for a,b in ends)}


def report(data):
    lines=["# What the same test command establishes in a public trace", "",
           "All ten issues were reserved in both archives before the earlier audit. Counts refer to episodes, using the first and last invocation of each identical admitted command. Two SWE-agent trace files were unavailable. An exit code and a test-suite verdict have separate definitions.", "",
           "| Archive | Reserved | Trace available | Admitted command | Exact repeat | Two formal verdicts | Formal fail to pass | Nonzero to zero exit |",
           "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    if "sensitivity_sha256" in data:
        lines[0]="# Post-hoc sensitivity to working-directory prefixes"
        lines[2]+=" This sensitivity also admits a literal directory change followed by a single eligible invocation. The directory remains part of the full command identity."
    for series, label in (("A","SWE-agent"),("B","OpenHands")):
        group=[flags(r) for r in data["rows"] if r["series"]==series]
        values=[str(sum(r[k] for r in group)) for k in ("available","any_command","repeat","suite_pair","suite_recovery","exit_recovery")]
        if series=="A":
            values[-1]="unassessed"
        lines.append("| "+" | ".join([label,str(len(group)),*values])+" |")
    lines += ["", "## Witnesses", "", "| Archive / issue | Change observed | Benchmark resolved | First output locator | Last output locator |",
              "| --- | --- | --- | --- | --- |"]
    for r in data["rows"]:
        for calls in (r["commands"] or {}).values():
            a,b=calls[0],calls[-1]
            changes=[]
            if len(calls)>1 and a["verdict"]=="fail" and b["verdict"]=="pass":
                changes.append("test suite fail to pass")
            if len(calls)>1 and a["process_exit"] not in (None,0) and b["process_exit"]==0:
                changes.append("process nonzero to zero")
            if changes:
                lines.append(f"| {r['series']} / {r['instance_id']} | {', '.join(changes)} | {r['benchmark_resolved']} | {a['observation']} | {b['observation']} |")
    lines+=["", "A repeated command can run a changed script or cover a different set of tests. A process can also exit successfully after printing a wrong answer. Positive rows locate observations in the public trace. They cannot establish that feedback caused the next edit.", "",
            "Rebuild from hash-matched public traces with `python3 -B -m analysis.swe_recheck --fetch`. The default command uses the local cache. To recount from the released per-command ledger, use `--recount`.", ""]
    if "sensitivity_sha256" in data:
        lines[-2]=lines[-2].replace("--fetch","--allow-cd --fetch").replace("--recount","--allow-cd --recount")
    if not any(" | /" in line for line in lines):
        i=lines.index("## Witnesses")+2
        lines[i:i+2]=["No command met either transition rule."]
    return "\n".join(lines)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache",type=Path,default=ROOT/".local_private/swe_recheck_20261128")
    parser.add_argument("--fetch",action="store_true")
    parser.add_argument("--recount",action="store_true")
    parser.add_argument("--allow-cd",action="store_true",help="Use the separate post-hoc literal-cd wrapper rule")
    args=parser.parse_args()
    ledger=PUBLIC/("wrapper_results.json" if args.allow_cd else "results.json")
    data=json.loads(ledger.read_bytes()) if args.recount else read_rows(args.cache,args.fetch,args.allow_cd)
    md=report(data)
    for path,value in ((ledger,json.dumps(data,indent=2,ensure_ascii=False)+"\n"),(PUBLIC/("wrapper_comparison.md" if args.allow_cd else "comparison.md"),md)):
        if path.exists() and path.read_text()!=value:
            raise ValueError(f"Stored contents differ: {path}")
        if not path.exists():
            path.write_text(value)
    print("\n".join(md.splitlines()[4:8]))

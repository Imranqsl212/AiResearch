"""Export whitelisted usage counters for the matched hosted-feedback studies."""
import argparse
from collections import defaultdict, deque
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "analysis"
OUTPUT = PUBLIC / "feedback_resource_ledger_20261128"
STUDIES = ("feedback_factorial_20261128","free_patch_20261128","production_patch_20261128",
           "output_provenance_20261128","replicate_display_20261128","quix_contract_reversal_20261128",
           "matplotlib_replication_20261128","quix_rule_omission_20261128","selection_disclosure_20261128")
COUNTERS = ("input_tokens","cached_input_tokens","cache_write_input_tokens","output_tokens","reasoning_output_tokens")


def read(path):
    return json.loads(path.read_bytes())


def usage_line(raw):
    completed = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event,dict) and event.get("type")=="turn.completed":
            completed.append(event.get("usage"))
    if not completed:
        return None
    if len(completed)!=1 or not isinstance(completed[0],dict):
        raise ValueError("Expected one completed native turn per call")
    usage = {k:completed[0].get(k) for k in COUNTERS}
    if any(v is not None and (type(v) is not int or v<0) for v in usage.values()):
        raise ValueError("Invalid usage field")
    return usage


def harvest(studies):
    rows=[]
    bound={}
    for study in studies:
        ledger_file=PUBLIC/study/"results.json"
        ledger=read(ledger_file)
        bound[study]=sha256(ledger_file.read_bytes()).hexdigest()
        raw_by_hash=defaultdict(deque)
        for path in sorted((ROOT/".local_private"/study/"calls").rglob("process.json")):
            proc=read(path)
            start=read(path.parent/"start.json")
            raw=(path.parent/"stdout.bin").read_bytes()
            response_hash=sha256(raw).hexdigest()
            if response_hash!=proc["stdout_sha256"]:
                raise ValueError("Native capture differs from receipt")
            key=(response_hash,start["prompt_sha256"])
            if datetime.fromisoformat(start["utc"]) < datetime.fromisoformat(ledger["frozen_at_utc"]):
                raise ValueError("Native dispatch precedes recorded freeze")
            raw_by_hash[key].append((start["utc"],proc["elapsed_seconds"],usage_line(raw)))
        for i, entry in enumerate(ledger["rows"]):
            response_hash=entry.get("native_response_sha256")
            record={"study":study,"row":i,"model":entry["model"],"status":entry["status"],
                    "prompt_sha256":entry["prompt_sha256"],"native_response_sha256":response_hash,
                    "dispatch_utc":None,"elapsed_seconds":None,"usage":None}
            if response_hash is not None:
                key=(response_hash,entry["prompt_sha256"])
                if not raw_by_hash[key]:
                    raise ValueError(f"No private capture for {study}/{i}")
                utc,duration,usage=raw_by_hash[key].popleft()
                if duration!=entry["elapsed_seconds"]:
                    raise ValueError("Duration differs from public decision ledger")
                record.update(dispatch_utc=utc,elapsed_seconds=duration,usage=usage)
            rows.append(record)
        if any(raw_by_hash.values()):
            raise ValueError(f"Unassigned private capture in {study}")
    return {"schema_version":1,"decision_ledger_sha256":bound,"rows":rows}


def recount(data):
    rows=data["rows"]
    expected={(name,i):r for name in data["decision_ledger_sha256"]
              for i,r in enumerate(read(PUBLIC/name/"results.json")["rows"])}
    for name,digest in data["decision_ledger_sha256"].items():
        if sha256((PUBLIC/name/"results.json").read_bytes()).hexdigest()!=digest:
            raise ValueError("Decision ledger hash mismatch")
    if len(rows)!=len(expected) or {(r["study"],r["row"]) for r in rows}!=set(expected):
        raise ValueError("Resource roster differs")
    for r in rows:
        original=expected[r["study"],r["row"]]
        if any(r[k]!=original.get(k) for k in ("model","status","native_response_sha256","prompt_sha256","elapsed_seconds")):
            raise ValueError("Resource and outcome records differ")
        if r["usage"] is not None and set(r["usage"]) != set(COUNTERS):
            raise ValueError("Unexpected usage dimensions")
    lines=["# Native session resources", "",
           "One row per frozen assignment links the provider-reported token counters to its released outcome. Cached input is included in input tokens. The CLI reports wall-clock duration. Counters cover the full native session, including system context. They cannot identify pricing or the contribution of this study to account-level quota consumption.", "",
           "| Study | Scheduled | Native captures | Scored | Usage records | Input tokens | Cached input | Output tokens | Median seconds per captured call |",
           "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name in data["decision_ledger_sha256"]:
        group=[r for r in rows if r["study"]==name]
        durations=[r["elapsed_seconds"] for r in group if r["elapsed_seconds"] is not None]
        usage=[r["usage"] for r in group if r["usage"] is not None]
        counts=[sum(u[k] for u in usage) if usage and all(u[k] is not None for u in usage) else "—"
                for k in ("input_tokens","cached_input_tokens","output_tokens")]
        cells=[name,len(group),len(durations),sum(r["status"]=="OK" for r in group),len(usage),
               *counts,f"{median(durations):.1f}" if durations else "—"]
        lines.append("| "+" | ".join(map(str,cells))+" |")
    lines+=["","This recount uses the released usage records. Re-extracting provider counters requires the original private native streams.",""]
    return "\n".join(lines)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--harvest",action="store_true",help="Read and validate native captures and write public counters")
    args=p.parse_args()
    ledger=OUTPUT/"results.json"
    data=harvest(STUDIES) if args.harvest else read(ledger)
    report=recount(data)
    if args.harvest:
        ledger.write_text(json.dumps(data,indent=2)+"\n")
        (OUTPUT/"comparison.md").write_text(report)
    elif report!=(OUTPUT/"comparison.md").read_text():
        raise ValueError("Resource totals differ")
    print(report)

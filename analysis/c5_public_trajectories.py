"""Build a fixed-field public deposit candidate from 28 archived finite-policy continuations."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from analysis.c5_trace_flags import indicators

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/c5"
INDEX = ROOT / "analysis/c5_feedback_action_20261104.json"
BOUND = "f1b4ef4b90a639c0c1223cf954f38c3f99f0b9942736dbce398c12eee7408f8c"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def boolean_cases():
    source = ROOT / "analysis/c5_persistent_boolean_errors_20261123.json"
    audit = json.loads(source.read_bytes())
    cases = []
    for pair in audit["pairs"]:
        terminal = {arm: {w["case_id"]: w for w in entry["worlds"]}
                    for arm, entry in pair["arms"].items()}
        for index, world in enumerate(pair["onset"]["worlds"], 1):
            row = {"pair": pair["slot_id"], "family": pair["family"], "case_index": index,
                   "required": world["required"], "onset": world["actual"]}
            for arm in ("TRUTHFUL_PASS", "FALSE_FAIL"):
                observed = terminal[arm][world["case_id"]]
                if observed["required"] != world["required"]:
                    raise ValueError("Paired branches disagree on the task requirement")
                row[arm] = observed["actual"]
            cases.append(row)
    return (json.dumps({"source_audit_sha256": digest(source.read_bytes()),
                        "eligible_pairs": audit["included_pairs"], "cohort_pairs": audit["original_pairs"],
                        "cases": cases}, indent=2) + "\n").encode()


def collect():
    assert digest(INDEX.read_bytes()) == BOUND
    families = json.loads((OUT / "event.schema.json").read_bytes())["properties"]["family"]["enum"]
    rows = []
    sources = {}
    for pair in json.loads(INDEX.read_bytes())["pairs"]:
        for arm, record in sorted(pair["arms"].items()):
            path = ROOT / record["event_path"]
            raw = path.read_bytes()
            assert digest(raw) == record["event_sha256"]
            assert re.fullmatch(r"slot-\d{6}", pair["slot_id"])
            assert pair["family"] in families
            sources[pair["slot_id"] + "/" + arm] = record["event_sha256"]
            events = [json.loads(line) for line in raw.splitlines()]
            assert [event["kind"] for event in events] == record["actions"]
            for i, event in enumerate(events, 1):
                assert event["arm"] == arm and event["decision"] == i
                row = {"pair": pair["slot_id"], "family": pair["family"], "arm": arm,
                       "step": i, "action": event["kind"], "candidate_sha256": event.get("candidate_hash"),
                       "raw": event.get("raw_test_result"), "finite_oracle": event.get("security_oracle_result"),
                       "delivered": event.get("benchmark_verdict"), "flags": indicators(candidate=event.get("candidate")),
                       "controller_end": record["terminal"] if i == len(events) else None}
                assert row["action"] in {"ATTEMPT", "INSPECT", "TERMINATE", "STOP_REQUEST"}
                assert arm in {"FALSE_FAIL", "TRUTHFUL_PASS"} and record["terminal"] in {"VOLUNTARY", "BUDGET"}
                if row["action"] == "ATTEMPT":
                    assert re.fullmatch("[0-9a-f]{64}", row["candidate_sha256"])
                    assert row["raw"] in {"PASS", "FAIL"} and row["delivered"] in {"PASS", "FAIL"}
                    assert row["finite_oracle"] in {"SECURE", "INSECURE"}
                else:
                    assert all(row[k] is None for k in ("candidate_sha256", "raw", "finite_oracle", "delivered"))
                rows.append(row)
    payload = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows).encode()
    report = {"schema_version": 1, "source_revision": "3b5679d5b2df0d231a981fdd1419eb37fb0df721",
              "index_sha256": BOUND, "source_event_digests": sources, "jsonl_sha256": digest(payload),
              "schema_sha256": digest((OUT / "event.schema.json").read_bytes()),
              "terminal_cases_sha256": digest(boolean_cases()),
              "pairs": len({r["pair"] for r in rows}), "arms": len(sources), "events": len(rows),
              "submissions": sum(r["action"] == "ATTEMPT" for r in rows),
              "review_flags": dict(Counter(flag for row in rows for flag in row["flags"])),
              "scope": "Selected October persistent-verdict feasibility rows. No free text, paths, commands, or candidate source."}
    return payload, (json.dumps(report, indent=2) + "\n").encode()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    events, report = collect()
    for name, content in (("trajectories.jsonl", events), ("provenance.json", report),
                          ("terminal_boolean_cases.json", boolean_cases())):
        path = OUT / name
        if args.write:
            path.write_bytes(content)
        elif path.read_bytes() != content:
            raise SystemExit(f"Mismatch: {name}")
    print(json.loads(report)["events"], "allowlisted decision records across", json.loads(report)["arms"], "continuations")

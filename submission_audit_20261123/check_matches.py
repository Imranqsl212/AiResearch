"""Reconstruct the matched-issue analysis. Use --raw to re-read the public artifacts."""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "external_audit_20261122"))
from public_io import fetch


def sha(data):
    return hashlib.sha256(data).hexdigest()


def predictions(raw):
    patches = defaultdict(set)
    for line in raw.splitlines():
        if line.strip():
            prediction = json.loads(line)
            patches[prediction["instance_id"]].add(prediction.get("model_patch"))
    return patches


def check_class(trace, submitted):
    info = trace.get("info") or {}
    patch = info.get("submission")
    if not patch or submitted != {patch}:
        return "unknown"
    steps = trace.get("trajectory") or []
    source = [turn for turn in trace.get("history", [])
              if turn.get("role") == "assistant" and not turn.get("is_demo")]
    if not steps or not source:
        return "unknown"
    action = (source[-1].get("action") or "").strip()
    if action != (steps[-1].get("action") or "").strip():
        return "unknown"
    status = info.get("exit_status")
    receipt = (steps[-1].get("observation") or "").strip()
    if status == "submitted" and action == "submit" and receipt != "Exited (autosubmitted)":
        return "explicit"
    if status == f"submitted ({action})" and action.startswith("exit_") and receipt == "Exited (autosubmitted)":
        return "automatic"
    return "unknown"


def check_sources(rows):
    """Code from the non-demo history first, then check the transition and prediction."""
    heads = {r["series"]:r for r in rows}
    counts = Counter()
    for series, entry in heads.items():
        grade, grade_meta = fetch(entry["results_url"])
        pred, pred_meta = fetch(entry["prediction_url"])
        assert grade_meta["sha256"] == entry["results_sha256"]
        assert pred_meta["sha256"] == entry["prediction_file_sha256"]
        records = [r for r in rows if r["series"] == series]
        ids = [r["instance_id"] for r in records]
        assert len(set(ids)) == len(ids) and set(ids) == set(json.loads(grade)["resolved"])
        patches = predictions(pred)
        for r in records:
            issue = r["instance_id"]
            expected = set(json.loads(r["prediction_patch_sha256s"]))
            assert expected == {sha(p.encode()) for p in patches[issue] if p is not None}
            if not r["trace_sha256"]:
                assert r["classification"] == "unknown"
                counts["missing_trace_rows"] += 1
                continue
            raw, meta = fetch(r["trace_url"])
            assert meta["sha256"] == r["trace_sha256"]
            observed = check_class(json.loads(raw), patches[issue])
            assert observed == r["classification"], (series, issue, observed, r["classification"])
            counts[observed] += 1
    return dict(sorted(counts.items()))


def exact_patch(row):
    values = json.loads(row["prediction_patch_sha256s"])
    if len(values) == 1 and values[0] != sha(b""):
        return values[0]
    return None


def matched(rows):
    groups = {"same_issue": [], "same_issue_and_patch": []}
    indexed = defaultdict(dict)
    for row in rows:
        if row["primary_included"] == "True":
            indexed[row["series"]][row["instance_id"]] = row
    left, right = indexed["claude3opus"], indexed["gpt4"]
    for issue in sorted(left.keys() & right.keys()):
        a, b = left[issue], right[issue]
        detail = {"instance_id":issue, "claude3opus":a["classification"], "gpt4":b["classification"]}
        groups["same_issue"].append(detail)
        if exact_patch(a) and exact_patch(a) == exact_patch(b):
            groups["same_issue_and_patch"].append(detail)
    out = {}
    for label, pairs in groups.items():
        known = [p for p in pairs if "unknown" not in (p["claude3opus"], p["gpt4"])]
        opposite = [p for p in known if p["claude3opus"] != p["gpt4"]]
        out[label] = {"pairs":len(pairs), "both_known":len(known), "unknown":len(pairs)-len(known),
                      "opposite":len(opposite), "opposite_examples":opposite,
                      "cross_tab":dict(sorted(Counter(f"{p['claude3opus']}|{p['gpt4']}" for p in pairs).items()))}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", action="store_true", help="cross-check against URL-addressed public raw files")
    parser.add_argument("--write", action="store_true", help="save the checked result (requires --raw)")
    args = parser.parse_args()
    if args.write and not args.raw:
        parser.error("--write requires --raw")
    receipt = json.loads((ROOT / "matched_plan.receipt.json").read_bytes())
    assert sha((ROOT / "matched_plan.md").read_bytes()) == receipt["sha256"]
    with (ROOT / "rows.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    freeze = json.loads((ROOT / "freeze.json").read_bytes())
    excluded = set(freeze["excluded_ids"])
    assert all((r["primary_included"] == "True") == (r["instance_id"] not in excluded) for r in rows)
    report = {"matched_plan_sha256":receipt["sha256"], "rows_csv_sha256":sha((ROOT / "rows.csv").read_bytes()),
              "held_out":matched(rows)}
    path = ROOT / "matches.json"
    if args.raw:
        report["independently_checked_against_sources"] = check_sources(rows)
    if args.write:
        path.write_text(json.dumps(report, indent=2) + "\n")
    else:
        saved = json.loads(path.read_bytes())
        assert all(saved.get(key) == value for key, value in report.items())
    for group, stats in report["held_out"].items():
        print(group, {k:v for k,v in stats.items() if k != "opposite_examples"})


if __name__ == "__main__":
    main()

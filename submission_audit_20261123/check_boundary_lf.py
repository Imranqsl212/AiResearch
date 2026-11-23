"""Post hoc within-run byte diagnostic. Can a single boundary LF account for the trace/prediction difference?"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from check_matches import check_class, fetch, predictions, sha

ROOT = Path(__file__).resolve().parent


def diagnose():
    with (ROOT / "rows.csv").open(newline="", encoding="utf-8") as stream:
        rows = [row for row in csv.DictReader(stream)
                if row["series"] == "gpt4" and row["primary_included"] == "True"]
    raw, meta = fetch(rows[0]["prediction_url"])
    assert meta["sha256"] == rows[0]["prediction_file_sha256"]
    patches = predictions(raw)
    items = []
    for row in rows:
        raw, meta = fetch(row["trace_url"])
        assert meta["sha256"] == row["trace_sha256"]
        trace = json.loads(raw)
        issue = row["instance_id"]
        candidates = patches[issue]
        assert len(candidates) == 1 and None not in candidates
        candidate = next(iter(candidates))
        in_trace = trace["info"]["submission"]
        relation = "different"
        if candidate == in_trace:
            relation = "identical"
        elif candidate + "\n" == in_trace:
            relation = "trace_equals_prediction_plus_one_LF"
        elif "\n" + candidate == in_trace:
            relation = "trace_equals_one_LF_plus_prediction"
        eligible = {in_trace} if relation != "different" else candidates
        items.append({"instance_id":issue, "prediction_sha256":sha(candidate.encode()),
                      "trace_patch_sha256":sha(in_trace.encode()), "byte_relation":relation,
                      "class_with_declared_LF_rule":check_class(trace, eligible)})
    return {"design":"Post hoc after the exact-byte mismatch and one-byte length differences were observed. "
                    "The final-LF check matched zero. Inspection of common suffixes motivated checking one leading LF. Test only these two within-run transformations; retain the strict primary "
                    "and the cross-model patch comparison exactly as specified.",
            "rows_csv_sha256":sha((ROOT / "rows.csv").read_bytes()),
            "relations":dict(Counter(r["byte_relation"] for r in items)),
            "under_LF_rule":dict(Counter(r["class_with_declared_LF_rule"] for r in items)), "items":items}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write observed diagnostics; default verifies them")
    args = parser.parse_args()
    result = diagnose()
    path = ROOT / "boundary_lf.json"
    if args.write:
        path.write_text(json.dumps(result, indent=2) + "\n")
    else:
        assert json.loads(path.read_bytes()) == result
    print(result["relations"], result["under_LF_rule"])

"""Recalculate reported counts and verify artifact links without fetching raw trajectories."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from check_matches import matched, sha
from openhands.coverage import verify as verify_openhands

ROOT = Path(__file__).resolve().parent


def read(name):
    return json.loads((ROOT / name).read_bytes())


def file_digest(name):
    return sha((ROOT / name).read_bytes())


def table(name):
    with (ROOT / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    verify_openhands()
    canonical = set(read("openhands/verified_roster.json")["roster"])
    assert len(canonical) == 500 and canonical == {r["instance_id"] for r in table("openhands/rows.csv")}
    prior = read("../external_audit_20261122/selection.json")
    excluded = {r["instance_id"] for r in prior["slots"]}
    freeze = read("freeze.json")
    assert excluded == set(freeze["excluded_ids"]) and len(canonical - excluded) == 490
    assert file_digest("protocol.md") == freeze["protocol_sha256"]
    rows = table("rows.csv")
    summary, manifest = read("summary.json"), read("manifest.json")
    assert file_digest("manifest.json") == summary["manifest_sha256"]
    assert file_digest("rows.csv") == summary["rows_csv_sha256"] == manifest["rows_csv_sha256"]
    assert file_digest("census.py") == manifest["census_script_sha256"]
    by_series = defaultdict(list)
    for r in rows:
        assert r["instance_id"] in canonical and r["published_resolved"] == "True"
        assert (r["primary_included"] == "True") == (r["instance_id"] not in excluded)
        by_series[r["series"]].append(r)
    for series, subset in by_series.items():
        assert len({r["instance_id"] for r in subset}) == len(subset)
        for cohort, selected in (
            ("full_cohort_descriptive_only", subset),
            ("primary_excluding_discovery_issues", [r for r in subset if r["instance_id"] not in excluded]),
        ):
            counts = Counter(r["classification"] for r in selected)
            report = summary[cohort][series]
            assert len(selected) == report["published_resolved_N"]
            for label, key in (("explicit", "explicit_E"), ("automatic", "automatic_A"), ("unknown", "unknown_U")):
                assert counts[label] == report[key]
            assert report["explicit_credit_success_count_bounds"] == [counts["explicit"], len(selected) - counts["automatic"]]
            assert report["auto_share_identification_bounds"]["numerators"] == [counts["automatic"], len(selected) - counts["explicit"]]
    assert file_digest("matched_plan.md") == read("matched_plan.receipt.json")["sha256"]
    matches, sensitivity = read("matches.json"), read("boundary_lf.json")
    assert matches["rows_csv_sha256"] == sensitivity["rows_csv_sha256"] == file_digest("rows.csv")
    assert matched(rows) == matches["held_out"]
    gpt = {r["instance_id"]:r for r in by_series["gpt4"] if r["instance_id"] not in excluded}
    assert len(sensitivity["items"]) == len(gpt)
    assert {r["instance_id"] for r in sensitivity["items"]} == gpt.keys()
    for r in sensitivity["items"]:
        original = gpt[r["instance_id"]]
        assert json.loads(original["prediction_patch_sha256s"]) == [r["prediction_sha256"]]
        assert original["trace_submission_sha256"] == r["trace_patch_sha256"]
    assert Counter(r["class_with_declared_LF_rule"] for r in sensitivity["items"]) == sensitivity["under_LF_rule"]
    assert Counter(r["byte_relation"] for r in sensitivity["items"]) == sensitivity["relations"]
    execution, result = read("projection/execution_receipt.json"), read("projection/results.json")
    assert file_digest("projection/protocol.json") == result["protocol_sha256"] == execution["protocol_sha256"]
    assert file_digest("projection/provenance.json") == result["provenance_sha256"]
    assert file_digest("projection/results.json") == execution["result_sha256"]
    assert file_digest("projection/run_projection.py") == execution["script_sha256"]
    assert {case["instance_id"] for case in result["cases"]} == excluded
    for case in result["cases"]:
        variants = case["variants"]
        assert variants["finish"]["export_sha256"] == variants["continue"]["export_sha256"] == case["input_messages_sha256"]
        assert case["receipt_split"] and case["extended_view_collision"] and case["actual_termination_cause"] is None
    grading = read("grading/required_tests_13658.json")
    assert grading["script_sha256"] == file_digest("grading/check_required_tests.py")
    assert len({r["id"] for r in grading["required"]}) == grading["required_distinct_id_count"] == 182
    assert {r["status"] for r in grading["required"]} == {"observed_ok"}
    assert grading["published_resolved_membership"]
    assert len(grading["outside_required_lists"]) == 3
    assert all(not r["id_in_required_lists"] and not r["description_in_required_lists"]
               for r in grading["outside_required_lists"])
    print("Verified saved cohort counts, bounds, matched issues, byte diagnostics, and paired export digests.")


if __name__ == "__main__":
    main()

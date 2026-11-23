"""Read-only comparison of official required IDs with one existing evaluator log.

Requires Python 3 and pyarrow 22.0.0; uses the repository's public_io HTTPS cache.
Run from the repository root:
    python3 -B submission_audit_20261123/grading/check_required_tests.py
No test, patch, model, or downloaded program is executed. This does not invoke
the SWE-bench grader or replace the official published resolved label.
"""
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import sys

import pyarrow
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "external_audit_20261122"))
from public_io import fetch

INSTANCE = "django__django-13658"
DATASET_URL = ("https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified/resolve/"
               "78f471bf655a3137b2e8a75af1501690ec009ec3/data/test-00000-of-00001.parquet")
DATASET_SHA = "030cfd7f2a704c4c0226e7f104c725a3b41230b1d3517f9c915ad7ea5be3fa25"
LOG_URL = ("https://swe-bench-submissions.s3.amazonaws.com/verified/20240402_sweagent_claude3opus/"
           "logs/django__django-13658.20240402_sweagent_claude3opus.eval.log")
LOG_SHA = "2262d4ff332ae890a4febba951ee440c12ca8991250ee7aba223116cc91b96ce"
RESULTS_URL = ("https://raw.githubusercontent.com/SWE-bench/experiments/"
               "40f164d5b8f1d249bf95a6df8b74b577fd8e519d/evaluation/verified/"
               "20240402_sweagent_claude3opus/results/results.json")
RESULTS_SHA = "18a7f9f8ac2ede71046c3d961ce4a7478b025549a5c4298ff811d60245e692b7"


def read_pinned(url, expected):
    raw, metadata = fetch(url)
    if metadata["sha256"] != expected:
        raise ValueError(f"Source hash changed: {url}")
    return raw, metadata


def run():
    data_raw, data_meta = read_pinned(DATASET_URL, DATASET_SHA)
    log_raw, log_meta = read_pinned(LOG_URL, LOG_SHA)
    results_raw, results_meta = read_pinned(RESULTS_URL, RESULTS_SHA)
    columns = ["instance_id", "FAIL_TO_PASS", "PASS_TO_PASS"]
    records = pq.read_table(io.BytesIO(data_raw), columns=columns).to_pylist()
    matches = [(i, row) for i, row in enumerate(records) if row["instance_id"] == INSTANCE]
    if len(matches) != 1:
        raise ValueError("Expected one canonical task record")
    row_index, record = matches[0]
    lines = log_raw.decode("utf-8").splitlines()
    required = []
    for group in ["FAIL_TO_PASS", "PASS_TO_PASS"]:
        ids = record[group]
        ids = json.loads(ids) if isinstance(ids, str) else ids
        if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
            raise ValueError("Malformed required test list")
        for ordinal, test_id in enumerate(ids):
            # Equality, not substring matching: similar descriptions cannot
            # inherit one another's status. Keep every matching line.
            observed = [{"line": i, "status": "ok"} for i, line in enumerate(lines, 1)
                        if line == test_id + " ... ok"]
            required.append({"group": group, "id": test_id,
                             "dataset_locator": {"row_zero_based": row_index,
                                                 "column": group, "list_index_zero_based": ordinal},
                             "observed": observed,
                             "status": "observed_ok" if observed else "not_found_as_exact_ok_line"})
    required_ids = {r["id"] for r in required}
    outside = []
    # These are the three FAIL/ERROR summary IDs actually in this pinned log.
    for test_id, description_id, status in [
        ("test_startapp_unicode_name (admin_scripts.tests.DjangoAdminSettingsDirectory)",
         "startapp creates the correct directory with Unicode characters.", "ERROR"),
        ("test_all (admin_scripts.tests.DiffSettings)",
         "The all option also shows settings with the default value.", "FAIL"),
        ("test_unified_all (admin_scripts.tests.DiffSettings)", None, "FAIL"),
    ]:
        label = description_id or test_id
        observed_lines = [i for i, line in enumerate(lines, 1) if line == label + " ... " + status]
        summary_lines = [i for i, line in enumerate(lines, 1) if line == status + ": " + test_id]
        if not observed_lines or not summary_lines:
            raise ValueError("Expected failure/error marker absent")
        outside.append({"id": test_id, "description_id": description_id, "status": status,
                        "observed_line_locators": observed_lines, "summary_line_locators": summary_lines,
                        "id_in_required_lists": test_id in required_ids,
                        "description_in_required_lists": description_id in required_ids if description_id else False})
    marker_lines = [i for i, line in enumerate(lines, 1) if line == ">>>>> Some Tests Failed"]
    output = {
        "schema": "required-test-log-comparison-v1", "instance_id": INSTANCE,
        "sources": [data_meta, log_meta, results_meta],
        "published_resolved_membership": INSTANCE in json.loads(results_raw)["resolved"],
        "published_grade_locator": "/resolved (instance-ID membership)",
        "required_entry_counts": dict(Counter(r["group"] for r in required)),
        "required_entry_count": len(required), "required_distinct_id_count": len(required_ids),
        "observed_required_status_counts": dict(Counter(r["status"] for r in required)),
        "required": required, "outside_required_lists": outside,
        "general_grader_marker": {"status": "Some Tests Failed", "line_locators": marker_lines},
        "method": "Compare each canonical required test ID with an exact existing log line ending ' ... ok'; retain list ordinals and every matching line. Check failing IDs and their verbose description aliases against both required lists.",
        "scope": "This is a post hoc source reconciliation, not test execution, regrading, an explanation of the unrelated failures, or evaluated-patch byte attestation. Census classification and official labels are unchanged.",
        "dependencies": {"python_major": sys.version_info.major, "pyarrow": pyarrow.__version__},
        "verification_command": "python3 -B submission_audit_20261123/grading/check_required_tests.py",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    if len(required) != 182 or any(r["status"] != "observed_ok" for r in required):
        raise ValueError("Required-status comparison changed")
    if any(r["id_in_required_lists"] or r["description_in_required_lists"] for r in outside):
        raise ValueError("Failure/error intersects a required ID")
    (HERE / "required_tests_13658.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: output[k] for k in ["required_entry_counts", "required_entry_count",
                     "required_distinct_id_count", "observed_required_status_counts"]}, indent=2))


if __name__ == "__main__":
    run()

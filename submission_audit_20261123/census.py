"""Recode frozen published successes; never execute archived code or actions.

Raw public artifacts stay in public_io's URL-addressed temporary cache. Outputs
contain only hashes, structural locators, narrow terminal markers, and counts.
Run: python3 -B submission_audit_20261123/census.py --workers 4
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "external_audit_20261122"))
from public_io import fetch, BUCKET  # Local read-only HTTPS client, not downloaded code.

COMMIT = "40f164d5b8f1d249bf95a6df8b74b577fd8e519d"
PROTOCOL_SHA = "6d6a0a284158066007386aa44b76862a9a964aeb9f7993659b1d1c232b68f17d"
SERIES = {"claude3opus": "20240402_sweagent_claude3opus",
          "gpt4": "20240402_sweagent_gpt4"}
CACHE = Path(tempfile.gettempdir()) / "swe_public_io_20261122"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def cache_key(url):
    return digest(url.encode("utf-8"))


def source(url, category):
    raw, meta = fetch(url)
    return raw, dict(meta, category=category, cache_key=cache_key(url))


def list_prefix(prefix):
    """Record every page, including continuation tokens, of an official listing."""
    params = {"list-type": "2", "prefix": prefix}
    keys, sources = set(), []
    while True:
        raw, meta = source(BUCKET + "/?" + urlencode(params), "s3_listing")
        tree = ET.fromstring(raw)
        if tree.tag.split("}")[-1] != "ListBucketResult":
            raise ValueError("Not an S3 object listing")
        sources.append(meta)
        keys.update(k.text for k in tree.findall(".//{*}Contents/{*}Key"))
        token = tree.findtext("{*}NextContinuationToken")
        if not token:
            if tree.findtext("{*}IsTruncated") == "true":
                raise ValueError("Truncated listing without continuation token")
            return keys, sources
        params["continuation-token"] = token


def confirmed_missing(url):
    """404 plus absence from the complete listing; never turn network errors into missingness."""
    result = subprocess.run(
        ["curl", "-sSLI", "--retry", "2", "--max-time", "90", "-o", "/dev/null",
         "-w", "%{http_code}", url], capture_output=True, text=True, check=True)
    code = result.stdout.strip()
    if code != "404":
        raise RuntimeError(f"Unlisted artifact did not confirm HTTP404: {url} ({code})")
    return {"url": url, "status": "confirmed_missing", "http_status": 404,
            "evidence": "Absent from complete official prefix listing; direct HTTPS HEAD returned 404."}


def prediction_index(raw):
    index = defaultdict(list)
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        issue = record.get("instance_id")
        if not isinstance(issue, str):
            raise ValueError(f"Prediction record {line_number} lacks a string instance ID")
        patch = record.get("model_patch")
        try:
            patch_bytes = patch.encode("utf-8") if isinstance(patch, str) else None
        except UnicodeEncodeError:
            patch_bytes = None
        index[issue].append({"line": line_number,
                             "sha256": digest(patch_bytes) if patch_bytes is not None else None,
                             "bytes": len(patch_bytes) if patch_bytes is not None else None})
    return index


def classify(row, raw, predictions):
    """Inspect structured action/status fields only; no thought, response, or content fields."""
    data = json.loads(raw)
    issues = []
    if not isinstance(data, dict):
        row["unknown_reasons"] = ["trace_not_object"]
        return
    info = data.get("info")
    info = info if isinstance(info, dict) else {}
    patch = info.get("submission")
    try:
        patch_bytes = patch.encode("utf-8") if isinstance(patch, str) else None
    except UnicodeEncodeError:
        patch_bytes = None
    row["trace_submission_sha256"] = digest(patch_bytes) if patch_bytes is not None else None
    row["trace_submission_utf8_bytes"] = len(patch_bytes) if patch_bytes is not None else None
    distinct = row["prediction_patch_sha256s"]
    if not predictions:
        issues.append("no_prediction_record")
    elif any(p["sha256"] is None for p in predictions):
        issues.append("malformed_prediction_patch")
    elif len(distinct) != 1:
        issues.append("multiple_distinct_prediction_patches")
    if patch_bytes is None:
        issues.append("missing_or_malformed_trace_submission")
    elif len(patch_bytes) == 0:
        issues.append("empty_trace_submission")
    row["prediction_match"] = (len(distinct) == 1 and patch_bytes is not None
                                and distinct[0] == digest(patch_bytes)
                                and all(p["sha256"] is not None for p in predictions))
    if patch_bytes and len(distinct) == 1 and not row["prediction_match"]:
        issues.append("trace_prediction_byte_mismatch")

    trajectory, history = data.get("trajectory"), data.get("history")
    trajectory_ok = (isinstance(trajectory, list) and bool(trajectory)
                     and all(isinstance(s, dict) and isinstance(s.get("action"), str)
                             for s in trajectory))
    history_ok = isinstance(history, list) and all(isinstance(h, dict) for h in history)
    if not trajectory_ok:
        issues.append("missing_or_malformed_trajectory_actions")
    if not history_ok:
        issues.append("missing_or_malformed_history")
    assistant = ([(i, h) for i, h in enumerate(history)
                  if h.get("role") == "assistant" and not h.get("is_demo", False)]
                 if history_ok else [])
    history_actions = [(i, h["action"]) for i, h in assistant
                       if isinstance(h.get("action"), str)]
    if not assistant or not isinstance(assistant[-1][1].get("action"), str):
        issues.append("missing_terminal_history_action")
    if trajectory_ok and history_actions:
        row["history_actions_equal_trajectory"] = ([s["action"] for s in trajectory]
                                                  == [a for _, a in history_actions])
        last = len(trajectory) - 1
        action = trajectory[-1]["action"].strip()
        row["terminal_actions_match"] = action == history_actions[-1][1].strip()
        if not row["terminal_actions_match"]:
            issues.append("terminal_action_mismatch")
        row["terminal_action_sha256"] = digest(trajectory[-1]["action"].encode("utf-8"))
        row["trajectory_action_locator"] = f"/trajectory/{last}/action"
        row["history_action_locator"] = f"/history/{history_actions[-1][0]}/action"
        row["observation_locator"] = f"/trajectory/{last}/observation"
        observation = trajectory[-1].get("observation")
        row["observation_sha256"] = (digest(observation.encode("utf-8"))
                                     if isinstance(observation, str) else None)
        status = info.get("exit_status")
        row["exit_status"] = status if isinstance(status, str) and re.fullmatch(r"[a-z_ ()]+", status) else None
        row["terminal_action_category"] = (action if re.fullmatch(r"submit|exit_[a-z_]+", action)
                                           else "other_or_compound")
        auto_receipt = isinstance(observation, str) and observation.strip() == "Exited (autosubmitted)"
        row["autosubmission_receipt"] = auto_receipt
        candidate = "unknown"
        if action == "submit" and status == "submitted":
            candidate = "explicit"
            if auto_receipt:
                issues.append("explicit_action_with_automatic_receipt")
        elif re.fullmatch(r"exit_[a-z_]+", action) and status == f"submitted ({action})" and auto_receipt:
            candidate = "automatic"
            row["boundary_reason"] = ("cost" if action == "exit_cost" else
                                      "context" if action == "exit_context" else "other")
        else:
            issues.append("no_matching_canonical_terminal_submission")
        if candidate != "unknown" and not issues:
            row["classification"] = candidate
    row["unknown_reasons"] = sorted(set(issues))
    if row["classification"] == "unknown" and not row["unknown_reasons"]:
        row["unknown_reasons"] = ["insufficient_terminal_structure"]


def audit_row(job):
    series, submission, issue, excluded, preds, base_meta, trace_keys = job
    key = f"verified/{submission}/trajs/{issue}.traj"
    url = BUCKET + "/" + key
    row = {"series": series, "submission": submission, "instance_id": issue,
           "primary_included": issue not in excluded, "published_resolved": True,
           "classification": "unknown", "boundary_reason": None, "unknown_reasons": [],
           "prediction_record_count": len(preds),
           "prediction_patch_sha256s": sorted({p["sha256"] for p in preds if p["sha256"] is not None}),
           "prediction_patch_utf8_bytes": sorted({p["bytes"] for p in preds if p["bytes"] is not None}),
           "prediction_line_locators": [p["line"] for p in preds],
           "prediction_match": None, "prediction_url": base_meta["predictions"]["url"],
           "prediction_file_sha256": base_meta["predictions"]["sha256"],
           "results_url": base_meta["results"]["url"], "results_sha256": base_meta["results"]["sha256"],
           "grade_locator": "/resolved (instance-ID membership)",
           "trace_url": url, "trace_sha256": None, "trace_cache_key": cache_key(url),
           "trace_submission_sha256": None, "trace_submission_utf8_bytes": None,
           "trace_submission_locator": "/info/submission", "exit_status_locator": "/info/exit_status",
           "exit_status": None, "terminal_action_category": None, "terminal_action_sha256": None,
           "history_actions_equal_trajectory": None, "terminal_actions_match": None,
           "trajectory_action_locator": None, "history_action_locator": None,
           "observation_locator": None, "observation_sha256": None, "autosubmission_receipt": None,
           "grader_log_url": None, "grader_log_sha256": None, "grader_log_status": "not_requested",
           "grader_markers": [], "terminal_grader_marker": None}
    if key not in trace_keys:
        evidence = confirmed_missing(url)
        row["unknown_reasons"] = ["confirmed_missing_official_trace"]
        return row, evidence
    raw, meta = source(url, "trace")
    row["trace_sha256"] = meta["sha256"]
    classify(row, raw, preds)
    return row, meta


def grader_check(job):
    row, keys = job
    key = f'verified/{row["submission"]}/logs/{row["instance_id"]}.{row["submission"]}.eval.log'
    url = BUCKET + "/" + key
    row["grader_log_url"] = url
    if key not in keys:
        row["grader_log_status"] = "confirmed_missing"
        return confirmed_missing(url)
    raw, meta = source(url, "automatic_submission_grader_log")
    markers = [{"line": i, "marker": line.strip()} for i, line in
               enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1)
               if re.match(r"^>>>>> (?:All Tests Passed|Some Tests Failed|Tests (?:Failed|Passed)|Patch (?:Applied|Apply Failed)|Test (?:Errored|Timed Out))", line.strip())]
    row.update(grader_log_sha256=meta["sha256"], grader_log_status="available",
               grader_markers=markers, terminal_grader_marker=markers[-1] if markers else None)
    return meta


def account(rows, denominator):
    counts = Counter(r["classification"] for r in rows)
    n, e, a, u = len(rows), counts["explicit"], counts["automatic"], counts["unknown"]
    assert e + a + u == n
    return {"published_resolved_N": n, "explicit_E": e, "automatic_A": a, "unknown_U": u,
            "task_denominator": denominator, "native_archived_success_score": n / denominator,
            "auto_share_identification_bounds": {"numerators": [a, a + u], "denominator": n,
                                                   "decimal": [a / n, (a + u) / n] if n else [None, None]},
            "explicit_credit_success_count_bounds": [e, e + u],
            "explicit_credit_score_bounds": [e / denominator, (e + u) / denominator],
            "automatic_boundary_reasons": dict(sorted(Counter(r["boundary_reason"] for r in rows
                                                               if r["classification"] == "automatic").items())),
            "unknown_reason_counts_nonexclusive": dict(sorted(Counter(reason for r in rows
                if r["classification"] == "unknown" for reason in r["unknown_reasons"]).items())),
            "trace_prediction_byte_matches": sum(r["prediction_match"] is True for r in rows),
            "automatic_grader_log_availability": dict(Counter(r["grader_log_status"] for r in rows
                                                               if r["classification"] == "automatic")),
            "automatic_terminal_grader_markers": dict(Counter(
                r["terminal_grader_marker"]["marker"] if r["terminal_grader_marker"] else "unavailable_or_no_marker"
                for r in rows if r["classification"] == "automatic"))}


def run(workers):
    protocol = (ROOT / "protocol.md").read_bytes()
    if digest(protocol) != PROTOCOL_SHA:
        raise ValueError("Frozen protocol hash mismatch")
    freeze_raw = (ROOT / "freeze.json").read_bytes()
    freeze = json.loads(freeze_raw)
    if freeze["protocol_sha256"] != PROTOCOL_SHA:
        raise ValueError("Freeze receipt disagrees with protocol")
    selection_raw = (ROOT.parent / "external_audit_20261122/selection.json").read_bytes()
    if digest(selection_raw) != freeze["prior_selection_sha256"]:
        raise ValueError("Prior discovery selection hash mismatch")
    excluded = set(freeze["excluded_ids"])
    prior_ids = {s["instance_id"] for s in json.loads(selection_raw)["slots"]}
    if len(excluded) != 10 or excluded != prior_ids:
        raise ValueError("Expected exactly the ten frozen prior discovery issues")
    sources, jobs, metadata, log_keys = [], [], {}, {}
    for series, submission in SERIES.items():
        result_url = f"https://raw.githubusercontent.com/SWE-bench/experiments/{COMMIT}/evaluation/verified/{submission}/results/results.json"
        pred_url = f"{BUCKET}/verified/{submission}/all_preds.jsonl"
        with ThreadPoolExecutor(max_workers=min(workers, 2)) as pool:
            (result_raw, result_meta), (pred_raw, pred_meta) = list(pool.map(
                lambda args: source(*args), [(result_url, "published_results"), (pred_url, "predictions")]))
        result = json.loads(result_raw)
        resolved = result["resolved"]
        if not isinstance(resolved, list) or not all(isinstance(x, str) for x in resolved):
            raise ValueError("Malformed resolved list")
        roster = sorted(set(resolved))
        if len(roster) != len(resolved):
            raise ValueError("Duplicate published resolved ID; review population before continuing")
        predictions = prediction_index(pred_raw)
        trace_keys, listing_sources = list_prefix(f"verified/{submission}/trajs/")
        logs, log_sources = list_prefix(f"verified/{submission}/logs/")
        sources.extend([result_meta, pred_meta] + listing_sources + log_sources)
        base_meta = {"results": result_meta, "predictions": pred_meta}
        metadata[series] = {"submission": submission, "resolved_count": len(roster),
                            "prediction_record_count": sum(map(len, predictions.values())),
                            "prediction_distinct_ids": len(predictions),
                            "trace_object_count": len(trace_keys), "log_object_count": len(logs)}
        log_keys[series] = logs
        jobs.extend((series, submission, issue, excluded, predictions.get(issue, []), base_meta, trace_keys)
                    for issue in roster)
        print(f"Prepared {series}: {len(roster)} published successes", flush=True)
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, (row, meta) in enumerate(pool.map(audit_row, jobs), 1):
            rows.append(row)
            sources.append(meta)
            if i % 20 == 0 or i == len(jobs):
                print(f"Linked {i}/{len(jobs)} records", flush=True)
    auto = [r for r in rows if r["classification"] == "automatic"]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for meta in pool.map(grader_check, [(r, log_keys[r["series"]]) for r in auto]):
            sources.append(meta)
    by_series = {s: [r for r in rows if r["series"] == s] for s in SERIES}
    summary = {"schema": "submission-census-v1", "protocol_sha256": PROTOCOL_SHA,
               "freeze_sha256": digest(freeze_raw), "catalogue_commit": COMMIT,
               "excluded_discovery_ids": sorted(excluded), "population_metadata": metadata,
               "primary_excluding_discovery_issues": {s: account([r for r in rs if r["primary_included"]], 490)
                                                       for s, rs in by_series.items()},
               "full_cohort_descriptive_only": {s: account(rs, 500) for s, rs in by_series.items()},
               "same_issue_joint_successes": {},
               "interpretation": ["Bounds are exact finite-cohort identification bounds, not sampling confidence intervals.",
                 "The primary cohort excludes the ten discovery issues in both submissions; overlapping issues are paired, not independent replication.",
                 "Official resolved membership is retained regardless of trace or patch linkage; missing evidence is never imputed.",
                 "A trace-to-prediction byte match does not establish evaluated-patch byte identity.",
                 "Grader markers are a positive cross-check, not a reconstruction of SWE-bench grading or patch identity.",
                 "Explicit-credit bounds change only the readout of fixed archived histories; they do not estimate rerun performance or agent intent.",
                 "The original SWE-agent paper tabulated termination reasons. This is independent Verified recoding with artifact-linkage uncertainty, not a first discovery."],
               "implementation_details": {"max_concurrent_fetches": workers,
                 "raw_cache": "tempfile.gettempdir()/swe_public_io_20261122",
                 "cache_key": "SHA256(exact UTF-8 URL)", "download_client": "../external_audit_20261122/public_io.py",
                 "history_consistency": "Require matching terminal actions and exclude history is_demo records. Whole-sequence equality is a diagnostic, not an added eligibility restriction.",
                 "raw_reasoning_or_patches_in_outputs": False, "archived_code_or_models_executed": False}}
    indexed = {s: {r["instance_id"]: r for r in rs} for s, rs in by_series.items()}
    shared = sorted(set(indexed["claude3opus"]) & set(indexed["gpt4"]))
    for name, ids in [("primary", [i for i in shared if i not in excluded]), ("full_descriptive", shared)]:
        pairs = [{"instance_id": i, "claude3opus": indexed["claude3opus"][i]["classification"],
                  "gpt4": indexed["gpt4"][i]["classification"]} for i in ids]
        summary["same_issue_joint_successes"][name] = {"N": len(ids), "rows": pairs,
            "cross_classification": dict(sorted(Counter(f'{r["claude3opus"]}|{r["gpt4"]}' for r in pairs).items()))}
    csv_path = ROOT / "rows.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
                             if isinstance(v, (list, dict)) else v for k, v in row.items()})
    manifest = {"retrieval_completed_utc": datetime.now(timezone.utc).isoformat(),
                "protocol_sha256": PROTOCOL_SHA, "sources": sorted(sources, key=lambda x: x["url"]),
                "census_script_sha256": digest(Path(__file__).read_bytes()),
                "public_io_sha256": digest((ROOT.parent / "external_audit_20261122/public_io.py").read_bytes()),
                "rows_csv_sha256": digest(csv_path.read_bytes()),
                "raw_cache": "tempfile.gettempdir()/swe_public_io_20261122"}
    manifest_path = ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary["manifest_sha256"] = digest(manifest_path.read_bytes())
    summary["rows_csv_sha256"] = manifest["rows_csv_sha256"]
    (ROOT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary["primary_excluding_discovery_issues"], indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    run(parser.parse_args().workers)

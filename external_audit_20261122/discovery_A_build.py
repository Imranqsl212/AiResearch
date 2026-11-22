"""Assemble source availability and ID-only roster; never read outcome/trace data."""
import datetime
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRATCH = ROOT / "scratch_A"
COMMIT = "40f164d5b8f1d249bf95a6df8b74b577fd8e519d"
SUBMISSION = "20240402_sweagent_claude3opus"
BASE = f"https://raw.githubusercontent.com/SWE-bench/experiments/{COMMIT}/evaluation/verified/{SUBMISSION}/"
API_BASE = f"https://api.github.com/repos/SWE-bench/experiments/contents/evaluation/verified"
S3 = "https://swe-bench-submissions.s3.amazonaws.com/"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}

def hashed(name):
    path = SCRATCH / name
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}

catalogue = json.loads((SCRATCH / "catalog_verified.json").read_text())
pool = []
for entry in catalogue:
    name = entry["name"]
    normalized = re.sub("[^a-z0-9]", "", name.lower())
    date = re.match(r"^(\d{8})", name)
    if entry["type"] != "dir" or date is None: continue
    datetime.datetime.strptime(date[1], "%Y%m%d")
    if date[1] <= "20251231" and "sweagent" in normalized and "minisweagent" not in normalized:
        pool.append(name)
pool.sort()
assert pool[0] == SUBMISSION
roster = json.loads((SCRATCH / "roster_id_only.json").read_text())
results = json.loads((SCRATCH / "results_index.json").read_text())
published = next(row for row in results if row["name"] == "results.json")
s3_root = ET.fromstring((SCRATCH / "s3_root.xml").read_bytes())
prediction = next(row for row in s3_root.findall("s:Contents", NS)
                  if row.findtext("s:Key", namespaces=NS).endswith("/all_preds.jsonl"))
assert int(prediction.findtext("s:Size", namespaces=NS)) == roster["raw_bytes"]
trajs = ET.fromstring((SCRATCH / "s3_trajs.xml").read_bytes())
trace_keys = [{"key": row.findtext("s:Key", namespaces=NS),
               "bytes": int(row.findtext("s:Size", namespaces=NS)),
               "etag": row.findtext("s:ETag", namespaces=NS),
               "last_modified": row.findtext("s:LastModified", namespaces=NS)}
              for row in trajs.findall("s:Contents", NS)]
assert trace_keys and all(row["key"].endswith(".traj") for row in trace_keys)
discovery = {
    "family": "A", "family_match": "SWE-agent; punctuation/spacing ignored; mini-SWE-agent excluded",
    "submission": SUBMISSION, "catalog_commit": COMMIT, "split": "Verified",
    "phase": "outcome_blind_source_discovery_before_sample_freeze",
    "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "protocol_sha256": hashlib.sha256((ROOT / "protocol.md").read_bytes()).hexdigest(),
    "candidate_pool_ascii_sorted": pool,
    "attempted": [{"submission": SUBMISSION, "eligible": True,
                   "reason": "Prediction-ID file publicly retrieved; published results.json listed at pinned catalogue commit; official metadata links identifiable public per-instance trajectory collection."}],
    "skipped": [], "fallback_used": False,
    "roster": roster["roster"],
    "prediction_record_count": roster["prediction_record_count"],
    "distinct_prediction_ids": roster["distinct_id_count"],
    "duplicate_prediction_id_records": roster["duplicate_id_count"],
    "sources": {
        "catalogue_index": {"url": f"{API_BASE}?ref={COMMIT}", **hashed("catalog_verified.json")},
        "submission_index": {"url": f"{API_BASE}/{SUBMISSION}?ref={COMMIT}", **hashed(f"candidate_{SUBMISSION}.json")},
        "documentation": [
            {"url": BASE + "README.md", "access": "artifact URLs extracted programmatically; narrative and outcome values not displayed", **hashed("A_README.md")},
            {"url": BASE + "metadata.yaml", "access": "artifact URLs extracted programmatically", **hashed("A_metadata.yaml")},
        ],
        "predictions": {**{k: v for k, v in roster.items() if k != "roster"},
                        "s3_etag": prediction.findtext("s:ETag", namespaces=NS),
                        "s3_last_modified": prediction.findtext("s:LastModified", namespaces=NS)},
        "published_outcomes": {"url": published["download_url"], "git_blob_sha": published["sha"],
                               "bytes": published["size"], "content_read": False,
                               "availability_evidence": {"url": f"{API_BASE}/{SUBMISSION}/results?ref={COMMIT}", **hashed("results_index.json")}},
        "trajectory_collection": {"metadata_uri": f"s3://swe-bench-submissions/verified/{SUBMISSION}/trajs",
                                  "base_url": f"{S3}verified/{SUBMISSION}/trajs/",
                                  "instance_url_template": f"{S3}verified/{SUBMISSION}/trajs/{{instance_id}}.traj",
                                  "listing_url": f"{S3}?list-type=2&prefix=verified%2F{SUBMISSION}%2Ftrajs%2F&delimiter=%2F&max-keys=20",
                                  "listing_is_truncated": trajs.findtext("s:IsTruncated", namespaces=NS) == "true",
                                  "availability_evidence": hashed("s3_trajs.xml"),
                                  "listed_file_metadata_only": trace_keys, "trajectory_contents_read": False},
        "logs_collection": {"metadata_uri": f"s3://swe-bench-submissions/verified/{SUBMISSION}/logs",
                            "base_url": f"{S3}verified/{SUBMISSION}/logs/", "contents_read": False},
        "s3_root_listing": {"url": f"{S3}?list-type=2&prefix=verified%2F{SUBMISSION}%2F&delimiter=%2F", **hashed("s3_root.xml")},
    },
    "selection_notes": [
        "Distinct IDs retained from every prediction record, without filtering on patch presence or any outcome.",
        "The public predictions file contains duplicate instance IDs. No patch comparisons or record-selection decisions have been made; the later outcome/patch audit must retain this ambiguity.",
        "Trajectory availability established from official metadata plus public object names and sizes; coverage of sampled instances is not presumed.",
        "No trajectory, individual result, submitted patch value, or outcome value has been inspected in this discovery stage.",
        "Public S3 objects are not content-addressed by the Git commit; capture current object hashes/ETags and do not imply historical immutability.",
    ],
    "discovery_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
target = ROOT / "discovery_A.json"
with target.open("x", encoding="utf-8") as handle:
    json.dump(discovery, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print(json.dumps({"path": str(target), "submission": SUBMISSION, "roster_count": len(discovery["roster"]),
                  "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}))

"""Discovery only for the frozen SWE-bench B selection; never inspect outcomes/traces.

Prediction JSONL is streamed and only instance_id is selected. All records are
included irrespective of patch contents; patch values are never inspected.
"""
import datetime
import hashlib
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

COMMIT = "40f164d5b8f1d249bf95a6df8b74b577fd8e519d"
REPO = "https://api.github.com/repos/SWE-bench/experiments"
RAW = "https://raw.githubusercontent.com/SWE-bench/experiments"
EXPECTED = "20241029_OpenHands-CodeAct-2.1-sonnet-20241022"
HISTORICAL = "f353999852cdb97b36bb58766d04043206a62f4c"
OUT = Path(__file__).with_name("discovery_B.json")


def read(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        body = response.read()
    return body, hashlib.sha256(body).hexdigest()


def normalized(value):
    return "".join(c for c in value.lower() if c.isalnum())


def metadata(url):
    body, digest = read(url)
    return json.loads(body), {"url": url, "sha256": digest}


catalog_url = f"{REPO}/contents/evaluation/verified?ref={COMMIT}"
catalog, catalog_evidence = metadata(catalog_url)
candidates = sorted(item["name"] for item in catalog
                    if item["type"] == "dir"
                    and item["name"][:8].isdigit()
                    and item["name"][:8] <= "20251231"
                    and any(tag in normalized(item["name"]) for tag in ("openhands", "opendevin"))
                    and "sweagent" not in normalized(item["name"]))
assert candidates and candidates[0] == EXPECTED, "Frozen candidate-order expectation differs"
name = candidates[0]
subpath = f"evaluation/verified/{name}"
index, index_evidence = metadata(f"{REPO}/contents/{subpath}?ref={COMMIT}")
result_index, result_evidence = metadata(f"{REPO}/contents/{subpath}/results?ref={COMMIT}")
result_file = next(item for item in result_index if item["name"] == "results.json")
outcomes_url = result_file["download_url"]
with urllib.request.urlopen(urllib.request.Request(outcomes_url, method="HEAD"), timeout=60) as response:
    outcome_head = {"status": response.status, "content_type": response.headers.get("Content-Type")}
metadata_url = f"{RAW}/{COMMIT}/{subpath}/metadata.yaml"
metadata_bytes, metadata_hash = read(metadata_url)
# Only artifact locators are selected from documentation; no score fields.
artifact_locations = dict(re.findall(r"^\s*(logs|trajs):\s*(s3://\S+)\s*$",
                                     metadata_bytes.decode(), flags=re.MULTILINE))
assert "trajs" in artifact_locations and "logs" in artifact_locations
traj_s3 = urllib.parse.urlparse(artifact_locations["trajs"])
bucket = traj_s3.netloc
prefix = traj_s3.path.lstrip("/")
s3_base = f"https://{bucket}.s3.amazonaws.com"
trace_listing_url = s3_base + "/?" + urllib.parse.urlencode(
    {"list-type": "2", "prefix": prefix, "max-keys": "1000"})
trace_listing, trace_listing_hash = read(trace_listing_url)
tree = ET.fromstring(trace_listing)
trace_keys = [node.text for node in tree.iter() if node.tag.split("}")[-1] == "Key"]
assert trace_keys, "No identifiable trajectory objects"
truncated = next((node.text for node in tree.iter()
                  if node.tag.split("}")[-1] == "IsTruncated"), None)
submission_prefix = prefix.rsplit("/", 1)[0] + "/"
artifact_listing_url = s3_base + "/?" + urllib.parse.urlencode(
    {"list-type": "2", "prefix": submission_prefix, "delimiter": "/", "max-keys": "1000"})
artifact_listing, artifact_listing_hash = read(artifact_listing_url)
artifact_tree = ET.fromstring(artifact_listing)
artifact_keys = [node.text for node in artifact_tree.iter() if node.tag.split("}")[-1] == "Key"]
prediction_key = next(k for k in artifact_keys if k.endswith("/all_preds.jsonl"))
prediction_url = s3_base + "/" + prediction_key
ids = []
hasher = hashlib.sha256()
byte_count = 0
with urllib.request.urlopen(prediction_url, timeout=60) as response:
    headers = {"etag": response.headers.get("ETag"),
               "last_modified": response.headers.get("Last-Modified"),
               "content_length": response.headers.get("Content-Length")}
    for line in response:
        hasher.update(line)
        byte_count += len(line)
        if not line.strip():
            continue
        instance_id = json.loads(line)["instance_id"]
        if not isinstance(instance_id, str) or not instance_id:
            raise ValueError("Prediction row lacks a nonempty string ID")
        ids.append(instance_id)
roster = sorted(set(ids))
if not roster:
    raise ValueError("Empty prediction roster")

evidence = {
    "family": "B", "submission": name, "roster": roster,
    "discovered_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "catalog_commit": COMMIT, "cutoff_submission_directory_date": "2025-12-31",
    "protocol_sha256": "c05546f93b6dc57606fab61383a9b931f0930d5e906572ebd3ab04812a8905d7",
    "selection": "First ASCII-sorted eligible OpenHands/OpenDevin directory; no fallback or candidate skip.",
    "candidate_pool": candidates, "attempted_candidates": [
        {"submission": name, "status": "ELIGIBLE_SELECTED",
         "basis": "Public prediction-ID roster, published outcome file, and metadata-linked public trajectory object collection."}],
    "skipped_candidates": [],
    "remaining_candidates_not_assessed": candidates[1:],
    "catalog_evidence": catalog_evidence,
    "submission_index_evidence": index_evidence,
    "outcome_index_evidence": result_evidence,
    "outcomes": {"url": outcomes_url, "git_blob_sha1_from_index": result_file["sha"],
                 "size_from_index": result_file["size"], "head": outcome_head,
                 "content_read": False},
    "roster_source": {"url": prediction_url, "sha256": hasher.hexdigest(),
                      "bytes": byte_count, "headers": headers,
                      "jsonl_rows": len(ids), "distinct_ids": len(roster),
                      "duplicate_id_rows": len(ids) - len(roster),
                      "extraction": "Stream every JSONL row; select instance_id only; never inspect model_patch or filter empty patches."},
    "trajectory_collection": {
        "metadata_url": metadata_url, "metadata_sha256": metadata_hash,
        "s3_uri": artifact_locations["trajs"],
        "https_prefix": s3_base + "/" + prefix + "/",
        "per_instance_url_template": s3_base + "/" + prefix + "/{instance_id}.json",
        "listing_url": trace_listing_url, "listing_sha256": trace_listing_hash,
        "listed_object_count": len(trace_keys), "listing_truncated": truncated,
        "example_object_names_only": trace_keys[:15],
        "trajectory_content_read": False},
    "evaluation_log_collection": {"s3_uri": artifact_locations["logs"], "content_read": False},
    "artifact_listing_evidence": {
        "url": artifact_listing_url, "sha256": artifact_listing_hash, "keys": artifact_keys},
    "historical_official_roster_locator": {
        "commit": HISTORICAL,
        "url": f"{RAW}/{HISTORICAL}/{subpath}/all_preds.jsonl",
        "git_blob_sha1_from_historical_index": "f617418f9206ceac6d6bb7ad7316b13ca3ac3d8d",
        "size_from_historical_index": 31227948,
        "content_read": False,
        "note": "Historical directory index confirmed this alternative before the metadata-linked current S3 path was located."},
    "discovery_attempts": [
        {"stage": "initial_catalog_http", "result": "Sandbox DNS unavailable; read-only public HTTPS succeeded with approved escalation."},
        {"stage": "current_submission_index", "result": "README, metadata, results directory; no local all_preds at pinned current commit."},
        {"stage": "documentation_url_extraction", "result": "URLs only extracted from README/metadata; no document outcome text displayed."},
        {"stage": "official_history_index", "result": "Original commit contains all_preds.jsonl; 2025 directory index no longer contains that file."},
        {"stage": "guessed_s3_bucket", "bucket": "swe-bench-experiments.s3.amazonaws.com",
         "prefixes": ["verified/"+name, "evaluation/verified/"+name, name],
         "result": "All three list requests HTTP 404; no artifact content retrieved."},
        {"stage": "metadata_artifact_flags", "result": "Exact logs/trajs locations found under swe-bench-submissions."},
        {"stage": "official_s3_indices", "result": "Prediction object and per-instance trajectory collection identified from object names."},
        {"stage": "prediction_id_only_download", "result": "All prediction rows included; only IDs retained."},
    ],
    "blinding": {
        "instance_outcomes_read": False, "patch_contents_inspected": False,
        "trace_contents_read": False, "selection_conditioned_on_patch_presence": False,
        "prediction_payload_handling": "JSON parsed only to extract IDs; unused fields never inspected or persisted.",
        "notes": "No trajectory or outcome content was consulted to choose this submission or roster."},
}
with OUT.open("x", encoding="utf-8") as handle:
    json.dump(evidence, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print(json.dumps({"saved": str(OUT), "submission": name, "roster_count": len(roster),
                  "prediction_rows": len(ids), "trace_objects_listed": len(trace_keys),
                  "outcomes_or_traces_read": False}))


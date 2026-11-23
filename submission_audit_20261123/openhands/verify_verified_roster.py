"""Verify public roster IDs only; never execute or inspect candidate source.

Requires pyarrow. Downloaded Parquet/prediction bytes remain in memory; only the
instance_id column/field is accessed. --build exclusively creates the report;
the default invocation checks it without changing repository files.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import pyarrow
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = HERE / "verified_roster.json"
CATALOG_COMMIT = "40f164d5b8f1d249bf95a6df8b74b577fd8e519d"
DATASETS = {
    "canonical": {
        "dataset": "SWE-bench/SWE-bench_Verified",
        "revision": "78f471bf655a3137b2e8a75af1501690ec009ec3",
        "sha256": "030cfd7f2a704c4c0226e7f104c725a3b41230b1d3517f9c915ad7ea5be3fa25",
        "bytes": 6304616,
    },
    "legacy_namespace": {
        "dataset": "princeton-nlp/SWE-bench_Verified",
        "revision": "c104f840cc67f8b6eec6f759ebc8b2693d585d4a",
        "sha256": "a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd",
        "bytes": 2096679,
    },
}
PARQUET_PATH = "data/test-00000-of-00001.parquet"
CACHE_DIRECTORY = None


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fetch(url, expected_sha256=None, expected_bytes=None):
    cached = CACHE_DIRECTORY / digest(url.encode("utf-8")) if CACHE_DIRECTORY else None
    if expected_sha256 is not None and cached is not None and cached.is_file():
        data = cached.read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "SWE-Verified-roster-audit/1.0"})
        with urllib.request.urlopen(request, timeout=90) as response:
            data = response.read(100_000_001)
    if len(data) > 100_000_000:
        raise ValueError("Public file exceeds size limit")
    if expected_sha256 is not None and digest(data) != expected_sha256:
        raise ValueError(f"Source digest mismatch: {url}")
    if expected_bytes is not None and len(data) != expected_bytes:
        raise ValueError(f"Source length mismatch: {url}")
    return data


def ids_and_counts(values):
    if not values or any(not isinstance(v, str) or not v for v in values):
        raise ValueError("Invalid/empty instance ID roster")
    counts = Counter(values)
    return sorted(counts), {
        "row_count": len(values), "distinct_id_count": len(counts),
        "duplicate_rows": len(values) - len(counts),
    }


def differences(reference, observed):
    reference, observed = set(reference), set(observed)
    return {
        "reference_count": len(reference), "observed_count": len(observed),
        "intersection_count": len(reference & observed),
        "missing_from_observed": sorted(reference - observed),
        "outside_reference": sorted(observed - reference),
        "sets_equal": reference == observed,
    }


def dataset_roster(label):
    source = dict(DATASETS[label])
    name, revision = source["dataset"], source["revision"]
    url = f"https://huggingface.co/datasets/{name}/resolve/{revision}/{PARQUET_PATH}"
    data = fetch(url, source["sha256"], source["bytes"])
    # Column projection avoids decoding patch, problem statement, or test data.
    values = pq.read_table(io.BytesIO(data), columns=["instance_id"])["instance_id"].to_pylist()
    roster, counts = ids_and_counts(values)
    if counts != {"row_count": 500, "distinct_id_count": 500, "duplicate_rows": 0}:
        raise ValueError(f"Unexpected Verified roster size: {label}: {counts}")
    return {**source, "file": PARQUET_PATH, "url": url,
            "metadata_url": f"https://huggingface.co/api/datasets/{name}/tree/{revision}/data?expand=true",
            "split": "test", "decoded_columns": ["instance_id"], **counts, "roster": roster}


def prediction_roster(family):
    path = ROOT / "external_audit_20261122" / f"discovery_{family}.json"
    raw_discovery = path.read_bytes()
    discovery = json.loads(raw_discovery)
    selection = json.loads((ROOT / "external_audit_20261122/selection.json").read_bytes())
    if digest(raw_discovery) != selection["discovery_sha256"][family]:
        raise ValueError(f"Frozen discovery digest mismatch: {family}")
    if discovery["catalog_commit"] != CATALOG_COMMIT:
        raise ValueError("Catalogue revision mismatch")
    source = discovery["sources"]["predictions"] if family == "A" else discovery["roster_source"]
    sha = source["raw_sha256"] if family == "A" else source["sha256"]
    size = source["raw_bytes"] if family == "A" else source["bytes"]
    raw = fetch(source["url"], sha, size)
    values = [json.loads(line)["instance_id"] for line in raw.splitlines() if line.strip()]
    roster, counts = ids_and_counts(values)
    if roster != sorted(discovery["roster"]):
        raise ValueError(f"Prediction IDs differ from frozen discovery: {family}")
    return {"submission": discovery["submission"], "url": source["url"],
            "sha256": sha, "bytes": len(raw), "accessed_fields": ["instance_id"],
            "empty_patch_policy": "No patch field inspected; all nonblank prediction rows retained.",
            "discovery_file": str(path.relative_to(ROOT)), "discovery_sha256": digest(raw_discovery),
            **counts, "roster": roster}


def gpt4_prediction_roster():
    submission = "20240402_sweagent_gpt4"
    url = f"https://swe-bench-submissions.s3.amazonaws.com/verified/{submission}/all_preds.jsonl"
    sha = "ed3da60d2f0f064d4b916b3ebbb1d7612e53e3207444fd4aa63954b27c8a5cb8"
    raw = fetch(url, sha, 1006197)
    values = [json.loads(line)["instance_id"] for line in raw.splitlines() if line.strip()]
    roster, counts = ids_and_counts(values)
    return {"submission": submission, "url": url, "sha256": sha, "bytes": len(raw),
            "accessed_fields": ["instance_id"],
            "empty_patch_policy": "No patch field inspected; all nonblank prediction rows retained.",
            **counts, "roster": roster}


def archive_roster():
    submission = "20241029_OpenHands-CodeAct-2.1-sonnet-20241022"
    prefix = f"verified/{submission}/trajs/"
    url = ("https://swe-bench-submissions.s3.amazonaws.com/?list-type=2&prefix="
           + urllib.parse.quote(prefix, safe="") + "&max-keys=1000")
    raw = fetch(url)
    tree = ET.fromstring(raw)
    if tree.findtext("{*}IsTruncated") != "false":
        raise ValueError("Archive listing is incomplete")
    keys = [item.text for item in tree.findall("{*}Contents/{*}Key")]
    if not all(k.startswith(prefix) and k.endswith(".json") and "/" not in k[len(prefix):] for k in keys):
        raise ValueError("Unexpected archive key")
    roster, counts = ids_and_counts([key[len(prefix):-5] for key in keys])
    return {"submission": submission, "listing_url": url, "listing_sha256": digest(raw),
            "listing_bytes": len(raw), "truncated": False,
            "content_access": "Object names only; no trajectory content retrieved.",
            **counts, "roster": roster}


def recompute():
    jobs = {
        "canonical": lambda: dataset_roster("canonical"),
        "legacy_namespace": lambda: dataset_roster("legacy_namespace"),
        "A": lambda: prediction_roster("A"),
        "B": lambda: prediction_roster("B"),
        "sweagent_gpt4": gpt4_prediction_roster,
        "openhands_archive": archive_roster,
    }
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {key: pool.submit(fn) for key, fn in jobs.items()}
        sources = {key: future.result() for key, future in futures.items()}
    roster = sources["canonical"]["roster"]
    return {
        "schema_version": "verified-id-roster-v1", "catalog_commit": CATALOG_COMMIT,
        "official_dataset_documentation": "https://www.swebench.com/SWE-bench/guides/datasets/",
        "canonical_count": len(roster), "roster": roster,
        "roster_sha256": digest(("\n".join(roster) + "\n").encode("utf-8")),
        "roster_hash_encoding": "Sorted unique IDs, LF-separated, final LF, UTF-8.",
        "sources": sources,
        "comparisons": {key: differences(roster, value["roster"])
                        for key, value in sources.items() if key != "canonical"},
        "scope": "Membership only; no candidate execution, outcome analysis, or inference about why an ID is absent.",
    }


def main():
    global CACHE_DIRECTORY
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Exclusively create verified_roster.json")
    parser.add_argument("--cache-directory", type=Path,
                        help="Optional existing URL-hash cache, read-only; every cached byte string is SHA-256 verified")
    args = parser.parse_args()
    CACHE_DIRECTORY = args.cache_directory
    result = recompute()
    if args.build:
        result["retrieved_utc"] = datetime.now(timezone.utc).isoformat()
        result["verifier_sha256"] = digest(Path(__file__).read_bytes())
        result["extraction_software"] = {"pyarrow": pyarrow.__version__}
        with OUTPUT.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    else:
        saved = json.loads(OUTPUT.read_bytes())
        if saved["verifier_sha256"] != digest(Path(__file__).read_bytes()):
            raise ValueError("Verifier differs from frozen report")
        for key in result:
            if saved[key] != result[key]:
                raise ValueError(f"Recomputed report differs: {key}")
    print(json.dumps({"status": "CREATED" if args.build else "VERIFIED",
                      "canonical_count": result["canonical_count"],
                      "comparisons": result["comparisons"]}, indent=2))


if __name__ == "__main__":
    main()

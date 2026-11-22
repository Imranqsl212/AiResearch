"""Retrieve only the ten frozen B trace objects; never execute their contents."""
import concurrent.futures
import datetime
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
selection_bytes = (ROOT / "selection.json").read_bytes()
assert hashlib.sha256(selection_bytes).hexdigest() == "7b8e1869d1101c0851935686c20e1003f78922bf75840cab17c702d4aa9e23e2"
selection = json.loads(selection_bytes)
discovery = json.loads((ROOT / "discovery_B.json").read_text())
assert hashlib.sha256((ROOT / "discovery_B.json").read_bytes()).hexdigest() == selection["discovery_sha256"]["B"]
ids = [row["instance_id"] for row in selection["slots"] if row["series"] == "B"]
assert len(ids) == len(set(ids)) == 10
scratch = Path(tempfile.mkdtemp(prefix="swe_external_B_20261122_", dir="/private/tmp"))
template = discovery["trajectory_collection"]["per_instance_url_template"]


def retrieve(instance_id):
    url = template.format(instance_id=instance_id)
    row = {"instance_id": instance_id, "trace_url": url}
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            raw = response.read()
            row["etag"] = response.headers.get("ETag")
            row["last_modified"] = response.headers.get("Last-Modified")
        path = scratch / (instance_id + ".json")
        with path.open("xb") as handle:
            handle.write(raw)
        value = json.loads(raw)
        row.update(status="DOWNLOADED", trace_path=str(path),
                   trace_sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                   top_level_type=type(value).__name__,
                   top_level_keys=list(value) if isinstance(value, dict) else None)
    except Exception as error:
        row.update(status="MISSING", error_type=type(error).__name__, error=str(error))
    return row


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    rows = list(executor.map(retrieve, ids))
manifest = {"series": "B", "selection_sha256": hashlib.sha256(selection_bytes).hexdigest(),
            "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "scratch": str(scratch), "rows": rows}
with (scratch / "download_manifest.json").open("x", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2)
    handle.write("\n")
print(json.dumps(manifest, indent=2))


"""Download only the ten A trajectories reserved before any content inspection."""
import concurrent.futures
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = Path("/private/tmp/external_audit_A_20261122/traces")
RAW.mkdir(parents=True, exist_ok=True)
selection_raw = (ROOT / "selection.json").read_bytes()
assert hashlib.sha256(selection_raw).hexdigest() == "7b8e1869d1101c0851935686c20e1003f78922bf75840cab17c702d4aa9e23e2"
selection = json.loads(selection_raw)
ids = [slot["instance_id"] for slot in selection["slots"] if slot["series"] == "A"]
assert len(ids) == len(set(ids)) == 10
submission = selection["submission"]["A"]

def download(instance):
    url = f"https://swe-bench-submissions.s3.amazonaws.com/verified/{submission}/trajs/{instance}.traj"
    path = RAW / (instance + ".traj")
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "--connect-timeout", "10",
                             "--max-time", "60", "--retry", "1", "--output", str(path), url], capture_output=True, text=True)
    row = {"instance_id": instance, "trace_url": url, "raw_path": str(path), "retrieved_utc": started,
           "curl_exit": result.returncode, "available": result.returncode == 0}
    if result.returncode == 0:
        row.update(trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)
    else:
        row["retrieval_error"] = result.stderr.strip()[:500]
    return row

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    rows = list(pool.map(download, ids))
output = {"submission": submission, "selection_sha256": hashlib.sha256(selection_raw).hexdigest(), "rows": rows,
          "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(ROOT / "scratch_A" / "trace_manifest.json").write_text(json.dumps(output, indent=2) + "\n")
print(json.dumps({"downloaded": sum(row["available"] for row in rows), "reserved": len(rows), "paths": [r["raw_path"] for r in rows if r["available"]]}, indent=2))

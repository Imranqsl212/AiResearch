"""Outcome-blind prediction roster extraction for the frozen external audit.

Reads only instance_id as a field. Does not branch on, display, summarize or
retain patch/score/outcome fields. Raw downloaded public bytes stay in /private/tmp.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = Path("/private/tmp/external_audit_A_20261122")
RAW.mkdir(parents=True, exist_ok=True)
URL = "https://swe-bench-submissions.s3.amazonaws.com/verified/20240402_sweagent_claude3opus/all_preds.jsonl"
path = RAW / "all_preds.jsonl"
if not path.exists():
    subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "--connect-timeout", "10",
                    "--max-time", "90", "--retry", "1", "--output", str(path), URL], check=True)
ids = []
with path.open(encoding="utf-8") as handle:
    for line in handle:
        if not line.strip(): continue
        record = json.loads(line)
        instance_id = record["instance_id"]
        if not isinstance(instance_id, str) or not instance_id.strip():
            raise ValueError("invalid prediction instance_id")
        ids.append(instance_id)
        del record
roster = sorted(set(ids))
result = {
    "roster": roster, "prediction_record_count": len(ids), "distinct_id_count": len(roster),
    "duplicate_id_count": len(ids) - len(roster), "url": URL,
    "raw_bytes": path.stat().st_size, "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "raw_path": str(path), "parser_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "field_access": ["instance_id"],
    "selection_note": "Every nonblank prediction record contributes its instance_id; patch presence, contents and outcomes are not inspected or used as filters.",
}
(ROOT / "scratch_A" / "roster_id_only.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({key: value for key, value in result.items() if key != "roster"}, indent=2))

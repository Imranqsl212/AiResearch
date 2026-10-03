"""Post-collection coverage audit of *unsealed* Docker sidecar logs.

This is deliberately separate from paper_pipeline: a hash found in a local
sidecar is not a uniquely linked action receipt and cannot upgrade the main
paper's stopping or strategy claims. This script never executes a candidate.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ID = "rag-overnight-v2-main-0-5-0"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize_matches(action_hashes: list[str], sidecars_by_hash: dict[str, list[bool]]) -> dict[str, int]:
    matched = [sidecars_by_hash.get(value, []) for value in action_hashes]
    return {
        "action_check_count": len(action_hashes),
        "matched_by_source_hash": sum(bool(values) for values in matched),
        "unmatched_by_source_hash": sum(not values for values in matched),
        "multiple_sidecar_matches": sum(len(values) > 1 for values in matched),
        "unique_sidecar_matches": sum(len(values) == 1 for values in matched),
        "conflicting_sidecar_results": sum(len(set(values)) > 1 for values in matched),
    }


def audit() -> dict[str, object]:
    index_path = ROOT / "experiments/results" / f"{EXPERIMENT_ID}.jsonl"
    index = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(index) != 40 or len({row["slot_id"] for row in index}) != 40:
        raise ValueError("main cohort is not the expected 40 unique slots")

    trajectory_paths = [Path(row["log_path"]).resolve() for row in index]
    if any(not path.is_relative_to(ROOT / "experiments/runs") for path in trajectory_paths):
        raise ValueError("unexpected trajectory path outside research runs")
    sidecar_paths = sorted((ROOT / "sandbox/logs").glob("candidate-*.log"))
    inputs = [index_path, *trajectory_paths, *sidecar_paths]
    before = {str(path): sha256(path) for path in inputs}

    action_hashes: list[str] = []
    for path in trajectory_paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("event_type") == "TOOL_OBSERVATION" and event.get("tool") in {"attempt", "security_check"}:
                action_hashes.append(event["verifier_result"]["source_sha256"])

    sidecars_by_hash: dict[str, list[bool]] = defaultdict(list)
    malformed_json_lines = 0
    for path in sidecar_paths:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith("{"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                malformed_json_lines += 1
                continue
            if isinstance(record.get("source_sha256"), str) and isinstance(record.get("passed"), bool):
                sidecars_by_hash[record["source_sha256"]].append(record["passed"])

    if any(sha256(path) != before[str(path)] for path in inputs):
        raise ValueError("audit input changed while being read")
    return {
        "study": EXPERIMENT_ID,
        "scope": "auxiliary local logs; not the sealed trajectory archive",
        "sidecar_log_files_scanned": len(sidecar_paths),
        "sidecar_json_errors": malformed_json_lines,
        **summarize_matches(action_hashes, sidecars_by_hash),
        "read_only_inputs_unchanged": True,
        "interpretation": "Source-hash matches alone do not identify an action's Docker execution or reconstruct its raw-check timeline.",
    }


def main() -> None:
    result = audit()
    destination = ROOT / "paper/artifacts/auxiliary_sidecar_audit.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

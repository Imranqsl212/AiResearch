"""Create the versioned batch-C v7 proposal without touching v6 or main inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmark.finite_batch_c_v7 import FAMILIES, build_reference_tasks, certify_task


ROOT = Path(__file__).resolve().parent / "tasks" / "v7_batch_c"


def _encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def generate(directory: Path = ROOT) -> dict[str, object]:
    """Write once; an existing different byte sequence is a versioning error."""
    directory.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, bytes] = {}
    rows: list[dict[str, object]] = []
    for task in build_reference_tasks():
        task_name = f"{task['task_id']}.task.json"
        proof_name = f"{task['task_id']}.proof.json"
        task_bytes = _encoded(task)
        proof_bytes = _encoded(certify_task(task))
        payloads[task_name], payloads[proof_name] = task_bytes, proof_bytes
        rows.append({
            "task_id": task["task_id"], "family": task["family"],
            "condition": task["condition"],
            "ground_truth_state": ("UNREPAIRABLE" if task["condition"] in {"C3", "C4"}
                                   else "EVALUATOR_MISMATCH" if task["condition"] == "C5"
                                   else "REPAIRABLE"),
            "task_file": task_name, "task_file_sha256": hashlib.sha256(task_bytes).hexdigest(),
            "proof_file": proof_name, "proof_file_sha256": hashlib.sha256(proof_bytes).hexdigest(),
        })
    index = {
        "schema_version": "7.0", "scope": "bounded_stateless_modes_and_explicit_finite_worlds_only",
        "status": "PROPOSED_NOT_HUMAN_ADMITTED", "family_count": len(FAMILIES),
        "condition_count": len(rows), "tasks": rows,
    }
    payloads["index.json"] = _encoded(index)
    present = {path.name for path in directory.iterdir() if path.is_file()}
    if present and present != set(payloads):
        raise ValueError("existing v7 artifact set is incomplete or has extra files")
    for name, data in payloads.items():
        path = directory / name
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"versioned v7 artifact differs: {name}")
    for name, data in payloads.items():
        path = directory / name
        if not path.exists():
            path.write_bytes(data)
    return {"directory": str(directory), "families": len(FAMILIES),
            "tasks": len(rows), "files": len(payloads),
            "index_sha256": hashlib.sha256(payloads["index.json"]).hexdigest(),
            "status": index["status"]}


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2, sort_keys=True))

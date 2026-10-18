"""Write-once artifacts for the corrected excluded v1.1 feedback design."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from benchmark.real_code_candidate_v1 import FAMILY_CONFIG, ROOT
from benchmark.real_code_candidate_v1_1 import (
    STATUS, SUPERSEDED_INDEX_SHA256, VERSION, build_contract,
    validate_candidate,
)


DIRECTORY = ROOT / "benchmark" / "tasks" / "real_code_candidate_v1_1"


def _formatted(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _artifacts() -> dict[str, bytes]:
    validate_candidate()
    artifacts = {f"{family}.contract.json": _formatted(build_contract(family))
                 for family in sorted(FAMILY_CONFIG)}
    rows = [{"family": family, "contract_file": f"{family}.contract.json",
             "contract_sha256": hashlib.sha256(artifacts[f"{family}.contract.json"]).hexdigest()}
            for family in sorted(FAMILY_CONFIG)]
    artifacts["index.json"] = _formatted({
        "schema_version": VERSION, "status": STATUS,
        "family_count": len(FAMILY_CONFIG), "condition_count": len(FAMILY_CONFIG) * 5,
        "contracts": rows,
        "purpose": "offline_task_design_only_no_model_or_docker_execution",
        "supersedes_index_sha256": SUPERSEDED_INDEX_SHA256,
    })
    return artifacts


def generate(directory: Path = DIRECTORY) -> dict[str, Any]:
    artifacts = _artifacts()
    directory.mkdir(parents=True, exist_ok=True)
    present = {p.name for p in directory.iterdir() if p.is_file()}
    if present - set(artifacts):
        raise ValueError("unindexed v1.1 artifact exists")
    for name, data in artifacts.items():
        path = directory / name
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError(f"versioned v1.1 artifact differs: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(data)
    return validate(directory)


def validate(directory: Path = DIRECTORY) -> dict[str, Any]:
    artifacts = _artifacts()
    present = {p.name for p in directory.iterdir() if p.is_file()}
    if present != set(artifacts):
        raise ValueError("v1.1 artifact inventory differs")
    for name, expected in artifacts.items():
        if (directory / name).read_bytes() != expected:
            raise ValueError(f"v1.1 artifact differs: {name}")
    return {"status": STATUS, "schema_version": VERSION,
            "family_count": len(FAMILY_CONFIG),
            "condition_count": len(FAMILY_CONFIG) * 5,
            "artifact_count": len(artifacts),
            "index_sha256": hashlib.sha256(artifacts["index.json"]).hexdigest(),
            "supersedes_index_sha256": SUPERSEDED_INDEX_SHA256,
            "main_ready": False, "model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(generate(), sort_keys=True, indent=2))

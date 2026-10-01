"""Mapping contract for the twelve existing four-cell crypto tasks.

The approved image is used only through the fail-closed runner. Private source
verification remains evaluator-side; the container's public capability marker never
receives a model credential or an external target.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sandbox.policy import APPROVED_IMAGES_PATH, approved_images


ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "benchmark" / "tasks" / "four_cell"


def build_mapping() -> list[dict[str, Any]]:
    image = approved_images(APPROVED_IMAGES_PATH)[0]
    rows = []
    for task_path in sorted(TASK_DIR.glob("fc-*.json")):
        task = json.loads(task_path.read_text(encoding="utf-8"))
        family = task["difficulty"]["family"]
        rows.append({
            "task_id": task["task_id"], "family": family, "condition": task["condition"],
            "image_ref": image.image_ref, "image_config_digest": image.config_digest,
            "capability_command": ["/crypto-target", "self-test"],
            "host_verifier": task["verifier"]["id"], "evaluator_only": True,
            "network": "none", "credentials": "none", "mapping_version": "0.1.0",
        })
    return rows


def validate_mapping() -> dict[str, Any]:
    rows = build_mapping()
    errors = []
    if len(rows) != 12: errors.append(f"expected 12 four-cell crypto tasks, found {len(rows)}")
    image_refs = {row["image_ref"] for row in rows}
    if len(image_refs) != 1: errors.append("mapping uses more than one image")
    if any(row["network"] != "none" or row["credentials"] != "none" for row in rows): errors.append("unsafe mapping metadata")
    return {"passed": not errors, "task_count": len(rows), "image_ref": next(iter(image_refs), None), "errors": errors, "rows": rows}


if __name__ == "__main__":
    print(json.dumps(validate_mapping(), indent=2, sort_keys=True))

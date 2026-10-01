"""Digest-pinned mapping for the 32 local web tasks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.executable_catalog import CONDITIONS, WEB_FAMILIES
from sandbox.policy import APPROVED_IMAGES_PATH, approved_images


ROOT = Path(__file__).resolve().parents[1]


def validate_mapping() -> dict[str, Any]:
    image = approved_images(APPROVED_IMAGES_PATH)[0]
    rows = [
        {
            "task_id": f"web-{family}-{condition.lower()}", "family": family, "condition": condition,
            "image_ref": image.image_ref, "image_config_digest": image.config_digest,
            "capability_command": ["/crypto-target", "self-test"],
            "host_verifier": verifier, "network": "none", "credentials": "none",
            "external_target": False, "mapping_version": "0.1.0",
        }
        for family, _, _, verifier, _, _ in WEB_FAMILIES for condition in CONDITIONS
    ]
    errors = []
    if len(rows) != 32: errors.append(f"expected 32 web tasks, found {len(rows)}")
    if len({row["image_ref"] for row in rows}) != 1: errors.append("web mapping uses more than one image")
    return {"passed": not errors, "task_count": len(rows), "image_ref": image.image_ref, "errors": errors, "rows": rows}


if __name__ == "__main__":
    print(json.dumps(validate_mapping(), indent=2, sort_keys=True))

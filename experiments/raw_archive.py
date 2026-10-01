"""Content-addressed sealing for observable experiment artifacts.

This is a local integrity layer, not a claim that an ordinary filesystem is WORM
storage.  A production collection should copy the sealed directory to independent
write-once or access-controlled storage after sealing.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any


ARCHIVE_SCHEMA_VERSION = "0.1.0"


class ArchiveError(ValueError):
    """The archive would be overwritten or has inconsistent content."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not run_id or run_id in {".", ".."}:
        raise ArchiveError("run_id must be a non-empty path-safe string")
    if any(part in {".", ".."} for part in Path(run_id).parts) or Path(run_id).name != run_id:
        raise ArchiveError("run_id must not contain path separators")
    return run_id


def archive_run(source: Path, archive_root: Path, run_id: str) -> dict[str, Any]:
    """Copy one completed run exactly once and return its immutable metadata.

    Re-archiving byte-identical content is idempotent; different content under the
    same run id is rejected.  The source is never deleted or modified.
    """

    run_id = _safe_run_id(run_id)
    source = source.resolve()
    if not source.is_file():
        raise ArchiveError(f"source run does not exist: {source}")
    digest = sha256_file(source)
    destination = archive_root / "runs" / f"{run_id}.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing = sha256_file(destination)
        if existing != digest:
            raise ArchiveError(f"archive already contains different content for run_id={run_id}")
    else:
        shutil.copyfile(source, destination)
        os.chmod(destination, 0o444)
    return {"run_id": run_id, "path": str(destination.relative_to(archive_root)), "sha256": digest, "bytes": destination.stat().st_size}


def seal_archive(archive_root: Path, *, experiment_id: str, manifest_version: str) -> Path:
    """Write a create-once hash manifest for all archived run files."""

    archive_root.mkdir(parents=True, exist_ok=True)
    manifest_path = archive_root / "archive_manifest.json"
    entries: list[dict[str, Any]] = []
    for path in sorted((archive_root / "runs").glob("*.jsonl")) if (archive_root / "runs").exists() else []:
        entries.append({"path": str(path.relative_to(archive_root)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "manifest_version": manifest_version,
        "sealed": True,
        "files": entries,
        "archive_sha256": hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing != manifest:
            raise ArchiveError("archive manifest already exists with different content")
        return manifest_path
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(manifest_path, 0o444)
    return manifest_path


def verify_archive(archive_root: Path) -> dict[str, Any]:
    manifest_path = archive_root / "archive_manifest.json"
    if not manifest_path.is_file():
        raise ArchiveError("archive_manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for entry in manifest.get("files", []):
        path = archive_root / entry["path"]
        if not path.is_file():
            errors.append(f"missing archived file: {entry['path']}")
            continue
        if sha256_file(path) != entry["sha256"]:
            errors.append(f"hash mismatch: {entry['path']}")
    return {"passed": not errors, "manifest": str(manifest_path), "file_count": len(manifest.get("files", [])), "errors": errors}

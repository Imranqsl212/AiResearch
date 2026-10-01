"""Versioned, immutable experiment manifests for reproducible episode runs."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA_VERSION = "0.1.0"
UNAVAILABLE_GIT_COMMIT = "UNAVAILABLE_NO_GIT"
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40,64}$")


def utc_now() -> str:
    """Return a UTC timestamp with stable second precision for an audit record."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_date() -> str:
    return datetime.now(UTC).date().isoformat()


def _safe_component(value: str, field: str) -> None:
    if not isinstance(value, str) or not _SAFE_COMPONENT.fullmatch(value):
        raise ValueError(f"{field} must be a short filesystem-safe identifier")


def resolve_git_commit(repository_root: Path) -> str:
    """Resolve HEAD when available; never invent a revision for a non-Git checkout."""

    try:
        result = subprocess.run(
            ("git", "rev-parse", "--verify", "HEAD"),
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return UNAVAILABLE_GIT_COMMIT
    candidate = result.stdout.strip().lower()
    if result.returncode == 0 and _GIT_SHA.fullmatch(candidate):
        return candidate
    return UNAVAILABLE_GIT_COMMIT


@dataclass(frozen=True)
class ExperimentManifest:
    """All execution-affecting settings that must be frozen before a run series."""

    experiment_id: str
    model: str
    agent_version: str
    benchmark_version: str
    task_ids: tuple[str, ...]
    runs_per_task: int
    temperature: float | None
    max_steps: int
    timeout_seconds: int
    git_commit: str
    adapter_type: str
    sandbox_type: str
    safety_mode: str
    seed: int | None = None
    token_budget: int | None = None
    schedule_sha256: str | None = None
    notes: str = ""
    created_at: str = ""
    date: str = ""
    schema_version: str = MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _safe_component(self.experiment_id, "experiment_id")
        for field in (
            "model",
            "agent_version",
            "benchmark_version",
            "git_commit",
            "adapter_type",
            "sandbox_type",
            "safety_mode",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
        if self.schema_version != MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"schema_version must equal {MANIFEST_SCHEMA_VERSION}")
        if not self.task_ids or any(not isinstance(task_id, str) or not task_id for task_id in self.task_ids):
            raise ValueError("task_ids must be a non-empty tuple of strings")
        for field in ("runs_per_task", "max_steps", "timeout_seconds"):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{field} must be a positive integer")
        for field in ("seed", "token_budget"):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise ValueError(f"{field} must be a non-negative integer or None")
        if self.temperature is not None and not isinstance(self.temperature, (int, float)):
            raise ValueError("temperature must be numeric or None")
        if self.schedule_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", self.schedule_sha256):
            raise ValueError("schedule_sha256 must be a SHA-256 hex digest or None")
        if not isinstance(self.notes, str):
            raise ValueError("notes must be a string")
        if not self.created_at:
            object.__setattr__(self, "created_at", utc_now())
        if not self.date:
            object.__setattr__(self, "date", utc_date())

    @property
    def task_count(self) -> int:
        return len(self.task_ids)

    def as_mapping(self) -> dict[str, Any]:
        document = asdict(self)
        document["task_ids"] = list(self.task_ids)
        document["task_count"] = self.task_count
        return document

    def immutable_configuration(self) -> dict[str, Any]:
        """Fields that must agree if an existing manifest ID is reused."""

        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "model": self.model,
            "agent_version": self.agent_version,
            "benchmark_version": self.benchmark_version,
            "task_ids": list(self.task_ids),
            "task_count": self.task_count,
            "runs_per_task": self.runs_per_task,
            "temperature": self.temperature,
            "max_steps": self.max_steps,
            "timeout_seconds": self.timeout_seconds,
            "git_commit": self.git_commit,
            "adapter_type": self.adapter_type,
            "sandbox_type": self.sandbox_type,
            "safety_mode": self.safety_mode,
            "seed": self.seed,
            "token_budget": self.token_budget,
            "schedule_sha256": self.schedule_sha256,
            "notes": self.notes,
        }


def manifest_path(manifest: ExperimentManifest, directory: Path) -> Path:
    _safe_component(manifest.experiment_id, "experiment_id")
    return directory / f"{manifest.experiment_id}.json"


def write_manifest(manifest: ExperimentManifest, directory: Path) -> Path:
    """Create an immutable manifest, or reuse a configuration-identical one.

    Existing output is never overwritten.  Reusing an experiment identifier with a
    different configuration raises instead of quietly changing the audit record.
    """

    directory.mkdir(parents=True, exist_ok=True)
    path = manifest_path(manifest, directory)
    payload = manifest.as_mapping()
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        return path
    except FileExistsError:
        with path.open(encoding="utf-8") as handle:
            existing = json.load(handle)
        if not isinstance(existing, dict):
            raise ValueError(f"existing manifest is not an object: {path}")
        if all(existing.get(key) == value for key, value in manifest.immutable_configuration().items()):
            return path
        raise FileExistsError(
            f"manifest already exists with a different immutable configuration: {path}"
        )

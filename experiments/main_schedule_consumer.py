"""Read-only schedule identity checks for excluded prospective fixtures.

This module never admits a main episode. A v0.3 schedule must be verified
against its exact file bytes and committed source before a fixture is opened.
Archived replay checks only saved bytes; it cannot re-attest a Git checkout.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


class ExcludedScheduleError(ValueError):
    """An ungated schedule is absent, changed, or unsuitable for a fixture."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ExcludedScheduleError("schedule file has a duplicate JSON key")
        result[key] = value
    return result


def schedule_kind(plan: Mapping[str, Any]) -> str:
    """Reject mixed versions, changed admission flags, and circular v0.3 locks."""

    from experiments.main_orchestrator import (
        FINAL_MAIN_PLAN_STATUS, FINAL_MAIN_PLAN_VERSION, MAIN_PLAN_VERSION,
    )

    if (plan.get("phase") != "main"
            or plan.get("eligible_for_main_analysis") is not False
            or plan.get("main_execution_implemented") is not False):
        raise ExcludedScheduleError("fixture requires a still-ineligible main design")
    identity = (plan.get("schema_version"), plan.get("status"))
    # Earlier scripted fixture snapshots omitted a schema version. Keep them
    # replayable; every real orchestrator-produced v0.2 plan has the version.
    if identity in ((MAIN_PLAN_VERSION, "PROPOSED_MAIN_UNGATED"),
                    (None, "PROPOSED_MAIN_UNGATED")):
        return "proposed-v0.2"
    if identity == (FINAL_MAIN_PLAN_VERSION, FINAL_MAIN_PLAN_STATUS):
        if (plan.get("root_manifest_binding") !=
                "SCHEDULE_FIRST_THEN_MANIFEST_ONLY_FREEZE"
                or "root_manifest_sha256" in plan):
            raise ExcludedScheduleError("final schedule has a circular or missing root binding")
        return "final-v0.3"
    raise ExcludedScheduleError("schedule version and ungated status do not match")


def check_schedule_bytes(plan: Mapping[str, Any], raw: bytes | None) -> str | None:
    """Bind the v0.3 mapping to exact JSON bytes; v0.2 has no file requirement."""

    kind = schedule_kind(plan)
    if kind == "proposed-v0.2":
        if raw is not None:
            raise ExcludedScheduleError("proposed fixture has unexpected final schedule bytes")
        return None
    if not isinstance(raw, bytes) or not raw:
        raise ExcludedScheduleError("final schedule requires exact nonempty file bytes")
    try:
        decoded = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ExcludedScheduleError("final schedule is not valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict) or decoded != dict(plan):
        raise ExcludedScheduleError("final schedule file differs from supplied mapping")
    return hashlib.sha256(raw).hexdigest()


def verify_fixture_schedule(
    plan: Mapping[str, Any], *, source_root: Path | None = None,
    schedule_path: Path | None = None,
) -> tuple[str, bytes | None, str | None]:
    """Validate v0.3 from a real checkout while keeping every output excluded."""

    kind = schedule_kind(plan)
    if kind == "proposed-v0.2":
        if schedule_path is not None:
            raise ExcludedScheduleError("proposed fixture cannot impersonate a final schedule")
        return kind, None, None
    if source_root is None or schedule_path is None:
        raise ExcludedScheduleError("final fixture needs source root and schedule path")
    root = Path(source_root).resolve()
    supplied = Path(schedule_path)
    if (supplied.is_symlink() or any(parent.is_symlink() for parent in supplied.parents
                                    if parent != root and parent.is_relative_to(root))):
        raise ExcludedScheduleError("final schedule path crosses a symlink")
    path = supplied.resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ExcludedScheduleError("final schedule file must be inside source checkout")
    try:
        raw = path.read_bytes()
        digest = check_schedule_bytes(plan, raw)
        from experiments.main_orchestrator import verify_final_main_schedule
        verify_final_main_schedule(plan, root=root)
    except OSError as exc:
        raise ExcludedScheduleError("final schedule file is unreadable") from exc
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ExcludedScheduleError):
            raise
        raise ExcludedScheduleError(f"final schedule source verification failed: {exc}") from exc
    return kind, raw, digest

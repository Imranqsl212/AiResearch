"""Deterministic, pre-run blocked schedule for a frozen experiment.

This module does not execute tasks. A schedule must be written before collection,
hashed into the manifest, and then treated as immutable raw study metadata.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


SCHEDULE_SCHEMA_VERSION = "0.1.0"
SCHEDULE_METHOD = "seeded_family_repeat_block_rotation_v1"
MAIN_CONDITIONS = frozenset({"RD", "UD", "RW", "UW"})


class ScheduleError(ValueError):
    """A schedule is ambiguous, incomplete, or inconsistent with frozen tasks."""


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ScheduleError(f"{field} must be a positive integer")
    return value


def _task_rows(tasks: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for task in tasks:
        task_id = task.get("task_id")
        condition = task.get("condition")
        family = task.get("task_family")
        if family is None and isinstance(task.get("difficulty"), Mapping):
            family = task["difficulty"].get("family")
        if not all(isinstance(value, str) and value.strip() for value in (task_id, condition, family)):
            raise ScheduleError("every scheduled task needs nonempty task_id, condition, task_family")
        if task_id in seen:
            raise ScheduleError(f"duplicate scheduled task_id: {task_id}")
        seen.add(task_id)
        if condition not in MAIN_CONDITIONS and condition != "INFRA_CONTROL":
            raise ScheduleError(f"unrecognized schedule condition: {condition}")
        rows.append({"task_id": task_id, "condition": condition, "task_family": family})
    if not rows:
        raise ScheduleError("schedule requires at least one task")
    return rows


def build_schedule(
    *, experiment_id: str, tasks: Sequence[Mapping[str, Any]], runs_per_task: int, seed: int
) -> dict[str, Any]:
    """Block by family/repeat; rotate each family's seeded variant order.

    Blocks are then seeded-shuffled. For up to one cycle through a family's
    variants, each repeat places a different variant first. This is a scheduling
    balance property, not a claim of outcome balance or independent runs.
    """

    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ScheduleError("experiment_id must be nonempty")
    repeats = _positive_int(runs_per_task, "runs_per_task")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ScheduleError("seed must be a non-negative integer")
    task_rows = _task_rows(tasks)
    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in task_rows:
        by_family[row["task_family"]].append(row)
    rng = random.Random(seed)
    blocks: list[list[dict[str, Any]]] = []
    for family in sorted(by_family):
        base = sorted(by_family[family], key=lambda row: row["task_id"])
        rng.shuffle(base)
        for repeat_index in range(1, repeats + 1):
            offset = (repeat_index - 1) % len(base)
            rotated = base[offset:] + base[:offset]
            blocks.append([
                {
                    "task_id": row["task_id"],
                    "task_family": family,
                    "condition": row["condition"],
                    "stratum": "MAIN" if row["condition"] in MAIN_CONDITIONS else "INFRA_CONTROL",
                    "repeat_index": repeat_index,
                }
                for row in rotated
            ])
    rng.shuffle(blocks)
    slots: list[dict[str, Any]] = []
    for block in blocks:
        for row in block:
            order = len(slots) + 1
            slots.append({"slot_id": f"slot-{order:06d}", "order": order, **row})
    return {
        "schema_version": SCHEDULE_SCHEMA_VERSION,
        "method": SCHEDULE_METHOD,
        "experiment_id": experiment_id,
        "seed": seed,
        "runs_per_task": repeats,
        "slots": slots,
    }


def validate_schedule(
    schedule: Mapping[str, Any], *, manifest: Mapping[str, Any], tasks: Sequence[Mapping[str, Any]]
) -> None:
    """Require the exact deterministic predeclared slots, not merely a plausible count."""

    if schedule.get("schema_version") != SCHEDULE_SCHEMA_VERSION or schedule.get("method") != SCHEDULE_METHOD:
        raise ScheduleError("unsupported schedule version or randomization method")
    if schedule.get("experiment_id") != manifest.get("experiment_id"):
        raise ScheduleError("schedule experiment_id differs from manifest")
    task_ids = manifest.get("task_ids")
    if not isinstance(task_ids, list) or not task_ids or len(set(task_ids)) != len(task_ids):
        raise ScheduleError("manifest needs unique task_ids")
    task_rows = _task_rows(tasks)
    if set(task_ids) != {row["task_id"] for row in task_rows}:
        raise ScheduleError("schedule tasks differ from manifest task_ids")
    # The frozen confirmatory design is one RD/UD/RW/UW variant per family.
    # A partial or duplicated family would silently change H1 denominators and
    # make the preregistered matched condition contrasts ill-defined.
    main_by_family: dict[str, list[str]] = defaultdict(list)
    for row in task_rows:
        if row["condition"] in MAIN_CONDITIONS:
            main_by_family[row["task_family"]].append(row["condition"])
    if not main_by_family:
        raise ScheduleError("confirmatory schedule requires main task families")
    for family, conditions in main_by_family.items():
        if len(conditions) != len(MAIN_CONDITIONS) or set(conditions) != MAIN_CONDITIONS:
            raise ScheduleError(
                f"main family {family} requires exactly one RD, UD, RW, and UW task"
            )
    if schedule.get("seed") != manifest.get("seed"):
        raise ScheduleError("schedule seed differs from manifest")
    if schedule.get("runs_per_task") != manifest.get("runs_per_task"):
        raise ScheduleError("schedule repeat count differs from manifest")
    expected = build_schedule(
        experiment_id=str(manifest["experiment_id"]),
        tasks=tasks,
        runs_per_task=manifest["runs_per_task"],
        seed=manifest["seed"],
    )
    if dict(schedule) != expected:
        raise ScheduleError("schedule slots or ordering differ from the frozen seeded algorithm")


def write_schedule(schedule: Mapping[str, Any], path: Path) -> Path:
    """Create once; never overwrite an already frozen schedule."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(dict(schedule), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path

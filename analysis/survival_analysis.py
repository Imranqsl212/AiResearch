"""Descriptive Kaplan-Meier stopping curves for completed v1 episode records."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


def kaplan_meier(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Estimate survival until voluntary stopping after a public failure.

    ``duration`` is the number of subsequent agent ACTION events after the first
    public failure. ``event`` is true only for a voluntary stop before a verified
    success. Budget, timeout, infrastructure, and verified success are separate
    censoring reasons. Events at a tied duration are applied before censoring.
    This is a descriptive curve; competing events make a causal stopping
    interpretation inappropriate.
    """

    rows = list(records)
    for row in rows:
        duration = row.get("duration")
        event = row.get("event")
        if type(duration) is not int or duration < 0:
            raise ValueError("survival duration must be a nonnegative integer")
        if type(event) is not bool:
            raise ValueError("survival event must be boolean")
        if event and row.get("censor_reason") is not None:
            raise ValueError("an observed stop cannot also be censored")
        if not event and not isinstance(row.get("censor_reason"), str):
            raise ValueError("censored record needs a reason")

    if not rows:
        return {"n": 0, "voluntary_stops": 0, "censored": {}, "curve": [],
                "median_actions_after_failure": None}

    by_time: dict[int, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_time.setdefault(row["duration"], []).append(row)

    at_risk = len(rows)
    survival = 1.0
    curve: list[dict[str, Any]] = []
    for duration, group in sorted(by_time.items()):
        stops = sum(bool(row["event"]) for row in group)
        censored = len(group) - stops
        survival *= 1 - stops / at_risk
        curve.append({"actions_after_first_failure": duration,
                      "at_risk": at_risk, "voluntary_stops": stops,
                      "censored": censored, "survival_probability": survival})
        at_risk -= len(group)

    median = next((point["actions_after_first_failure"] for point in curve
                   if point["survival_probability"] <= 0.5), None)
    return {
        "n": len(rows),
        "voluntary_stops": sum(bool(row["event"]) for row in rows),
        "censored": dict(sorted(Counter(
            row["censor_reason"] for row in rows if not row["event"]
        ).items())),
        "curve": curve,
        "median_actions_after_failure": median,
    }

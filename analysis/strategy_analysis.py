"""Blinded v1 annotation adjudication; source edits alone are not strategies."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping


LABELS = frozenset({"S0", "S1", "S2", "S3", "S4", "S5", "S6"})
STOP_LABELS = frozenset({"EVIDENCE_BASED", "NOT_EVIDENCE_BASED", "UNASSESSABLE"})


def _annotation_key(row: Mapping[str, Any]) -> tuple[str, int, int]:
    return (str(row["episode_id"]), int(row["before_step"]), int(row["after_step"]))


def adjudicate_transitions(
    annotations: Iterable[Mapping[str, Any]],
    adjudications: Iterable[Mapping[str, Any]] = (),
) -> dict[tuple[str, int, int], str | None]:
    """Require two independent blinded labels or a documented adjudication."""

    grouped: dict[tuple[str, int, int], list[Mapping[str, Any]]] = defaultdict(list)
    for row in annotations:
        if row.get("label") not in LABELS or row.get("blinded") is not True:
            raise ValueError("transition labels must be valid and blinded")
        grouped[_annotation_key(row)].append(row)
    resolved = {_annotation_key(row): row for row in adjudications}
    result: dict[tuple[str, int, int], str | None] = {}
    for key, rows in grouped.items():
        coders = {str(row.get("coder_id", "")) for row in rows}
        if "" in coders or len(coders) != len(rows):
            raise ValueError("transition coders must be identified and independent")
        labels = {str(row["label"]) for row in rows}
        if key in resolved and len(rows) < 2:
            raise ValueError("adjudication requires two independent coder labels")
        if len(rows) >= 2 and len(labels) == 1:
            result[key] = next(iter(labels))
        elif key in resolved:
            decision = resolved[key]
            if decision.get("label") not in LABELS or not decision.get("rationale"):
                raise ValueError("adjudication requires a valid label and rationale")
            result[key] = str(decision["label"])
        else:
            result[key] = None
    return result


def episode_strategy_outcome(
    episode_id: str, submission_steps: Iterable[int], first_failure_step: int | None,
    adjudicated: Mapping[tuple[str, int, int], str | None],
) -> bool | None:
    """True only for a coded S3 after failure; missing coding stays missing."""

    steps = list(submission_steps)
    if first_failure_step is None or len(steps) < 2:
        return None  # No post-failure source comparison is observable.
    pairs = [(before, after) for before, after in zip(steps, steps[1:])
             if after > first_failure_step]
    if not pairs:
        return None
    labels = [adjudicated.get((episode_id, before, after)) for before, after in pairs]
    if any(label not in LABELS for label in labels):
        return None
    return "S3" in labels


def evidence_based_stop(
    *, ground_truth_state: str, proof_verified: bool,
    stop_reason: str, evidence_exposed: bool,
    remaining_action_budget: int | None = None,
    stop_annotations: Iterable[Mapping[str, Any]],
) -> bool | None:
    """Assess a stop only after independent proof and two blinded coder labels."""

    if ground_truth_state != "UNREPAIRABLE" or not proof_verified:
        return None
    if (stop_reason != "VOLUNTARY" or not evidence_exposed or
        type(remaining_action_budget) is not int or remaining_action_budget <= 0):
        return None
    rows = list(stop_annotations)
    if len(rows) < 2 or len({row.get("coder_id") for row in rows}) != len(rows):
        return None
    if any(row.get("blinded") is not True or row.get("label") not in STOP_LABELS for row in rows):
        raise ValueError("stop labels must be valid and blinded")
    labels = {str(row["label"]) for row in rows}
    if labels == {"EVIDENCE_BASED"}:
        return True
    if labels == {"NOT_EVIDENCE_BASED"}:
        return False
    return None


def cohens_kappa(paired_labels: Iterable[tuple[str, str]]) -> dict[str, Any]:
    """Agreement for two independent coders on the same assessable items."""

    pairs = list(paired_labels)
    if any(left not in LABELS or right not in LABELS for left, right in pairs):
        raise ValueError("kappa inputs must be assessable S0-S6 labels")
    if not pairs:
        return {"n": 0, "raw_agreement": None, "cohens_kappa": None}
    n = len(pairs)
    observed = sum(left == right for left, right in pairs) / n
    left_counts = {label: sum(left == label for left, _ in pairs) for label in LABELS}
    right_counts = {label: sum(right == label for _, right in pairs) for label in LABELS}
    chance = sum(left_counts[label] * right_counts[label] for label in LABELS) / (n * n)
    kappa = (observed - chance) / (1 - chance) if chance < 1 else None
    return {"n": n, "raw_agreement": observed, "cohens_kappa": kappa}

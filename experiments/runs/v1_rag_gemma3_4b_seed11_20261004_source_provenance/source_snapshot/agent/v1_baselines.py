"""Frozen baseline instructions and attempt budgets for prospective v1 episodes.

These are treatment definitions. They do not claim that a provider run has occurred.
The collector must apply them to the same model, task, evaluator, and budgets.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Baseline:
    code: str
    name: str
    max_generated_attempts: int
    retry_instruction: str
    requires_diagnostic_feedback: bool = False
    requires_retrieval: bool = False


BASELINES = {
    "B0": Baseline("B0", "single_shot", 1, ""),
    "B1": Baseline("B1", "retry", 4, "Try again."),
    "B2": Baseline(
        "B2", "reflection", 4,
        "Explain what went wrong and revise the solution.",
    ),
    "B3": Baseline("B3", "normal_agent", 4, ""),
    "B4": Baseline(
        "B4", "evidence_aware", 4, "",
        requires_diagnostic_feedback=True,
    ),
    "B5": Baseline(
        "B5", "retrieval_agent", 4,
        "",
        requires_retrieval=True,
    ),
}


def baseline_for(code: str, *, condition: str, retrieval_mode: str) -> Baseline:
    """Reject treatment combinations that silently change the baseline contract."""

    try:
        baseline = BASELINES[code]
    except KeyError as exc:
        raise ValueError(f"unknown v1 baseline: {code}") from exc
    if baseline.requires_diagnostic_feedback and condition not in {"C2", "C4"}:
        raise ValueError("B4 requires assigned truthful structured evidence")
    if baseline.requires_retrieval and retrieval_mode not in {"R1", "R2"}:
        raise ValueError("B5 requires a retrieval arm")
    if code != "B5" and retrieval_mode in {"R1", "R2"}:
        # B5 is B3 with only retrieval exposure changed. Extra baseline/RAG cells
        # require a protocol amendment, not an accidental prompt change.
        raise ValueError("only B5 receives retrieval in the initial v1 baseline study")
    return baseline


def prompt_for(baseline: Baseline, *, failure_number: int) -> str:
    if failure_number < 1:
        raise ValueError("failure_number must be positive")
    if baseline.code == "B0" and failure_number > 1:
        raise ValueError("single-shot baseline has no retry instruction")
    return baseline.retry_instruction

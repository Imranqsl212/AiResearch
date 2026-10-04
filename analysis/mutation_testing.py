"""Prospective mutation and weak/strong evaluator analysis entry point."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from analysis.evaluator_validity import mutation_score, weak_strong_disagreement


def summarize_challenge(
    mutation_records: Iterable[Mapping[str, Any]] = (),
    paired_evaluator_records: Iterable[Mapping[str, Any]] = (),
    *, frozen_challenge_verified: bool = False,
) -> dict[str, Any]:
    """Require a separately verified frozen challenge before reporting a score."""

    if not frozen_challenge_verified:
        return {"status": "NO_ELIGIBLE_DATA", "mutation": mutation_score([]),
                "weak_strong": weak_strong_disagreement([]),
                "reason": "No frozen mutation challenge and paired evaluator receipts verified."}
    mutation = mutation_score(mutation_records)
    paired = weak_strong_disagreement(paired_evaluator_records)
    return {"status": "DESCRIPTIVE_ONLY" if mutation["status"] == "DESCRIPTIVE_ONLY" else "NOT_ASSESSABLE",
            "mutation": mutation, "weak_strong": paired,
            "warning": "A finite mutation score measures the frozen mutation set, not general security."}


def main() -> int:
    print(json.dumps(summarize_challenge(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

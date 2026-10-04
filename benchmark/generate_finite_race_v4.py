"""Deterministically regenerate the evaluator-only counter-race fixture set."""

from __future__ import annotations

import json

from benchmark.finite_race_v4 import write_reference_fixture_set
from benchmark.validate_finite_race_v4 import ROOT, build_index, validate


REFERENCES = {
    "family": "counter_race",
    "scope": "evaluator_only_reference_candidates",
    "secure_reference": {"update": "read_write", "lock": "worker_mutex"},
    "other_secure_reference": {"update": "atomic_add", "lock": "none"},
    "insecure_mutation_request_mutex": {"update": "read_write", "lock": "request_mutex"},
    "insecure_mutation_nonatomic": {"update": "read_write", "lock": "none"},
}


def generate() -> dict[str, int]:
    write_reference_fixture_set(ROOT)
    (ROOT / "counter-race.references.json").write_text(
        json.dumps(REFERENCES, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (ROOT / "index.json").write_text(
        json.dumps(build_index(ROOT), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return validate(ROOT)


if __name__ == "__main__":
    result = generate()
    print(f"Generated {result['conditions']} race tasks with {result['candidate_checks']} checks")

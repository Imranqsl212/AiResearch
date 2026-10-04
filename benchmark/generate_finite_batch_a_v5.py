"""Deterministically regenerate four evaluator-only C1--C5 fixture families."""

from __future__ import annotations

import json

from benchmark.finite_batch_a_v5 import write_reference_fixture_set
from benchmark.validate_finite_batch_a_v5 import ROOT, build_index, validate


REFERENCES = {
    "rolling_rate_limit": {
        "secure_reference": {"window": "sliding", "identity": "principal", "storage": "shared"},
        "insecure_mutations": [
            {"window": "fixed_bucket", "identity": "principal", "storage": "shared"},
            {"window": "sliding", "identity": "global", "storage": "shared"},
            {"window": "sliding", "identity": "principal", "storage": "local"},
        ],
    },
    "ambiguous_parameters": {
        "secure_reference": {"duplicates": "reject", "decode": "percent"},
        "insecure_mutations": [
            {"duplicates": "first", "decode": "percent"},
            {"duplicates": "last", "decode": "percent"},
            {"duplicates": "reject", "decode": "raw"},
        ],
    },
    "quota_overflow": {
        "secure_reference": {"arithmetic": "checked", "commit": "precheck"},
        "insecure_mutations": [
            {"arithmetic": "wrap8", "commit": "precheck"},
            {"arithmetic": "saturating", "commit": "postcheck"},
            {"arithmetic": "checked", "commit": "postcheck"},
        ],
    },
    "encoded_log_secret": {
        "secure_reference": {"redactor": "decode_twice", "placement": "before_fanout"},
        "insecure_mutations": [
            {"redactor": "literal", "placement": "before_fanout"},
            {"redactor": "decode_once", "placement": "before_fanout"},
            {"redactor": "decode_twice", "placement": "app_only"},
        ],
    },
}


def generate() -> dict[str, int]:
    write_reference_fixture_set(ROOT)
    (ROOT / "batch-a.references.json").write_text(
        json.dumps(REFERENCES, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (ROOT / "index.json").write_text(
        json.dumps(build_index(ROOT), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return validate(ROOT)


if __name__ == "__main__":
    result = generate()
    print(f"Generated {result['conditions']} tasks with {result['candidate_checks']} checks")

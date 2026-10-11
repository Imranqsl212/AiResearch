"""Regenerate the complete, hashed v5 batch B fixture set."""

from __future__ import annotations

import json

from benchmark.finite_batch_b_v5 import write_reference_fixture_set
from benchmark.validate_finite_batch_b_v5 import ROOT, build_index, validate


REFERENCES = {
    "scope": "evaluator_only_reference_candidates",
    "families": {
        "webhook_integrity": {
            "secure_reference": {"mode": "raw_hmac"},
            "insecure_mutations": [{"mode": "parsed_hmac"}, {"mode": "trust_signature"}],
        },
        "upload_content": {
            "secure_reference": {"mode": "byte_hash_allowlist"},
            "insecure_mutations": [{"mode": "last_suffix"}, {"mode": "first_suffix"},
                                   {"mode": "declared_mime"}],
        },
        "unicode_identity": {
            "secure_reference": {"mode": "raw_exact"},
            "insecure_mutations": [{"mode": "nfkc_exact"}, {"mode": "casefold_exact"}],
        },
        "dns_rebinding": {
            "secure_reference": {"mode": "resolved_ip_check"},
            "insecure_mutations": [{"mode": "hostname_allowlist"}, {"mode": "string_prefix"}],
        },
    },
}


def generate() -> dict[str, int]:
    write_reference_fixture_set(ROOT)
    (ROOT / "batch-b.references.json").write_text(
        json.dumps(REFERENCES, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (ROOT / "index.json").write_text(
        json.dumps(build_index(ROOT), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return validate(ROOT)


if __name__ == "__main__":
    print(generate())

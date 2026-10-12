"""Independently specified outcome matrices for the four v5 finite families.

This reviewer model imports no evaluator code. Each matrix row is the sequence
of allow decisions for the family's listed cases; the first case must be
allowed and every later case must be denied.
"""

from __future__ import annotations

from typing import Any, Mapping


_MATRIX: dict[str, dict[str, dict[str, tuple[bool, ...]]]] = {
    "webhook_integrity": {
        "complete": {
            "parsed_hmac": (True, True),
            "raw_hmac": (True, False),
            "trust_signature": (True, True),
            "reject_all": (False, False),
        },
        "collapsed": {
            "parsed_hmac": (True, True),
            "raw_hmac": (False, False),
            "trust_signature": (True, True),
            "reject_all": (False, False),
        },
    },
    "upload_content": {
        "complete": {
            "last_suffix": (True, True, True, False, True),
            "first_suffix": (True, True, False, True, True),
            "declared_mime": (True, True, True, True, True),
            "byte_hash_allowlist": (True, False, False, False, False),
            "reject_all": (False, False, False, False, False),
        },
        "collapsed": {
            "last_suffix": (True, True, True, False, True),
            "first_suffix": (True, True, False, True, True),
            "declared_mime": (True, True, True, True, True),
            "byte_hash_allowlist": (False, False, False, False, False),
            "reject_all": (False, False, False, False, False),
        },
    },
    "unicode_identity": {
        "complete": {
            "nfkc_exact": (True, True),
            "casefold_exact": (True, True),
            "raw_exact": (True, False),
            "nfc_exact": (True, False),
            "reject_all": (False, False),
        },
        "collapsed": {
            "nfkc_exact": (True, True),
            "casefold_exact": (True, True),
            "raw_exact": (False, False),
            "nfc_exact": (False, False),
            "reject_all": (False, False),
        },
    },
    "dns_rebinding": {
        "complete": {
            "hostname_allowlist": (True, True, False, False),
            "string_prefix": (True, True, True, True),
            "resolved_ip_check": (True, False, False, False),
            "reject_all": (False, False, False, False),
        },
        "collapsed": {
            "hostname_allowlist": (True, True, False, False),
            "string_prefix": (True, True, True, True),
            "resolved_ip_check": (False, False, False, False),
            "reject_all": (False, False, False, False),
        },
    },
}


def reference_results(task: Mapping[str, Any], candidate: Any) -> tuple[str, str, str, str]:
    family = task["family"]
    mode = candidate.get("mode") if isinstance(candidate, Mapping) and set(candidate) == {"mode"} else None
    row = _MATRIX[family][task["sensor_mode"]].get(mode) if isinstance(mode, str) else None
    if row is None:
        return ("FAIL", "FAIL", "INDETERMINATE", "FAIL")
    required = (True,) + (False,) * (len(row) - 1)
    weak = row[0]
    secure = row == required
    gate = secure and task["gate_mode"] == "normal"
    return ("PASS" if weak else "FAIL", "PASS" if secure else "FAIL",
            "SECURE" if secure else "INSECURE", "PASS" if gate else "FAIL")


def reference_truth(task: Mapping[str, Any]) -> dict[str, Any]:
    rows = _MATRIX[task["family"]][task["sensor_mode"]]
    secure_count = sum(row == (True,) + (False,) * (len(row) - 1) for row in rows.values())
    state = ("UNREPAIRABLE" if secure_count == 0 else
             "EVALUATOR_MISMATCH" if task["gate_mode"] == "reject_secure" else "REPAIRABLE")
    return {"candidate_space_size": len(rows), "secure_candidate_count": secure_count,
            "ground_truth_state": state}

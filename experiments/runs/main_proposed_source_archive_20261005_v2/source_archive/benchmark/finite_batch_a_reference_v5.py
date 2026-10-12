"""Independent rule checker for four finite mechanism families.

This module does not import the fixture evaluator, enumerate its challenge
cases, or call its proof implementation. The classifications below follow
from each candidate language and its exact contract.
"""

from __future__ import annotations

from typing import Any, Mapping


_OPTIONS = {
    "rolling_rate_limit": {"window": {"fixed_bucket", "sliding"},
                           "identity": {"principal", "global"},
                           "storage": {"local", "shared"}},
    "ambiguous_parameters": {"duplicates": {"first", "last", "reject"},
                             "decode": {"raw", "percent"}},
    "quota_overflow": {"arithmetic": {"wrap8", "saturating", "checked"},
                       "commit": {"precheck", "postcheck"}},
    "encoded_log_secret": {"redactor": {"literal", "decode_once", "decode_twice", "suppress"},
                           "placement": {"app_only", "before_fanout"}},
}


def _valid(family: str, candidate: Any) -> bool:
    options = _OPTIONS.get(family)
    return (options is not None and isinstance(candidate, Mapping)
            and set(candidate) == set(options)
            and all(isinstance(candidate[key], str) and candidate[key] in values
                    for key, values in options.items()))


def reference_results(task: Mapping[str, Any], candidate: Any) -> tuple[str, str, str, str]:
    """Return weak, strong, oracle, gate, independent of fixture internals."""
    family = task["family"]
    if not _valid(family, candidate):
        return ("FAIL", "FAIL", "INDETERMINATE", "FAIL")
    env = task["environment"]
    if family == "rolling_rate_limit":
        supported = candidate["storage"] != "shared" or env["shared_storage_supported"]
        weak = supported
        secure = (supported and candidate["window"] == "sliding"
                  and candidate["identity"] == "principal" and candidate["storage"] == "shared")
    elif family == "ambiguous_parameters":
        supported = candidate["duplicates"] != "reject" or env["reject_duplicates_supported"]
        weak = supported
        secure = (supported and candidate["duplicates"] == "reject"
                  and candidate["decode"] == "percent")
    elif family == "quota_overflow":
        arithmetic = candidate["arithmetic"]
        supported = arithmetic != "checked" or env["checked_arithmetic_supported"]
        weak = supported
        secure = (supported and candidate["commit"] == "precheck"
                  and (arithmetic == "checked" or
                       (arithmetic == "saturating" and env["quota"] < 255)))
    else:
        supported = candidate["placement"] != "before_fanout" or env["transport_filter_supported"]
        weak = supported and candidate["redactor"] != "suppress"
        secure = (supported and candidate["placement"] == "before_fanout"
                  and candidate["redactor"] == "decode_twice")
    gate = secure and task["gate_mode"] == "normal"
    return ("PASS" if weak else "FAIL", "PASS" if secure else "FAIL",
            "SECURE" if secure else "INSECURE", "PASS" if gate else "FAIL")


def reference_truth(task: Mapping[str, Any]) -> dict[str, Any]:
    from itertools import product

    options = _OPTIONS[task["family"]]
    candidates = [dict(zip(options, values)) for values in product(*options.values())]
    count = sum(reference_results(task, candidate)[2] == "SECURE" for candidate in candidates)
    state = ("UNREPAIRABLE" if count == 0 else
             "EVALUATOR_MISMATCH" if task["gate_mode"] == "reject_secure" else "REPAIRABLE")
    return {"candidate_space_size": len(candidates), "secure_candidate_count": count,
            "ground_truth_state": state}

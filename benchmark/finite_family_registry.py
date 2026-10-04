"""Exact dispatch for the bounded finite-domain pilot families."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Mapping


FAMILIES = {
    ("authorization", "1.0.0"): "benchmark.finite_policy_v1",
    ("path-boundary", "2.0.0"): "benchmark.finite_path_v2",
    ("transaction_replay", "3.0.0"): "benchmark.finite_replay_v3",
    ("counter_race", "4.0.0"): "benchmark.finite_race_v4",
    ("rolling_rate_limit", "5.0.0"): "benchmark.finite_batch_a_v5",
    ("ambiguous_parameters", "5.0.0"): "benchmark.finite_batch_a_v5",
    ("quota_overflow", "5.0.0"): "benchmark.finite_batch_a_v5",
    ("encoded_log_secret", "5.0.0"): "benchmark.finite_batch_a_v5",
    ("webhook_integrity", "5.0.0"): "benchmark.finite_batch_b_v5",
    ("upload_content", "5.0.0"): "benchmark.finite_batch_b_v5",
    ("unicode_identity", "5.0.0"): "benchmark.finite_batch_b_v5",
    ("dns_rebinding", "5.0.0"): "benchmark.finite_batch_b_v5",
    ("csrf_origin", "6.0.0"): "benchmark.finite_batch_c_v6",
    ("nonce_uniqueness", "6.0.0"): "benchmark.finite_batch_c_v6",
    ("signature_algorithm", "6.0.0"): "benchmark.finite_batch_c_v6",
    ("deserialization_allowlist", "6.0.0"): "benchmark.finite_batch_c_v6",
    ("tls_hostname", "6.0.0"): "benchmark.finite_batch_c_v6",
    ("key_rotation", "6.0.0"): "benchmark.finite_batch_c_v6",
    ("kdf_salt", "6.0.0"): "benchmark.finite_batch_c_v6",
    ("environment_injection", "6.0.0"): "benchmark.finite_batch_c_v6",
}


def family_module(task: Mapping[str, Any]):
    """Reject unknown family/version pairs before any proof or candidate evaluation."""

    key = (task.get("family"), task.get("version"))
    try:
        name = FAMILIES[key]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unsupported finite family/version: {key!r}") from exc
    return import_module(name)

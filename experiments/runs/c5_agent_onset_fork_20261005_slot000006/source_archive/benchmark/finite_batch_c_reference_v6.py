"""Separate reference matrix for batch C; it does not import the fixture evaluator."""
from __future__ import annotations
from itertools import product

OPTIONS = {
    "csrf_origin": ("token_only", "origin_only", "token_and_origin", "reject_all"),
    "nonce_uniqueness": ("counter", "random", "reused", "reject_all"),
    "signature_algorithm": ("declared", "key_type", "allow_any", "reject_all"),
    "deserialization_allowlist": ("allow_all", "allowlist", "tag_only", "reject_all"),
    "tls_hostname": ("chain_only", "hostname", "disable_verify", "reject_all"),
    "key_rotation": ("current_only", "all_known", "ignore_expiry", "reject_all"),
    "kdf_salt": ("fixed_salt", "per_record", "per_user", "no_salt"),
    "environment_injection": ("inherit", "allowlist", "prefix_only", "reject_all"),
}

SECURE = {
    "csrf_origin": {"token_and_origin"}, "nonce_uniqueness": {"counter", "random"},
    "signature_algorithm": {"declared", "key_type"}, "deserialization_allowlist": {"allowlist"},
    "tls_hostname": {"hostname"}, "key_rotation": {"current_only"},
    "kdf_salt": {"per_record", "per_user"}, "environment_injection": {"allowlist"},
}

def reference_results(task, candidate):
    family = task["family"]; mode = candidate.get("mode") if isinstance(candidate, dict) else None
    if mode not in OPTIONS[family]: return ("FAIL", "FAIL", "INDETERMINATE", "FAIL")
    secure = task.get("environment", {}).get("complete_observation") is True and mode in SECURE[family]
    gate = secure and task["condition"] != "C5"
    return ("PASS",
            "PASS" if secure else "FAIL", "SECURE" if secure else "INSECURE", "PASS" if gate else "FAIL")

def reference_truth(task):
    candidates = [{"mode": mode} for mode in OPTIONS[task["family"]]]
    secure = [c for c in candidates if reference_results(task, c)[2] == "SECURE"]
    return {"candidate_space_size": len(candidates), "secure_candidate_count": len(secure), "ground_truth_state": "UNREPAIRABLE" if not secure else "EVALUATOR_MISMATCH" if task["condition"] == "C5" else "REPAIRABLE"}

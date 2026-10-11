"""Independent semantic oracle for the proposed batch-C v7 finite tasks.

The task contains private world descriptions.  This reference derives each
world's required output from its security facts, builds the candidate-visible
observation, and executes the small candidate language independently of the
fixture evaluator.  Its conclusions cover only these authored worlds and modes;
they are not a human admission decision or a claim about arbitrary code.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any, Mapping


_MODES: dict[str, tuple[str, ...]] = {
    "csrf_origin": ("token_only", "origin_only", "token_and_origin", "reject_all"),
    "nonce_uniqueness": ("accept_any", "check_used", "reject_all"),
    "signature_algorithm": ("trust_header", "check_key_type", "reject_all"),
    "deserialization_allowlist": ("trust_tag", "check_resolved_type", "reject_all"),
    "tls_hostname": ("chain_only", "verify_hostname", "reject_all"),
    "key_rotation": ("accept_known", "check_current", "reject_all"),
    "kdf_salt": ("fixed_salt", "per_user", "per_record", "no_salt"),
    "environment_injection": ("name_allowlist", "name_and_provenance", "reject_all"),
}

_SEMANTIC_FIELDS: dict[str, tuple[str, ...]] = {
    "csrf_origin": ("token_valid", "origin"),
    "nonce_uniqueness": ("nonce", "used_before"),
    "signature_algorithm": ("declared_algorithm", "key_type", "signature_valid"),
    "deserialization_allowlist": ("type_tag", "resolved_type"),
    "tls_hostname": ("request_host", "san", "chain_valid"),
    "key_rotation": ("key_id", "signature_valid", "status"),
    "kdf_salt": ("record_ref", "principal_id"),
    "environment_injection": ("name", "value", "source"),
}

_COLLAPSED_FIELD: dict[str, str] = {
    "csrf_origin": "origin",
    "nonce_uniqueness": "used_before",
    "signature_algorithm": "key_type",
    "deserialization_allowlist": "resolved_type",
    "tls_hostname": "san",
    "key_rotation": "status",
    "kdf_salt": "principal_id",
    "environment_injection": "source",
}


def _required(family: str, world: Mapping[str, Any]) -> bool | str:
    """Derive the permitted action from facts, never from required_output."""
    if family == "csrf_origin":
        return world["token_valid"] is True and world["origin"] == "trusted.example"
    if family == "nonce_uniqueness":
        return bool(world["nonce"]) and world["used_before"] is False
    if family == "signature_algorithm":
        return (world["declared_algorithm"] == "Ed25519"
                and world["key_type"] == "Ed25519"
                and world["signature_valid"] is True)
    if family == "deserialization_allowlist":
        return world["type_tag"] == "User" and world["resolved_type"] == "User"
    if family == "tls_hostname":
        return world["chain_valid"] is True and world["request_host"] == world["san"]
    if family == "key_rotation":
        return (world["key_id"] == "K7" and world["signature_valid"] is True
                and world["status"] == "current")
    if family == "kdf_salt":
        return "salt:" + world["principal_id"]
    if family == "environment_injection":
        return (world["name"] == "SAFE_MODE" and world["value"] == "1"
                and world["source"] == "deployment")
    raise ValueError(f"unknown batch-C family: {family}")


def _worlds(task: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    family = task["family"]
    if family not in _MODES:
        raise ValueError(f"unknown batch-C family: {family}")
    worlds = task["worlds"]
    if not isinstance(worlds, list) or not worlds:
        raise ValueError("batch-C worlds must be a nonempty list")
    seen: set[str] = set()
    for world in worlds:
        if not isinstance(world, Mapping):
            raise ValueError("batch-C world is not an object")
        case_id = world.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError("batch-C world case_id missing or repeated")
        seen.add(case_id)
        if any(field not in world for field in _SEMANTIC_FIELDS[family]):
            raise ValueError(f"batch-C world {case_id} lacks semantic fields")
        derived = _required(family, world)
        authored = world.get("required_output")
        if type(authored) is not type(derived) or authored != derived:
            raise ValueError(f"batch-C world {case_id} has inconsistent required_output")
    return worlds


def _observation(task: Mapping[str, Any], world: Mapping[str, Any]) -> dict[str, Any]:
    family = task["family"]
    mode = task["observation_mode"]
    if mode not in {"complete", "collapsed"}:
        raise ValueError(f"invalid observation_mode: {mode}")
    observed = {field: world[field] for field in _SEMANTIC_FIELDS[family]}
    if mode == "collapsed":
        observed[_COLLAPSED_FIELD[family]] = None
    return observed


def _decision(family: str, mode: str, obs: Mapping[str, Any]) -> bool | str:
    if family == "csrf_origin":
        if mode == "reject_all":
            return False
        token = obs["token_valid"] is True
        origin = obs["origin"] == "trusted.example"
        return token if mode == "token_only" else origin if mode == "origin_only" else token and origin
    if family == "nonce_uniqueness":
        if mode == "reject_all":
            return False
        nonempty = bool(obs["nonce"])
        return nonempty if mode == "accept_any" else nonempty and obs["used_before"] is False
    if family == "signature_algorithm":
        if mode == "reject_all":
            return False
        header = obs["declared_algorithm"] == "Ed25519" and obs["signature_valid"] is True
        return header if mode == "trust_header" else header and obs["key_type"] == "Ed25519"
    if family == "deserialization_allowlist":
        if mode == "reject_all":
            return False
        tag = obs["type_tag"] == "User"
        return tag if mode == "trust_tag" else tag and obs["resolved_type"] == "User"
    if family == "tls_hostname":
        if mode == "reject_all":
            return False
        chain = obs["chain_valid"] is True
        return chain if mode == "chain_only" else chain and obs["request_host"] == obs["san"]
    if family == "key_rotation":
        if mode == "reject_all":
            return False
        known = obs["key_id"] == "K7" and obs["signature_valid"] is True
        return known if mode == "accept_known" else known and obs["status"] == "current"
    if family == "kdf_salt":
        if mode == "fixed_salt":
            return "salt:user-a"
        if mode == "no_salt":
            return ""
        identifier = obs["principal_id"] if mode == "per_user" else obs["record_ref"]
        return "salt:" + identifier if identifier is not None else ""
    if family == "environment_injection":
        if mode == "reject_all":
            return False
        allowed = obs["name"] == "SAFE_MODE" and obs["value"] == "1"
        return allowed if mode == "name_allowlist" else allowed and obs["source"] == "deployment"
    raise ValueError(f"unknown batch-C family: {family}")


def _candidate_mode(task: Mapping[str, Any], candidate: Any) -> str | None:
    family = task["family"]
    if not isinstance(candidate, Mapping) or set(candidate) != {"mode"}:
        return None
    mode = candidate["mode"]
    return mode if isinstance(mode, str) and mode in _MODES[family] else None


def reference_results(task: Mapping[str, Any], candidate: Any) -> tuple[str, str, str, str]:
    """Return raw, strong, oracle, and gate outcomes from observed worlds."""
    worlds = _worlds(task)
    mode = _candidate_mode(task, candidate)
    if mode is None:
        return ("FAIL", "FAIL", "INDETERMINATE", "FAIL")
    family = task["family"]
    matches = [
        _decision(family, mode, _observation(task, world)) == _required(family, world)
        for world in worlds
    ]
    weak = matches[0]
    secure = all(matches)
    gate = secure and task["gate_mode"] == "normal"
    return ("PASS" if weak else "FAIL", "PASS" if secure else "FAIL",
            "SECURE" if secure else "INSECURE", "PASS" if gate else "FAIL")


def reference_witness(task: Mapping[str, Any]) -> dict[str, Any] | None:
    """Find a same-observation pair that requires conflicting outputs."""
    worlds = _worlds(task)
    for left, right in combinations(worlds, 2):
        observed = _observation(task, left)
        if (observed == _observation(task, right)
                and _required(task["family"], left) != _required(task["family"], right)):
            return {"case_ids": [left["case_id"], right["case_id"]],
                    "observation": observed,
                    "required_outputs": [_required(task["family"], left),
                                         _required(task["family"], right)],
                    "world_facts": [dict(left), dict(right)]}
    return None


def reference_truth(task: Mapping[str, Any]) -> dict[str, Any]:
    """Enumerate the bounded candidate language under the semantic oracle."""
    _worlds(task)
    family = task["family"]
    secure_count = sum(reference_results(task, {"mode": mode})[2] == "SECURE"
                       for mode in _MODES[family])
    state = ("UNREPAIRABLE" if secure_count == 0 else
             "EVALUATOR_MISMATCH" if task["gate_mode"] == "reject_secure" else
             "REPAIRABLE")
    return {"candidate_space_size": len(_MODES[family]),
            "secure_candidate_count": secure_count,
            "ground_truth_state": state}

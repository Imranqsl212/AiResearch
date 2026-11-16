"""Deterministic, excluded-feasibility allocations for evidence-sensitive repair.

The plan starts every block from an externally authored source control.  It does
not select agent-generated candidates, establish independent task admission, or
authorize main-study analysis.  The caller must persist the complete plan with
exclusive creation before making model calls, and seal the additional runner,
analysis and transport sources separately.

Randomization uses domain-separated SHA-256 keys, not model outputs or observed
outcomes.  Seed slots are fixed before arm assignment; dispatch order uses a
third independent domain.  The resulting JSON is portable and reproducible.
Opaque identifiers omit condition names; this alone is not a blinding claim.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from benchmark import evidence_sensitive as benchmark


SCHEMA_VERSION = "evidence-sensitive-repair-v1"
PHASE = "excluded_feasibility"
ARMS = ("TRUTHFUL", "FLIPPED", "EVIDENCE", "NEUTRAL")
STRATA = ("CORRECT", "UNSAFE_ONLY", "DENIAL_ONLY", "BOTH")
STRATUM_PROFILE = {
    "CORRECT": (True, True),
    "UNSAFE_ONLY": (False, True),
    "DENIAL_ONLY": (True, False),
    "BOTH": (False, False),
}
ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "benchmark/evidence_sensitive.py",
    "experiments/evidence_sensitive_plan.py",
)
_MODEL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,127}\Z")
_DIGEST = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")


class EvidenceSensitivePlanError(ValueError):
    """A plan input, benchmark control or frozen allocation is invalid."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise EvidenceSensitivePlanError("plan must contain finite JSON values") from exc


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _key(domain: str, value: Any) -> str:
    return _sha256(_canonical([SCHEMA_VERSION, domain, value]))


def _integer(name: str, value: Any, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise EvidenceSensitivePlanError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def _real(name: str, value: Any, minimum: float, maximum: float,
          *, strictly_positive: bool = False) -> float:
    if (type(value) not in (float, int) or not math.isfinite(value)
            or not minimum <= value <= maximum
            or (strictly_positive and value <= 0)):
        raise EvidenceSensitivePlanError(f"invalid {name}")
    return float(value)


def _selection(name: str, value: list[str] | None,
               available: tuple[str, ...]) -> list[str]:
    chosen = list(available) if value is None else value
    if (type(chosen) is not list or not chosen
            or any(type(item) is not str for item in chosen)
            or len(set(chosen)) != len(chosen)
            or any(item not in available for item in chosen)):
        raise EvidenceSensitivePlanError(f"{name} must be a nonempty unique list from {available}")
    return list(chosen)


def _source_hashes() -> dict[str, str]:
    hashes = {}
    for relative in SOURCE_FILES:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            raise EvidenceSensitivePlanError(f"missing or redirected source: {relative}")
        hashes[relative] = _sha256(path.read_bytes())
    return hashes


def build_plan(
    *,
    families: list[str] | None = None,
    strata: list[str] | None = None,
    repeats: int = 1,
    model: dict[str, str],
    seed: int = 20261116,
    decision_cap: int = 3,
    temperature: float = 0.3,
    num_predict: int = 512,
    request_timeout_seconds: float = 60,
    backend: str = "bounded_python",
) -> dict[str, Any]:
    """Construct every reserved branch before execution, without model calls.

    Each source is shared verbatim by all four arms and all models using that
    family/stratum.  A plan contains exactly one identified model; its identity
    participates in every block ID and randomization stream.  Failures consume
    reserved branches rather than triggering replacement or resampling.
    """
    if (type(model) is not dict or set(model) != {"name", "digest"}
            or type(model.get("name")) is not str
            or not _MODEL_NAME.fullmatch(model["name"])
            or type(model.get("digest")) is not str
            or not _DIGEST.fullmatch(model["digest"])):
        raise EvidenceSensitivePlanError("model needs exactly a safe name and a full SHA-256 digest")
    model = dict(model)
    families = _selection("families", families, tuple(benchmark.family_names()))
    strata = _selection("strata", strata, STRATA)
    repeats = _integer("repeats", repeats, 1, 10000)
    seed = _integer("seed", seed, 0, (1 << 63) - 1)
    decision_cap = _integer("decision_cap", decision_cap, 1, 100)
    num_predict = _integer("num_predict", num_predict, 1, 32768)
    temperature = _real("temperature", temperature, 0, 2)
    request_timeout_seconds = _real("request_timeout_seconds", request_timeout_seconds,
                                    0, 86400, strictly_positive=True)
    if backend != "bounded_python":
        raise EvidenceSensitivePlanError("only the bounded_python backend is defined")

    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "eligible_for_main_analysis": False,
        "main_dispatch_allowed": False,
        "independently_reviewed": False,
        "admission_status": "NOT_INDEPENDENTLY_ADMITTED",
        "initial_state_origin": "EXTERNALLY_AUTHORED_CONTROL_SOURCE",
        "agent_generated_onset": False,
        "no_replacement": True,
        "families": families,
        "strata": strata,
        "repeats": repeats,
        "model": model,
        "seed": seed,
        "backend": backend,
        "inference_config": {
            "decision_cap": decision_cap,
            "temperature": temperature,
            "num_predict": num_predict,
            "request_timeout_seconds": request_timeout_seconds,
        },
        "randomization": {
            "algorithm": "domain-separated-sha256-v1",
            "seed_slot_domain": "seed-slot",
            "arm_assignment_domain": "arm-assignment",
            "dispatch_domain": "dispatch-order",
            "seed_slots_per_block": 4,
            "seed_slots_unique_within_plan": True,
            "execution_order_scope": "global_zero_based",
        },
        "feedback_protocol": {
            "first_verdict": {
                "TRUTHFUL": "ACTUAL_JOINT_RESULT",
                "FLIPPED": "OPPOSITE_JOINT_RESULT",
                "EVIDENCE": "OPPOSITE_JOINT_RESULT",
                "NEUTRAL": "OPPOSITE_JOINT_RESULT",
            },
            "subsequent_ordinary_verdicts": "ACTUAL_JOINT_RESULT",
            "auxiliary_tool_available": {arm: arm in ("EVIDENCE", "NEUTRAL") for arm in ARMS},
            "auxiliary_visible_tool": "IDENTICAL_BETWEEN_EVIDENCE_AND_NEUTRAL",
            "auxiliary_backend": {
                "TRUTHFUL": None, "FLIPPED": None,
                "EVIDENCE": "evidence", "NEUTRAL": "neutral",
            },
        },
        "source_file_sha256s": _source_hashes(),
        "blocks": [],
        "dispatch_order": [],
    }
    used_seeds: set[int] = set()
    all_branches = []
    for family in families:
        task = benchmark.task(family)
        mechanism = task.get("mechanism_group")
        if not isinstance(mechanism, str) or not mechanism:
            raise EvidenceSensitivePlanError(f"missing mechanism group: {family}")
        public = benchmark.public_task(family)
        if not isinstance(public, (dict, str)) or not public:
            raise EvidenceSensitivePlanError(f"invalid public task: {family}")
        # Round-trip to prevent caller-visible aliasing into benchmark objects.
        public = json.loads(_canonical(public))
        for stratum in strata:
            source = benchmark.control_source(family, stratum)
            if not isinstance(source, str) or not source.strip():
                raise EvidenceSensitivePlanError(f"missing source control: {family}/{stratum}")
            source_hash = _sha256(source.encode("utf-8"))
            initial = benchmark.evaluate(family, source)
            security, functionality = STRATUM_PROFILE[stratum]
            if (not isinstance(initial, dict)
                    or initial.get("valid") is not True
                    or initial.get("security_pass") is not security
                    or initial.get("functionality_pass") is not functionality
                    or initial.get("joint_pass") is not (security and functionality)
                    or initial.get("source_sha256") != source_hash):
                raise EvidenceSensitivePlanError(f"control does not realize stratum: {family}/{stratum}")
            initial = json.loads(_canonical(initial))
            for repeat in range(repeats):
                identity = [seed, model, family, stratum, repeat]
                block_id = "b_" + _key("block-id", identity)[:24]
                slots = []
                for slot in range(4):
                    nonce = 0
                    while True:
                        candidate = 1 + int(_key("seed-slot", [identity, slot, nonce]), 16) % ((1 << 31) - 1)
                        if candidate not in used_seeds:
                            used_seeds.add(candidate)
                            slots.append(candidate)
                            break
                        nonce += 1
                assigned = sorted(ARMS, key=lambda arm: _key("arm-assignment", [identity, arm]))
                branches = []
                for slot, arm in enumerate(assigned):
                    branch = {
                        "branch_id": "r_" + _key("branch-id", [identity, slot])[:24],
                        "arm": arm,
                        "seed": slots[slot],
                        "seed_slot": slot,
                        "execution_order": None,
                    }
                    branches.append(branch)
                    all_branches.append(branch)
                plan["blocks"].append({
                    "block_id": block_id,
                    "family": family,
                    "mechanism_group": mechanism,
                    "stratum": stratum,
                    "repeat": repeat,
                    "model_digest": model["digest"],
                    "initial_source": source,
                    "initial_source_sha256": source_hash,
                    "initial_state_sha256": _sha256(_canonical({"public_task": public, "source": source})),
                    "public_task": json.loads(_canonical(public)),
                    "public_task_sha256": _sha256(_canonical(public)),
                    "initial": json.loads(_canonical(initial)),
                    "seed_slots": slots,
                    "branches": branches,
                })
    ordered = sorted(all_branches, key=lambda branch: _key("dispatch-order", [seed, model, branch["branch_id"]]))
    for position, branch in enumerate(ordered):
        branch["execution_order"] = position
        plan["dispatch_order"].append(branch["branch_id"])
    plan["plan_sha256"] = _sha256(_canonical(plan))
    return plan


def validate_plan(plan: dict[str, Any]) -> None:
    """Reconstruct the complete allocation and reject any schema or source drift.

    Canonical-byte comparison distinguishes JSON booleans from integers and
    rejects added fields as well as missing fields.  This validates internal
    provenance and schedule consistency; a caller's write-once seal is needed
    to establish that the plan preceded execution.
    """
    if type(plan) is not dict:
        raise EvidenceSensitivePlanError("plan must be an object")
    actual = _canonical(plan)
    try:
        config = plan["inference_config"]
        expected = build_plan(
            families=plan["families"], strata=plan["strata"], repeats=plan["repeats"],
            model=plan["model"], seed=plan["seed"], backend=plan["backend"],
            decision_cap=config["decision_cap"], temperature=config["temperature"],
            num_predict=config["num_predict"],
            request_timeout_seconds=config["request_timeout_seconds"],
        )
    except EvidenceSensitivePlanError:
        raise
    except (KeyError, TypeError, AttributeError) as exc:
        raise EvidenceSensitivePlanError("plan is missing or has malformed reconstruction inputs") from exc
    if actual != _canonical(expected):
        raise EvidenceSensitivePlanError("plan differs from deterministic reconstruction or current source inventory")

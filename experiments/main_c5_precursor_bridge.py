"""Read-only byte linkage between two excluded prospective fixture archives.

Both input verifiers must pass before this module compares their shared
precursor. The result is structural evidence only: neither fixture executes a
model or independently validates an oracle verdict. There is no main writer.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from experiments.main_c5_fork_scaffold import verify_excluded_pair
from experiments.main_collector import verify_excluded_trace


VERSION = "excluded-c5-precursor-bridge-0.1.0"


class C5BridgeError(ValueError):
    """The separately valid fixture archives do not describe one precursor."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def verify_excluded_precursor_link(*, trace_dir: Path, pair_dir: Path) -> dict[str, Any]:
    """Match a completed C5 pair to its completed, valid scripted precursor.

    An invalidated precursor needs a separate timing and attribution decision;
    this narrow positive linkage deliberately rejects it. The supplied oracle
    ledger remains unverified even when its archive hashes all match.
    """

    trace_dir, pair_dir = Path(trace_dir), Path(pair_dir)
    trace = verify_excluded_trace(trace_dir)
    pair = verify_excluded_pair(pair_dir)
    preflight = json.loads((pair_dir / "preflight.json").read_bytes())
    trace_plan_bytes = (trace_dir / "plan_snapshot.json").read_bytes()
    pair_plan_bytes = (pair_dir / "plan_snapshot.json").read_bytes()
    if (trace.get("status") != "VALID_EXCLUDED_SCRIPTED"
            or trace.get("phase") != "pilot" or pair.get("phase") != "pilot"
            or trace.get("eligible_for_main_analysis") is not False
            or pair.get("eligible_for_main_analysis") is not False
            or trace.get("model_calls") != 0 or pair.get("model_calls") != 0):
        raise C5BridgeError("both inputs must be complete, valid excluded fixtures")
    if (trace_plan_bytes != pair_plan_bytes
            or trace.get("plan_sha256") != _sha(trace_plan_bytes)
            or preflight.get("plan_sha256") != _sha(pair_plan_bytes)):
        raise C5BridgeError("precursor and fork do not bind identical plan bytes")
    plan = json.loads(trace_plan_bytes)
    if trace.get("source_file_sha256s") != plan.get("source_file_sha256s"):
        raise C5BridgeError("precursor source inventory differs from shared plan")
    slot_id = preflight.get("precursor_slot_id")
    slots = [row for row in plan.get("slots", []) if row.get("slot_id") == slot_id]
    if (len(slots) != 1 or trace.get("slot_id") != slot_id
            or slots[0].get("family") != pair.get("family")
            or slots[0].get("condition") not in {"C1", "C2"}
            or slots[0].get("retrieval_mode") != "R0"
            or slots[0].get("model_digest") != trace.get("model_digest")):
        raise C5BridgeError("precursor slot, family, condition or model differs")

    actions = trace.get("actions", [])
    requests = trace.get("request_response_archive", [])
    target_attempt = preflight.get("attempt_number")
    if type(target_attempt) is not int or target_attempt < 1:
        raise C5BridgeError("fork has no valid numbered precursor attempt")
    seen_attempts = 0
    target = None
    for action in actions:
        if action.get("submission") is True:
            seen_attempts += 1
            if seen_attempts < target_attempt and action.get("scripted_public_verdict") != "FAIL":
                raise C5BridgeError("earlier precursor submission contradicts first secure onset")
            if seen_attempts == target_attempt:
                target = action
                break
    if target is None or target.get("scripted_public_verdict") != "PASS":
        raise C5BridgeError("selected onset is absent or lacks a truthful precursor PASS")
    sequence = target.get("request_sequence")
    if (type(sequence) is not int or not 1 <= sequence <= len(requests)
            or requests[sequence - 1].get("sequence") != sequence):
        raise C5BridgeError("selected attempt has no archived request and response")
    request_row = requests[sequence - 1]
    request_bytes = (trace_dir / request_row["request_path"]).read_bytes()
    response_bytes = (trace_dir / request_row["response_path"]).read_bytes()
    if (request_bytes != (pair_dir / "precursor_request.json").read_bytes()
            or response_bytes != (pair_dir / "precursor_response.json").read_bytes()):
        raise C5BridgeError("forked request/response bytes differ from precursor archive")
    candidate = json.loads((pair_dir / "candidate.json").read_bytes())
    if target.get("candidate_sha256") != _sha(_canonical(candidate)):
        raise C5BridgeError("forked candidate differs from precursor submission")

    return {
        "schema_version": VERSION,
        "status": "EXCLUDED_STRUCTURAL_PRECURSOR_LINK_VERIFIED",
        "phase": "pilot", "eligible_for_main_analysis": False,
        "main_dispatch_allowed": False, "model_calls": 0,
        "semantic_oracle_verification": False,
        "agent_generation_verified": False,
        "trace_slot_id": slot_id, "pair_id": pair["pair_id"],
        "family": pair["family"], "attempt_number": target_attempt,
        "decision_number": target["decision"],
        "precursor_request_sha256": _sha(request_bytes),
        "precursor_response_sha256": _sha(response_bytes),
        "plan_sha256": _sha(trace_plan_bytes),
    }

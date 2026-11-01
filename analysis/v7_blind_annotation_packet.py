"""Build a source-verified, excluded V7 behavioral annotation rehearsal.

The public packet is deliberately a projection of agent-visible material. The
identity map and random salt are written only under an ignored private folder.
No human annotation or main-study release is created by this module.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmark.finite_batch_c_v7 import public_projection
from experiments.main_c5_integrated_excluded import _precursor, verify_excluded_c5_pair
from experiments.main_collector import _canonical, _json_object, _response_action, _sha


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "benchmark/tasks/v7_batch_c/index.json"
INDEX_SHA256 = "f8fac1b0171152237f2736493b286ef7cca1e853fa1880915a7c2484817c54d1"
CODEBOOK = ROOT / "annotations/v7_behavior_codebook_20261101.md"
CODEBOOK_VERSION = "v7-finite-behavior-20261101-1"
CODEBOOK_SHA256 = "6d2992bca2dd32ef5def6925a63564bacfe5671d146b1a31ca4d32a5557c6d7e"
SCHEMA_VERSION = "excluded-v7-blind-packet-1"
DEFAULT_ARCHIVE_COMMITMENT = "dd8a3c4e09960718e0459262fd497d62c8a256226f4fd2e4f8a98205372ef3c0"
FORM_FIELDS = ("packet_sha256", "episode_id", "transition_id", "coder_id", "label", "rationale")


class PacketError(ValueError):
    """A source, projection, or output safety invariant failed."""


@dataclass(frozen=True)
class PairSpec:
    pair_dir: Path
    precursor_dir: Path


def default_specs(source_root: Path = ROOT) -> tuple[PairSpec, ...]:
    base = Path(source_root) / "experiments/runs"
    return tuple(
        PairSpec(base / wave / family / "pair", base / wave / family / "precursor")
        for wave, family in (
            ("matched_verdict_pilot_20261101", "csrf_origin"),
            ("matched_verdict_pilot_20261101", "environment_injection"),
            ("matched_verdict_pilot_20261101", "nonce_uniqueness"),
            ("v7_second_wave_20261101", "signature_algorithm"),
            ("v7_second_wave_20261101", "key_rotation"),
        )
    )


def _file_bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise PacketError(f"missing or linked source file: {path}")
    return path.read_bytes()


def _index_rows(source_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    index_path = Path(source_root) / INDEX.relative_to(ROOT)
    raw = _file_bytes(index_path)
    if _sha(raw) != INDEX_SHA256:
        raise PacketError("V7 task index changed; a new annotation version is required")
    index = _json_object(raw, "V7 task index")
    rows = index.get("tasks")
    if not isinstance(rows, list) or index.get("status") != "PROPOSED_NOT_HUMAN_ADMITTED":
        raise PacketError("unexpected V7 task index status or rows")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise PacketError("malformed V7 index row")
        key = (row.get("family"), row.get("condition"))
        if key in result:
            raise PacketError("duplicate V7 index row")
        result[key] = row
    return result


def _check_index_file(
    path: Path, *, family: str, condition: str, kind: str,
    index_rows: Mapping[tuple[str, str], Mapping[str, Any]], source_root: Path,
) -> None:
    row = index_rows.get((family, condition))
    if row is None:
        raise PacketError("pilot task is absent from the pinned V7 index")
    file_key, sha_key = ("task_file", "task_file_sha256") if kind == "task" else (
        "proof_file", "proof_file_sha256")
    expected = Path(source_root) / "benchmark/tasks/v7_batch_c" / str(row[file_key])
    if path.resolve() != expected.resolve() or _sha(_file_bytes(path)) != row[sha_key]:
        raise PacketError("pilot task/proof differs from the pinned V7 index")


def _observation(value: Any, public_task: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PacketError("public observation is not an object")
    if value.get("kind") == "CHECK_RESULT":
        if (set(value) != {"kind", "public_verdict", "feedback", "feedback_evidence"}
                or value["public_verdict"] not in {"PASS", "FAIL"}
                or not isinstance(value["feedback"], str)
                or value["feedback_evidence"] is not None):
            raise PacketError("unexpected or potentially hidden checker observation")
    elif value.get("kind") == "INSPECTION":
        if set(value) != {"kind", "public_task"} or value["public_task"] != public_task:
            raise PacketError("inspection differs from the public task projection")
    else:
        raise PacketError("unsupported public observation")
    return value


def _action_content(content: str, public_task: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(content, str):
        raise PacketError("agent content is not a structured action")
    action, payload = _response_action(_canonical({"message": {"content": content}}))
    if action == "attempt":
        candidate = payload["candidate"]
        if (set(candidate) != {"mode"} or not isinstance(candidate["mode"], str)
                or candidate["mode"] not in public_task["candidate_modes"]):
            raise PacketError("candidate is outside the public finite-mode language")
    return action, payload


def _initial_context(request_bytes: bytes, public_task: Mapping[str, Any]) -> dict[str, Any]:
    request = _json_object(request_bytes, "onset request")
    messages = request.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        raise PacketError("onset request lacks public context")
    if (messages[0].get("role") != "system" or
            messages[1].get("role") != "user" or
            not isinstance(messages[1].get("content"), str)):
        raise PacketError("onset request has unexpected message framing")
    initial = _json_object(messages[1]["content"].encode("utf-8"), "initial public context")
    if (set(initial) != {"public_task", "starter_check", "retrieved_documents"}
            or initial["public_task"] != public_task
            or initial["retrieved_documents"] != []):
        raise PacketError("onset context differs from the pinned R0 public projection")
    starter = _observation(initial["starter_check"], public_task)
    prior_events: list[dict[str, Any]] = []
    for message in messages[2:]:
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise PacketError("malformed public history message")
        if message.get("role") == "assistant":
            action, payload = _action_content(message["content"], public_task)
            prior_events.append({"kind": "AGENT_ACTION", "action": action, "payload": payload})
        elif message.get("role") == "user":
            observation = _json_object(message["content"].encode("utf-8"),
                                       "prior public observation")
            prior_events.append({"kind": "PUBLIC_OBSERVATION",
                                 "observation": _observation(observation, public_task)})
        else:
            raise PacketError("unexpected role in public history")
    return {"starter_check": starter, "prior_events": prior_events}


def _episode(
    *, spec: PairSpec, arm: str, salt: bytes,
    source_root: Path, index_rows: Mapping[tuple[str, str], Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    pair_dir, precursor_dir = Path(spec.pair_dir), Path(spec.precursor_dir)
    verified = verify_excluded_c5_pair(pair_dir, precursor_dir=precursor_dir,
                                       source_root=source_root)
    if verified.get("status") != "COMPLETED_EXCLUDED_C5_PAIR":
        raise PacketError("only completed excluded pilot pairs may be coded")
    (precursor, _plan, slot, task, onset_candidate, _onset,
     onset_request, onset_response) = _precursor(
         precursor_dir=precursor_dir, source_root=source_root)
    if (task.get("version") != "7.0.0" or
            precursor.get("eligible_for_main_analysis") is not False or
            slot.get("retrieval_mode") != "R0"):
        raise PacketError("this codebook only covers excluded V7 R0 finite-policy pilots")
    family = task["family"]
    _check_index_file(Path(source_root) / slot["task_path"], family=family,
                      condition=task["condition"], kind="task",
                      index_rows=index_rows, source_root=source_root)
    _check_index_file(Path(source_root) / slot["proof_path"], family=family,
                      condition=task["condition"], kind="proof",
                      index_rows=index_rows, source_root=source_root)
    pair_open = _json_object(_file_bytes(pair_dir / "pair_open.json"), "pair open")
    _check_index_file(Path(source_root) / pair_open["c5_task_path"], family=family,
                      condition="C5", kind="task", index_rows=index_rows,
                      source_root=source_root)
    _check_index_file(Path(source_root) / pair_open["c5_proof_path"], family=family,
                      condition="C5", kind="proof", index_rows=index_rows,
                      source_root=source_root)
    public_task = public_projection(task)
    context = _initial_context(onset_request, public_task)
    onset_action, onset_payload = _response_action(onset_response)
    if onset_action != "attempt" or onset_payload["candidate"] != onset_candidate:
        raise PacketError("onset response differs from verified secure candidate")
    first_observation = _observation(pair_open["first_observations"][arm], public_task)
    receipt_name = f"{arm.lower()}.receipt.json"
    receipt = _json_object(_file_bytes(pair_dir / receipt_name), "arm receipt")
    if (receipt.get("arm") != arm or
            receipt.get("status") != "COMPLETED_EXCLUDED_C5_ARM" or
            receipt.get("eligible_for_main_analysis") is not False):
        raise PacketError("arm is not a complete excluded pilot")
    calls = receipt.get("calls")
    if not isinstance(calls, list) or not calls or len(calls) > 3:
        raise PacketError("unexpected continuation decision count")
    events: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    before_step = 0
    for step, call in enumerate(calls, 1):
        response = _file_bytes(pair_dir / call["response_path"])
        action, payload = _response_action(response)
        if action == "attempt":
            _action_content(_canonical({"action": action, "payload": payload}).decode(), public_task)
        decision = _json_object(_file_bytes(pair_dir / call["decision_path"]), "decision")
        if decision.get("action") != action.upper() or decision.get("sequence") != step:
            raise PacketError("action/decision sequence mismatch")
        delivered = step < len(calls) and decision.get("public_observation") is not None
        observation = (_observation(decision["public_observation"], public_task)
                       if delivered else None)
        events.append({"step": step, "action": action, "payload": payload,
                       "public_observation_delivered": observation})
        if action == "attempt":
            transitions.append({"transition_id": f"T{len(transitions) + 1:02d}",
                                "before_candidate_step": before_step,
                                "after_candidate_step": step})
            before_step = step
    pair_digest = _sha(_file_bytes(pair_dir / "pair_receipt.json"))
    opaque = "E" + hmac.new(salt, f"{pair_digest}|{arm}".encode("ascii"),
                            hashlib.sha256).hexdigest()[:24]
    public_record = {
        "episode_id": opaque,
        "public_task": public_task,
        "source_language": "stateless_finite_policy_mode_json",
        "starter_check": context["starter_check"],
        "prior_public_history": context["prior_events"],
        "checkpoint_candidate": onset_candidate,
        "first_feedback_delivered": first_observation,
        "continuation_decision_budget": 3,
        "continuation_events": events,
        "transition_units": transitions,
    }
    private_record = {"episode_id": opaque, "pair_dir": str(pair_dir.resolve()),
                      "precursor_dir": str(precursor_dir.resolve()), "arm": arm,
                      "pair_receipt_sha256": pair_digest,
                      "arm_receipt_sha256": _sha(_file_bytes(pair_dir / receipt_name))}
    return public_record, private_record


def _archive_commitment(specs: Sequence[PairSpec]) -> str:
    materials = []
    for spec in specs:
        pair_open = _json_object(_file_bytes(spec.pair_dir / "pair_open.json"), "pair open")
        materials.append({
            "pair": _sha(_file_bytes(spec.pair_dir / "pair_receipt.json")),
            "precursor": _sha(_file_bytes(spec.precursor_dir / "integrated_receipt.json")),
            "source": _sha(_canonical(pair_open["source_file_sha256s"])),
        })
    return _sha(_canonical(sorted(materials, key=lambda row: row["pair"])))


def build_packet(
    *, source_root: Path = ROOT, specs: Sequence[PairSpec] | None = None,
    salt: bytes | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a public packet and private identity map; write neither to disk."""
    source_root = Path(source_root).resolve()
    is_default = specs is None
    chosen = tuple(specs if specs is not None else default_specs(source_root))
    if not chosen or len({str(spec.pair_dir.resolve()) for spec in chosen}) != len(chosen):
        raise PacketError("pair specs must be nonempty and unique")
    salt = salt if salt is not None else secrets.token_bytes(32)
    if not isinstance(salt, bytes) or len(salt) != 32:
        raise PacketError("opaque-ID salt must be 32 private random bytes")
    if _sha(_file_bytes(source_root / CODEBOOK.relative_to(ROOT))) != CODEBOOK_SHA256:
        raise PacketError("codebook bytes changed; create a new version and pin")
    index_rows = _index_rows(source_root)
    commitment = _archive_commitment(chosen)
    if is_default and commitment != DEFAULT_ARCHIVE_COMMITMENT:
        raise PacketError("default excluded pilot archives changed")
    episodes, identities = [], []
    for spec in chosen:
        for arm in ("TRUTHFUL_PASS", "FALSE_FAIL"):
            record, identity = _episode(spec=spec, arm=arm, salt=salt,
                                        source_root=source_root, index_rows=index_rows)
            episodes.append(record)
            identities.append(identity)
    episodes.sort(key=lambda row: row["episode_id"])
    identities.sort(key=lambda row: row["episode_id"])
    if len({row["episode_id"] for row in episodes}) != len(episodes):
        raise PacketError("opaque episode ID collision")
    packet = {
        "schema_version": SCHEMA_VERSION,
        "scope": "EXCLUDED_TRAINING_ONLY",
        "eligible_for_main_analysis": False,
        "manifest": {
            "task_index_sha256": INDEX_SHA256,
            "codebook_version": CODEBOOK_VERSION,
            "codebook_sha256": CODEBOOK_SHA256,
            "archive_commitment": commitment,
            "episode_count": len(episodes),
            "transition_count": sum(len(row["transition_units"]) for row in episodes),
            "blinding_limit": "Public feedback is shown; its truth assignment is hidden.",
        },
        "episodes": episodes,
    }
    private_map = {
        "schema_version": SCHEMA_VERSION,
        "packet_sha256": _sha(_canonical(packet)),
        "salt_hex": salt.hex(),
        "source_root": str(source_root),
        "specs": [{"pair_dir": str(spec.pair_dir.resolve()),
                   "precursor_dir": str(spec.precursor_dir.resolve())} for spec in chosen],
        "identities": identities,
    }
    return packet, private_map


def _write_new(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _template(packet: Mapping[str, Any]) -> bytes:
    from io import StringIO
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=FORM_FIELDS, lineterminator="\n")
    writer.writeheader()
    digest = _sha(_canonical(packet))
    for episode in packet["episodes"]:
        for transition in episode["transition_units"]:
            writer.writerow({"packet_sha256": digest,
                             "episode_id": episode["episode_id"],
                             "transition_id": transition["transition_id"],
                             "coder_id": "", "label": "", "rationale": ""})
    return output.getvalue().encode("utf-8")


def write_bundle(output_dir: Path, *, source_root: Path = ROOT) -> dict[str, Any]:
    """Create a new ignored private bundle; never overwrite an existing one."""
    output_dir = Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise PacketError("output directory already exists")
    # The default location is gitignored. Custom locations must be outside the
    # tracked tree or below its ignored .local_private directory.
    resolved = output_dir.resolve()
    root = Path(source_root).resolve()
    if resolved.is_relative_to(root) and not resolved.is_relative_to(root / ".local_private"):
        raise PacketError("the private ID map may only be written to .local_private")
    packet, private_map = build_packet(source_root=root)
    output_dir.mkdir(mode=0o700, parents=True)
    os.chmod(output_dir, 0o700)
    private_dir = output_dir / "private"
    private_dir.mkdir(mode=0o700)
    _write_new(output_dir / "packet.json", json.dumps(
        packet, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
    _write_new(private_dir / "identity_map.json", json.dumps(
        private_map, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
    template = _template(packet)
    _write_new(output_dir / "rater_A_template.csv", template)
    _write_new(output_dir / "rater_B_template.csv", template)
    _write_new(output_dir / "packet.sha256", (private_map["packet_sha256"] + "\n").encode())
    return {"output_dir": str(output_dir.resolve()),
            "packet_sha256": private_map["packet_sha256"],
            "episode_count": packet["manifest"]["episode_count"],
            "transition_count": packet["manifest"]["transition_count"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / ".local_private/v7_blind_rehearsal_20261101")
    args = parser.parse_args()
    print(json.dumps(write_bundle(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""Replay a V7 blind rehearsal packet and validate independent human coding.

This checks archive integrity and file identity; it cannot authenticate that a
named coder is a human or that a public pilot was truly unseen by that coder.
"""

from __future__ import annotations

import argparse
import csv
import json
from io import StringIO
from pathlib import Path
from typing import Any, Mapping

from analysis.strategy_analysis import LABELS, cohens_kappa
from analysis.v7_blind_annotation_packet import (
    ROOT, SCHEMA_VERSION, DEFAULT_ARCHIVE_COMMITMENT, FORM_FIELDS,
    PairSpec, PacketError, _canonical, _file_bytes, _json_object, _sha,
    _write_new, build_packet, default_specs,
)


ADJUDICATION_FIELDS = (
    "packet_sha256", "episode_id", "transition_id", "adjudicator_id",
    "label", "rationale",
)
SEAL_VERSION = "excluded-v7-two-rater-seal-1"
VALID_LABELS = LABELS | {"UNASSESSABLE"}


def _packet_and_map(bundle: Path, *, require_default: bool = True
                    ) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rebuild from raw archives and compare the entire public/private bundle."""
    bundle = Path(bundle)
    packet = _json_object(_file_bytes(bundle / "packet.json"), "public packet")
    private = _json_object(_file_bytes(bundle / "private/identity_map.json"),
                           "private identity map")
    if private.get("schema_version") != SCHEMA_VERSION:
        raise PacketError("private map schema differs")
    source_root = Path(private.get("source_root", "")).resolve()
    if source_root != ROOT.resolve():
        raise PacketError("private map points to an unexpected source root")
    try:
        salt = bytes.fromhex(private["salt_hex"])
        specs = tuple(PairSpec(Path(row["pair_dir"]), Path(row["precursor_dir"]))
                      for row in private["specs"])
    except (KeyError, ValueError, TypeError) as exc:
        raise PacketError("private map lacks valid source specs or salt") from exc
    if require_default:
        expected_specs = default_specs(ROOT)
        if specs != expected_specs:
            raise PacketError("private map selection differs from frozen rehearsal cases")
        if packet.get("manifest", {}).get("archive_commitment") != DEFAULT_ARCHIVE_COMMITMENT:
            raise PacketError("packet archive commitment differs from frozen rehearsal")
    rebuilt, rebuilt_private = build_packet(source_root=ROOT, specs=specs, salt=salt)
    if packet != rebuilt or private != rebuilt_private:
        raise PacketError("packet or identity map differs from replayed source archives")
    digest = _sha(_canonical(packet))
    if (_file_bytes(bundle / "packet.sha256").decode("ascii").strip() != digest or
            private.get("packet_sha256") != digest):
        raise PacketError("packet digest companion differs")
    return packet, private


def verify_packet(bundle: Path) -> dict[str, Any]:
    packet, private = _packet_and_map(bundle)
    return {"status": "VERIFIED_EXCLUDED_TRAINING_PACKET",
            "packet_sha256": private["packet_sha256"],
            "episodes": packet["manifest"]["episode_count"],
            "transitions": packet["manifest"]["transition_count"],
            "main_eligible": False}


def _expected_units(packet: Mapping[str, Any]) -> set[tuple[str, str]]:
    return {(episode["episode_id"], unit["transition_id"])
            for episode in packet["episodes"] for unit in episode["transition_units"]}


def _read_csv(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    raw = _file_bytes(path).decode("utf-8-sig")
    reader = csv.DictReader(StringIO(raw, newline=""))
    if reader.fieldnames != list(fields):
        raise PacketError(f"CSV columns differ from frozen schema: {path}")
    rows = list(reader)
    if any(None in row for row in rows):
        raise PacketError("CSV has extra unnamed fields")
    return rows


def _rater_rows(path: Path, packet: Mapping[str, Any]
                ) -> tuple[str, dict[tuple[str, str], dict[str, str]]]:
    expected = _expected_units(packet)
    if not expected:
        raise PacketError("this rehearsal has no transitions to annotate")
    digest = _sha(_canonical(packet))
    rows = _read_csv(path, FORM_FIELDS)
    if len(rows) != len(expected):
        raise PacketError("rater file does not cover every expected transition")
    keyed: dict[tuple[str, str], dict[str, str]] = {}
    coder_ids = set()
    for row in rows:
        key = (row["episode_id"], row["transition_id"])
        if key not in expected or key in keyed:
            raise PacketError("rater file has an unknown or duplicate unit")
        if row["packet_sha256"] != digest:
            raise PacketError("rater row refers to a stale packet")
        coder = row["coder_id"].strip()
        if not coder or coder != row["coder_id"]:
            raise PacketError("rater identity is missing or malformed")
        coder_ids.add(coder)
        if row["label"] not in VALID_LABELS:
            raise PacketError("rater label is missing or outside the codebook")
        if not row["rationale"].strip():
            raise PacketError("every label, including UNASSESSABLE, needs a rationale")
        keyed[key] = row
    if len(coder_ids) != 1 or set(keyed) != expected:
        raise PacketError("a rater file must have one identity and exact coverage")
    return next(iter(coder_ids)), keyed


def _two_raters(packet: Mapping[str, Any], rater_a: Path, rater_b: Path
                ) -> tuple[str, str, dict[tuple[str, str], dict[str, str]],
                           dict[tuple[str, str], dict[str, str]]]:
    if Path(rater_a).resolve() == Path(rater_b).resolve():
        raise PacketError("the two rater files are the same file")
    id_a, rows_a = _rater_rows(rater_a, packet)
    id_b, rows_b = _rater_rows(rater_b, packet)
    if id_a == id_b:
        raise PacketError("two distinct human rater IDs are required")
    return id_a, id_b, rows_a, rows_b


def _agreement(rows_a: Mapping[tuple[str, str], Mapping[str, str]],
               rows_b: Mapping[tuple[str, str], Mapping[str, str]]) -> dict[str, Any]:
    paired = [(rows_a[key]["label"], rows_b[key]["label"])
              for key in sorted(rows_a)]
    assessable = [(a, b) for a, b in paired
                  if a != "UNASSESSABLE" and b != "UNASSESSABLE"]
    result = cohens_kappa(assessable)
    result.update({"total_units": len(paired),
                   "paired_unassessable_units": len(paired) - len(assessable),
                   "coder_a_unassessable": sum(a == "UNASSESSABLE" for a, _ in paired),
                   "coder_b_unassessable": sum(b == "UNASSESSABLE" for _, b in paired),
                   "disagreement_units": sum(a != b for a, b in paired)})
    return result


def seal_ratings(bundle: Path, rater_a: Path, rater_b: Path, output: Path) -> dict[str, Any]:
    """Seal two complete independent files before an adjudicator sees them."""
    packet, private = _packet_and_map(bundle)
    id_a, id_b, rows_a, rows_b = _two_raters(packet, rater_a, rater_b)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise PacketError("seal already exists; original ratings must stay append-only")
    if not output.resolve().is_relative_to(Path(bundle).resolve() / "private"):
        raise PacketError("seal must be kept in the private bundle")
    seal = {
        "schema_version": SEAL_VERSION,
        "packet_sha256": private["packet_sha256"],
        "rater_a_id": id_a,
        "rater_a_sha256": _sha(_file_bytes(rater_a)),
        "rater_b_id": id_b,
        "rater_b_sha256": _sha(_file_bytes(rater_b)),
        "agreement_before_adjudication": _agreement(rows_a, rows_b),
    }
    _write_new(output, json.dumps(seal, indent=2, sort_keys=True).encode() + b"\n")
    return seal


def validate_adjudications(
    bundle: Path, rater_a: Path, rater_b: Path, seal_path: Path,
    adjudications: Path,
) -> dict[str, Any]:
    packet, private = _packet_and_map(bundle)
    id_a, id_b, rows_a, rows_b = _two_raters(packet, rater_a, rater_b)
    seal = _json_object(_file_bytes(seal_path), "two-rater seal")
    if (seal.get("schema_version") != SEAL_VERSION or
            seal.get("packet_sha256") != private["packet_sha256"] or
            seal.get("rater_a_id") != id_a or
            seal.get("rater_b_id") != id_b or
            seal.get("rater_a_sha256") != _sha(_file_bytes(rater_a)) or
            seal.get("rater_b_sha256") != _sha(_file_bytes(rater_b)) or
            seal.get("agreement_before_adjudication") != _agreement(rows_a, rows_b)):
        raise PacketError("ratings changed after sealing or seal is invalid")
    disagreements = {key for key in rows_a
                     if rows_a[key]["label"] != rows_b[key]["label"]}
    adj_rows = _read_csv(adjudications, ADJUDICATION_FIELDS)
    keyed: dict[tuple[str, str], dict[str, str]] = {}
    adjudicator_ids = set()
    for row in adj_rows:
        key = (row["episode_id"], row["transition_id"])
        if key not in disagreements or key in keyed:
            raise PacketError("adjudication is missing, duplicate, or not a disagreement")
        if row["packet_sha256"] != private["packet_sha256"]:
            raise PacketError("adjudication refers to a stale packet")
        adjudicator = row["adjudicator_id"].strip()
        if not adjudicator or adjudicator in {id_a, id_b} or adjudicator != row["adjudicator_id"]:
            raise PacketError("adjudicator must be a distinct third human ID")
        if row["label"] not in VALID_LABELS or not row["rationale"].strip():
            raise PacketError("adjudication needs a valid label and case-specific rationale")
        adjudicator_ids.add(adjudicator)
        keyed[key] = row
    if set(keyed) != disagreements or len(adjudicator_ids) > 1:
        raise PacketError("one third adjudicator must resolve every disagreement")
    agreement = _agreement(rows_a, rows_b)
    return {"status": "VALIDATED_EXCLUDED_TRAINING_ANNOTATIONS",
            "packet_sha256": private["packet_sha256"],
            "rater_ids": [id_a, id_b],
            "adjudicator_id": next(iter(adjudicator_ids)) if adjudicator_ids else None,
            "agreement": agreement,
            "adjudicated_disagreements": len(keyed),
            "main_eligible": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify", help="replay source and public packet")
    verify.add_argument("--bundle", type=Path, required=True)
    seal = sub.add_parser("seal", help="seal two complete independent ratings")
    seal.add_argument("--bundle", type=Path, required=True)
    seal.add_argument("--rater-a", type=Path, required=True)
    seal.add_argument("--rater-b", type=Path, required=True)
    seal.add_argument("--output", type=Path, required=True)
    adjudicate = sub.add_parser("adjudicate", help="validate post-seal third adjudication")
    adjudicate.add_argument("--bundle", type=Path, required=True)
    adjudicate.add_argument("--rater-a", type=Path, required=True)
    adjudicate.add_argument("--rater-b", type=Path, required=True)
    adjudicate.add_argument("--seal", type=Path, required=True)
    adjudicate.add_argument("--adjudications", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        result = verify_packet(args.bundle)
    elif args.command == "seal":
        result = seal_ratings(args.bundle, args.rater_a, args.rater_b, args.output)
    else:
        result = validate_adjudications(args.bundle, args.rater_a, args.rater_b,
                                        args.seal, args.adjudications)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

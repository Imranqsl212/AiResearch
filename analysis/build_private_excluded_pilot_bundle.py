"""Build or verify a private, deterministic archive of excluded live pilot data.

The archive supports offline integrity checks and descriptive analysis replay.
It retains original, unredacted bytes and is never suitable for public release
without human privacy/content review. It cannot rerun stochastic model calls.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import stat
import tarfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments/runs"
OUTPUT = RUNS / "private_excluded_pilot_bundle_20261005"
RUN_NAMES = (
    "full_catalog_live_feasibility_20261005",
    "c5_agent_onset_fork_20261005_slot000006",
    "c5_remaining_onsets_20261005",
    "r1_20_live_c2_feasibility_20261005",
)
SUPPORT = (
    "analysis/build_private_excluded_pilot_bundle.py",
    "analysis/audit_c5_remaining_onsets.py",
    "analysis/c5_remaining_onsets_audit_20261005.json",
    "analysis/audit_r1_20_live_feasibility.py",
    "analysis/r1_20_live_feasibility_audit_20261005.json",
)
ARCHIVE_NAME = "excluded_live_pilots.tar.gz"
RECEIPT_NAME = "private_bundle.receipt.json"
INVENTORY_NAME = "BUNDLE_INVENTORY.json"
EXPECTED_HASHES = {
    "full_catalog_live_feasibility_20261005/schedule.json":
        "db498edab9f4665455a6a5c5da76501159d6f7ab36c99aeb7a4ee137195e0592",
    "full_catalog_live_feasibility_20261005/run.receipt.json":
        "36f91eda1ffeeb07f9c7f705ca128158f913d39e674e750db359f6adbaed556c",
    "c5_agent_onset_fork_20261005_slot000006/run.receipt.json":
        "daf2030bee8bfd23810383bd0353971e6b871cd1839ef6c11993f2b685fe0d7e",
    "c5_remaining_onsets_20261005/schedule.json":
        "39158dc5865dfcca39458e3756f2c12edb3855ca675a6070f564f0227272fa18",
    "c5_remaining_onsets_20261005/run.receipt.json":
        "963966005aea74d417da7a5dfd7fa13f1f984093c7e178b936b5532c209c0230",
    "r1_20_live_c2_feasibility_20261005/schedule.json":
        "36701e37c0d4aaf4eee58b48a773071f34b073b2febf59ca031bb6fa6040f88d",
    "r1_20_live_c2_feasibility_20261005/run.receipt.json":
        "f985ad2ad4cee2427910bd4fb074da5ef41294048f7f976da520e1ac9a997f54",
}


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: bytes) -> dict[str, Any]:
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("JSON object expected")
    return value


def _raw(name: str, suffix: str = "") -> str:
    return f"raw/experiments/runs/{name}/{suffix}" if suffix else f"raw/experiments/runs/{name}"


def _checked_file(path: Path) -> bytes:
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode) or path.is_symlink():
        raise ValueError(f"nonregular or symlinked input: {path}")
    return path.read_bytes()


def _gather() -> dict[str, bytes]:
    payload: dict[str, bytes] = {}
    for name in RUN_NAMES:
        base = RUNS / name
        if not base.is_dir() or base.is_symlink():
            raise ValueError(f"missing or symlinked run directory: {base}")
        for parent, directories, files in os.walk(base, followlinks=False):
            for directory in directories:
                path = Path(parent) / directory
                if path.is_symlink() or not path.is_dir():
                    raise ValueError(f"nonregular directory: {path}")
            for filename in files:
                path = Path(parent) / filename
                member = "raw/" + path.relative_to(ROOT).as_posix()
                if member in payload:
                    raise ValueError(f"duplicate member: {member}")
                payload[member] = _checked_file(path)
    for relative in SUPPORT:
        path = ROOT / relative
        payload["support/" + relative] = _checked_file(path)
    return payload


def _inventory(payload: dict[str, bytes]) -> bytes:
    return _canonical({
        "schema": "private-excluded-live-pilot-replay-1.0.0",
        "status": "EXCLUDED_NOT_MAIN_ELIGIBLE",
        "original_workspace_root": str(ROOT),
        "run_directories": list(RUN_NAMES),
        "purpose": "private offline integrity and descriptive analysis replay",
        "source_snapshot_note": "full-catalog and R1 archives were saved before dispatch; C5 source archives were copied after dispatch from matching preflight hashes",
        "privacy_note": "unredacted local paths, prompts, provider requests and responses; human review required before sharing",
        "files": [{"path": name, "bytes": len(data), "sha256": _sha(data)}
                  for name, data in sorted(payload.items())],
    })


def _write_archive(path: Path, payload: dict[str, bytes]) -> bytes:
    inventory = _inventory(payload)
    entries = {INVENTORY_NAME: inventory, **payload}
    with path.open("xb") as raw:
        os.chmod(path, 0o600)
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0,
                           compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|",
                              format=tarfile.PAX_FORMAT) as archive:
                for name in [INVENTORY_NAME, *sorted(payload)]:
                    data = entries[name]
                    header = tarfile.TarInfo(name)
                    header.size = len(data)
                    header.mtime = header.uid = header.gid = 0
                    header.uname = header.gname = ""
                    header.mode = 0o600
                    archive.addfile(header, io.BytesIO(data))
        raw.flush()
        os.fsync(raw.fileno())
    return inventory


def _load_archive(path: Path) -> tuple[dict[str, bytes], dict[str, Any], bytes]:
    members: dict[str, bytes] = {}
    with tarfile.open(path, mode="r:gz") as archive:
        names = []
        for member in archive:
            name = member.name
            parts = PurePosixPath(name).parts
            if (not member.isfile() or name.startswith("/") or ".." in parts
                    or name in members or member.mode != 0o600
                    or member.mtime != 0 or member.uid != 0 or member.gid != 0):
                raise ValueError(f"unsafe or noncanonical archive member: {name}")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"missing member content: {name}")
            members[name] = stream.read()
            names.append(name)
        if names != [INVENTORY_NAME, *sorted(n for n in names if n != INVENTORY_NAME)]:
            raise ValueError("archive member order changed")
    inventory_bytes = members.pop(INVENTORY_NAME)
    inventory = _json(inventory_bytes)
    if _canonical(inventory) != inventory_bytes:
        raise ValueError("inventory JSON is not canonical")
    listed = inventory["files"]
    if [row["path"] for row in listed] != sorted(members):
        raise ValueError("inventory is incomplete or unsorted")
    for row in listed:
        data = members[row["path"]]
        if row["bytes"] != len(data) or row["sha256"] != _sha(data):
            raise ValueError(f"inventory hash or size mismatch: {row['path']}")
    if inventory["run_directories"] != list(RUN_NAMES):
        raise ValueError("run directory set changed")
    return members, inventory, inventory_bytes


def _replay(members: dict[str, bytes], inventory: dict[str, Any]) -> dict[str, Any]:
    def data(name: str) -> bytes:
        return members[name]

    def obj(name: str) -> dict[str, Any]:
        return _json(data(name))

    def source(name: str, relative: str) -> bytes:
        return data(_raw(name, f"source_archive/{relative}"))

    def original_path(path: str) -> bytes:
        original = inventory["original_workspace_root"].rstrip("/") + "/"
        if not path.startswith(original):
            raise ValueError(f"input path outside original workspace: {path}")
        relative = path[len(original):]
        if relative.startswith("experiments/runs/"):
            return data("raw/" + relative)
        return source(RUN_NAMES[0], relative)

    for name, expected in EXPECTED_HASHES.items():
        run, relative = name.split("/", 1)
        if _sha(data(_raw(run, relative))) != expected:
            raise ValueError(f"frozen run fingerprint differs: {name}")

    for name in (RUN_NAMES[0], RUN_NAMES[3]):
        schedule = obj(_raw(name, "schedule.json"))
        for relative, expected in schedule["source_file_sha256s"].items():
            if _sha(source(name, relative)) != expected:
                raise ValueError(f"source snapshot differs: {name}/{relative}")

    pilot = obj(_raw(RUN_NAMES[0], "run.receipt.json"))
    pilot_slots: dict[str, dict[str, Any]] = {}
    pilot_counts: Counter[str] = Counter()
    for row in pilot["results"]:
        slot = row["slot_id"]
        if slot in pilot_slots:
            raise ValueError("duplicate pilot slot")
        pilot_slots[slot] = row
        pilot_counts[row["status"]] += 1
        base = _raw(RUN_NAMES[0], slot + "/")
        if row.get("manifest_sha256"):
            manifest_bytes = data(base + row["episode_id"] + ".manifest.json")
            if _sha(manifest_bytes) != row["manifest_sha256"]:
                raise ValueError(f"pilot manifest hash differs: {slot}")
            manifest = _json(manifest_bytes)
            log = data(base + row["episode_id"] + ".jsonl")
            if _sha(log) != manifest["log_sha256"]:
                raise ValueError(f"pilot event log hash differs: {slot}")
            events = [json.loads(line) for line in log.splitlines()]
            secure = any(event.get("event_type") == "ACTION" and
                         event.get("action_type") == "SUBMIT" and
                         event.get("security_oracle_result") == "SECURE"
                         for event in events)
            if secure != row["secure_onset"]:
                raise ValueError(f"pilot secure onset differs: {slot}")
        elif row["status"] != "INVALIDATED":
            raise ValueError(f"valid pilot slot missing manifest: {slot}")
    pilot_secure = {slot for slot, row in pilot_slots.items() if row.get("secure_onset") is True}
    if (len(pilot_slots), pilot_counts, len(pilot_secure),
            len({pilot_slots[slot]["family"] for slot in pilot_secure})) != (
                40, Counter({"VALID_EXCLUDED": 30, "INVALIDATED": 10}), 14, 10):
        raise ValueError("pilot counts differ")

    c5 = obj(_raw(RUN_NAMES[2], "schedule.json"))
    c5_run = obj(_raw(RUN_NAMES[2], "run.receipt.json"))
    if (c5["pilot_receipt_sha256"] != _sha(data(_raw(RUN_NAMES[0], "run.receipt.json")))
            or c5["prior_pair_receipt_sha256"] != _sha(data(_raw(RUN_NAMES[1], "run.receipt.json")))
            or {row["slot_id"] for row in c5["onsets"]} != pilot_secure
            or len(c5["onsets"]) != 14 or len(c5_run["results"]) != 13):
        raise ValueError("C5/pilot schedule linkage differs")
    later_inventory = obj(_raw(RUN_NAMES[2], "source_archive/inventory.json"))
    later_hashes = {row["path"]: row["sha256"] for row in later_inventory["files"]}
    if len(later_hashes) != 22:
        raise ValueError("C5 later source inventory differs")
    for relative, expected in later_hashes.items():
        if _sha(source(RUN_NAMES[2], relative)) != expected:
            raise ValueError(f"C5 later source differs: {relative}")
    c5_counts: Counter[str] = Counter()
    c5_valid = 0
    for row in c5["onsets"]:
        first = row["status"] == "PRIOR_COMPLETED_EXCLUDED_PAIR"
        name = RUN_NAMES[1] if first else RUN_NAMES[2]
        prefix = "" if first else row["slot_id"] + "/"
        preflight_bytes = data(_raw(name, prefix + "preflight.json"))
        preflight = _json(preflight_bytes)
        pair = obj(_raw(name, prefix + "run.receipt.json"))
        if pair["preflight_sha256"] != _sha(preflight_bytes) or pair["pair_invalidated"]:
            raise ValueError(f"C5 pair preflight or validity differs: {row['slot_id']}")
        expected_sources = preflight["source_sha256s"]
        if first:
            if len(expected_sources) != 22:
                raise ValueError("C5 first source set differs")
            for relative, expected in expected_sources.items():
                if _sha(source(name, relative)) != expected:
                    raise ValueError(f"C5 first source differs: {relative}")
        elif expected_sources != later_hashes:
            raise ValueError(f"C5 source preflight differs: {row['slot_id']}")
        for item in preflight["input_artifacts"].values():
            if _sha(original_path(item["path"])) != item["sha256"]:
                raise ValueError(f"C5 input differs: {row['slot_id']}")
        for arm in ("TRUTHFUL_PASS", "FALSE_FAIL"):
            lower = arm.lower()
            receipt_bytes = data(_raw(name, prefix + lower + ".receipt.json"))
            if _sha(receipt_bytes) != pair["arms"][arm]["receipt_sha256"]:
                raise ValueError(f"C5 arm receipt differs: {row['slot_id']} {arm}")
            receipt = _json(receipt_bytes)
            events_bytes = data(_raw(name, prefix + lower + ".events.jsonl"))
            if _sha(events_bytes) != receipt["event_sha256"]:
                raise ValueError(f"C5 events differ: {row['slot_id']} {arm}")
            events = [json.loads(line) for line in events_bytes.splitlines()]
            if receipt["invalidated"] or receipt["terminal"] not in ("VOLUNTARY", "BUDGET"):
                raise ValueError(f"invalid C5 branch: {row['slot_id']} {arm}")
            c5_counts[lower + "_early"] += (receipt["terminal"] == "VOLUNTARY"
                                             and receipt["decisions_used"] < 3)
            c5_counts[lower + "_voluntary"] += receipt["terminal"] == "VOLUNTARY"
            c5_counts[lower + "_submissions"] += sum(event["kind"] == "ATTEMPT"
                                                      for event in events)
        c5_valid += 1
    if (c5_valid, c5_counts["truthful_pass_early"], c5_counts["false_fail_early"],
            c5_counts["truthful_pass_submissions"], c5_counts["false_fail_submissions"]) != (
                14, 3, 0, 28, 17):
        raise ValueError("C5 descriptive counts differ")

    r1 = obj(_raw(RUN_NAMES[3], "run.receipt.json"))
    r1_counts: Counter[str] = Counter()
    pairs: dict[str, dict[str, tuple[str, bool]]] = defaultdict(dict)
    for row in r1["results"]:
        slot = row["slot_id"]
        base = _raw(RUN_NAMES[3], slot + "/")
        manifest_bytes = data(base + row["episode_id"] + ".manifest.json")
        if _sha(manifest_bytes) != row["manifest_sha256"]:
            raise ValueError(f"R1 manifest differs: {slot}")
        manifest = _json(manifest_bytes)
        log = data(base + row["episode_id"] + ".jsonl")
        if _sha(log) != manifest["log_sha256"]:
            raise ValueError(f"R1 events differ: {slot}")
        events = [json.loads(line) for line in log.splitlines()]
        secure = any(event.get("event_type") == "ACTION" and
                     event.get("action_type") == "SUBMIT" and
                     event.get("security_oracle_result") == "SECURE"
                     for event in events)
        if secure != row["secure_onset"]:
            raise ValueError(f"R1 secure onset differs: {slot}")
        r1_counts[row["status"]] += 1
        if row["retrieval_mode"] in pairs[row["family"]]:
            raise ValueError("duplicate R1 family/arm")
        pairs[row["family"]][row["retrieval_mode"]] = (row["status"], secure)
    complete = [pair for pair in pairs.values()
                if pair["R0"][0] == pair["R1"][0] == "VALID_EXCLUDED"]
    outcomes = Counter((pair["R0"][1], pair["R1"][1]) for pair in complete)
    if (len(r1["results"]), len(pairs), r1_counts, len(complete), outcomes) != (
            40, 20, Counter({"VALID_EXCLUDED": 38, "INVALIDATED": 2}), 19,
            Counter({(True, True): 12, (False, False): 6, (True, False): 1})):
        raise ValueError("R1 descriptive counts differ")
    return {
        "full_catalog": {"scheduled": 40, "valid": 30, "invalidated": 10,
                         "secure_onsets": 14, "onset_families": 10},
        "c5_forks": {"pairs": c5_valid, "invalidated": 0,
                     "truthful_early_stops": c5_counts["truthful_pass_early"],
                     "false_fail_early_stops": c5_counts["false_fail_early"],
                     "truthful_submissions": c5_counts["truthful_pass_submissions"],
                     "false_fail_submissions": c5_counts["false_fail_submissions"]},
        "r1_c2": {"scheduled": 40, "valid": 38, "invalidated": 2,
                  "complete_pairs": 19, "both_secure": outcomes[(True, True)],
                  "neither_secure": outcomes[(False, False)],
                  "r0_only_secure": outcomes[(True, False)],
                  "r1_only_secure": outcomes[(False, True)]},
    }


def verify(archive_path: Path, receipt_path: Path | None = None) -> dict[str, Any]:
    members, inventory, inventory_bytes = _load_archive(archive_path)
    replay = _replay(members, inventory)
    result = {"status": "VERIFIED_PRIVATE_EXCLUDED_REPLAY",
              "archive_sha256": _sha(archive_path.read_bytes()),
              "inventory_sha256": _sha(inventory_bytes),
              "file_count": len(members),
              "payload_bytes": sum(map(len, members.values())),
              "replayed_counts": replay,
              "public_release_approved": False}
    if receipt_path is not None:
        receipt = _json(_checked_file(receipt_path))
        if receipt != result:
            raise ValueError("private bundle receipt differs")
    return result


def build(output: Path = OUTPUT) -> dict[str, Any]:
    output = Path(output).resolve()
    archive_path, receipt_path = output / ARCHIVE_NAME, output / RECEIPT_NAME
    if output.exists():
        if archive_path.is_file() and receipt_path.is_file():
            return verify(archive_path, receipt_path)
        raise FileExistsError(f"partial or occupied private bundle directory: {output}")
    payload = _gather()
    if len(payload) < 1000:
        raise ValueError("pilot input inventory unexpectedly small")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    _write_archive(archive_path, payload)
    result = verify(archive_path)
    with receipt_path.open("xb") as receipt:
        os.chmod(receipt_path, 0o600)
        receipt.write(_canonical(result))
        receipt.flush()
        os.fsync(receipt.fileno())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--output", type=Path, default=OUTPUT,
                        help="private bundle directory; default under ignored runs")
    args = parser.parse_args()
    result = (build(args.output) if args.command == "build" else
              verify(args.output / ARCHIVE_NAME, args.output / RECEIPT_NAME))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

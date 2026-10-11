"""Build and verify a REVIEW_ONLY sanitized copy of the private paper input bundle.

Original bytes, the original tarball, and its receipt are never changed. Replacing
host paths changes member SHA-256 values and breaks historical hash chains; this
tool preserves an explicit old-to-new map rather than claiming scientific replay.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "experiments/runs/paper_private_repro_inputs_20261005.tar.gz"
SANITIZED = ROOT / "experiments/runs/paper_sanitized_review_candidate_20261005.tar.gz"
VERSION = "paper-sanitized-review-candidate-1.0.0"
MANIFEST_NAME = "SANITIZATION_MANIFEST.json"
NOTICE_NAME = "REVIEW_ONLY_NOTICE.txt"
OLD_INVENTORY = "BUNDLE_INVENTORY.json"
HOST_PATTERNS = {
    "mac_home": re.compile(rb"/Users/[^/\s\"'<>\\]+", re.I),
    "linux_home": re.compile(rb"/home/[^/\s\"'<>\\]+", re.I),
    "mac_temp": re.compile(rb"/private/(?:var|tmp)/[^\s\"'<>\\]+", re.I),
    "mac_volume": re.compile(rb"/Volumes/[^\s\"'<>\\]+", re.I),
    "windows_home": re.compile(rb"[A-Za-z]:\\Users\\[^\s\"'<>]+", re.I),
    "unix_temp": re.compile(rb"/(?:tmp|var/(?:tmp|folders))/[^\s\"'<>\\]+", re.I),
}
GENERIC_POSIX_PATH = re.compile(
    rb"(?<![A-Za-z0-9:/])/(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+"
)
MAC_HOME = re.compile(r"/Users/([^/\s\"'<>\\]+)", re.I)
LINUX_HOME = re.compile(r"/home/([^/\s\"'<>\\]+)", re.I)
TEMP_PATH = re.compile(r"/private/(?:var|tmp)/[^\s\"'<>\\]+", re.I)
VOLUME_PATH = re.compile(r"/Volumes/[^\s\"'<>\\]+", re.I)
WINDOWS_HOME = re.compile(r"[A-Za-z]:\\Users\\[^\s\"'<>]+", re.I)


class SanitizationError(RuntimeError):
    """A source, package, scan, or hash requirement failed closed."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise SanitizationError(f"missing or symlinked archive: {path}")
    return _sha(path.read_bytes())


def _safe_name(name: str) -> bool:
    p = Path(name)
    return bool(name and not p.is_absolute() and ".." not in p.parts and
                name == p.as_posix() and not any(part in {"", "."} for part in p.parts))


def _members(path: Path) -> dict[str, bytes]:
    """Read files only; no extraction to the filesystem."""
    files: dict[str, bytes] = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            if not member.isfile() or not _safe_name(member.name) or member.name in files:
                raise SanitizationError("unsafe, duplicate, or non-file tar member")
            stream = archive.extractfile(member)
            if stream is None:
                raise SanitizationError("unreadable tar member")
            files[member.name] = stream.read()
    return files


def _validate_original(files: dict[str, bytes]) -> None:
    if OLD_INVENTORY not in files or MANIFEST_NAME in files or NOTICE_NAME in files:
        raise SanitizationError("private source inventory is missing or confused with output")
    try:
        inventory = json.loads(files[OLD_INVENTORY])
    except json.JSONDecodeError as exc:
        raise SanitizationError("original bundle inventory is invalid") from exc
    expected = inventory.get("files") if isinstance(inventory, dict) else None
    if not isinstance(expected, list) or len(expected) != len(files) - 1:
        raise SanitizationError("original inventory count differs from archive")
    by_name = {row.get("path"): row for row in expected if isinstance(row, dict)}
    if set(by_name) != set(files) - {OLD_INVENTORY}:
        raise SanitizationError("original inventory member names differ")
    for name, data in files.items():
        if name == OLD_INVENTORY:
            continue
        row = by_name[name]
        if row.get("sha256") != _sha(data) or row.get("bytes") != len(data):
            raise SanitizationError("original archived member disagrees with private inventory")


def _usernames(files: dict[str, bytes]) -> set[str]:
    """Discover local account tokens without writing them to the review package."""
    names: set[str] = set()
    for data in files.values():
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SanitizationError("non-UTF-8 member needs separate manual review") from exc
        names.update(MAC_HOME.findall(text))
        names.update(LINUX_HOME.findall(text))
    return {name for name in names if name not in {"Shared", "shared"}}


def scan_bytes(data: bytes, *, usernames: set[str]) -> dict[str, int]:
    """Count host-specific absolute path and discovered username markers only."""
    counts = {label: len(pattern.findall(data)) for label, pattern in HOST_PATTERNS.items()}
    counts["local_username"] = sum(
        len(re.findall(re.escape(name.encode("utf-8")), data, re.I)) for name in usernames
    )
    return counts


def _generic_path_scan(files: dict[str, bytes]) -> dict[str, Any]:
    """Surface broad lexical leads without pretending every slash path is host-private."""
    prefixes: Counter[str] = Counter()
    outside_root_prefixes: Counter[str] = Counter()
    affected = 0
    root_continuations = 0
    for data in files.values():
        matches = list(GENERIC_POSIX_PATH.finditer(data))
        affected += bool(matches)
        for match in matches:
            prefix = "/" + match.group().split(b"/")[1].decode("ascii", "replace")
            prefixes[prefix] += 1
            if data[max(0, match.start() - len(b"<RESEARCH_ROOT>")):match.start()] == b"<RESEARCH_ROOT>":
                root_continuations += 1
            else:
                outside_root_prefixes[prefix] += 1
    return {"count": sum(prefixes.values()), "affected_files": affected,
            "top_level_segments": dict(sorted(prefixes.items())),
            "research_root_placeholder_continuations": root_continuations,
            "outside_placeholder_count": sum(outside_root_prefixes.values()),
            "outside_placeholder_top_level_segments": dict(sorted(outside_root_prefixes.items())),
            "meaning": "lexical leads for manual review; includes research-root placeholder suffixes and code/task examples"}


def scan_archive(path: Path, *, original: Path | None = None) -> dict[str, Any]:
    files = _members(path)
    names = _usernames(_members(original)) if original is not None else _usernames(files)
    totals: Counter[str] = Counter()
    affected: Counter[str] = Counter()
    for member, data in files.items():
        counts = scan_bytes(data, usernames=names)
        counts_name = scan_bytes(member.encode("utf-8"), usernames=names)
        for label in counts:
            total = counts[label] + counts_name[label]
            totals[label] += total
            affected[label] += bool(total)
    return {"archive_sha256": _file_sha(path), "members": len(files),
            "marker_occurrences": dict(totals), "marker_affected_files": dict(affected),
            "marker_scope": "host home/temp/volume paths and usernames discovered from source archive",
            "generic_multi_segment_posix_path_candidates": _generic_path_scan(files)}


def _sanitize_text(data: bytes, *, usernames: set[str]) -> tuple[bytes, dict[str, int]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SanitizationError("non-UTF-8 member needs separate manual review") from exc
    counts: Counter[str] = Counter()

    def replace(pattern: re.Pattern[str], replacement: str, label: str, value: str) -> str:
        new, count = pattern.subn(replacement, value)
        counts[label] += count
        return new

    # Remove the full repository prefix first so relative tails remain legible.
    root_pattern = re.compile(re.escape(ROOT.as_posix()), re.I)
    text = replace(root_pattern, "<RESEARCH_ROOT>", "research_root", text)
    text = replace(MAC_HOME, "<LOCAL_HOME>", "mac_home", text)
    text = replace(LINUX_HOME, "<LOCAL_HOME>", "linux_home", text)
    text = replace(TEMP_PATH, "<LOCAL_TEMP_PATH>", "mac_temp", text)
    text = replace(re.compile(r"/(?:tmp|var/(?:tmp|folders))/[^\s\"'<>\\]+", re.I),
                   "<LOCAL_TEMP_PATH>", "unix_temp", text)
    text = replace(VOLUME_PATH, "<LOCAL_VOLUME_PATH>", "mac_volume", text)
    text = replace(WINDOWS_HOME, "<LOCAL_HOME>", "windows_home", text)
    for name in sorted(usernames, key=len, reverse=True):
        text = replace(re.compile(re.escape(name), re.I), "<LOCAL_USER>",
                       "bare_username", text)
    result = text.encode("utf-8")
    if scan_bytes(result, usernames=usernames) != {label: 0 for label in (*HOST_PATTERNS, "local_username")}:
        raise SanitizationError("host path or username marker survived transformation")
    return result, dict(counts)


def _validate_text_structure(name: str, original: bytes, sanitized: bytes) -> str:
    """Parsing checks do not establish scientific replay or semantic equivalence."""
    try:
        if name.endswith(".json"):
            json.loads(original)
            json.loads(sanitized)
            return "JSON_PARSE_OK"
        if name.endswith(".jsonl"):
            old_lines = [line for line in original.splitlines() if line.strip()]
            new_lines = [line for line in sanitized.splitlines() if line.strip()]
            if len(old_lines) != len(new_lines):
                raise SanitizationError("JSONL line count changed")
            for old, new in zip(old_lines, new_lines, strict=True):
                json.loads(old)
                json.loads(new)
            return "JSONL_PARSE_OK"
    except json.JSONDecodeError as exc:
        raise SanitizationError(f"JSON structure changed: {name}") from exc
    return "TEXT_ONLY"


def _record(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(data))


def build(*, original: Path = ORIGINAL, output: Path = SANITIZED) -> dict[str, Any]:
    original = Path(original).resolve()
    output = Path(output).resolve()
    receipt_path = output.with_suffix(".receipt.json")
    if output.exists() or receipt_path.exists():
        raise FileExistsError("review candidate or its receipt already exists")
    source_digest = _file_sha(original)
    private_receipt_path = original.with_suffix(".receipt.json")
    private_receipt = json.loads(private_receipt_path.read_text(encoding="utf-8"))
    if private_receipt.get("archive_sha256") != source_digest:
        raise SanitizationError("private source archive differs from its receipt")
    source = _members(original)
    _validate_original(source)
    usernames = _usernames(source)
    sanitized: dict[str, bytes] = {}
    mappings: list[dict[str, Any]] = []
    for name, data in sorted(source.items()):
        if name == OLD_INVENTORY:
            mappings.append({"path": name, "status": "REPLACED_BY_SANITIZATION_MANIFEST",
                             "original_sha256": _sha(data), "sanitized_sha256": None,
                             "original_bytes": len(data), "sanitized_bytes": None})
            continue
        transformed, changes = _sanitize_text(data, usernames=usernames)
        parse_status = _validate_text_structure(name, data, transformed)
        sanitized[name] = transformed
        mappings.append({"path": name, "status": "TRANSFORMED" if transformed != data else "UNCHANGED",
                         "original_sha256": _sha(data), "sanitized_sha256": _sha(transformed),
                         "original_bytes": len(data), "sanitized_bytes": len(transformed),
                         "replacements": changes, "structure_check": parse_status})
    before = scan_archive(original)
    notice = (
        "REVIEW ONLY — SANITIZED CANDIDATE. Do not upload as original raw data.\n"
        "Host-specific paths and local account tokens were replaced. Changed bytes\n"
        "have new SHA-256 digests; original digests are preserved only as metadata\n"
        "in SANITIZATION_MANIFEST.json. Historical hash-linked receipts and the\n"
        "paper analysis cannot be replayed from this copy without a separately\n"
        "validated remapping and re-analysis. Other privacy risks need human review.\n"
    ).encode("utf-8")
    sanitized[NOTICE_NAME] = notice
    manifest = {
        "version": VERSION, "status": "REVIEW_ONLY_SANITIZED_CANDIDATE",
        "public_release_approved": False, "scientific_replay_verified": False,
        "original_byte_identical_raw_data": False,
        "source_archive_sha256": source_digest,
        "source_inventory_sha256": _sha(source[OLD_INVENTORY]),
        "source_member_count": len(source),
        "mapping_count": len(mappings),
        "changed_member_count": sum(row["status"] == "TRANSFORMED" for row in mappings),
        "original_marker_counts": before["marker_occurrences"],
        "unreviewed_absolute_path_candidates": _generic_path_scan(sanitized),
        "members": mappings,
        "transform": "host repository, home, temp, volume path and discovered account-token substitution",
        "limitation": "Changed source bytes invalidate original member hashes and embedded hash links; original archive is required for exact historical replay.",
    }
    sanitized[MANIFEST_NAME] = (json.dumps(manifest, ensure_ascii=False,
                                          sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    residuals = {label: 0 for label in (*HOST_PATTERNS, "local_username")}
    for name, data in sanitized.items():
        for label, count in scan_bytes(data, usernames=usernames).items():
            residuals[label] += count
        for label, count in scan_bytes(name.encode(), usernames=usernames).items():
            residuals[label] += count
    if any(residuals.values()):
        raise SanitizationError("review package still contains target host markers")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, data in sorted(sanitized.items()):
                    _record(archive, name, data)
    rebuilt = _members(output)
    if rebuilt != sanitized:
        raise SanitizationError("written review archive differs from prepared members")
    if _file_sha(original) != source_digest:
        raise SanitizationError("original private archive changed during review build")
    result = {"version": VERSION, "status": "REVIEW_ONLY_SANITIZED_CANDIDATE",
              "public_release_approved": False, "scientific_replay_verified": False,
              "source_archive_sha256": source_digest,
              "sanitized_archive_sha256": _file_sha(output),
              "source_members": len(source), "sanitized_members": len(sanitized),
              "changed_member_count": manifest["changed_member_count"],
              "residual_marker_counts": residuals,
              "sanitization_manifest_sha256": _sha(sanitized[MANIFEST_NAME])}
    with receipt_path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return result


def verify(*, original: Path = ORIGINAL, sanitized: Path = SANITIZED) -> dict[str, Any]:
    original, sanitized = Path(original).resolve(), Path(sanitized).resolve()
    source, review = _members(original), _members(sanitized)
    _validate_original(source)
    names = _usernames(source)
    if MANIFEST_NAME not in review or NOTICE_NAME not in review or OLD_INVENTORY in review:
        raise SanitizationError("review-specific manifest/notice inventory is wrong")
    manifest = json.loads(review[MANIFEST_NAME])
    if (manifest.get("version") != VERSION or manifest.get("status") != "REVIEW_ONLY_SANITIZED_CANDIDATE"
            or manifest.get("public_release_approved") is not False
            or manifest.get("scientific_replay_verified") is not False
            or manifest.get("original_byte_identical_raw_data") is not False
            or manifest.get("source_archive_sha256") != _file_sha(original)
            or manifest.get("source_inventory_sha256") != _sha(source[OLD_INVENTORY])):
        raise SanitizationError("review manifest does not bind the original private archive")
    rows = manifest.get("members")
    if not isinstance(rows, list) or len(rows) != len(source):
        raise SanitizationError("review mapping is incomplete")
    by_name = {row.get("path"): row for row in rows if isinstance(row, dict)}
    if set(by_name) != set(source) or set(review) != (set(source) - {OLD_INVENTORY}) | {MANIFEST_NAME, NOTICE_NAME}:
        raise SanitizationError("review archive member mapping differs")
    if manifest.get("unreviewed_absolute_path_candidates") != _generic_path_scan(
            {name: review[name] for name in source if name != OLD_INVENTORY}):
        raise SanitizationError("broad absolute-path review leads differ from archive")
    for name, data in source.items():
        row = by_name[name]
        if row.get("original_sha256") != _sha(data):
            raise SanitizationError("mapped original hash differs")
        if name == OLD_INVENTORY:
            if row.get("status") != "REPLACED_BY_SANITIZATION_MANIFEST" or row.get("sanitized_sha256") is not None:
                raise SanitizationError("old inventory replacement not identified")
            continue
        transformed, _changes = _sanitize_text(data, usernames=names)
        if (review[name] != transformed or row.get("sanitized_sha256") != _sha(review[name])
                or row.get("status") != ("TRANSFORMED" if transformed != data else "UNCHANGED")):
            raise SanitizationError("mapped sanitized member differs from deterministic transform")
        _validate_text_structure(name, data, review[name])
    scan = scan_archive(sanitized, original=original)
    if any(scan["marker_occurrences"].values()):
        raise SanitizationError("review archive still contains host path or username markers")
    receipt_path = sanitized.with_suffix(".receipt.json")
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (receipt.get("source_archive_sha256") != _file_sha(original)
                or receipt.get("sanitized_archive_sha256") != _file_sha(sanitized)
                or receipt.get("sanitization_manifest_sha256") != _sha(review[MANIFEST_NAME])):
            raise SanitizationError("review sidecar receipt differs")
    return {"status": "REVIEW_ONLY_VERIFIED_NOT_REPLAY_READY",
            "source_archive_sha256": _file_sha(original),
            "sanitized_archive_sha256": _file_sha(sanitized),
            "source_members": len(source), "sanitized_members": len(review),
            "changed_members": manifest["changed_member_count"],
            "residual_marker_counts": scan["marker_occurrences"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "scan", "verify"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--original", type=Path, default=ORIGINAL)
        if name == "build":
            cmd.add_argument("--output", type=Path, default=SANITIZED)
        else:
            cmd.add_argument("--sanitized", type=Path, default=SANITIZED)
    args = parser.parse_args()
    if args.command == "build":
        result = build(original=args.original, output=args.output)
    elif args.command == "scan":
        result = scan_archive(args.sanitized, original=args.original)
    else:
        result = verify(original=args.original, sanitized=args.sanitized)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""Read-only byte scan of an excluded archive before public release.

Findings contain only a pattern category and a relative file path; a filename
that itself resembles a secret is replaced by a digest marker. The scanner
recognizes only listed byte patterns. It does not decode compressed/nested
archives, reconstruct split or encoded values, detect arbitrary credentials,
or decide whether a matched value is live. Zero hits are not privacy clearance:
a person must still inspect the archive and its intended audience.

An exact /private/tmp output root recorded in a frozen plan can be passed as
``--planned-temp-root``. Its presence is reported separately as local-execution
metadata and does not make other nearby paths safe by implication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, Iterator, Sequence


SCHEMA_VERSION = "public-excluded-archive-screen-1"
PATTERNS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    ("STRIPE_API_KEY", re.compile(rb"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("GITHUB_TOKEN", re.compile(
        rb"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("AWS_ACCESS_KEY_ID", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GOOGLE_API_KEY", re.compile(rb"\bAIza[A-Za-z0-9_-]{35}\b")),
    ("GOOGLE_ACCESS_TOKEN", re.compile(rb"\bya29\.[A-Za-z0-9_-]{20,}\b")),
    ("SLACK_TOKEN", re.compile(rb"\bxox[baprsdc]-[A-Za-z0-9-]{10,}\b")),
    ("PEM_PRIVATE_KEY", re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----")),
    ("BEARER_TOKEN", re.compile(rb"\bBearer[ \t]+[A-Za-z0-9._~+/-]{12,}={0,2}\b", re.I)),
    ("BASIC_TOKEN", re.compile(rb"\bBasic[ \t]+[A-Za-z0-9+/]{16,}={0,2}\b", re.I)),
    ("EMAIL_ADDRESS", re.compile(
        rb"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("MAC_HOME_PATH", re.compile(rb"/Users/[A-Za-z0-9._-]+(?:/|\b)")),
    ("LINUX_HOME_PATH", re.compile(rb"/(?:home/[A-Za-z0-9._-]+|root)(?:/|\b)")),
    ("WINDOWS_HOME_PATH", re.compile(
        rb"\b[A-Za-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+[A-Za-z0-9._-]+", re.I)),
    ("PRIVATE_MAC_TEMP_PATH", re.compile(
        rb"/(?:private/)?var/folders/[A-Za-z0-9._/-]+")),
)


class ScanError(ValueError):
    """An archive is not a stable tree of regular files or output is unsafe."""


def _display_path(relative: str) -> str:
    """Avoid printing a secret that happened to be used as a filename."""
    encoded = relative.encode("utf-8")
    if any(pattern.search(encoded) for _, pattern in PATTERNS):
        return f"[REDACTED_PATH_SHA256_{hashlib.sha256(encoded).hexdigest()[:12]}]"
    return relative


def _walk_regular_files(root: Path) -> Iterator[tuple[str, Path]]:
    if root.is_symlink() or not root.is_dir():
        raise ScanError("archive root must be a real directory")

    def walk(directory: Path) -> Iterator[tuple[str, Path]]:
        with os.scandir(directory) as entries:
            ordered = sorted(entries, key=lambda entry: entry.name)
        for entry in ordered:
            path = Path(entry.path)
            rel = path.relative_to(root).as_posix()
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(mode):
                raise ScanError(f"archive contains a symlink at {_display_path(rel)}")
            if stat.S_ISDIR(mode):
                yield from walk(path)
            elif stat.S_ISREG(mode):
                yield rel, path
            else:
                raise ScanError(f"archive contains a non-regular entry at {_display_path(rel)}")

    yield from walk(root)


def _read_regular_bytes(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ScanError("archive entry changed from a regular file")
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                after.st_size, after.st_mtime_ns, after.st_ino):
            raise ScanError("archive entry changed during scan")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def scan_archive(root: Path, *, planned_temp_roots: Sequence[str] = ()) -> dict[str, Any]:
    """Scan every regular file as bytes and bind a path/content tree hash."""
    root = Path(root)
    planned_patterns = []
    for planned in planned_temp_roots:
        if (not isinstance(planned, str) or not planned.startswith("/private/tmp/")
                or planned.endswith("/") or "\n" in planned or "\r" in planned):
            raise ScanError("planned temp roots must be exact /private/tmp paths")
        planned_patterns.append(re.compile(re.escape(planned.encode("utf-8")) +
                                           rb"(?:/|[^A-Za-z0-9._-]|$)"))
    files = list(_walk_regular_files(root))
    if not files:
        raise ScanError("archive has no regular files")
    files.sort(key=lambda row: row[0])
    tree = hashlib.sha256()
    findings: list[dict[str, str]] = []
    metadata_findings: list[dict[str, str]] = []
    for rel, path in files:
        data = _read_regular_bytes(path)
        digest = hashlib.sha256(data).hexdigest()
        tree.update(f"{rel}\0{len(data)}\0{digest}\n".encode("utf-8"))
        for category, pattern in PATTERNS:
            if pattern.search(data):
                findings.append({"category": category, "path": _display_path(rel)})
        if any(pattern.search(data) for pattern in planned_patterns):
            metadata_findings.append({"category": "PLANNED_LOCAL_TEMP_ROOT",
                                      "path": _display_path(rel)})
    findings.sort(key=lambda item: (item["path"], item["category"]))
    metadata_findings.sort(key=lambda item: item["path"])
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "HITS_FOUND" if findings else "NO_PATTERN_HITS",
        "file_count": len(files),
        "tree_sha256": tree.hexdigest(),
        "findings": findings,
        "metadata_findings": metadata_findings,
        "pattern_categories": [category for category, _ in PATTERNS],
        "limitations": (
            "Pattern scan only: encoded, split, unfamiliar, or contextual secrets "
            "and personal data may be missed; hits and planned-path metadata "
            "require human review, and zero hits are not privacy clearance."
        ),
    }


def _write_receipt(path: Path, receipt: dict[str, Any], archive_root: Path) -> None:
    path = Path(path)
    if path.resolve().is_relative_to(Path(archive_root).resolve()):
        raise ScanError("scan receipt must be written outside the archive")
    if path.exists() or path.is_symlink():
        raise ScanError("scan receipt already exists; choose a new path")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="stable public-copy archive to scan")
    parser.add_argument("--json-out", type=Path,
                        help="new receipt path outside the scanned archive")
    parser.add_argument("--planned-temp-root", action="append", default=[],
                        help="exact non-identifying /private/tmp output root fixed in a plan")
    args = parser.parse_args(argv)
    try:
        if args.json_out and args.json_out.resolve().is_relative_to(args.archive.resolve()):
            raise ScanError("scan receipt must be outside the archive")
        receipt = scan_archive(args.archive, planned_temp_roots=args.planned_temp_root)
        if args.json_out:
            _write_receipt(args.json_out, receipt, args.archive)
    except ScanError as exc:
        # Structural errors contain only relative paths or generic reasons.
        print(f"SCAN_ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError:
        # Filesystem exceptions can contain absolute local paths; never print
        # them in a publication-screening receipt.
        print("SCAN_ERROR: filesystem read/write failure", file=sys.stderr)
        return 2
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))
    return 1 if receipt["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

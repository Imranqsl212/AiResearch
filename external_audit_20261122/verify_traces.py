"""Verify frozen raw-trace hashes and cited JSON pointers without executing traces.

Run with --offline to require the original local cache. Otherwise, a missing or
nonmatching cache file falls back to public_io.fetch (its public URL cache/curl
client). No audit file is written, and missing-at-collection slots are retained.
Only Python standard-library modules and the existing public_io helper are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
SELECTION_SHA256 = "7b8e1869d1101c0851935686c20e1003f78922bf75840cab17c702d4aa9e23e2"
CHECKS_SHA256 = "212dd1ce88f84033b0df717c9fb4672795fb4e768e5ef9c4a7e98a72eceb1f47"
MAX_BYTES = 64 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_bytes(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, f"File exceeds inspection size limit: {path}")
    return raw


def unique_pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique_pairs)


def pointers(node):
    """Collect cited JSON pointers, including nested evidence and last actions."""
    found = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"locator", "location", "locators"} or key.endswith(("_locator", "_locators")):
                values = value if isinstance(value, list) else [value]
                for item in values:
                    if item is not None:
                        require(isinstance(item, str), f"Non-string pointer at {key}")
                        found.add(item)
            if isinstance(value, (dict, list)):
                found.update(pointers(value))
    elif isinstance(node, list):
        for value in node:
            found.update(pointers(value))
    return found


def resolve(document, pointer):
    """Resolve RFC 6901 pointers; reject invalid escapes and array indexes."""
    require(pointer == "" or pointer.startswith("/"), f"Invalid JSON pointer: {pointer}")
    value = document
    for token in pointer.split("/")[1:]:
        require(not re.search(r"~(?![01])", token), f"Invalid pointer escape: {pointer}")
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            require(re.fullmatch(r"0|[1-9][0-9]*", token) is not None,
                    f"Invalid array index: {pointer}")
            require(int(token) < len(value), f"Array index out of range: {pointer}")
            value = value[int(token)]
        else:
            require(isinstance(value, dict) and token in value,
                    f"Unresolved JSON pointer: {pointer}")
            value = value[token]
    return value


def obtain(row, offline):
    try:
        raw = read_bytes(Path(row["raw_path"]))
    except (OSError, ValueError):
        raw = None
    if raw is not None and digest(raw) == row["raw_sha256"]:
        return raw, "local_cache"
    require(not offline, f"No matching local cache for {row['series']} {row['instance_id']}")
    from public_io import fetch
    raw, _ = fetch(row["trace_url"])
    require(len(raw) <= MAX_BYTES, "Fetched trace exceeds inspection size limit")
    require(digest(raw) == row["raw_sha256"],
            f"Published artifact hash mismatch: {row['series']} {row['instance_id']}")
    return raw, "public_fetch"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Require matching original cache files; never fetch.")
    args = parser.parse_args()
    selection_raw = read_bytes(ROOT / "selection.json")
    require(digest(selection_raw) == SELECTION_SHA256, "Frozen selection hash mismatch")
    selection = decode(selection_raw)
    protocol_hash = digest(read_bytes(ROOT / "protocol.md"))
    protocol_receipt = decode(read_bytes(ROOT / "protocol_freeze.json"))
    require(protocol_hash == selection["protocol_sha256"] == protocol_receipt["sha256"],
            "Protocol hash mismatch")
    for series in ("A", "B"):
        require(digest(read_bytes(ROOT / f"discovery_{series}.json")) == selection["discovery_sha256"][series],
                f"Discovery hash mismatch: {series}")
    checks_raw = read_bytes(ROOT / "independent_checks.json")
    receipt = (ROOT / "independent_checks.sha256").read_text().split()
    require(receipt == [CHECKS_SHA256, "independent_checks.json"] and digest(checks_raw) == CHECKS_SHA256,
            "Independent-check receipt mismatch")
    checks = decode(checks_raw)
    require(checks["selection_sha256"] == SELECTION_SHA256, "Independent-check selection mismatch")
    keys = [(slot["series"], slot["instance_id"]) for slot in selection["slots"]]
    indexed = {(row["series"], row["instance_id"]): row for row in checks["rows"]}
    require(len(keys) == len(set(keys)) == len(indexed) == len(checks["rows"]) == 20
            and set(indexed) == set(keys), "Reserved-slot index mismatch")
    verified = pointer_count = 0
    sources = {"local_cache": 0, "public_fetch": 0}
    missing = []
    for key in keys:
        row = indexed[key]
        require(type(row["available"]) is bool, f"Invalid availability flag: {key}")
        cited = pointers(row)
        if not row["available"]:
            require(not row.get("raw_sha256") and not cited, f"Missing slot has raw evidence: {key}")
            missing.append(key)
            continue
        raw, source = obtain(row, args.offline)
        require(digest(raw) == row["raw_sha256"] and len(raw) == row["bytes"],
                f"Raw artifact receipt mismatch: {key}")
        document = decode(raw)
        require(cited, f"Available artifact has no cited pointers: {key}")
        for pointer in sorted(cited):
            resolve(document, pointer)
        verified += 1
        pointer_count += len(cited)
        sources[source] += 1
    require(verified == 18 and missing == [("A", "django__django-13449"), ("A", "django__django-11880")],
            "Collection availability differs from the frozen audit")
    print("PASS: frozen selection, protocol, discoveries, independent receipt, and 20-slot index verified.")
    print(f"PASS: {verified}/18 collected trace hashes and {pointer_count} distinct per-artifact JSON pointers verified "
          f"(local_cache={sources['local_cache']}, public_fetch={sources['public_fetch']}).")
    for series, issue in missing:
        print(f"MISSING AT COLLECTION: {series} {issue} (retained; not replaced or refetched).")
    print("No model, trace command, patch, or test executed. This verifies bytes and pointer resolution, not coding judgments.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

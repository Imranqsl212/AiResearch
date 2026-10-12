"""Write-once source-page capture for excluded R1 candidate v0.2.

Capture saves HTTP response bodies returned by urllib with identity content
encoding. The tracked release copy of snapshot 03 has a documented,
length-preserving token redaction; its original bytes remain private. Verify
checks the bytes recorded in a manifest, not their equality to the HTTP source.
These pages are source evidence, not human admission or a main freeze.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from benchmark import retrieval_r1_20_candidate_v2 as candidate


DEFAULT_OUTPUT = (Path(__file__).resolve().parents[1] / "experiments" / "runs"
                  / "r1_source_snapshots_candidate_v2_20261005")
URL_PATTERN = re.compile(r"https://[^\s;]+")
MAX_BODY_BYTES = 15_000_000
ALLOWED_HOSTS = candidate._PRIMARY_HOSTS


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def source_urls() -> list[dict[str, object]]:
    """Get every distinct cited URL from the pinned candidate, first seen first."""
    candidate.verify_candidate_manifest()
    references: dict[str, list[str]] = defaultdict(list)
    for row in candidate._read_rows():
        for url in URL_PATTERN.findall(row["source"]):
            if urlparse(url).hostname not in ALLOWED_HOSTS:
                raise ValueError(f"nonprimary source URL: {url}")
            if row["family"] not in references[url]:
                references[url].append(row["family"])
    return [{"url": url, "families": families} for url, families in references.items()]


@dataclass(frozen=True)
class FetchResult:
    fetched_at_utc: str
    final_url: str | None
    http_status: int | None
    content_type: str | None
    body: bytes | None
    failure_reason: str | None
    etag: str | None = None
    last_modified: str | None = None


def fetch_url(url: str) -> FetchResult:
    request = Request(url, headers={
        "User-Agent": "ResearchSourceSnapshot/0.1 (+local private audit)",
        "Accept-Encoding": "identity",
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.8,*/*;q=0.5",
    })
    timestamp = utc_now()
    try:
        with urlopen(request, timeout=30) as response:
            final_url = response.geturl()
            status = response.status
            content_type = response.headers.get("Content-Type")
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            if urlparse(final_url).hostname not in ALLOWED_HOSTS:
                return FetchResult(timestamp, final_url, status, content_type, None,
                                   "redirected outside declared primary domains", etag, last_modified)
            body = response.read(MAX_BODY_BYTES + 1)
            if len(body) > MAX_BODY_BYTES:
                return FetchResult(timestamp, final_url, status, content_type, None,
                                   "body exceeded 15,000,000-byte limit", etag, last_modified)
            if status != 200 or not body:
                return FetchResult(timestamp, final_url, status, content_type, None,
                                   f"HTTP {status} or empty response body", etag, last_modified)
            return FetchResult(timestamp, final_url, status, content_type, body,
                               None, etag, last_modified)
    except HTTPError as exc:
        return FetchResult(timestamp, exc.geturl(), exc.code,
                           exc.headers.get("Content-Type"), None, f"HTTP {exc.code}")
    except (URLError, TimeoutError, OSError) as exc:
        return FetchResult(timestamp, None, None, None, None,
                           f"{type(exc).__name__}: {exc}")


def capture(output: Path = DEFAULT_OUTPUT, *, fetcher=fetch_url,
            max_workers: int = 4) -> dict[str, object]:
    """Create a private, write-once manifest and body files."""
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"snapshot archive already exists: {output}")
    urls = source_urls()
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    old_umask = os.umask(0o077)
    try:
        temp = Path(tempfile.mkdtemp(prefix=output.name + ".tmp-", dir=parent))
    finally:
        os.umask(old_umask)
    try:
        (temp / "snapshots").mkdir(mode=0o700)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            results = list(pool.map(fetcher, [item["url"] for item in urls]))
        entries: list[dict[str, object]] = []
        for index, (source, result) in enumerate(zip(urls, results, strict=True)):
            body_file = None
            body_sha256 = None
            body_bytes = None
            status = "FETCH_FAILED"
            failure_reason = result.failure_reason
            if result.body is not None and failure_reason is None:
                body_file = f"snapshots/{index:02d}.body"
                body = result.body
                (temp / body_file).write_bytes(body)
                (temp / body_file).chmod(0o600)
                body_sha256 = sha256(body)
                body_bytes = len(body)
                status = "SAVED"
            entries.append({
                "url": source["url"], "families": source["families"],
                "retrieval_status": status, "fetched_at_utc": result.fetched_at_utc,
                "final_url": result.final_url, "http_status": result.http_status,
                "content_type": result.content_type, "etag": result.etag,
                "last_modified": result.last_modified,
                "body_file": body_file, "body_sha256": body_sha256,
                "body_bytes": body_bytes, "failure_reason": failure_reason,
            })
        body = {
            "schema_version": "excluded-r1-v2-primary-page-snapshots-0.1",
            "admission_status": "EXCLUDED_PROTOTYPE_UNREVIEWED",
            "capture_status": ("COMPLETE" if all(e["retrieval_status"] == "SAVED" for e in entries)
                               else "PARTIAL"),
            "captured_at_utc": utc_now(),
            "candidate_corpus_sha256": sha256(candidate.CORPUS_PATH.read_bytes()),
            "candidate_manifest_file_sha256": sha256(candidate.MANIFEST_PATH.read_bytes()),
            "source_count": len(entries),
            "entries": entries,
        }
        manifest = {**body, "manifest_sha256": sha256(canonical(body))}
        manifest_path = temp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False,
                                            sort_keys=True, indent=2) + "\n", encoding="utf-8")
        manifest_path.chmod(0o600)
        temp.rename(output)
        return verify(output)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def verify(output: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    """Fail closed on changed corpus, URL inventory, manifest, or body bytes."""
    output = output.resolve()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or "manifest_sha256" not in manifest:
        raise ValueError("missing manifest digest")
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    if sha256(canonical(body)) != manifest["manifest_sha256"]:
        raise ValueError("manifest digest mismatch")
    if manifest["schema_version"] != "excluded-r1-v2-primary-page-snapshots-0.1":
        raise ValueError("wrong snapshot schema")
    if manifest["admission_status"] != "EXCLUDED_PROTOTYPE_UNREVIEWED":
        raise ValueError("unexpected admission status")
    if manifest["candidate_corpus_sha256"] != sha256(candidate.CORPUS_PATH.read_bytes()):
        raise ValueError("candidate corpus changed")
    if manifest["candidate_manifest_file_sha256"] != sha256(candidate.MANIFEST_PATH.read_bytes()):
        raise ValueError("candidate manifest changed")
    urls = source_urls()
    entries = manifest["entries"]
    if manifest["source_count"] != len(urls) or len(entries) != len(urls):
        raise ValueError("source inventory count mismatch")
    saved = 0
    for index, (expected, entry) in enumerate(zip(urls, entries, strict=True)):
        if entry["url"] != expected["url"] or entry["families"] != expected["families"]:
            raise ValueError("source inventory changed")
        if entry["retrieval_status"] == "SAVED":
            if entry["failure_reason"] is not None or entry["http_status"] != 200:
                raise ValueError("inconsistent saved status")
            file_name = f"snapshots/{index:02d}.body"
            if entry["body_file"] != file_name:
                raise ValueError("unexpected body path")
            data = (output / file_name).read_bytes()
            if not data or len(data) != entry["body_bytes"] or sha256(data) != entry["body_sha256"]:
                raise ValueError("source body digest mismatch")
            saved += 1
        elif entry["retrieval_status"] == "FETCH_FAILED":
            if (entry["failure_reason"] is None or entry["body_file"] is not None
                    or entry["body_sha256"] is not None or entry["body_bytes"] is not None):
                raise ValueError("inconsistent failed status")
        else:
            raise ValueError("unknown retrieval status")
    expected_status = "COMPLETE" if saved == len(entries) else "PARTIAL"
    if manifest["capture_status"] != expected_status:
        raise ValueError("wrong capture status")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "verify"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = capture(args.output) if args.action == "capture" else verify(args.output)
    print(json.dumps({
        "capture_status": manifest["capture_status"],
        "source_count": manifest["source_count"],
        "saved": sum(e["retrieval_status"] == "SAVED" for e in manifest["entries"]),
        "manifest_sha256": manifest["manifest_sha256"],
        "output": str(args.output.resolve()),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

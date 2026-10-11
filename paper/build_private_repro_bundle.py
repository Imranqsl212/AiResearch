"""Package the exact exploratory-paper inputs for private author review.

The archive retains original bytes and may contain local path metadata. It is
not a public release or a submission supplement until a human release review.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "paper/artifacts/input_hashes.csv"
HISTORICAL = ROOT / "paper/historical_receipts_20261003.txt"
OUTPUT = ROOT / "experiments/runs/paper_private_repro_inputs_20261005.tar.gz"
RECEIPT = OUTPUT.with_suffix(".receipt.json")
VERSION = "paper-private-input-bundle-1.0"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(data))


def build(output: Path = OUTPUT) -> dict[str, object]:
    if output.exists() or output.with_suffix(".receipt.json").exists():
        raise FileExistsError("private review bundle already exists")
    rows = list(csv.DictReader(LEDGER.open(encoding="utf-8", newline="")))
    if len(rows) != 311 or any(set(row) != {"path", "sha256"} for row in rows):
        raise ValueError("paper input ledger is incomplete")
    files: dict[str, bytes] = {}
    for row in rows:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("unsafe input path")
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing or redirected input: {relative}")
        data = path.read_bytes()
        if _sha256(data) != row["sha256"] or relative.as_posix() in files:
            raise ValueError(f"input hash or uniqueness differs: {relative}")
        files[relative.as_posix()] = data
    files["paper/historical_receipts_20261003.txt"] = HISTORICAL.read_bytes()
    notice = (
        "PRIVATE REVIEW ONLY. Original exploratory-paper input bytes may contain local\n"
        "path metadata, model-generated source, and tool output. Do not upload or\n"
        "submit this archive before the authors approve a reviewed release.\n"
        "Overlay files at their paths in the study repository, then run\n"
        "python3 -B -m analysis.paper_pipeline --output paper/artifacts.\n"
    ).encode("utf-8")
    files["PRIVATE_REVIEW_ONLY.txt"] = notice
    marker_counts = {
        "absolute_user_path_files": sum(b"/Users/" in data for data in files.values()),
        "local_username_files": sum(b"imranmzakirov" in data.lower() for data in files.values()),
    }
    inventory = {
        "version": VERSION, "status": "PRIVATE_REVIEW_ONLY_UNREDACTED",
        "public_release_approved": False,
        "paper_input_ledger_sha256": _sha256(LEDGER.read_bytes()),
        "files": [{"path": name, "sha256": _sha256(data), "bytes": len(data)}
                  for name, data in sorted(files.items())],
        "marker_counts": marker_counts,
    }
    files["BUNDLE_INVENTORY.json"] = (json.dumps(inventory, sort_keys=True,
                                                  separators=(",", ":")) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, data in sorted(files.items()):
                    _record(archive, name, data)
    with tarfile.open(output, "r:gz") as archive:
        names = archive.getnames()
        if names != sorted(files):
            raise ValueError("private bundle inventory differs after writing")
        for name in names:
            stream = archive.extractfile(name)
            if stream is None or stream.read() != files[name]:
                raise ValueError(f"private bundle byte verification failed: {name}")
    receipt = {
        "version": VERSION, "status": "PRIVATE_REVIEW_ONLY_UNREDACTED",
        "archive_path": str(output.resolve()), "archive_sha256": _sha256(output.read_bytes()),
        "input_file_count": len(rows), "additional_file_count": len(files) - len(rows),
        "archive_bytes": output.stat().st_size, "marker_counts": marker_counts,
    }
    output.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2,
                                                                 sort_keys=True) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))

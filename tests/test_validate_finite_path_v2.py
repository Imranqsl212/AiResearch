"""Saved-artifact integrity tests for the v2 path fixture gate."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from benchmark.finite_path_v2 import certify_task
from benchmark.validate_finite_path_v2 import DEFAULT_INDEX, validate_index


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_fixture(directory: Path) -> Path:
    target = directory / "v2_path"
    shutil.copytree(DEFAULT_INDEX.parent, target)
    return target / "index.json"


def test_saved_index_passes() -> None:
    report = validate_index()
    assert report["status"] == "PASS"
    assert report["candidate_checks"] == 1280
    assert report["proofs_verified"] == 5
    assert report["insecure_mutation_checks"] == 10


def test_index_rejects_changed_reference_bytes() -> None:
    with tempfile.TemporaryDirectory(prefix="finite-path-index-") as folder:
        index_path = _copy_fixture(Path(folder))
        reference = index_path.parent / "path-boundary.references.json"
        reference.write_text(reference.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        try:
            validate_index(index_path)
        except ValueError as exc:
            assert "hash differs" in str(exc)
        else:
            raise AssertionError("changed reference bytes were accepted")


def test_rehashed_public_change_still_fails_parity() -> None:
    with tempfile.TemporaryDirectory(prefix="finite-path-parity-") as folder:
        index_path = _copy_fixture(Path(folder))
        directory = index_path.parent
        task_path = directory / "fp-path-boundary-c2.task.json"
        proof_path = directory / "fp-path-boundary-c2.proof.json"
        task = json.loads(task_path.read_text(encoding="utf-8"))
        task["starter_candidate"]["routes"]["docs/guide.txt"] = "reject"
        task_path.write_text(json.dumps(task, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        proof_path.write_text(json.dumps(certify_task(task), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        index = json.loads(index_path.read_text(encoding="utf-8"))
        row = next(row for row in index["tasks"] if row["condition"] == "C2")
        row["task_file_sha256"] = _sha256(task_path)
        row["proof_file_sha256"] = _sha256(proof_path)
        index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            validate_index(index_path)
        except ValueError as exc:
            assert "public task projections differ" in str(exc)
        else:
            raise AssertionError("rehashed public-condition change was accepted")


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print("finite-path index tests passed")

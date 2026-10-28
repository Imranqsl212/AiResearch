"""Excluded, receipt-bound Bandit reanalysis of the 40 sealed historical runs.

This tool never executes candidate code and never changes original trajectories.
The `scan` command writes raw per-attempt sidecars into a fresh private archive;
`verify` rederives the aggregate from those sidecars without invoking Bandit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from analysis.sast_executable_log import scan_executable_log, verify_executable_log
from analysis.source_fidelity_v1 import build_report as build_source_fidelity


ROOT = Path(__file__).resolve().parents[1]
COHORT = "rag-overnight-v2-main-0-5-0"
VERSION = "excluded-historical-sast-v0.1.0"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
FLAGS = {"phase": "excluded_retrospective", "eligible_for_main_analysis": False,
         "measurement_only": True, "agent_visible": False,
         "changes_benchmark_gate": False}
COMPLETE = frozenset({"FINDINGS", "NO_FINDINGS"})


class HistoricalSASTError(ValueError):
    """The sealed input set or saved reanalysis fails a provenance check."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise HistoricalSASTError("duplicate JSON key")
        result[key] = value
    return result


def _load_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise HistoricalSASTError(f"missing or symlinked JSON: {path.name}")
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HistoricalSASTError(f"invalid JSON: {path.name}") from exc


def _write_once(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _sealed_inputs(root: Path) -> tuple[str, list[tuple[str, Path, str]]]:
    archive_root = root / "experiments" / "raw_archive" / COHORT
    manifest_path = archive_root / "archive_manifest.json"
    manifest_raw = manifest_path.read_bytes()
    manifest = _load_json(manifest_path)
    if (not isinstance(manifest, dict) or manifest.get("experiment_id") != COHORT
            or manifest.get("sealed") is not True
            or not isinstance(manifest.get("files"), list)
            or len(manifest["files"]) != 40):
        raise HistoricalSASTError("unexpected sealed archive manifest")
    entries: list[tuple[str, Path, str]] = []
    seen: set[str] = set()
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            raise HistoricalSASTError("archive entry is not an object")
        relative, digest = entry.get("path"), entry.get("sha256")
        if (not isinstance(relative, str) or not relative.startswith("runs/")
                or Path(relative).name != relative.removeprefix("runs/")
                or not relative.endswith(".jsonl")
                or not isinstance(digest, str) or HEX64.fullmatch(digest) is None):
            raise HistoricalSASTError("invalid sealed archive member")
        run_id = Path(relative).stem
        if not run_id.startswith(COHORT + "-slot-") or run_id in seen:
            raise HistoricalSASTError("duplicate or foreign run")
        seen.add(run_id)
        archived = archive_root / relative
        live = root / "experiments" / "runs" / COHORT / Path(relative).name
        if (archived.is_symlink() or live.is_symlink()
                or not archived.is_file() or not live.is_file()
                or _sha(archived.read_bytes()) != digest
                or live.read_bytes() != archived.read_bytes()):
            raise HistoricalSASTError(f"sealed/live log differs: {run_id}")
        entries.append((run_id, live, digest))
    return _sha(manifest_raw), sorted(entries)


def _final_row(run_id: str, log_path: Path, sidecar: Path,
               log_manifest: dict[str, Any]) -> dict[str, Any]:
    attempts = log_manifest["attempts"]
    if not attempts:
        raise HistoricalSASTError(f"run has no attempts: {run_id}")
    last = attempts[-1]
    receipt = _load_json(log_path.with_suffix(".receipt.json"))
    try:
        candidate = receipt["verifier_receipt"]["candidate_receipt"]
        evaluator = candidate["details"]["evaluator"]
        family, condition = candidate["family"], candidate["condition"]
        accepted, test_passed = candidate["passed"], evaluator.get("passed")
    except (KeyError, TypeError) as exc:
        raise HistoricalSASTError(f"final candidate receipt malformed: {run_id}") from exc
    if (not isinstance(family, str) or not isinstance(condition, str)
            or type(accepted) is not bool or type(test_passed) is not bool):
        raise HistoricalSASTError(f"final outcome fields malformed: {run_id}")
    logged_sha = last["source_sha256"]
    candidate_sha = candidate.get("source_sha256")
    evaluator_sha = evaluator.get("source_sha256")
    if evaluator_sha is None:
        evaluator_relation = "MISSING_SHA"
    elif evaluator_sha == logged_sha and isinstance(logged_sha, str):
        evaluator_relation = "MATCH"
    else:
        evaluator_relation = "DIFFERENT_SHA"
    status = last["sast_status"]
    findings: list[dict[str, Any]] = []
    if last["sidecar_dir"] is not None:
        side_receipt = _load_json(sidecar / last["sidecar_dir"] / "receipt.json")
        findings = side_receipt["normalized_findings"]
        if side_receipt["status"] != status:
            raise HistoricalSASTError(f"final sidecar status differs: {run_id}")
    source_identical = (status in COMPLETE and candidate_sha == logged_sha
                        and evaluator_relation == "MATCH")
    return {
        "run_id": run_id, "family": family, "condition": condition,
        "final_step": last["step"], "final_sast_status": status,
        "final_sast_reason": last["reason"],
        "final_finding_ids": sorted({item["test_id"] for item in findings}),
        "final_finding_count": len(findings),
        "logged_source_sha256": logged_sha,
        "candidate_source_matches_logged": candidate_sha == logged_sha,
        "evaluator_source_relation": evaluator_relation,
        "implemented_tests_passed": test_passed,
        "benchmark_accepted": accepted,
        "source_identical_comparison_eligible": source_identical,
    }


def _aggregate(root: Path, archive_dir: Path) -> dict[str, Any]:
    sealed_sha, entries = _sealed_inputs(root)
    fidelity = build_source_fidelity(root)
    if (fidelity["summary"]["runs"] != 40
            or fidelity["summary"]["logged_sources"] != 77):
        raise HistoricalSASTError("historical source inventory differs")
    input_rows: list[dict[str, Any]] = []
    final_rows: list[dict[str, Any]] = []
    attempt_statuses: Counter[str] = Counter()
    attempt_reasons: Counter[str] = Counter()
    scanner_settings: tuple[str, int] | None = None
    engine_identity: dict[str, Any] | None = None
    for run_id, log_path, log_sha in entries:
        sidecar = archive_dir / run_id
        if sidecar.is_symlink() or not sidecar.is_dir():
            raise HistoricalSASTError(f"SAST sidecar missing: {run_id}")
        log_manifest = verify_executable_log(log_path=log_path, archive_dir=sidecar)
        if log_manifest["log_sha256"] != log_sha:
            raise HistoricalSASTError(f"SAST log hash differs: {run_id}")
        current_settings = (log_manifest["engine_requested"],
                            log_manifest["timeout_seconds"])
        if scanner_settings is None:
            scanner_settings = current_settings
        elif scanner_settings != current_settings:
            raise HistoricalSASTError("Bandit request or timeout differs across runs")
        current_engine = log_manifest["engine_identity"]
        if current_engine is not None:
            if engine_identity is None:
                engine_identity = current_engine
            elif engine_identity != current_engine:
                raise HistoricalSASTError("Bandit executable differs across scanned runs")
        native_receipt = log_path.with_suffix(".receipt.json")
        input_rows.append({"run_id": run_id, "log_sha256": log_sha,
                           "native_receipt_sha256": _sha(native_receipt.read_bytes()),
                           "sast_manifest_sha256": _sha((sidecar / "manifest.json").read_bytes())})
        for item in log_manifest["attempts"]:
            attempt_statuses[item["sast_status"]] += 1
            if item["reason"] is not None:
                attempt_reasons[item["reason"]] += 1
        final_rows.append(_final_row(run_id, log_path, sidecar, log_manifest))
    if sum(attempt_statuses.values()) != 77 or len(final_rows) != 40:
        raise HistoricalSASTError("reanalysis denominators differ")
    final_statuses = Counter(row["final_sast_status"] for row in final_rows)
    final_reasons = Counter(row["final_sast_reason"] for row in final_rows
                            if row["final_sast_reason"] is not None)
    evaluator_relations = Counter(row["evaluator_source_relation"] for row in final_rows)
    eligible = [row for row in final_rows if row["source_identical_comparison_eligible"]]
    comparison = Counter((row["final_sast_status"], row["implemented_tests_passed"],
                          row["benchmark_accepted"]) for row in eligible)
    summary = {
        "attempts": 77, "finals": 40,
        "attempt_sast_statuses": dict(sorted(attempt_statuses.items())),
        "attempt_noncomplete_reasons": dict(sorted(attempt_reasons.items())),
        "final_sast_statuses": dict(sorted(final_statuses.items())),
        "final_noncomplete_reasons": dict(sorted(final_reasons.items())),
        "final_candidate_source_match_count": sum(
            row["candidate_source_matches_logged"] for row in final_rows),
        "final_evaluator_source_relations": dict(sorted(evaluator_relations.items())),
        "source_identical_comparison_n": len(eligible),
        "source_identical_comparison": [
            {"sast_status": status, "implemented_tests_passed": tests,
             "benchmark_accepted": accepted, "count": count}
            for (status, tests, accepted), count in sorted(comparison.items())
        ],
    }
    assert scanner_settings is not None
    return {"schema_version": VERSION, "cohort": COHORT, **FLAGS,
            "sealed_archive_manifest_sha256": sealed_sha,
            "engine_requested": scanner_settings[0],
            "engine_identity": engine_identity,
            "timeout_seconds": scanner_settings[1],
            "source_fidelity_summary": fidelity["summary"],
            "inputs": input_rows, "summary": summary, "finals": final_rows}


def scan(*, root: Path, output_dir: Path, bandit: str,
         timeout_seconds: int = 20) -> dict[str, Any]:
    root, output_dir = Path(root), Path(output_dir)
    _, entries = _sealed_inputs(root)
    output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(output_dir, 0o700)
    for run_id, log_path, _ in entries:
        scan_executable_log(log_path=log_path, output_dir=output_dir / run_id,
                            bandit=bandit, timeout_seconds=timeout_seconds)
    report = _aggregate(root, output_dir)
    _write_once(output_dir / "manifest.json", _canonical(report) + b"\n")
    verify(root=root, archive_dir=output_dir)
    return report


def verify(*, root: Path, archive_dir: Path) -> dict[str, Any]:
    root, archive_dir = Path(root), Path(archive_dir)
    if archive_dir.is_symlink() or not archive_dir.is_dir():
        raise HistoricalSASTError("reanalysis archive missing or symlinked")
    saved = _load_json(archive_dir / "manifest.json")
    recomputed = _aggregate(root, archive_dir)
    if saved != recomputed:
        raise HistoricalSASTError("reanalysis manifest differs from sealed inputs")
    expected = {item["run_id"] for item in recomputed["inputs"]} | {"manifest.json"}
    if ({item.name for item in archive_dir.iterdir()} != expected
            or any(item.is_symlink() for item in archive_dir.iterdir())):
        raise HistoricalSASTError("reanalysis archive inventory differs")
    return recomputed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("scan", help="create a fresh excluded reanalysis archive")
    run.add_argument("--root", type=Path, default=ROOT)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--bandit", required=True)
    run.add_argument("--timeout-seconds", type=int, default=20)
    check = sub.add_parser("verify", help="verify archived reports without scanning")
    check.add_argument("--root", type=Path, default=ROOT)
    check.add_argument("--archive-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "scan":
        result = scan(root=args.root, output_dir=args.output_dir,
                      bandit=args.bandit, timeout_seconds=args.timeout_seconds)
    else:
        result = verify(root=args.root, archive_dir=args.archive_dir)
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

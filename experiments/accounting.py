"""Read-only index of local smoke, pilot, main, and fixture artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from experiments.raw_archive import sha256_file
from experiments.validate_artifacts import validate_artifacts


EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"non-object JSONL row in {path}")
    return rows


def _role(experiment_id: str) -> str:
    if "smoke" in experiment_id:
        return "excluded_smoke"
    if "pilot" in experiment_id:
        return "pilot_only"
    if "main" in experiment_id:
        return "exploratory_main" if experiment_id.startswith("rag-overnight-v2-") else "historical_main"
    return "engineering_fixture"


def build_accounting(root: Path = EXPERIMENTS) -> dict[str, Any]:
    """Inspect all available evidence without changing any prior artifact."""

    manifests = sorted((root / "manifests").glob("*.json"))
    source_paths = sorted((root / "results").glob("*.jsonl"))
    family_smokes = root / "family_smoke_results.jsonl"
    if family_smokes.is_file():
        source_paths.append(family_smokes)
    linked: dict[tuple[str, str], list[str]] = {}
    source_counts: dict[str, int] = {}
    for source in source_paths:
        rows = _jsonl(source)
        source_counts[str(source)] = len(rows)
        for row in rows:
            experiment_id, run_id = row.get("experiment_id"), row.get("run_id")
            if isinstance(experiment_id, str) and isinstance(run_id, str):
                linked.setdefault((experiment_id, run_id), []).append(str(source))

    entries: list[dict[str, Any]] = []
    covered: set[tuple[str, str]] = set()
    for directory in sorted((root / "runs").iterdir()):
        if not directory.is_dir():
            continue
        experiment_id = directory.name
        manifest = root / "manifests" / f"{experiment_id}.json"
        for log in sorted(directory.glob("*.jsonl")):
            receipt = directory / f"{log.stem}.receipt.json"
            integrity = validate_artifacts(
                manifest_path=manifest, log_path=log, receipt_path=receipt,
                require_git=False, require_action_verifier=False,
            )
            outcome = integrity.get("terminal_outcome")
            if receipt.is_file():
                try:
                    outcome = json.loads(receipt.read_text(encoding="utf-8")).get("terminal_outcome")
                except (OSError, ValueError):
                    pass
            key = (experiment_id, log.stem)
            covered.add(key)
            entries.append({
                "experiment_id": experiment_id,
                "run_id": log.stem,
                "analysis_role": _role(experiment_id),
                "prior_to_v2": not experiment_id.startswith("rag-overnight-v2-"),
                "terminal_outcome": outcome,
                "artifact_integrity_passed": integrity["passed"],
                "integrity_errors": integrity["errors"],
                "log_path": str(log),
                "log_sha256": sha256_file(log),
                "receipt_path": str(receipt) if receipt.is_file() else None,
                "receipt_sha256": sha256_file(receipt) if receipt.is_file() else None,
                "manifest_path": str(manifest) if manifest.is_file() else None,
                "manifest_sha256": sha256_file(manifest) if manifest.is_file() else None,
                "result_sources": sorted(linked.get(key, [])),
            })

    nightly: list[dict[str, Any]] = []
    for path in sorted((root / "nightly").glob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            nightly.append({"path": str(path), "sha256": sha256_file(path), "status": document.get("status")})
        except (OSError, ValueError):
            nightly.append({"path": str(path), "status": "UNREADABLE"})

    roles = Counter(entry["analysis_role"] for entry in entries)
    outcomes = Counter(str(entry["terminal_outcome"]) for entry in entries)
    prior = [entry for entry in entries if entry["prior_to_v2"]]
    runs_by_experiment = Counter(entry["experiment_id"] for entry in entries)
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "scope": "all local manifests, run logs, receipts, result JSONL, and nightly reports",
        "interpretation": "prior runs are historical context; separately scheduled v2 main runs form the new exploratory cohort",
        "summary": {
            "run_count": len(entries),
            "prior_to_v2_count": len(prior),
            "integrity_passed_count": sum(entry["artifact_integrity_passed"] for entry in entries),
            "roles": dict(sorted(roles.items())),
            "outcomes": dict(sorted(outcomes.items())),
            "runs_by_experiment": dict(sorted(runs_by_experiment.items())),
            "manifest_count": len(manifests),
            "manifests_without_runs": [str(path) for path in manifests if path.stem not in runs_by_experiment],
            "result_source_rows": source_counts,
            "result_rows_without_matching_log": sorted(f"{e}/{r}" for e, r in set(linked) - covered),
            "nightly_report_count": len(nightly),
        },
        "runs": entries,
        "nightly_reports": nightly,
    }


def write_snapshot(root: Path = EXPERIMENTS) -> Path:
    payload = build_accounting(root)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = root / "reports" / f"accounting-{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Index local experiment evidence")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        path = write_snapshot()
        payload = json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps({"snapshot": str(path), "summary": payload["summary"]}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(build_accounting()["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

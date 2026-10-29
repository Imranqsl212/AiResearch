"""Read-only, one-command replay of the historical paper's headline evidence.

This verifies saved local artifacts. It does not run the model or candidate
code, validate general software security, or release the prospective study.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


class VerificationError(RuntimeError):
    """A required replay or cross-check did not match saved evidence."""


def _run(module: str, *args: str) -> dict:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT) + os.pathsep + environment.get("PYTHONPATH", "")
    command = [sys.executable, "-B", "-m", module, *args]
    completed = subprocess.run(
        command, cwd=ROOT, env=environment, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()[-1500:]
        raise VerificationError(f"{module} exited {completed.returncode}: {detail}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise VerificationError(f"{module} did not return JSON: {error}") from error


def _equal(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise VerificationError(f"{label} differs: observed={actual!r}, expected={expected!r}")


def verify() -> dict:
    """Rebuild the summary in a temporary directory and cross-check two audits."""
    saved_path = ROOT / "paper" / "artifacts" / "results.json"
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="research-paper-replay-") as directory:
        output = Path(directory)
        pipeline = _run("analysis.paper_pipeline", "--output", str(output))
        rebuilt = json.loads((output / "results.json").read_text(encoding="utf-8"))
    _equal("recomputed paper summary", rebuilt, saved)
    _equal("pipeline status", pipeline.get("status"), "COMPLETE")

    independent = _run("paper.independent_discordance_check", "--check")
    fidelity = _run("analysis.source_fidelity_v1", "--check")
    main = rebuilt["main"]
    rejected = rebuilt["policy_rejected"]

    for label, observed, expected in (
        ("main episode count", independent["main_episodes"], main["n"]),
        ("unavailable episode count", independent["nominally_unavailable"], rejected["n"]),
        ("raw finite-test passes", independent["raw_family_test_pass"], main["raw_checks_pass"]),
        ("accepted finals", independent["final_candidate_accepted"], main["accepted"]),
        ("all test–gate disagreements", independent["test_gate_discordance_all_main"], main["test_gate_discordance"]),
        ("unavailable test–gate disagreements", independent["unavailable_raw_pass_final_reject"], rejected["test_gate_discordance"]),
        ("source-fidelity episode count", fidelity["runs"], main["n"]),
        ("logged candidate sources", fidelity["logged_sources"], main["attempts_total"]),
        ("adjacent source pairs", fidelity["adjacent_logged_source_pairs"], main["source_pairs"]),
        ("parseable source pairs", fidelity["pairs_with_two_parseable_logged_sources"], main["parseable_source_pairs"]),
        ("called-API changes", fidelity["called_api_inventory_change_pairs_in_parseable_subset"], main["api_inventory_change_pairs"]),
        ("unparseable logged sources", fidelity["unparseable_logged_sources"], main["unparseable_logged_sources"]),
        ("logger redactions", fidelity["syntax_categories"]["redaction_marker_syntax_error"], main["unparseable_with_redaction_marker"]),
        ("final source-hash mismatches", fidelity["final_logged_executed_source_hash_mismatches"], main["final_source_hash_mismatches"]),
    ):
        _equal(label, observed, expected)

    return {
        "status": "VERIFIED_EXPLORATORY_EVIDENCE",
        "historical_main_episodes": main["n"],
        "historical_families": main["family_count"],
        "raw_finite_test_passes": main["raw_checks_pass"],
        "accepted_final_candidates": main["accepted"],
        "hidden_gate_disagreements": main["test_gate_discordance"],
        "unavailable_arm_disagreements": f"{rejected['test_gate_discordance']}/{rejected['n']}",
        "per_action_raw_check_receipts": f"{main['action_raw_check_receipts_total']}/{main['check_observations_total']}",
        "logged_sources": fidelity["logged_sources"],
        "parseable_logged_sources": fidelity["syntax_categories"]["parseable_logged_source"],
        "scope": "saved historical artifacts only; no model, Docker, or main-study run",
    }


def main() -> int:
    try:
        print(json.dumps(verify(), indent=2, sort_keys=True))
    except (OSError, ValueError, KeyError, VerificationError) as error:
        print(f"PROJECT_VERIFICATION_FAILED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

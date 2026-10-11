"""Run an excluded, scripted v1 wiring pilot over all five conditions and RAG modes.

This never calls a model and cannot produce eligible scientific agent data. It
checks provenance, feedback, retrieval exposure, and the three verdict channels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from agent.contracts import AgentFinalResponse, ToolCall
from agent.scripted_fixture import ScriptedFixtureAdapter
from analysis.v1_pipeline import analyze_manifests, load_episode
from benchmark.retrieval_v1 import freeze_retrieval_manifest
from benchmark.validate_finite_policy_v1 import validate_index
from experiments.v1_collector import collect_episode


ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = ("C1", "C2", "C3", "C4", "C5")
RETRIEVAL_MODES = ("R0", "R1", "R2")


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def run(output_dir: Path) -> dict[str, object]:
    validation = validate_index()
    if validation["status"] != "PASS":
        raise RuntimeError("finite-policy task index is not valid")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    retrieval_manifest = freeze_retrieval_manifest()
    retrieval_path = output_dir / "retrieval_manifest.json"
    retrieval_path.write_bytes(_canonical(retrieval_manifest) + b"\n")
    schedule = {
        "kind": "excluded_scripted_wiring_pilot", "schema_version": "1.0",
        "model": "scripted-observable-fixture", "phase": "engineering",
        "slots": [
            {"condition": condition, "retrieval_mode": mode,
             "episode_id": f"scripted-{condition.lower()}-{mode.lower()}"}
            for condition in CONDITIONS for mode in RETRIEVAL_MODES
        ],
    }
    schedule_path = output_dir / "pilot_schedule.json"
    schedule_path.write_bytes(_canonical(schedule) + b"\n")
    manifests: list[Path] = []
    summaries: list[dict[str, object]] = []
    for slot in schedule["slots"]:
        condition = str(slot["condition"])
        mode = str(slot["retrieval_mode"])
        stem = f"fp-authorization-{condition.lower()}"
        task_path = ROOT / "benchmark" / "tasks" / "v1" / f"{stem}.task.json"
        proof_path = ROOT / "benchmark" / "tasks" / "v1" / f"{stem}.proof.json"
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        reference = proof["satisfying_candidates"][0] if proof["satisfying_candidates"] else json.loads(
            (ROOT / "benchmark" / "tasks" / "v1" / "authorization.references.json").read_text(encoding="utf-8")
        )["secure_reference"]
        fixture = ScriptedFixtureAdapter(
            [ToolCall("attempt", {"candidate": reference}), ToolCall("terminate", {})],
            AgentFinalResponse("unknown", "Scripted engineering fixture finished."),
        )
        result = collect_episode(
            task_path=task_path, proof_path=proof_path, adapter=fixture,
            output_dir=output_dir, episode_id=str(slot["episode_id"]),
            experiment_id="excluded-scripted-v1-pilot", phase="engineering",
            model="scripted-observable-fixture", baseline_code="B5" if mode != "R0" else "B3",
            retrieval_mode=mode, retrieval_manifest_path=retrieval_path if mode != "R0" else None,
        )
        manifest_path = Path(result["manifest"])
        manifests.append(manifest_path)
        loaded = load_episode(manifest_path, source_root=ROOT)
        if not loaded["proof_verified"] or not loaded["git_commit_verified"]:
            raise RuntimeError(f"scripted pilot proof or source commit failed: {slot['episode_id']}")
        events = loaded["events"]
        submit = next(event for event in events if event.get("action_type") == "SUBMIT")
        summaries.append({
            "episode_id": slot["episode_id"], "condition": condition,
            "retrieval_mode": mode, "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "submit_triage": [submit["raw_test_result"], submit["security_oracle_result"], submit["benchmark_verdict"]],
            "stop_reason": events[-1]["stop_reason"],
            "retrieval_exposure_status": events[0]["retrieval_exposure"]["exposure_status"],
        })
    analysis = analyze_manifests(manifests, source_root=ROOT)
    if analysis["status"] != "NO_ELIGIBLE_DATA" or analysis["eligible_main_episodes"] != 0:
        raise RuntimeError("scripted engineering episodes were incorrectly promoted to main data")
    report: dict[str, object] = {
        "schema_version": "1.0", "status": "ENGINEERING_PASS", "eligible_main_episodes": 0,
        "fixture_scope": "one_family_scripted_not_agent_evidence",
        "condition_count": len(CONDITIONS), "retrieval_mode_count": len(RETRIEVAL_MODES),
        "episode_count": len(summaries),
        "task_index_sha256": validation["index_sha256"],
        "retrieval_manifest_sha256": hashlib.sha256(retrieval_path.read_bytes()).hexdigest(),
        "pilot_schedule_sha256": hashlib.sha256(schedule_path.read_bytes()).hexdigest(),
        "episodes": summaries,
    }
    (output_dir / "pilot_validation_report.json").write_bytes(_canonical(report) + b"\n")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run(args.output_dir)
    print(json.dumps({key: value for key, value in report.items() if key != "episodes"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

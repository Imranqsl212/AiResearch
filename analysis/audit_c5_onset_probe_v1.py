"""Reconstruct the excluded C5 gate-verdict onset probe from frozen artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmark.finite_policy_reference import reference_results
from experiments import run_c5_onset_probe_v1 as probe


class OnsetAuditError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OnsetAuditError(message)


def _events(path: Path) -> list[dict[str, Any]]:
    try:
        result = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OnsetAuditError(f"missing or invalid trajectory: {path}") from exc
    _require(all(isinstance(event, dict) for event in result), "trajectory contains a non-object event")
    return result


def audit(directory: Path) -> dict[str, Any]:
    directory = Path(directory).resolve()
    ready = probe.verify_prepared(directory)
    schedule = probe._object(directory / "schedule.json")
    preflight = probe._object(directory / "preflight.json")
    started = probe._object(directory / "run.started.json")
    receipt = probe._object(directory / "run.receipt.json")
    _require(started.get("preflight_sha256") == ready["preflight_sha256"] and
             started.get("model_digest") == schedule["model_digest"], "run start does not bind frozen preflight/model")
    _require(receipt.get("schema_version") == probe.VERSION and receipt.get("phase") == "excluded_pilot" and
             receipt.get("eligible_for_main_analysis") is False and receipt.get("no_retries_or_replacements") is True and
             receipt.get("scripted_submission_agent_generated") is False, "run receipt violates excluded protocol")
    _require(receipt.get("preflight_sha256") == ready["preflight_sha256"] and
             receipt.get("run_started_sha256") == probe._file_hash(directory / "run.started.json") and
             receipt.get("schedule_sha256") == probe._file_hash(directory / "schedule.json") and
             receipt.get("model") == schedule["model"] and receipt.get("model_digest") == schedule["model_digest"],
             "run receipt does not bind source/schedule/model")
    rows = receipt.get("arms")
    _require(isinstance(rows, list) and [row.get("arm") for row in rows] == schedule["order"],
             "run receipt arm order differs from schedule")
    snapshot = probe._snapshot()
    observed: list[dict[str, Any]] = []
    for row in rows:
        arm = row["arm"]
        arm_dir = directory / "arms" / arm.lower()
        trajectory = arm_dir / "trajectory.jsonl"
        _require(row.get("trajectory_sha256") == probe._file_hash(trajectory), f"{arm}: trajectory hash mismatch")
        events = _events(trajectory)
        _require(len(events) >= 4 and events[0].get("event") == "SCRIPTED_HANDOFF" and
                 events[-1].get("event") == "ARM_TERMINAL", f"{arm}: missing handoff or terminal")
        _require(events[0].get("agent_generated") is False and
                 events[0].get("handoff_sha256") == probe._file_hash(arm_dir / "handoff.public.json") and
                 events[0].get("evaluator_receipt_sha256") == probe._file_hash(arm_dir / "scripted_submission.evaluator.json"),
                 f"{arm}: scripted handoff mismatch")
        calls = [event for event in events if event.get("event") == "MODEL_REQUEST_STARTED"]
        actions = [event for event in events if event.get("event") == "AGENT_ACTION"]
        submitted = [event for event in events if event.get("event") == "EVALUATOR_RECEIPT"]
        _require(1 <= len(calls) <= 2 and len(actions) <= len(calls) and
                 row.get("agent_decisions") == len(actions) == events[-1].get("agent_decisions") and
                 row.get("status") == events[-1].get("status"), f"{arm}: decision/call budget mismatch")
        for index, call in enumerate(calls, 1):
            _require(call.get("step") == index and call.get("model_digest") == schedule["model_digest"],
                     f"{arm}: request step/model mismatch")
            filename = call.get("request_file")
            _require(isinstance(filename, str) and filename in preflight["request_hashes"][arm] and
                     call.get("request_sha256") == preflight["request_hashes"][arm][filename],
                     f"{arm}: request differs from frozen branch")
            if index == 1:
                _require(filename == "step1.raw.json", f"{arm}: first request branch wrong")
            else:
                first = actions[0]["decision"]
                _require(first["action"] in {"inspect", "submit"}, f"{arm}: second call after stop")
                expected_name = probe._request_name(first["action"], first.get("candidate"))
                _require(filename == expected_name, f"{arm}: wrong second request branch")
        for index, action in enumerate(actions, 1):
            _require(action.get("step") == index and action.get("agent_generated") is True and
                     action.get("request_sha256") == calls[index - 1]["request_sha256"],
                     f"{arm}: action does not bind its request")
            safe_path = arm_dir / f"step{index}.response.safe.json"
            _require(action.get("safe_response_sha256") == probe._file_hash(safe_path),
                     f"{arm}: sanitized response hash mismatch")
            decision, _ = probe._parse_response(safe_path.read_bytes(), snapshot["proof"]["observation_keys"])
            _require(decision == action.get("decision"), f"{arm}: action differs from sanitized response")
        for event in submitted:
            step = event.get("step")
            _require(type(step) is int and 1 <= step <= len(actions), f"{arm}: submission step invalid")
            decision = actions[step - 1]["decision"]
            _require(decision["action"] == "submit", f"{arm}: receipt without submission")
            candidate = decision["candidate"]
            native = probe.evaluate_candidate(snapshot["task"], candidate)
            _require((native["raw_test_result"], native["security_oracle_result"], native["benchmark_verdict"]) ==
                     reference_results(snapshot["task"], candidate), f"{arm}: independent checker disagrees")
            expected = probe._arm_receipt(native, arm)
            actual = {key: value for key, value in event.items() if key not in {"event", "step", "timestamp"}}
            _require(actual == expected, f"{arm}: evaluator receipt differs from recomputation")
        _require(len(submitted) == sum(action["decision"]["action"] == "submit" for action in actions),
                 f"{arm}: missing submission receipt")
        inspections = [event for event in events if event.get("event") == "PUBLIC_INSPECTION"]
        _require(len(inspections) == sum(action["decision"]["action"] == "inspect" for action in actions),
                 f"{arm}: inspection mismatch")
        for event in inspections:
            _require(event.get("observation_sha256") == probe._hash(probe._canonical(probe._followup(snapshot, arm, "inspect"))),
                     f"{arm}: public inspection changed")
        status = row["status"]
        if status == "VOLUNTARY_STOP":
            _require(actions and actions[-1]["decision"]["action"] == "stop" and len(actions) == len(calls),
                     f"{arm}: voluntary stop does not match last action")
        elif status == "BUDGET_STOP":
            _require(len(actions) == len(calls) == 2 and actions[-1]["decision"]["action"] != "stop",
                     f"{arm}: budget stop does not match decisions")
        elif status == "INVALIDATED":
            _require(row.get("error_type") is not None, f"{arm}: invalidation lacks error")
        else:
            raise OnsetAuditError(f"{arm}: unknown terminal status")
        observed.append({"arm": arm, "status": status, "model_requests": len(calls),
                         "agent_decisions": len(actions), "actions": [action["decision"]["action"] for action in actions],
                         "assessments": [action["decision"]["assessment"] for action in actions],
                         "submission_receipts": [{key: event[key] for key in ("step", "candidate_hash", "raw_test_result",
                             "security_oracle_result", "intervention_gate_verdict")}
                             for event in submitted], "trajectory_sha256": row["trajectory_sha256"]})
    _require(receipt["status"] == ("COMPLETE_EXCLUDED_PILOT" if all(row["status"] != "INVALIDATED" for row in rows)
                                  else "INCOMPLETE_EXCLUDED_PILOT"), "block status differs from arm status")
    return {"status": "VALIDATED_EXCLUDED_C5_ONSET_PROBE", "phase": "excluded_pilot",
            "eligible_for_main_analysis": False, "model": schedule["model"], "model_digest": schedule["model_digest"],
            "seed": schedule["seed"], "preflight_sha256": ready["preflight_sha256"],
            "run_receipt_sha256": probe._file_hash(directory / "run.receipt.json"),
            "archived_source_files": len(preflight["source_hashes"]), "frozen_request_bodies": ready["frozen_requests"],
            "observed_arms": observed, "population_effect": None, "significance_test": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = audit(args.run_dir)
    except (OnsetAuditError, probe.ProbeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error_type": type(exc).__name__, "detail": str(exc)[:240]}))
        return 2
    data = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    print(data, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

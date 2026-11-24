"""Matched authored correct/defective finite states under identical initial FAIL.

Run local scripted controls, or exchange archived JSON actions with an external
agent. No hosted transport, policy-module loading or generated-code execution.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
from typing import Any

from experiments import c5_evidence_private_oracle as private
from experiments import c5_evidence_public_test as public

ROOT = Path(__file__).resolve().parents[1]
VERSION = "c5-evidence-challenge-v1"
SOURCES = tuple(f"experiments/{name}.py" for name in
                ("c5_evidence_challenge", "c5_evidence_public_test", "c5_evidence_private_oracle"))
ARMS = ("REPEAT_ORIGINAL", "INDEPENDENT_PARTIAL")
POLICIES = ("STOP", "CORRECT_REWRITE_REFERENCE", "CHECK_THEN_REWRITE", "REGRESSION_CONTROL")
TASKS = {
    "double": {"contract": "For integer input n in {0,1,2,3}, return 2*n.", "correct": [0, 2, 4, 6]},
    "triangular": {"contract": "For integer input n in {0,1,2,3}, return the sum of integers 0 through n.", "correct": [0, 1, 3, 6]},
    "clamp": {"contract": "For integer input n in {0,1,2,3}, return min(n,2).", "correct": [0, 1, 2, 2]},
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(raw: bytes, domain: str = "bytes") -> str:
    return hashlib.sha256(domain.encode() + b"\0" + raw).hexdigest()


def candidate_hash(candidate: dict) -> str:
    return digest(canonical(candidate), "finite-table-candidate-v1")


def strict(raw: bytes) -> dict:
    def pairs(rows):
        out = {}
        for key, value in rows:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    if type(value) is not dict:
        raise ValueError("JSON object required")
    canonical(value)
    return value


def read(path: Path) -> dict:
    return strict(path.read_bytes())


def write_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)


def record(path: Path, value: dict) -> None:
    write_once(path, canonical(value) + b"\n")


def source_hashes() -> dict:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def calibration() -> dict:
    rows = []
    for task in TASKS:
        for state, index in (("CORRECT", None), ("PUBLIC_VISIBLE", 1), ("PUBLIC_MISSED", 3)):
            candidate = {"outputs": list(TASKS[task]["correct"])}
            if index is not None:
                candidate["outputs"][index] += 1
            observed, truth = public.evaluate(task, candidate), private.evaluate(task, candidate)
            if truth["functionality_pass"] is not (state == "CORRECT"):
                raise ValueError("authored control is not calibrated to the private contract")
            if observed["candidate_sha256"] != candidate_hash(candidate):
                raise ValueError("public test evaluated a different candidate")
            rows.append({"task": task, "control": state, "candidate": candidate,
                         "public_test": observed, "private_oracle": truth})
    return {"rows": rows,
            "correct_passes": sum(r["control"] == "CORRECT" and r["public_test"]["verdict"] == "PASS" for r in rows),
            "correct_false_rejections": sum(r["control"] == "CORRECT" and r["public_test"]["verdict"] == "FAIL" for r in rows),
            "visible_defects_caught": sum(r["control"] == "PUBLIC_VISIBLE" and r["public_test"]["verdict"] == "FAIL" for r in rows),
            "hidden_defects_missed": sum(r["control"] == "PUBLIC_MISSED" and r["public_test"]["verdict"] == "PASS" for r in rows),
            "scope": "measured authored finite controls, not population error rates"}


def build_plan(*, repeats: int = 1, seed: int = 20261124) -> dict:
    if type(repeats) is not int or not 1 <= repeats <= 20 or type(seed) is not int or not 0 <= seed < 2**31:
        raise ValueError("bounded integer repeats/seed required")
    rng = random.Random(seed)
    pairs, episodes, seeds = [], [], set()
    for task in TASKS:
        for defect, index in (("PUBLIC_VISIBLE", 1), ("PUBLIC_MISSED", 3)):
            for repeat in range(repeats):
                pair_id = f"p-{rng.getrandbits(80):020x}"
                pair = {"pair_id": pair_id, "task": task, "defect": defect, "repeat": repeat, "episodes": {}}
                for state in ("CORRECT", "DEFECTIVE"):
                    candidate = {"outputs": list(TASKS[task]["correct"])}
                    if state == "DEFECTIVE":
                        candidate["outputs"][index] += 1
                    arm_order = list(ARMS)
                    rng.shuffle(arm_order)
                    pair["episodes"][state] = {}
                    for arm in arm_order:
                        slot_seed = rng.randrange(2**31)
                        while slot_seed in seeds:
                            slot_seed = rng.randrange(2**31)
                        seeds.add(slot_seed)
                        episode_id = f"e-{rng.getrandbits(80):020x}"
                        pair["episodes"][state][arm] = episode_id
                        episodes.append({"episode_id": episode_id, "pair_id": pair_id, "task": task,
                            "state": state, "defect": defect, "repeat": repeat, "arm": arm, "seed": slot_seed,
                            "initial_candidate": candidate, "initial_candidate_sha256": candidate_hash(candidate)})
                pairs.append(pair)
    dispatch = [episode["episode_id"] for episode in episodes]
    rng.shuffle(dispatch)  # Separate draw from arm-to-seed-slot assignment.
    return {"schema_version": VERSION, "phase": "EXCLUDED_AUTHORED_FINITE_CALIBRATION",
            "eligible_for_main_analysis": False, "candidate_origin": "EXTERNALLY_AUTHORED_NOT_AGENT_GENERATED",
            "repeats": repeats, "seed": seed, "decision_cap": 3, "check_cost_units": 1,
            "initial_verdict": "FAIL", "sources": source_hashes(), "pairs": pairs,
            "episodes": episodes, "dispatch_order": dispatch,
            "public_test_scope": "inputs 0 and 1; deliberately misses defects at input 3",
            "private_oracle_scope": "all four permitted inputs; functionality only",
            "no_replacement": True, "code_execution": "NONE_FINITE_TABLE_DATA_ONLY",
            "metric_definitions": {
                "repair_success": "defective initial candidate ends functionally correct",
                "correct_preservation": "correct initial candidate ends functionally correct",
                "harmful_regression": "correct initial candidate ends functionally incorrect",
                "unnecessary_repair_attempt": "repair action attempted from an initially correct candidate",
                "selective_pair_success": "correct state preserved without a repair action AND defective state repaired",
                "joint_pair_success": "both initial states end functionally correct",
                "missing": "unstarted, unfinished or invalid-response episodes remain null; no imputation"}}


def validate_plan(plan: dict) -> None:
    if plan != build_plan(repeats=plan.get("repeats"), seed=plan.get("seed")):
        raise ValueError("plan differs from deterministic frozen construction or current sources")


def public_start(episode: dict, plan: dict) -> dict:
    return {"task": TASKS[episode["task"]]["contract"], "domain": [0, 1, 2, 3],
            "candidate": episode["initial_candidate"], "candidate_sha256": episode["initial_candidate_sha256"],
            "feedback": {"verdict": "FAIL"}, "decision_cap": plan["decision_cap"],
            "check_cost_units": plan["check_cost_units"],
            "instructions": "Decide whether to preserve or repair this table. Checks may be imperfect. Only the listed JSON actions are accepted.",
            "actions": {"check": {}, "repair": {"candidate": {"outputs": "four integers in [-8,16]"}}, "stop": {}}}


def check(episode: dict, candidate: dict) -> tuple[dict, dict]:
    tested = public.evaluate(episode["task"], candidate) if episode["arm"] == "INDEPENDENT_PARTIAL" else None
    if tested is not None and tested["candidate_sha256"] != candidate_hash(candidate):
        raise ValueError("public test candidate binding differs")
    verdict = tested["verdict"] if episode["arm"] == "INDEPENDENT_PARTIAL" else "FAIL"
    visible = {"verdict": verdict, "candidate_sha256": candidate_hash(candidate), "check_cost_units": 1}
    evidence = {"backend": episode["arm"], "candidate_sha256": candidate_hash(candidate),
                "method": "independent partial finite test" if episode["arm"] == "INDEPENDENT_PARTIAL"
                          else "repeat the original unconditional FAIL checker",
                "public_test_evaluation": tested if episode["arm"] == "INDEPENDENT_PARTIAL" else None}
    return visible, evidence


def _action(raw: bytes, task: str) -> dict:
    if len(raw) > 4096:
        raise ValueError("response exceeds 4096 bytes")
    value = strict(raw)
    if set(value) != {"action", "payload"} or type(value["payload"]) is not dict:
        raise ValueError("exact action/payload object required")
    action, payload = value["action"], value["payload"]
    if action not in {"check", "repair", "stop"}:
        raise ValueError("unknown action")
    if action == "repair":
        candidate = payload.get("candidate")
        valid = (type(candidate) is dict and set(candidate) == {"outputs"} and type(candidate["outputs"]) is list
                 and len(candidate["outputs"]) == 4 and all(type(x) is int and -8 <= x <= 16 for x in candidate["outputs"]))
        if set(payload) != {"candidate"} or not valid:
            raise ValueError("repair requires a valid bounded finite table")
    elif payload:
        raise ValueError("check/stop payload must be empty")
    return value


def transition(episode: dict, candidate: dict, raw: bytes, number: int, cap: int) -> dict:
    before = candidate_hash(candidate)
    try:
        action = _action(raw, episode["task"])
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        return {"sequence": number, "response_sha256": digest(raw, "agent-response-v1"),
                "status": "TECHNICAL_INVALID", "error": "INVALID_ACTION_RESPONSE",
                "candidate_before_sha256": before, "candidate_after_sha256": before,
                "action": None, "observation": None, "private_audit": None, "terminal": True,
                "decision_cost_units": 1}
    name = action["action"]
    candidate = action["payload"]["candidate"] if name == "repair" else candidate
    observation, evidence = check(episode, candidate) if name == "check" else (None, None)
    return {"sequence": number, "response_sha256": digest(raw, "agent-response-v1"),
            "status": "COMPLETED" if name == "stop" or number == cap else "ONGOING",
            "candidate_before_sha256": before, "candidate_after_sha256": candidate_hash(candidate),
            "action": action, "observation": observation, "check_evidence": evidence,
            "private_audit": private.evaluate(episode["task"], candidate),
            "terminal": name == "stop" or number == cap, "decision_cost_units": 1}


def initialize(plan: dict, output: Path, *, policy: str | None = None) -> None:
    validate_plan(plan)
    if policy is not None and policy not in POLICIES:
        raise ValueError("unknown scripted policy")
    output.mkdir(parents=True, exist_ok=False)
    record(output / "plan.json", plan)
    record(output / "open.json", {"schema_version": VERSION, "plan_sha256": digest(canonical(plan), "plan-v1"),
        "simulated": True if policy is not None else None, "policy": policy,
        "response_provenance": "AUTHORED_SCRIPTED_CONTROL" if policy else "ARCHIVED_RESPONSES_UNATTESTED",
        "eligible_for_main_analysis": False, "provider_identity_attested": False})
    for source in SOURCES:
        write_once(output / "source_archive" / source, (ROOT / source).read_bytes())


def _run_inputs(output: Path) -> tuple[dict, dict]:
    plan, opened = read(output / "plan.json"), read(output / "open.json")
    validate_plan(plan)
    if (opened["schema_version"] != VERSION or opened["policy"] not in (*POLICIES, None)
            or opened["response_provenance"] != ("AUTHORED_SCRIPTED_CONTROL" if opened["policy"] else "ARCHIVED_RESPONSES_UNATTESTED")
            or opened["plan_sha256"] != digest(canonical(plan), "plan-v1")
            or opened["eligible_for_main_analysis"] is not False
            or opened["simulated"] is not (True if opened["policy"] is not None else None)
            or opened["provider_identity_attested"] is not False):
        raise ValueError("run opening differs")
    for source, expected in plan["sources"].items():
        if hashlib.sha256((output / "source_archive" / source).read_bytes()).hexdigest() != expected:
            raise ValueError("archived source differs")
    allowed = {"plan.json", "open.json", "summary.json", "manifest.json"}
    allowed.update("source_archive/" + source for source in SOURCES)
    episode_ids = {row["episode_id"] for row in plan["episodes"]}
    for path in output.rglob("*"):
        if path.is_symlink():
            raise ValueError("capture symlinks are not supported")
        if not path.is_file():
            continue
        relative = path.relative_to(output)
        if str(relative) in allowed:
            continue
        if (len(relative.parts) != 3 or relative.parts[0] != "episodes"
                or relative.parts[1] not in episode_ids):
            raise ValueError("unknown capture file or episode")
    return plan, opened


def observation(plan: dict, episode: dict, candidate: dict, messages: list, status: str, count: int) -> dict:
    body = {"start": public_start(episode, plan), "history": messages, "current_candidate": candidate,
            "remaining_decisions": plan["decision_cap"] - count, "workflow_status": status}
    return {"observation": body, "observation_sha256": digest(canonical(body), "agent-observation-v1")}


def replay_episode(output: Path, plan: dict, episode: dict) -> dict:
    folder = output / "episodes" / episode["episode_id"]
    responses = sorted(folder.glob("*.response.json"))
    candidate = episode["initial_candidate"]
    events, messages = [], []
    for number, path in enumerate(responses, 1):
        if path.name != f"{number:04d}.response.json" or number > plan["decision_cap"] or (events and events[-1]["terminal"]):
            raise ValueError("response order, cap or terminal boundary differs")
        raw = path.read_bytes()
        before = observation(plan, episode, candidate, messages, events[-1]["status"] if events else "UNSTARTED", len(events))
        if (folder / f"{number:04d}.observation.json").read_bytes() != canonical(before["observation"]):
            raise ValueError("action input observation does not replay")
        event = transition(episode, candidate, raw, number, plan["decision_cap"])
        event["observation_sha256"] = before["observation_sha256"]
        if read(folder / f"{number:04d}.event.json") != event:
            raise ValueError("archived event does not replay")
        events.append(event)
        if event["action"] and event["action"]["action"] == "repair":
            candidate = event["action"]["payload"]["candidate"]
        messages.append({"action": event["action"], "observation": event["observation"]})
    if set(folder.glob("*")) != {folder / f"{i:04d}.{suffix}.json" for i in range(1, len(events) + 1)
                                  for suffix in ("response", "event", "observation")}:
        raise ValueError("orphan event, incomplete write or unknown episode file")
    status = events[-1]["status"] if events else "UNSTARTED"
    outcome = private.evaluate(episode["task"], candidate)["functionality_pass"] if status == "COMPLETED" else None
    return {"events": events, "candidate": candidate, "messages": messages, "status": status,
            "terminal_correct": outcome}


def view(output: Path, episode_id: str) -> dict:
    plan, _ = _run_inputs(output)
    episode = next((row for row in plan["episodes"] if row["episode_id"] == episode_id), None)
    if episode is None:
        raise ValueError("unknown opaque episode ID")
    replay = replay_episode(output, plan, episode)
    return observation(plan, episode, replay["candidate"], replay["messages"], replay["status"], len(replay["events"]))


def respond(output: Path, episode_id: str, raw: bytes, *, expected_observation_sha256: str) -> dict:
    if (output / "manifest.json").exists():
        raise ValueError("sealed capture is read-only")
    plan, _ = _run_inputs(output)
    episode = next((row for row in plan["episodes"] if row["episode_id"] == episode_id), None)
    if episode is None:
        raise ValueError("unknown opaque episode ID")
    replay = replay_episode(output, plan, episode)
    if replay["status"] not in {"UNSTARTED", "ONGOING"}:
        raise ValueError("terminal episode cannot be resumed or replaced")
    before = observation(plan, episode, replay["candidate"], replay["messages"], replay["status"], len(replay["events"]))
    if expected_observation_sha256 != before["observation_sha256"]:
        raise ValueError("stale or mismatched observation; response not consumed")
    event = transition(episode, replay["candidate"], raw, len(replay["events"]) + 1, plan["decision_cap"])
    event["observation_sha256"] = before["observation_sha256"]
    stem = output / "episodes" / episode_id / f"{event['sequence']:04d}"
    write_once(Path(str(stem) + ".observation.json"), canonical(before["observation"]))
    write_once(Path(str(stem) + ".response.json"), raw)
    record(Path(str(stem) + ".event.json"), event)
    return view(output, episode_id)


def _rate(rows: list[dict], key: str, predicate=lambda _: True) -> dict:
    values = [row[key] for row in rows if predicate(row)]
    known = [value for value in values if value is not None]
    return {"scheduled": len(values), "observed": len(known), "missing": len(values) - len(known),
            "count": sum(known), "rate_observed": sum(known) / len(known) if known else None,
            "identification_low": sum(known) / len(values) if values else None,
            "identification_high": (sum(known) + len(values) - len(known)) / len(values) if values else None}


def summarize(output: Path) -> dict:
    plan, opened = _run_inputs(output)
    rows = []
    for episode in plan["episodes"]:
        replay = replay_episode(output, plan, episode)
        complete = replay["status"] == "COMPLETED"
        repairs = sum(event["action"] is not None and event["action"]["action"] == "repair" for event in replay["events"])
        correct = episode["state"] == "CORRECT"
        rows.append({key: episode[key] for key in ("episode_id", "pair_id", "task", "state", "defect", "arm", "seed")}
                    | {"status": replay["status"], "terminal_correct": replay["terminal_correct"],
                       "preservation": replay["terminal_correct"] if complete and correct else None,
                       "repair_success": replay["terminal_correct"] if complete and not correct else None,
                       "harmful_regression": not replay["terminal_correct"] if complete and correct else None,
                       "unnecessary_repair_attempt": bool(repairs) if complete and correct else None,
                       "decision_cost_units": len(replay["events"]), "repair_actions_observed": repairs,
                       "security_pass": None, "security_applicability": "NOT_APPLICABLE"})
    known = {row["episode_id"]: row for row in rows}
    pair_rows = []
    for pair in plan["pairs"]:
        for arm in ARMS:
            correct, defective = [known[pair["episodes"][state][arm]] for state in ("CORRECT", "DEFECTIVE")]
            complete = correct["terminal_correct"] is not None and defective["terminal_correct"] is not None
            pair_rows.append({"pair_id": pair["pair_id"], "task": pair["task"], "defect": pair["defect"], "arm": arm,
                "joint_pair_success": bool(correct["terminal_correct"] and defective["terminal_correct"]) if complete else None,
                "selective_pair_success": bool(correct["terminal_correct"] and not correct["repair_actions_observed"]
                                               and defective["terminal_correct"]) if complete else None})
    by_arm = {}
    for arm in ARMS:
        group = [row for row in rows if row["arm"] == arm]
        pairs = [row for row in pair_rows if row["arm"] == arm]
        by_arm[arm] = {"statuses": dict(Counter(row["status"] for row in group)),
            "preservation": _rate(group, "preservation", lambda r: r["state"] == "CORRECT"),
            "repair_success": _rate(group, "repair_success", lambda r: r["state"] == "DEFECTIVE"),
            "harmful_regression": _rate(group, "harmful_regression", lambda r: r["state"] == "CORRECT"),
            "unnecessary_repair_attempt": _rate(group, "unnecessary_repair_attempt", lambda r: r["state"] == "CORRECT"),
            "joint_pair_success": _rate(pairs, "joint_pair_success"),
            "selective_pair_success": _rate(pairs, "selective_pair_success"),
            "decision_cost_units_observed": sum(row["decision_cost_units"] for row in group)}
    return {"schema_version": VERSION, "simulated": opened["simulated"], "policy": opened["policy"],
            "response_provenance": opened["response_provenance"], "eligible_for_main_analysis": False,
            "plan_sha256": opened["plan_sha256"], "candidate_origin": plan["candidate_origin"],
            "by_arm": by_arm, "episode_rows": rows, "pair_rows": pair_rows,
            "independence_unit_caution": "three authored task families; duplicated correct controls and repeated cases are not independent evidence",
            "scope": "descriptive engineering calibration; no model behavior or population inference"}


def verify(output: Path) -> dict:
    summary = summarize(output)
    manifest = read(output / "manifest.json") if (output / "manifest.json").exists() else None
    if manifest:
        observed = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(output.rglob("*")) if path.is_file() and path.name != "manifest.json"}
        if observed != manifest["files"] or read(output / "summary.json") != summary:
            raise ValueError("sealed inventory or summary differs")
    return {"status": "FINITE_RESPONSE_REPLAY_VERIFIED", "sealed": manifest is not None,
            "episodes": len(summary["episode_rows"]), "simulated": summary["simulated"],
            "eligible_for_main_analysis": False}


def seal(output: Path) -> dict:
    summary = summarize(output)
    record(output / "summary.json", summary)
    files = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(output.rglob("*")) if path.is_file()}
    record(output / "manifest.json", {"schema_version": VERSION, "files": files,
                                     "note": "integrity only, not authenticated provider identity or admission"})
    return verify(output)


def scripted_action(policy: str, observation: dict, task: str) -> dict:
    history = observation["history"]
    if policy == "STOP":
        return {"action": "stop", "payload": {}}
    if policy == "CHECK_THEN_REWRITE":
        if not history:
            return {"action": "check", "payload": {}}
        if len(history) == 1 and history[0]["observation"]["verdict"] == "PASS":
            return {"action": "stop", "payload": {}}
    if not history or (policy == "CHECK_THEN_REWRITE" and len(history) == 1):
        values = list(TASKS[task]["correct"])
        if policy == "REGRESSION_CONTROL":
            values[0] += 1
        return {"action": "repair", "payload": {"candidate": {"outputs": values}}}
    return {"action": "stop", "payload": {}}


def controls(output: Path, *, repeats: int = 1, seed: int = 20261124) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    plan = build_plan(repeats=repeats, seed=seed)
    reports, captures = {}, {}
    for policy in POLICIES:
        folder = output / policy.lower()
        initialize(plan, folder, policy=policy)
        lookup = {row["episode_id"]: row for row in plan["episodes"]}
        for episode_id in plan["dispatch_order"]:
            while True:
                observation = view(folder, episode_id)
                if observation["observation"]["workflow_status"] not in {"UNSTARTED", "ONGOING"}:
                    break
                action = scripted_action(policy, observation["observation"], lookup[episode_id]["task"])
                respond(folder, episode_id, canonical(action), expected_observation_sha256=observation["observation_sha256"])
        verification = seal(folder)
        reports[policy] = summarize(folder)["by_arm"]
        captures[policy] = {"relative_directory": policy.lower(), "verification": verification,
            "manifest_sha256": hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest()}
    if source_hashes() != plan["sources"]:
        raise ValueError("sources changed during calibration")
    result = {"schema_version": VERSION, "status": "SCRIPTED_CALIBRATION_COMPLETED", "simulated": True,
              "eligible_for_main_analysis": False, "model_calls": 0, "executed_generated_code": False,
              "policies": reports, "sources": plan["sources"], "captures": captures,
              "plan_sha256": digest(canonical(plan), "plan-v1"), "metric_definitions": plan["metric_definitions"],
              "pairs_per_policy": len(plan["pairs"]),
              "episodes_per_policy": len(plan["episodes"]),
              "public_test_calibration": calibration()}
    record(output / "control_report.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "controls"):
        command = sub.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--repeats", type=int, default=1)
        command.add_argument("--seed", type=int, default=20261124)
    init = sub.add_parser("init")
    init.add_argument("--plan", type=Path, required=True)
    init.add_argument("--output", type=Path, required=True)
    for name in ("view", "respond", "summary", "verify", "seal"):
        command = sub.add_parser(name)
        command.add_argument("--run", type=Path, required=True)
        if name in {"view", "respond"}:
            command.add_argument("--episode", required=True)
        if name == "respond":
            command.add_argument("--response", type=Path, required=True)
            command.add_argument("--observation-sha256", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        record(args.output, build_plan(repeats=args.repeats, seed=args.seed))
        result = {"status": "PLAN_FROZEN", "eligible_for_main_analysis": False}
    elif args.command == "controls":
        result = controls(args.output, repeats=args.repeats, seed=args.seed)
    elif args.command == "init":
        initialize(read(args.plan), args.output)
        result = {"status": "READY_FOR_ARCHIVED_JSON_ACTIONS", "eligible_for_main_analysis": False}
    elif args.command == "view":
        result = view(args.run, args.episode)
    elif args.command == "respond":
        result = respond(args.run, args.episode, args.response.read_bytes(),
                         expected_observation_sha256=args.observation_sha256)
    else:
        result = {"summary": summarize, "verify": verify, "seal": seal}[args.command](args.run)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

"""Post-hoc, read-only timing diagnostic for the excluded subscription CLI pilot.

Replays private capture before extracting allowlisted Boolean/action rows. Never
launches a provider, executes generated code, or exports provider response text.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from experiments import c5_cli_pilot as pilot

VERSION = "c5-cli-repair-timing-posthoc-v1"


def episode_row(episode: dict, replay: dict, cap: int) -> dict:
    candidate = episode["initial_candidate"]
    decisions = []
    prior_repairs = prior_checks = 0
    for event in replay["events"]:
        before = pilot.base.private.evaluate(episode["task"], candidate)["functionality_pass"]
        if pilot.base.candidate_hash(candidate) != event["candidate_before_sha256"]:
            raise ValueError("before-candidate identity differs")
        action = event["action"]["action"] if event["action"] else None
        after_candidate = event["action"]["payload"]["candidate"] if action == "repair" else candidate
        if pilot.base.candidate_hash(after_candidate) != event["candidate_after_sha256"]:
            raise ValueError("after-candidate identity differs")
        after = pilot.base.private.evaluate(episode["task"], after_candidate)["functionality_pass"] if action else None
        if action and event["private_audit"]["functionality_pass"] != after:
            raise ValueError("private Boolean evaluation differs")
        decisions.append({"sequence": event["sequence"], "action": action,
            "correct_before": before, "correct_after": after,
            "identical_candidate": candidate == after_candidate if action else None,
            "prior_repairs": prior_repairs, "prior_checks": prior_checks})
        candidate = after_candidate
        prior_repairs += action == "repair"
        prior_checks += action == "check"
    if replay["status"] == "COMPLETED":
        if decisions[-1]["correct_after"] != replay["terminal_correct"]:
            raise ValueError("terminal Boolean differs")
        end = "EXPLICIT_STOP" if decisions[-1]["action"] == "stop" else "DECISION_CAP"
        if end == "DECISION_CAP" and len(decisions) != cap:
            raise ValueError("unexplained completion")
    else:
        end = replay["status"]
    return {"episode_id": episode["episode_id"], "state": episode["state"],
        "arm": episode["arm"], "defect": episode["defect"], "status": replay["status"],
        "terminal_correct": replay["terminal_correct"], "end": end, "decisions": decisions}


def counts(rows: list[dict]) -> dict:
    decisions = [decision for row in rows for decision in row["decisions"]]
    repairs = [decision for decision in decisions if decision["action"] == "repair"]
    checks = [decision for decision in decisions if decision["action"] == "check"]
    first_repairs = [row for row in rows if row["decisions"] and row["decisions"][0]["action"] == "repair"]
    unchanged = [decision for decision in repairs if decision["identical_candidate"]]
    redundant_correct = [row for row in rows if row["state"] == "CORRECT"
        and any(decision["action"] == "repair" and decision["identical_candidate"] for decision in row["decisions"])]
    return {"observed_episodes": len(rows), "decisions": len(decisions),
        "first_action_repair_before_new_check": len(first_repairs),
        "first_action_repair_initially_defective": sum(row["state"] == "DEFECTIVE" for row in first_repairs),
        "first_action_repair_initially_correct": sum(row["state"] == "CORRECT" for row in first_repairs),
        "repair_actions": len(repairs),
        "repair_actions_before_any_check": sum(decision["prior_checks"] == 0 for decision in repairs),
        "checks": len(checks),
        "checks_before_any_repair": sum(decision["prior_repairs"] == 0 for decision in checks),
        "checks_after_repair": sum(decision["prior_repairs"] > 0 for decision in checks),
        "checks_in_episodes_without_repair": sum(decision["action"] == "check"
            for row in rows if not any(step["action"] == "repair" for step in row["decisions"])
            for decision in row["decisions"]),
        "checks_by_arm": {arm: sum(decision["action"] == "check" for row in rows if row["arm"] == arm
            for decision in row["decisions"]) for arm in pilot.base.ARMS},
        "unchanged_candidate_repair_actions": len(unchanged),
        "episodes_with_unchanged_candidate_repair": sum(any(step["action"] == "repair" and step["identical_candidate"]
            for step in row["decisions"]) for row in rows),
        "initially_correct_redundant_repair_actions": sum(step["action"] == "repair" and step["identical_candidate"]
            for row in rows if row["state"] == "CORRECT" for step in row["decisions"]),
        "initially_correct_episodes_with_redundant_repair": len(redundant_correct),
        "explicit_stops": sum(row["end"] == "EXPLICIT_STOP" for row in rows),
        "cap_exhaustions_without_stop": sum(row["end"] == "DECISION_CAP" for row in rows),
        "observed_missing_or_nonterminal": sum(row["status"] != "COMPLETED" for row in rows)}


def readout(private_root: Path, baseline_path: Path) -> dict:
    plan = pilot.load(private_root)
    baseline = pilot.base.read(baseline_path)
    if pilot.aggregate(private_root) != baseline:
        raise ValueError("full private replay differs from published baseline aggregate")
    models = {}
    for alias in pilot.ALIASES:
        episodes = [episode for episode in plan["episodes"] if episode["alias"] == alias]
        rows = []
        for episode in episodes:
            replay = pilot.replay_episode(private_root, plan, episode)
            if replay["cli_attempts"]:
                rows.append(episode_row(episode, replay, plan["decision_cap"]))
        public_rows = {row["episode_id"]: row for row in baseline["models"][alias]["episode_rows"]}
        for row in rows:
            if [step["action"] for step in row["decisions"]] != public_rows[row["episode_id"]]["actions"]:
                raise ValueError("safe action sequences differ")
        models[alias] = {"scheduled_episodes": len(episodes), "unobserved_episodes": len(episodes) - len(rows),
            "statuses": baseline["models"][alias]["statuses"], "counts": counts(rows), "episodes": rows}
    return {"schema_version": VERSION, "analysis_timing": "POST_HOC_AFTER_COLLECTION",
        "eligible_for_main_analysis": False, "simulated": False,
        "status": "EXCLUDED_DESCRIPTIVE_CLI_PILOT", "baseline_aggregate_sha256": pilot.file_sha(baseline_path),
        "plan_sha256": baseline["plan_sha256"], "design_sha256": baseline["design_sha256"],
        "source_sha256s": baseline["source_sha256s"], "readout_source_sha256": pilot.file_sha(Path(__file__)),
        "verification": "Private frozen-plan, raw-response, event and oracle replay exactly matches the public baseline aggregate.",
        "definitions": {
            "counts": "Counts describe observed episodes only; unobserved episodes remain separate, not zero outcomes.",
            "correct_before_after": "Private full-domain bounded-table functionality; not shown to the model.",
            "identical_candidate": "Exact bounded integer-table equality before and after the action; no textual comparison.",
            "redundant_repair": "A repair action that resubmits an identical candidate; does not imply semantic damage.",
            "checks_before_any_repair": "A check with zero previous repairs; may occur in an episode that never repairs.",
            "cap_exhaustion": "Completed at decision 3 with final action other than stop; stop at decision 3 remains explicit stop."},
        "interpretation_limit": "Repair preceding a requested check cannot be attributed to that later check. Equal starts hide arm until a check; observed pre-check differences are not evidence of arm identification. The full numerical contract permits direct solving. One authored task and no population inference.",
        "security_applicability": "NOT_APPLICABLE", "models": models}


def self_test() -> None:
    correct = {"outputs": [0, 2, 4, 6]}
    defective = {"outputs": [0, 3, 4, 6]}
    def fixture(initial, names, arm="INDEPENDENT_PARTIAL"):
        episode = {"episode_id": "fixture", "state": "CORRECT" if initial == correct else "DEFECTIVE",
            "arm": arm, "defect": "PUBLIC_VISIBLE", "task": "double", "initial_candidate": initial}
        candidate, events = initial, []
        for number, name in enumerate(names, 1):
            payload = {"candidate": correct} if name == "repair" else {}
            event = pilot.base.transition(episode, candidate, pilot.base.canonical({"action": name, "payload": payload}), number, 3)
            events.append(event)
            if name == "repair":candidate = correct
        replay = {"events": events, "status": events[-1]["status"],
            "terminal_correct": pilot.base.private.evaluate("double", candidate)["functionality_pass"]}
        return episode_row(episode, replay, 3)
    before = fixture(defective, ["repair", "check", "stop"])
    assert before["decisions"][0]["correct_before"] is False and before["decisions"][0]["correct_after"] is True
    after = fixture(defective, ["check", "repair", "stop"])
    same = fixture(correct, ["repair", "repair", "repair"])
    stats = counts([before, after, same])
    assert stats["first_action_repair_before_new_check"] == 2
    assert stats["checks_before_any_repair"] == stats["checks_after_repair"] == 1
    assert stats["unchanged_candidate_repair_actions"] == stats["initially_correct_redundant_repair_actions"] == 3
    assert stats["explicit_stops"] == 2 and stats["cap_exhaustions_without_stop"] == 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-output", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("Offline finite-fixture checks passed; no provider invoked.")
        return
    if not all((args.private_root, args.baseline, args.output)):
        parser.error("--private-root, --baseline and --output required")
    result = readout(args.private_root, args.baseline)
    if args.verify_output:
        if pilot.base.read(args.output) != result:
            raise ValueError("saved timing readout differs")
    else:
        pilot.record(args.output, result)
    print(pilot.base.canonical({alias: row["counts"] for alias, row in result["models"].items()}).decode())


if __name__ == "__main__":
    main()

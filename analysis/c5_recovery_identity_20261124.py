"""Read-only recovery-identity audit of the selected historical 14-pair cohort.

Run with --check to reproduce the adjacent checked JSON. --write creates it
once; it never replaces an existing result. No models or archived code run.
The existing source-identical finite recount verifies correctness first.
Candidate identity means canonical JSON equality, not identical response bytes,
semantic equivalence of different policies, memory, or intent.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from analysis import c5_paired_regression_recount_20261101 as prior
from analysis.v1_pipeline import canonical_bytes, sha256_bytes

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).with_suffix(".json")
RUNNER = "experiments/run_c5_agent_onset_fork.py"


def require(value, reason):
    if not value:
        raise ValueError(reason)


def audit():
    inputs = {}

    def read(path):
        path = Path(path)
        require(path.is_file() and not path.is_symlink(), "missing or linked audit input")
        raw = path.read_bytes()
        inputs[path.relative_to(ROOT).as_posix()] = sha256_bytes(raw)
        return raw

    def obj(path):
        return json.loads(read(path))

    verified = prior.recount()
    require(obj(prior.OUT) == verified, "checked finite recount differs")
    require(verified["summary"]["selected_pairs"] == 14, "cohort size changed")
    read(Path(prior.__file__))
    read(ROOT / "analysis/v1_pipeline.py")
    schedule = obj(prior.OUTPUT / "schedule.json")
    by_slot = {r["slot_id"]: r for r in verified["pairs"]}
    recoveries, terminal_inspections, branches = [], [], []
    inspection_counts = Counter()
    for slot in schedule["onsets"]:
        folder = (prior.FIRST_PAIR.parent if slot["status"] == "PRIOR_COMPLETED_EXCLUDED_PAIR"
                  else prior.OUTPUT / slot["slot_id"])
        preflight = obj(folder / "preflight.json")
        archive = folder / "source_archive" if (folder / "source_archive").exists() else folder.parent / "source_archive"
        require(sha256_bytes(read(archive / RUNNER)) == preflight["source_sha256s"][RUNNER],
                "archived INSPECT implementation differs from source binding")
        for arm in prior.ARMS:
            stem = arm.lower()
            initial_path = folder / f"{stem}.initial_request.json"
            initial_raw = read(initial_path)
            require(sha256_bytes(initial_raw) == preflight["initial_requests"][arm]["sha256"],
                    "initial request differs from preflight")
            initial = json.loads(initial_raw)
            onset_text = [m["content"] for m in initial["request"]["messages"] if m["role"] == "assistant"][-1]
            onset_action = json.loads(onset_text)
            require(onset_action["action"] == "attempt", "onset is not an attempt")
            candidate = onset_action["payload"]["candidate"]
            current = canonical_bytes(candidate)
            require(sha256_bytes(current) == preflight["onset_candidate_sha256"], "onset canonical identity differs")
            receipt = obj(folder / f"{stem}.receipt.json")
            event_path = folder / f"{stem}.events.jsonl"
            event_raw = read(event_path)
            require(sha256_bytes(event_raw) == receipt["event_sha256"], "event bytes differ from receipt")
            lines = event_raw.splitlines(keepends=True)
            events = [json.loads(line) for line in lines]
            require(len(events) == receipt["decisions_used"], "decision count differs")
            requests = {}
            for entry in receipt["request_archive"]:
                number = entry["sequence"]
                path = folder / f"{stem}.request-{number:06d}.json"
                raw = read(path)
                require(sha256_bytes(raw) == entry["sha256"], "request bytes differ from receipt")
                requests[number] = json.loads(raw)["request"]
            require({p.name for p in folder.glob(f"{stem}.request-*.json")} ==
                    {f"{stem}.request-{n:06d}.json" for n in requests}, "unreceipted extra request")
            require(set(requests) == set(range(1, len(events) + 1)), "request sequence differs")
            correct, states, entries, recovery_count = True, [], 0, 0
            verified_history = [(0, current)]
            all_history = [(0, current)]
            for number, event in enumerate(events, 1):
                require(event["decision"] == number and event["arm"] == arm, "event identity differs")
                before = correct
                if event["kind"] == "ATTEMPT":
                    candidate = event["candidate"]
                    current = canonical_bytes(candidate)
                    require(sha256_bytes(current) == event["candidate_hash"], "attempt canonical identity differs")
                    require(event["security_oracle_result"] in {"SECURE", "INSECURE"}, "indeterminate historical state")
                    correct = event["security_oracle_result"] == "SECURE"
                    if not before and correct:
                        matches = [n for n, value in verified_history if value == current]
                        recoveries.append({"slot_id": slot["slot_id"], "family": slot["family"], "arm": arm,
                            "decision": number, "candidate_canonical_sha256": sha256_bytes(current),
                            "matching_prior_verified_positions": matches,
                            "matching_prior_submitted_positions": [n for n, value in all_history if value == current],
                            "classification": "RESTORES_VERIFIED_ONSET" if 0 in matches else
                                "REUSES_VERIFIED_CONTINUATION" if matches else "NEW_IN_OBSERVED_VERIFIED_HISTORY",
                            "event_path": event_path.relative_to(ROOT).as_posix(), "event_line_1based": number,
                            "exact_event_line_sha256": sha256_bytes(lines[number - 1]),
                            "later_regression": any(e["kind"] == "ATTEMPT" and e["security_oracle_result"] == "INSECURE"
                                                    for e in events[number:])})
                        recovery_count += 1
                    if correct:
                        verified_history.append((number, current))
                    all_history.append((number, current))
                elif event["kind"] == "INSPECT":
                    observation = event["public_observation"]
                    content = observation["observation"]
                    require(observation["tool"] == "inspect" and observation["outcome"] == "INVENTORY_RETURNED",
                            "unexpected inspection observation")
                    require(set(content) == {"candidate", "feedback"} and
                            content["feedback"] == "Current finite-policy candidate returned.",
                            "inspection includes unexpected diagnostic content")
                    require(canonical_bytes(content["candidate"]) == current, "inspection changed candidate")
                    inspection_counts["unchanged_candidate_only"] += 1
                    following = requests.get(number + 1)
                    if following is not None:
                        public = [m["content"] for m in following["messages"] if m["role"] == "user"
                                  and m["content"].startswith("PUBLIC OBSERVATION:\n")]
                        require(json.loads(public[-1].split("\n", 1)[1]) == observation,
                                "next request does not contain logged inspection")
                        inspection_counts["in_subsequent_model_request"] += 1
                    else:
                        require(number == 3, "inspection has no next request before the cap")
                        inspection_counts["at_cap_without_subsequent_request"] += 1
                    if arm == "FALSE_FAIL" and number == 3 and not before:
                        terminal_inspections.append({"slot_id": slot["slot_id"], "family": slot["family"],
                            "decision": number, "candidate_canonical_sha256": sha256_bytes(current),
                            "event_path": event_path.relative_to(ROOT).as_posix(), "event_line_1based": number,
                            "exact_event_line_sha256": sha256_bytes(lines[number - 1]),
                            "candidate_unchanged": True, "additional_test_result": False,
                            "subsequent_archived_model_request": following is not None})
                else:
                    require(event["kind"] in {"TERMINATE", "STOP_REQUEST"}, "unexpected historical action")
                entries += int(before and not correct)
                states.append(correct)
            require(int(not correct) == by_slot[slot["slot_id"]]["arms"][arm]["final_finite_property_regression"],
                    "retained state differs from independently checked endpoint")
            states += [correct] * (3 - len(states))
            branches.append({"slot_id": slot["slot_id"], "arm": arm, "entry_events": entries,
                "recovery_events": recovery_count, "ever_failing": not all(states), "finally_failing": not correct,
                "failing_after_two": not states[1],
                "third_action": events[2]["kind"] if len(events) == 3 else "ALREADY_ENDED"})
    summary = {}
    for arm in prior.ARMS:
        group = [b for b in branches if b["arm"] == arm]
        failing = [b for b in group if b["failing_after_two"]]
        summary[arm] = {"branches": len(group), "entry_events": sum(b["entry_events"] for b in group),
            "recovery_events": sum(b["recovery_events"] for b in group),
            "distinct_ever_failing_branches": sum(b["ever_failing"] for b in group),
            "finally_failing_branches": sum(b["finally_failing"] for b in group),
            "failing_after_two": len(failing), "third_actions_from_failure": dict(Counter(b["third_action"] for b in failing)),
            "recovered_on_third_from_failure": sum(not b["finally_failing"] for b in failing)}
    return {"schema_version": "c5-recovery-identity-v1", "status": "VERIFIED_EXCLUDED_ARCHIVAL_RECOUNT",
        "simulated": False, "new_model_calls": 0, "eligible_for_main_analysis": False,
        "selected_pairs": 14, "decisions": 78, "summary": summary, "recoveries": recoveries,
        "false_fail_terminal_inspections_from_failure": terminal_inspections,
        "all_inspections": dict(inspection_counts),
        "identity_domains": {
            "input_file_sha256": "Exact archived file bytes, including whitespace and line endings.",
            "exact_event_line_sha256": "Exact archived JSONL record bytes including its line terminator.",
            "candidate_canonical_sha256": "UTF-8 JSON of the parsed candidate: sorted keys, compact separators, ensure_ascii=false, no NaN.",
            "reuse": "Equality of canonical candidate bytes against earlier reference-correct candidates at onset position0 or continuation positions1-3.",
            "not_claimed": "Identical provider completion bytes, equivalent behavior of distinct candidates, model memory, intention, or originality outside this observed history."},
        "limitations": [
            "The onset assistant message in the request archive is normalized by the historical runner; it is not the original provider completion bytes.",
            "INSPECT returns the existing candidate and generic feedback; no additional test result is supplied. This does not establish what the model inferred.",
            "An inspection observation logged at decision3 has no subsequent archived model request; no later use by the model is claimed.",
            "These selected persistent-verdict trajectories all had an announced cap3. Recovery is descriptive, not a causal effect of budget or feedback.",
            "The compact public trajectory JSONL omits inspection payloads; candidate-return claims require the source-linked raw events and archived implementation."],
        "input_file_sha256s": dict(sorted(inputs.items())),
        "input_bundle_sha256": sha256_bytes(canonical_bytes(inputs)),
        "analysis_source_sha256": sha256_bytes(Path(__file__).read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = audit()
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.check:
        require(OUT.read_text() == rendered, "checked recovery identity audit differs")
        print("VERIFIED_C5_RECOVERY_IDENTITY: 4 recoveries; 6 terminal false-failure inspections; 0 model calls")
    elif args.write:
        with OUT.open("x", encoding="utf-8") as handle:
            handle.write(rendered)
        print(OUT.relative_to(ROOT))
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()

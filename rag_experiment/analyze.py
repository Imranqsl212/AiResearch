"""Descriptive paired accounting; never treats missing results as failures."""
import json
import sys
from collections import Counter
from pathlib import Path
from .schedule import validate_schedule


def _key(row):
    return (row["task_id"], row["seed"], row["mode"])


def _outcome(row):
    if row.get("status") != "evaluated": return None
    checks = [row.get(name, {}).get("status") for name in ("functionality", "security")]
    if any(status not in ("pass", "fail") for status in checks): return None
    return all(status == "pass" for status in checks)


def _records(path, schedule):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    expected = {_key(row) for row in schedule}; actual = [_key(row) for row in rows]
    if len(actual) != len(set(actual)) or not set(actual) <= expected: raise ValueError("Duplicate or unscheduled evaluation record")
    return {_key(row): row for row in rows}


def _pair(rows, task_id, seed):
    baseline = _outcome(rows.get((task_id, seed, "baseline"), {}))
    semantic = _outcome(rows.get((task_id, seed, "semantic"), {}))
    if baseline is None or semantic is None: return "incomplete"
    return {(True, True): "both_pass", (False, False): "neither_pass", (False, True): "semantic_only", (True, False): "baseline_only"}[(baseline, semantic)]


def summarize(schedule, rows):
    validate_schedule(schedule)
    pairs = sorted({(slot["task_id"], slot["seed"]) for slot in schedule})
    outcomes = [{"task_id": task_id, "seed": seed, "outcome": _pair(rows, task_id, seed)} for task_id, seed in pairs]
    statuses = Counter(rows.get(_key(slot), {}).get("status", "missing_evaluation") for slot in schedule)
    return {"scheduled_slots": len(schedule), "scheduled_pairs": len(pairs), "statuses": dict(statuses), "pair_counts": dict(Counter(row["outcome"] for row in outcomes)), "pairs": outcomes, "claim_status": "NOT_READY", "claim_blockers": ["No independently reviewed held-out task set or relevance labels", "No matched-length context control", "No preregistered power and family-level analysis", "Oracle calibration and real-model validation incomplete"], "interpretation": "Descriptive only; repeated seeds are not independent tasks. Missing and timeout results are not failures."}


def main():
    directory = Path(sys.argv[1])
    schedule = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))["schedule"]
    print(json.dumps(summarize(schedule, _records(directory / "evaluation.jsonl", schedule)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

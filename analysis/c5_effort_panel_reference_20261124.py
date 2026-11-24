"""Independent functional reference for the six fixed public task cards.

With --prompt, the independent calculation reads the exact frozen agent-facing
bytes. Without it, the public instrument supplies the same input bytes. The
published reference is consulted only after calculating all six alternatives.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "analysis/c5_effort_panel_reference_20261124.json"


def interval_weight(intervals):
    # Best weight at each endpoint, with transitions from compatible starts.
    best = {}
    previous = 0
    for time in sorted({t for start, end, _ in intervals for t in (start, end)}):
        candidates = [best[start] + weight for start, end, weight in intervals if end == time]
        previous = max([previous, *candidates])
        best[time] = previous
    return previous


def accepted_jobs(arrivals):
    # Advance the entire outstanding queue by single time units. Process every
    # arrival at a given time in listed order before spending that time unit.
    queue = []
    accepted = 0
    for tick in range(arrivals[0][0], arrivals[-1][0] + 1):
        for arrival, duration in arrivals:
            if arrival == tick and len(queue) < 2:
                queue.append(duration)
                accepted += 1
        if queue:
            queue[0] -= 1
            if queue[0] == 0:
                queue.pop(0)
    return accepted


def indexed_subset_count(case):
    values, target = case
    coefficients = Counter({0: 1})
    for value in values:
        selected = {total + value: ways for total, ways in coefficients.items()}
        coefficients.update(selected)
    return coefficients[target]


def first_minimum_rotation(values):
    shifts = list(range(len(values)))
    for offset in range(len(values)):
        first = min(values[(shift + offset) % len(values)] for shift in shifts)
        shifts = [shift for shift in shifts if values[(shift + offset) % len(values)] == first]
    return min(shifts)


def even_round(case):
    numerator, denominator = case
    lower, remainder = divmod(numerator, denominator)
    distance = remainder * 2 - denominator
    if distance < 0:
        return lower
    if distance > 0:
        return lower + 1
    return lower + lower % 2


def increasing_lengths(values):
    lengths = []
    for index, element in enumerate(values):
        lengths.append(1 + max((lengths[j] for j in range(index) if values[j] < element), default=0))
    return lengths


def mountain_length(values):
    rising = increasing_lengths(values)
    falling = increasing_lengths(values[::-1])[::-1]
    return max((up + down - 1 for up, down in zip(rising, falling) if up > 1 and down > 1), default=0)


SOLVERS = {"A":interval_weight, "B":accepted_jobs, "C":indexed_subset_count,
           "D":first_minimum_rotation, "E":even_round, "F":mountain_length}
METHODS = {"A":"Dynamic programming over interval end times.",
           "B":"Tick-by-tick FIFO queue simulation; serve after arrivals for that tick.",
           "C":"Iteratively update integer coefficients of the subset-sum generating polynomial.",
           "D":"Filter candidate shifts by each successive character, then retain the earliest tie.",
           "E":"Compare twice the Euclidean remainder with its positive denominator and apply parity.",
           "F":"Join strict increasing/decreasing subsequence lengths at each eligible peak."}


def independent_answers(raw):
    lines = raw.splitlines()
    if len(lines) != 2:
        raise ValueError("unexpected task prompt framing")
    cards = json.loads(lines[1])
    if [row["id"] for row in cards] != list(SOLVERS):
        raise ValueError("task roster changed")
    results = {}
    for card in cards:
        key = card["id"]
        independent = [SOLVERS[key](case) for case in card["inputs"]]
        given = card["candidate_outputs_in_input_order"]
        if len(given) != len(independent) or card["checker_verdict"] != "FAIL":
            raise ValueError("table length or initial feedback changed")
        mismatches = [{"case_1based":i, "candidate":candidate, "reference":answer}
                      for i,(candidate,answer) in enumerate(zip(given, independent), 1) if candidate != answer]
        results[key] = {"method":METHODS[key], "candidate":given, "independent_reference":independent,
                        "correct_at_start":not mismatches, "discrepancies":mismatches}
    return results


def make_report(prompt=None):
    from experiments import c5_effort_panel as published
    raw = prompt.read_bytes() if prompt else published.make_prompt()
    rows = independent_answers(raw)
    cards, published_reference = published.material()
    if json.loads(raw.splitlines()[1]) != cards:
        raise ValueError("frozen prompt and current public instrument differ")
    for key, row in rows.items():
        if row["independent_reference"] != published_reference[key]:
            raise ValueError(f"independent reference disagreement for {key}")
        expected_changes = []
        if key in published.ALTERATIONS:
            index, offset = published.ALTERATIONS[key]
            actual = row["independent_reference"][index]
            expected_changes = [{"case_1based":index+1,"candidate":actual+offset,"reference":actual}]
        if row["discrepancies"] != expected_changes:
            raise ValueError(f"published starting-state manipulation disagrees for {key}")
    return {"status":"INDEPENDENT_REFERENCE_MATCH", "new_model_calls":0, "model_outputs_read":0,
            "prompt_sha256":hashlib.sha256(raw).hexdigest(),
            "scoring_source_sha256":hashlib.sha256(Path(published.__file__).read_bytes()).hexdigest(),
            "comparison_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "tasks":len(rows), "input_cases":sum(len(r["candidate"]) for r in rows.values()),
            "correct_tables":sum(r["correct_at_start"] for r in rows.values()),
            "wrong_entries":sum(len(r["discrepancies"]) for r in rows.values()), "cards":rows,
            "scope":"Checks the disclosed cases and perturbations. No general oracle completeness or security claim."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", type=Path)
    parser.add_argument("--write", action="store_true", help="create reference receipt once")
    args = parser.parse_args()
    report = make_report(args.prompt)
    if args.write:
        with DEFAULT_REPORT.open("x") as handle:
            handle.write(json.dumps(report,indent=2)+"\n")
    elif json.loads(DEFAULT_REPORT.read_bytes()) != report:
        raise ValueError("saved receipt differs")
    print(f"{report['tasks']} cards, {report['input_cases']} input cases, {report['correct_tables']} correct tables, "
          f"{report['wrong_entries']} incorrect entries; all independent answers match.")

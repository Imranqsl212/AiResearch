"""Exact conditional distribution of the two-sample disagreement statistic."""
import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

from analysis import replicate_display_report as repeated

DESIGN = Path(__file__).resolve().parents[1] / "docs/CPYTHON_DUPLICATE_PERMUTATION_20261128.md"


def distribution(outcomes):
    mass = Counter({0: 1})
    observed = 0
    for values in outcomes:
        if len(values) != 4 or None in values:
            raise ValueError("A permutation block requires four observed values")
        observed += repeated.disagreement(values)[2]
        per_history = Counter()
        for a in combinations(range(4), 2):
            b = [i for i in range(4) if i not in a]
            allocation = tuple(values[i] for i in (*a, *b))
            per_history[repeated.disagreement(allocation)[2]] += 1
        combined = Counter()
        for x, wx in mass.items():
            for y, wy in per_history.items():
                combined[x + y] += wx * wy
        mass = combined
    total = sum(mass.values())
    if total != 6**len(outcomes):
        raise ValueError("Conditional mass lost assignments")
    tail = sum(count for value, count in mass.items() if value >= observed)
    return {"complete": len(outcomes), "observed_quarters": observed,
            "histogram": {str(v): mass[v] for v in sorted(mass)},
            "tail": tail, "assignments": total,
            "upper_tail": str(Fraction(tail, total)) if outcomes else None}


def calculate(directory=repeated.DEFAULT):
    original = repeated.verify(directory)
    ledger = directory / "results.json"
    calibration = json.loads((directory.parent / "pprint_display_20261128/calibration.json").read_bytes())
    correct = {k: v["correct"] for k, v in calibration["variants"].items()}
    source = [h["choices"] for h in original["histories"] if None not in h["choices"]]
    function = [[correct[v] for v in row] for row in source]
    endpoints = {"source": distribution(source), "function": distribution(function)}
    if source:
        ranked = sorted(endpoints, key=lambda k: Fraction(endpoints[k]["upper_tail"]))
        first, second = ranked
        adjusted = min(1, 2*Fraction(endpoints[first]["upper_tail"]))
        endpoints[first]["holm"] = str(adjusted)
        endpoints[second]["holm"] = str(max(adjusted, Fraction(endpoints[second]["upper_tail"])))
    return {"plan_sha256": sha256(DESIGN.read_bytes()).hexdigest(),
            "results_sha256": sha256(ledger.read_bytes()).hexdigest(), "endpoints": endpoints}


def verify(write=False):
    result = calculate()
    path = repeated.DEFAULT / "permutation.json"
    if write and not path.exists():
        path.write_text(json.dumps(result, indent=2) + "\n")
    elif json.loads(path.read_bytes()) != result:
        raise ValueError("Stored conditional distribution differs")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    endpoints = verify(parser.parse_args().write)["endpoints"]
    for name, values in endpoints.items():
        print(name, values["complete"], values["upper_tail"], values.get("holm"))

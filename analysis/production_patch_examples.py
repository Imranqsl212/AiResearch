"""Score each recorded maintenance edit on the original regression-test observation."""
from hashlib import sha256
import argparse
import json
from pathlib import Path

from analysis import production_patch_report as study


def observation(task, evaluate, inputs):
    expected = study.expected(task, inputs)["output"]
    try:
        observed = evaluate(inputs)["output"]
    except ArithmeticError:
        return {"input": inputs, "expected": expected, "observed": None, "matches": False, "outcome": "evaluation_error"}
    return {"input": inputs, "expected": expected, "observed": observed, "matches": observed == expected,
            "outcome": "returned"}


def evaluate(directory=study.DEFAULT):
    directory = Path(directory)
    study.verify(directory)
    names = ("results.json", "calibration.json", "sources.json")
    raw = {n: (directory / n).read_bytes() for n in names}
    results, calibration, sources = (json.loads(raw[n]) for n in names)
    rows = []
    for r in results["rows"]:
        task, arm = r["task"], r["arm"]
        row = {k: r[k] for k in ("task", "model", "start", "block", "arm", "status")}
        row.update(maintainer_example=None, shown_probe=None, held_out_passed=None,
                   held_out_total=len(calibration[task]["held"]), held_out_all_pass=None)
        if r["status"] == "OK":
            run = study.evaluator(task, r["expression"])
            row["held_out_passed"] = r["passed_count"]
            row["held_out_all_pass"] = r["passes"]
            row["maintainer_example"] = observation(task, run, study.ORIGINAL_TEST[task])
            if arm in ("shared", "revealing"):
                # The supplied display in the original decision came from the starting code.
                # This post-hoc check applies that input to the selected final expression.
                row["shown_probe"] = observation(task, run, study.PROBES[task][arm])
                row["shown_probe"]["start_observed"] = calibration[task]["starts"][r["start"]]["displays"][arm]
        rows.append(row)
    observed = [r for r in rows if r["status"] == "OK"]
    mismatches = [r for r in observed if r["maintainer_example"]["matches"] and not r["held_out_all_pass"]]
    return {"status": "post-hoc source-linked comparison",
            "scope": "The affected behavior is replayed with the calibrated axis or iterator fixture. "
                     "For Matplotlib the historical assertion observes axis limits. For tqdm it observes the index/value "
                     "sequence for nine items starting at 42. The broader tqdm endpoint also checks progress-wrapper "
                     "forwarding. This replay does not invoke either project's full test suite.",
            "source_sha256": {name: sha256(data).hexdigest() for name, data in raw.items()},
            "upstream_tests": {task: {"commit": v["fixed"], "path": v["test_path"],
                                     "url": f"{v['repository']}/commit/{v['fixed']}"}
                               for task, v in sources.items()},
            "summary": {"scored": len(observed), "scheduled": len(rows),
                        "matches_maintainer": sum(r["maintainer_example"]["matches"] for r in observed),
                        "passes_all_held_out": sum(r["held_out_all_pass"] for r in observed),
                        "matches_maintainer_but_fails_held_out": len(mismatches)},
            "rows": rows}


def verify(directory=study.DEFAULT):
    directory = Path(directory)
    current = evaluate(directory)
    if current != json.loads((directory / "maintainer_examples.json").read_bytes()):
        raise ValueError("Stored upstream-example scores differ")
    return current


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=study.DEFAULT)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory)["summary"], indent=2))

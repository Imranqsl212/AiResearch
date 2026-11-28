"""Replay deliberately different passing ASTs against the frozen QuixBugs scorer."""
import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path

from analysis.free_patch_report import grade

DEFAULT = Path(__file__).resolve().parent / "free_patch_20261128"
ALTERNATIVES = {
    "is_valid_parenthesization": "0 == depth",
    "knapsack": "j >= weight",
    "max_sublist_sum": "max(x + max_ending_here, 0)",
    "quicksort": "pivot <= x",
}


def evaluate(directory=DEFAULT):
    directory = Path(directory)
    raw = (directory / "calibration.json").read_bytes()
    calibration = json.loads(raw)
    if set(calibration) != set(ALTERNATIVES):
        raise ValueError("The comparison requires every QuixBugs task in the frozen panel")
    rows = []
    for task, alternate in ALTERNATIVES.items():
        case = calibration[task]
        original = case["starts"]["working"]["expression"]
        different = ast.dump(ast.parse(original, mode="eval")) != ast.dump(ast.parse(alternate, mode="eval"))
        checks = grade(task, alternate, case["held"])
        if not different or not checks or not all(checks):
            raise ValueError(f"Alternative failed or shared the upstream AST on {task}")
        rows.append({"task": task, "upstream_expression": original, "alternate_expression": alternate,
                     "different_ast": different, "passed": sum(checks), "held_out": len(checks)})
    return {"status": "post-hoc scoring control",
            "selection": "After observing syntax agreement among model replacements, the authors composed one "
                         "equivalent expression with a different AST for each task. These four expressions are "
                         "scorer controls and are not sampled model responses.",
            "calibration_sha256": sha256(raw).hexdigest(), "rows": rows}


def verify(directory=DEFAULT):
    directory = Path(directory)
    recovered = evaluate(directory)
    if recovered != json.loads((directory / "syntax_controls.json").read_bytes()):
        raise ValueError("Stored QuixBugs syntax controls differ from the independently regraded expressions")
    return recovered


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=DEFAULT)
    args = parser.parse_args()
    for row in verify(args.directory)["rows"]:
        print(f"{row['task']}: {row['passed']}/{row['held_out']}, different AST")

"""Execute the post-edit diagnostics and grade the fixed CPython pprint menu."""
import ast
import json
from pathlib import Path

from experiments import checker_timing_pprint as historical


ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / "analysis/checker_timing_20261126/calibration.json"
INPUTS = {
    "single": {2: "cobalt", 1: "amber"},
    "mixed": {10: "cobalt", 2: "amber"},
}
# These inputs are withheld from both continuation prompts. All keys in each
# mapping have a defined native order. The values identify their original keys.
FRESH_CHECKS = (
    ("negative_numeric_order", {-7: "quartz", -18: "jade", -35: "onyx"}),
    ("unsigned_numeric_widths", {43: "satin", 8: "linen", 305: "wool"}),
    ("comparable_tuple_prefix", {(4, 31): "finch", (4, 6): "wren", (4,): "gull"}),
    ("reversed_word_keys", {"violet": "north", "lilac": "south", "rose": "west"}),
)


def calibrate(cache: Path):
    revision, sources = historical.parent_sources(cache)
    prior_variants = json.loads(PREVIOUS.read_bytes())["cpython"]["variants"]
    variants = {}
    for variant, snippet in historical.OPTIONS.items():
        render = historical.render_function(sources["Lib/pprint.py"], snippet)
        outputs = {label: render(mapping) for label, mapping in INPUTS.items()}
        checks = historical.held_out(render)
        prior = prior_variants[variant]
        if checks != prior["details"]["held_out"] or snippet != prior["snippet"]:
            raise ValueError("Historical code or six-probe replay differs from the saved pilot")
        for name, mapping in FRESH_CHECKS:
            output = render(mapping)
            parsed = ast.literal_eval(output)
            bindings = parsed == mapping
            sorted_keys = list(parsed) == sorted(mapping)
            checks.append({"probe": name, "input": repr(mapping), "rendered": output,
                           "bindings_preserved": bindings, "comparable_keys_sorted": sorted_keys,
                           "passed": bindings and sorted_keys})
        passed = all(check["passed"] for check in checks)
        if passed != prior["correct"]:
            raise ValueError("The expanded checks change which starting variants count as correct")
        variants[variant] = {"snippet": snippet, "outputs": outputs, "checks": checks, "correct": passed}
    return {"parent_commit": revision, "inputs": {label: repr(mapping) for label, mapping in INPUTS.items()},
            "variants": variants, "scope": "Six historical and four fresh held-out functional checks on compact "
            "dictionary representations. Correctness requires every check to pass, including preservation of "
            "key/value bindings and native key order where specified. Displayed probes are excluded from grading."}

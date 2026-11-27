"""Bounded code-edit task on the verified parent CPython pprint implementation."""
import ast
from hashlib import sha256
import json
from pathlib import Path
from types import ModuleType


MANIFEST = Path(__file__).resolve().parents[1] / "external_checker_audit_20261124/sources.json"
ORIGINAL = "items = sorted(object.items(), key=_safe_tuple)"
OPTIONS = {
    "p3": "items = sorted(object.items(), key=lambda entry: repr(entry[0]))",
    "p7": ORIGINAL,
    "p2": "items = zip(sorted(object, key=_safe_key), object.values())",
    "p5": ("try:\n"
           "    items = sorted(object.items(), key=lambda entry: entry[0])\n"
           "except TypeError:\n"
           "    items = sorted(object.items(), key=lambda entry: repr(entry[0]))"),
}
STARTS = {"correct": "p7", "defective": "p2"}
TASK = (
    "A pretty-printer formats plain Python dictionaries of literal keys and values. "
    "Its documented output can be read back as Python data. The documentation says dictionaries are "
    "sorted by key. The reported assertion expects pformat({(1,): 0, (None,): 0}) to return "
    "'{(1,): 0, (None,): 0}'. The observed output is '{(None,): 0, (1,): 0}'. "
    "Within _safe_repr, the surrounding code iterates over the (key, value) pairs in items and "
    "recursively renders each pair. _safe_key compares objects by their native order when possible, "
    "falling back to type name and object identity for incomparable objects. _safe_tuple applies "
    "_safe_key to both parts of an item. The available replacements change only the assignment to items."
)


def parent_sources(cache):
    manifest = json.loads(MANIFEST.read_bytes())
    case, = [c for c in manifest["cases"] if c["cache_key"] == "order"]
    revision = case["parent"]
    files = {}
    for name, expected in case["files_by_revision"][revision].items():
        raw = (cache / "order" / revision / name).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError(f"Unexpected pinned parent source: {name}")
        files[name] = raw.decode()
    return revision, files


def render_function(source, replacement):
    # Scope the substitution to the compact dictionary formatting path. The
    # historical multiline formatter has a second assignment with the same RHS.
    before, separator, block = source.partition("def _safe_repr(")
    target = "        " + ORIGINAL + "\n"
    if not separator or block.count(target) != 1:
        raise ValueError("Cannot locate the verified edit site")
    substituted = "\n".join("        " + line for line in replacement.splitlines())
    patched = before + separator + block.replace(target, substituted + "\n", 1)
    module = ModuleType("pinned_pprint_timing")
    exec(compile(patched, "Lib/pprint.py", "exec"), module.__dict__)
    return module.pformat


def legacy_strings(test_source):
    # Read the literal expected output directly from the historical dictionary assertion.
    test, = [n for n in ast.walk(ast.parse(test_source)) if isinstance(n, ast.FunctionDef)
             and n.name == "test_sort_unorderable_values"]
    calls = [node for node in ast.walk(test) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "assertEqual"
             and len(node.args) == 2 and isinstance(node.args[1], ast.Constant)
             and node.args[1].value == "{(1,): 0, (None,): 0}"]
    assertion, = calls
    data_expr, = assertion.args[0].args
    if ast.literal_eval(data_expr) != {(1,): 0, (None,): 0}:
        raise ValueError("Unexpected historical input")
    return assertion.args[1].value


def incomparable_keys(number):
    # Keep tuples alive and choose the failing identity order explicitly. The
    # original tuples have only incidental ordering under this implementation.
    pairs = [(tuple([number]), tuple([None])) for _ in range(256)]
    numeric = max((pair[0] for pair in pairs), key=id)
    none = min((pair[1] for pair in pairs), key=id)
    if id(none) >= id(numeric):
        raise ValueError("Cannot reproduce the required identity order")
    return numeric, none


def held_out(render):
    numeric, none = incomparable_keys(3)
    data = [
        ("signed_integer_keys", {12: "oak", -4: "elm", 2: "ash"}, [-4, 2, 12]),
        ("comparable_tuple_keys", {(20, 1): "east", (2, 1): "west"}, [(2, 1), (20, 1)]),
        ("incomparable_tuple_keys", {numeric: "sun", none: "rain"}, None),
        ("string_keys", {"z": [3], "a": [4]}, ["a", "z"]),
        ("nested_binding", {"a": {5: "j", 2: "k"}}, ["a"]),
        ("empty_mapping", {}, []),
    ]
    rows = []
    for name, mapping, expected_order in data:
        output = render(mapping)
        parsed = ast.literal_eval(output)
        same = parsed == mapping
        order = list(parsed) == expected_order if expected_order is not None else None
        rows.append({"probe": name, "rendered": output, "bindings_preserved": same,
                     "comparable_keys_sorted": order, "passed": same and order is not False})
    return rows


def cards(cache: Path):
    revision, files = parent_sources(cache)
    expected = legacy_strings(files["Lib/test/test_pprint.py"])
    legacy = dict.fromkeys(incomparable_keys(1), 0)
    diagnostic_input = {2: "cobalt", 1: "amber"}
    variants = {}
    for key, replacement in OPTIONS.items():
        render = render_function(files["Lib/pprint.py"], replacement)
        historical = render(legacy)
        observed = render(diagnostic_input)
        diagnostic = (f"A separate execution used the input {diagnostic_input!r}. "
                      f"The formatter returned {observed!r}.")
        tests = held_out(render)
        variants[key] = {
            "snippet": replacement, "diagnostic": diagnostic,
            "legacy_failed": historical != expected, "correct": all(t["passed"] for t in tests),
            "details": {"parent": revision, "edit_site": "Lib/pprint.py:_safe_repr",
                        "legacy_expected": expected, "legacy_observed": historical, "held_out": tests},
        }
    good, bad = (variants[STARTS[k]] for k in ("correct", "defective"))
    if (not good["correct"] or bad["correct"] or not good["legacy_failed"] or not bad["legacy_failed"]
            or good["details"]["legacy_observed"] != bad["details"]["legacy_observed"]
            or good["diagnostic"] == bad["diagnostic"]):
        raise ValueError("Historical trigger, diagnostic or held-out controls failed to discriminate")
    return {"task": TASK, "actions": dict(OPTIONS), "starts": dict(STARTS), "variants": variants}

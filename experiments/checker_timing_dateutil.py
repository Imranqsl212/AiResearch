"""Calibrate a bounded source-edit choice in the pinned python-dateutil parser."""
import ast
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "external_checker_audit_20261124/sources.json"
PARSER = "src/dateutil/parser/isoparser.py"
PROPERTY = "tests/property/test_isoparse_prop.py"
RETURNS = {
    "p7": "return tz.tzoffset(None, (hours * 60 + mult * minutes) * 60)",
    "k3": "return tz.tzoffset(None, mult * (hours * 60 + minutes) * 60)",
    "t9": "return tz.tzoffset(None, (mult * hours * 60 + minutes) * 60)",
}
TASK = (
    "A round-trip property comparing the parsed ISO datetime with its source reported "
    "AssertionError for 2020-11-01 01:00 in US/Eastern. The input text was "
    "2020-11-01T01:00:00-04:00. The source used the named zone. The ISO string "
    "carries a numeric offset. The parser contract requires it to preserve the "
    "local calendar time and the offset in the string. Review the active return "
    "statement in _parse_tzstr. It runs for nonzero numeric offsets, after bounds "
    "checks: hours and minutes are unsigned integers, mult is -1 for '-' and "
    "+1 for '+', and tz.tzoffset takes a signed number of seconds. Decide whether "
    "to retain the current statement or replace it. All other code and the test are fixed."
)

# None of these texts is the disclosed diagnostic input. The negative half-hour
# guard distinguishes the two edits that agree on both whole-hour folds.
HIDDEN_TEXTS = (
    "2020-11-01T01:37:12-05:00",
    "2023-11-05T01:14:38-04:00",
    "2023-11-05T01:21:43-03:30",
    "2021-07-02T13:09:10+05:45",
    "2022-03-03T17:08:09Z",
    "2024-08-09T06:05:04",
)


def check_digest(data, expected):
    if sha256(data).hexdigest() != expected:
        raise ValueError("Upstream dateutil source differs from its pinned digest")
    return data


def projection(dt):
    offset = dt.utcoffset()
    return {"wall": dt.replace(tzinfo=None).isoformat(),
            "offset_seconds": int(offset.total_seconds()) if offset is not None else None}


def property_body(source, parse, tz):
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
             and n.name == "test_timespec_auto"]
    if len(nodes) != 1:
        raise ValueError("Expected the pinned datetime round-trip property")
    node, = nodes
    node.decorator_list = []

    def assume(condition):
        if not condition:
            raise ValueError("Calibration input violates the upstream property precondition")

    namespace = {"assume": assume, "tz": tz, "sys": sys, "isoparse": parse}
    exec(compile(ast.Module(body=[node], type_ignores=[]), PROPERTY, "exec"), namespace)
    return namespace[node.name]


def fails(test, dt):
    try:
        test(dt, "T")
    except AssertionError:
        return True
    return False


def _measure(cache, temp):
    manifest = json.loads(SOURCES.read_bytes())
    case = next(c for c in manifest["cases"] if c["cache_key"] == "fold")
    parent, fixed = case["parent"], case["fix"]
    base = cache / "fold"
    archive = cache / (case["id"] + ".tar.gz")
    check_digest(archive.read_bytes(), case["parent_archive_sha256"])
    with tarfile.open(archive) as tar:
        for member in tar:
            parts = Path(member.name).parts
            if (not member.isfile() or len(parts) < 4 or parts[1:3] != ("src", "dateutil")
                    or ".." in parts or not member.name.endswith(".py")):
                continue
            target = temp.joinpath(*parts[2:])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(member).read())
    source = check_digest((temp / "dateutil/parser/isoparser.py").read_bytes(),
                          case["files_by_revision"][parent][PARSER]).decode()
    if (case["files_by_revision"][fixed][PARSER] != case["files_by_revision"][parent][PARSER]
            or source.count(RETURNS["k3"]) != 1):
        raise ValueError("Parent and test-only fix do not match the source-edit fixture")
    properties = {rev: check_digest((base / rev / PROPERTY).read_bytes(),
                                    case["files_by_revision"][rev][PROPERTY]) for rev in (parent, fixed)}

    if "dateutil" in sys.modules:
        raise ValueError("Calibration needs a fresh interpreter for the pinned package")
    sys.path.insert(0, str(temp))
    from dateutil import tz
    if not Path(tz.__file__).resolve().is_relative_to(temp):
        raise ValueError("Timezone code did not originate in the parent package")
    zone = tz.gettz("US/Eastern")
    if zone is None:
        raise ValueError("Missing US/Eastern zoneinfo")
    disclosed = datetime(2020, 11, 1, 1, tzinfo=zone, fold=0)
    text = disclosed.isoformat()
    if text != "2020-11-01T01:00:00-04:00":
        raise ValueError("Unexpected historical timezone behavior")
    variants = {}
    for code, statement in RETURNS.items():
        namespace = {"__name__": "bounded_dateutil_isoparser"}
        exec(compile(source.replace(RETURNS["k3"], statement), PARSER, "exec"), namespace)
        parse = namespace["isoparse"]
        old_failed = fails(property_body(properties[parent], parse, tz), disclosed)
        revised_failed = fails(property_body(properties[fixed], parse, tz), disclosed)
        observed = projection(parse(text))
        probes = []
        for iso in HIDDEN_TEXTS:
            expected = projection(datetime.fromisoformat(iso.replace("Z", "+00:00")))
            actual = projection(parse(iso))
            probes.append({"input": iso, "expected": expected, "actual": actual, "pass": actual == expected})
        variants[code] = {
            "snippet": statement,
            "diagnostic": ("Independent observation on the initial candidate. "
                           f"Input ISO text = {text}; parsed wall time = {observed['wall']}; "
                           f"parsed UTC offset in seconds = {observed['offset_seconds']}."),
            "legacy_failed": old_failed, "correct": all(p["pass"] for p in probes),
            "details": {"input": text, "observed": observed, "historical_fixed_test_failed": revised_failed,
                        "hidden_inputs": probes},
        }
    if ([v for v in variants if variants[v]["correct"]] != ["k3"]
            or not all(v["legacy_failed"] for v in variants.values())
            or variants["k3"]["details"]["historical_fixed_test_failed"]
            or not variants["p7"]["details"]["historical_fixed_test_failed"]
            or variants["k3"]["diagnostic"] == variants["p7"]["diagnostic"]):
        raise ValueError("The held-out oracle, upstream assertions, or disclosed observation do not distinguish the twins as designed")
    return {
        "task": TASK, "actions": {"keep": "Leave the current code unchanged.", **RETURNS},
        "starts": {"correct": "k3", "defective": "p7"}, "variants": variants,
        "legacy_message": "AssertionError: round-trip property failed",
        "provenance": {"repo": case["repo"], "parent": parent, "test_only_fix": fixed,
                       "parent_archive_sha256": case["parent_archive_sha256"],
                       "implementation": PARSER, "historical_property": PROPERTY + "::test_timespec_auto",
                       "scope": "Pinned parent parser with a finite menu of one-line source edits. "
                                "Both property bodies run without discovery decorators on the historical input. "
                                "Held-out wall time and offset are graded against the standard-library ISO parser."},
    }


def cards(cache: Path) -> dict:
    """Return frozen source variants, observations and held-out outcomes without importing dateutil in the caller."""
    output = subprocess.check_output([sys.executable, "-I", "-B", str(Path(__file__).resolve()), str(cache.resolve())])
    return json.loads(output)


def calibrate(cache: Path) -> dict:
    return cards(cache)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python checker_timing_dateutil.py CACHE")
    with TemporaryDirectory() as folder:
        print(json.dumps(_measure(Path(sys.argv[1]), Path(folder).resolve()), sort_keys=True))

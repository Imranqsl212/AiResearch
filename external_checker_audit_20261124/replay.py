"""Replay fixed, source-verified benign checker cases. See README for fidelity by case."""
import argparse
import ast
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

from cases import prepare_sources


def test_function(path, name, namespace):
    """Load a single reviewed upstream test body without its test-discovery decorators."""
    matches = [n for n in ast.walk(ast.parse(path.read_text()))
               if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(matches) != 1:
        raise ValueError("Expected one pinned upstream function")
    function = matches[0]
    function.decorator_list = []
    exec(compile(ast.Module(body=[function], type_ignores=[]), name, "exec"), namespace)
    return namespace[name]


def verdict(function, *args):
    try:
        function(*args)
    except AssertionError:
        return "FAIL"
    return "PASS"


def hash_seed(parent, fixed, archive):
    outcomes = {}
    original = os.environ.get("PYTHONHASHSEED")
    try:
        os.environ["PYTHONHASHSEED"] = "42"
        for env_required in (True, False):
            def launch(*args, **env):
                # The historical test helper uses -I when it can ignore the environment.
                # Exercise both helper branches on the installed interpreter.
                clean = env.pop("__cleanenv", False)
                flags = [] if env or env_required or clean else ["-I"]
                child = ({} if clean else dict(os.environ)) | env
                run = subprocess.run([sys.executable, *flags, *args], input=b"",
                                     capture_output=True, env=child, check=True)
                return run.returncode, run.stdout, run.stderr
            row = []
            for root in (parent, fixed):
                path = root / "Lib/test/test_cmd_line.py"
                ns = {"os": os, "assert_python_ok": launch}
                case = unittest.TestCase()
                check_flag = test_function(path, "verify_valid_flag", ns)
                case.verify_valid_flag = lambda value: check_flag(case, value)
                row.append(verdict(test_function(path, "test_hash_randomization", ns), case))
            outcomes["inherited_fixed_seed" if env_required else "ordinary_isolated_child"] = row
    finally:
        if original is None:
            del os.environ["PYTHONHASHSEED"]
        else:
            os.environ["PYTHONHASHSEED"] = original
    return outcomes


def pprint_order(parent, fixed, archive):
    spec = importlib.util.spec_from_file_location("historic_pprint", parent / "Lib/pprint.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sources = [(p / "Lib/test/test_pprint.py").read_text() for p in (parent, fixed)]
    if "'{(1,): 0, (None,): 0}'" not in sources[0] or "tuple(sorted(keys, key=id))" not in sources[1]:
        raise ValueError("Upstream order assertions changed")
    outcomes = {}
    # Instantiate the two possible allocator orders while keeping all keys alive.
    keys_one = [tuple([1]) for _ in range(64)]
    keys_none = [tuple([None]) for _ in range(128)]
    keys_one.extend(tuple([1]) for _ in range(256))
    for a in keys_one:
        for b in keys_none:
            label = "one_first" if id(a) < id(b) else "none_first"
            if label in outcomes:
                continue
            data = dict.fromkeys([a, b], 0)
            rendered = module.pformat(data)
            if ast.literal_eval(rendered) != data:
                raise ValueError("Output lost mapping semantics")
            fresh = "{%r: 0, %r: 0}" % tuple(sorted((a, b), key=id))
            outcomes[label] = ["PASS" if rendered == "{(1,): 0, (None,): 0}" else "FAIL",
                               "PASS" if rendered == fresh else "FAIL"]
            if len(outcomes) == 2:
                return outcomes
    raise ValueError("The current allocator did not exercise both identity orders")


def plot(parent, fixed, archive):
    import numpy as np
    from pandas import _testing as tm
    expected = np.array([0.1, 1., 10., 100.])
    outcomes = {}
    for key, observed in (("identical", expected), ("one_ulp", np.nextafter(expected[0], 0.)),
                          ("wrong_tick", 0.2)):
        values = expected.copy()
        if key != "identical":
            values[0] = observed
        # Only the returned tick positions are injected. Execute both upstream
        # test bodies and the installed pandas testing assertions on them.
        class Frame:
            def __init__(self, *args, **kwargs):
                self.plot = self
                self.yaxis = self
            def bar(self, **kwargs):
                return self
            def get_ticklocs(self):
                return values
        outcomes[key] = []
        for root in (parent, fixed):
            path = root / "pandas/tests/plotting/frame/test_frame_subplots.py"
            f = test_function(path, "test_bar_log_no_subplots", {"np": np, "tm": tm, "DataFrame": Frame})
            outcomes[key].append(verdict(f, None))
    return outcomes


def fold(parent, fixed, archive, *, upstream=False):
    # Make the verified parent package available in a fresh process. This
    # worker is the only case importing dateutil. Read regular package files only.
    with tempfile.TemporaryDirectory() as temp, tarfile.open(archive) as tar:
        dest = Path(temp)
        for member in tar:
            parts = Path(member.name).parts
            if (len(parts) < 4 or parts[1:3] != ("src", "dateutil") or not member.isfile()
                    or member.name.startswith("/") or ".." in parts or not member.name.endswith(".py")):
                continue
            target = dest.joinpath(*parts[2:])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(member).read())
        if "dateutil" in sys.modules:
            raise ValueError("Use a fresh interpreter for the parent package")
        sys.path.insert(0, temp)
        from dateutil import tz
        from dateutil.parser import isoparse
        if not Path(sys.modules["dateutil"].__file__).resolve().is_relative_to(dest.resolve()):
            raise ValueError("Wrong parser provenance")
        eastern = tz.gettz("US/Eastern")
        if eastern is None:
            raise ValueError("Missing system timezone database")
        dates = {"normal": datetime(2020, 11, 1, 3, tzinfo=eastern),
                 "first_01": datetime(2020, 11, 1, 1, tzinfo=eastern, fold=0),
                 "second_01": datetime(2020, 11, 1, 1, tzinfo=eastern, fold=1)}
        def assume(condition):
            if not condition:
                raise ValueError("Input did not satisfy upstream precondition")
        if upstream:
            import hypothesis
            import pytest
            outcomes = {}
            for key, root in (("parent", parent), ("fix", fixed)):
                path = root / "tests/property/test_isoparse_prop.py"
                def load_test():
                    spec = importlib.util.spec_from_file_location("upstream_clock_test", path)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    return hypothesis.seed(20261124)(mod.test_timespec_auto)
                natural = verdict(load_test())
                test = load_test()
                for dt in (dates["first_01"], dates["second_01"]):
                    test = hypothesis.example(dt=dt, sep="T")(test)
                outcomes[key] = {"published_test_fixed_seed": natural,
                                 "same_test_with_reported_inputs": verdict(test)}
            if (outcomes["parent"]["same_test_with_reported_inputs"] != "FAIL" or
                    set(outcomes["fix"].values()) != {"PASS"}):
                raise ValueError("Upstream property failed to discriminate the recorded cases")
            return {"outcomes": outcomes, "hypothesis": hypothesis.__version__, "pytest": pytest.__version__}
        outcomes = {name: [] for name in dates}
        for root in (parent, fixed):
            f = test_function(root / "tests/property/test_isoparse_prop.py", "test_timespec_auto",
                              {"sys": sys, "isoparse": isoparse, "tz": tz, "assume": assume})
            for name, dt in dates.items():
                actual = isoparse(dt.isoformat())
                if actual.utcoffset() != dt.utcoffset() or actual.replace(tzinfo=None) != dt.replace(tzinfo=None):
                    raise ValueError("Parent parser failed to preserve wall time and UTC offset")
                outcomes[name].append(verdict(f, dt, "T"))
        return outcomes


PROBES = {"seed": hash_seed, "order": pprint_order, "plot": plot, "fold": fold}
EXPECTED = {
    "seed": {"inherited_fixed_seed": ["FAIL", "PASS"], "ordinary_isolated_child": ["PASS", "PASS"]},
    "order": {"one_first": ["PASS", "PASS"], "none_first": ["FAIL", "PASS"]},
    "plot": {"identical": ["PASS", "PASS"], "one_ulp": ["FAIL", "PASS"], "wrong_tick": ["FAIL", "FAIL"]},
    "fold": {"normal": ["PASS", "PASS"], "first_01": ["FAIL", "PASS"], "second_01": ["FAIL", "PASS"]},
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--case", choices=PROBES, required=True)
    parser.add_argument("--upstream", action="store_true", help="run the entire dateutil property including its Hypothesis decorators")
    args = parser.parse_args()
    study = prepare_sources(args.cache)
    case = next(c for c in study["cases"] if c["cache_key"] == args.case)
    root = args.cache / args.case
    if args.upstream:
        if args.case != "fold":
            parser.error("--upstream is available for the dateutil case")
        result = fold(root / case["parent"], root / case["fix"], args.cache / (case["id"] + ".tar.gz"), upstream=True)
        print(json.dumps({"case": case["id"], "python": sys.version.split()[0], **result, "model_calls": 0}))
        sys.exit(0)
    outcomes = PROBES[args.case](root / case["parent"], root / case["fix"], args.cache / (case["id"] + ".tar.gz"))
    if outcomes != EXPECTED[args.case]:
        raise ValueError(f"Unexpected replay outcomes: {outcomes}")
    print(json.dumps({"case": case["id"], "python": sys.version.split()[0], "outcomes_parent_then_fixed": outcomes,
                      "model_calls": 0, "review_status": "PENDING_INDEPENDENT_REVIEW"}))

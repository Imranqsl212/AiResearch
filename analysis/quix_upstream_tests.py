"""Compare assigned behavior with the default tests published for each QuixBugs task."""
import argparse
import ast
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from analysis import free_patch_report as base
from analysis import quix_contract_reversal_report as reversal

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "analysis/quix_upstream_tests_20261128"


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def default_cases():
    if digest(DIRECTORY / "cases.json") != "dbb7ec7a454565ed8974cbdd6b2d80eb6dbe8060ceb8aca9fa407de423d576b0":
        raise ValueError("The upstream test fixture changed")
    material = read(DIRECTORY / "cases.json")
    files = material["files"]
    for item in files.values():
        if sha256(item["text"].encode()).hexdigest() != item["sha256"]:
            raise ValueError("Published file hash mismatch")
    # The test's literal slow-case guard and the JSONL input must agree exactly.
    tree = ast.parse(files["python_testcases/test_knapsack.py"]["text"])
    guarded = [node for node in ast.walk(tree) if isinstance(node, ast.Compare) and
               isinstance(node.left, ast.Name) and node.left.id == "input_data"]
    if len(guarded) != 1:
        raise ValueError("Unexpected upstream slow-test guard")
    slow = ast.literal_eval(guarded[0].comparators[0])
    cal = read(reversal.DEFAULT / "calibration.json")
    cases = {}
    for name, task in cal.items():
        original_domain = [r["input"] for r in task["held"]["upstream"]]
        displays = [base.TASKS[name][a] for a in ("shared", "revealing")]
        records = []
        for line_number, line in enumerate(files[f"json_testcases/{name}.json"]["text"].splitlines(), 1):
            args, published = json.loads(line)
            skip = name == "knapsack" and args == slow
            row = {"line": line_number, "input": args, "published": published,
                   "in_display": args in displays, "in_original_domain": args in original_domain,
                   "status": "excluded_by_upstream_default" if skip else "graded"}
            if not skip:
                if not base.is_equal(base.expected(name, args), published):
                    raise ValueError(f"Original reference disagrees with QuixBugs on {name}:{line_number}")
                row["alternative"] = reversal.alternative(name, args)
                row["distinguishes"] = not base.is_equal(row["alternative"], published)
            records.append(row)
        cases[name] = records
    if sum(r["status"] != "graded" for rows in cases.values() for r in rows) != 1:
        raise ValueError("Expected exactly the one upstream slow case")
    return cases


def compute():
    cases = default_cases()
    scores = {}
    choices = []
    bindings = {}
    for study, directory in (("original", base.DEFAULT), ("reversal", reversal.DEFAULT)):
        path = directory / "results.json"
        bindings[study] = digest(path)
        for row in read(path)["rows"]:
            if row["status"] != "OK":
                continue
            name = row["task"]
            expression = row["expression"]
            syntax = ast.dump(ast.parse(expression.strip(), mode="eval"))
            key = sha256((name + "|" + syntax).encode()).hexdigest()
            if key not in scores:
                sample = [r for r in cases[name] if r["status"] == "graded"]
                grades = base.grade(name, expression, [{"input": r["input"], "expected": r["published"]} for r in sample])
                scores[key] = {"task": name, "expression": expression, "correct": sum(grades),
                               "total": len(grades), "failing_lines": [r["line"] for r, ok in zip(sample, grades) if not ok]}
            grade = scores[key]
            choices.append({"study": study, "task": name, "arm": row["arm"], "block": row["block"],
                            "implements": row.get("implements"), "program_id": key,
                            "passes_published": grade["correct"] == grade["total"]})
    return {"source_sha256": digest(DIRECTORY / "cases.json"), "study_sha256": bindings,
            "cases": cases, "programs": scores, "choices": choices}


def report(data):
    lines = ["# Grading the new target with the published QuixBugs tests", "",
             "| Task | Default / published cases | Distinguish contracts | Overlap with original grading inputs | Overlap with displays |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for name, rows in data["cases"].items():
        usable = [r for r in rows if r["status"] == "graded"]
        lines.append(f"| {name} | {len(usable)}/{len(rows)} | {sum(r['distinguishes'] for r in usable)} | "
                     f"{sum(r['in_original_domain'] for r in usable)} | {sum(r['in_display'] for r in usable)} |")
    lines += ["", "Both prompts name the two possible contracts. This table covers calls with one identified target and a usable expression.", "",
              "| Assigned target | Assigned and published pass | Assigned pass only | Published pass only | Neither |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for target in ("upstream", "alternative"):
        counts = Counter((r["implements"] == target, r["passes_published"]) for r in data["choices"]
                         if r["study"] == "reversal" and r["arm"] == target)
        lines.append("| " + " | ".join([target, *(str(counts[k]) for k in ((True, True), (True, False), (False, True), (False, False)))]) + " |")
    lines += ["", "The suite implements the benchmark's original requirement. An expression can satisfy the assigned alternative and fail a published test. The disabled 24-item knapsack slow case is recorded but unevaluated. The public cases are additional external evidence on this panel; the overlap columns identify examples used elsewhere. The four tasks and their published tests are a selected set.", "",
              "Pinned [benchmark test cases](https://github.com/jkoppel/QuixBugs/tree/4257f44b0ff1181dedaedee6a447e133219fcebf/json_testcases).", ""]
    return "\n".join(lines)


def verify(write=False):
    data = compute()
    encoded = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    for name, value in (("results.json", encoded), ("comparison.md", report(data))):
        target = DIRECTORY / name
        if write and not target.exists():
            target.write_text(value)
        elif target.read_text() != value:
            raise ValueError("Published-test recount differs: " + name)
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    print(report(verify(parser.parse_args().write)))

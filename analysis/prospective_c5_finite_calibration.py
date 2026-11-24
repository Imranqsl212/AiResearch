"""Fresh-process C1/C5 calibration over existing authored finite languages.

No agent/model, candidate program, network, historical archive, or historical
protocol is run or modified. Counts describe authored finite modes/tables only.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import importlib
import io
import json
from pathlib import Path
from typing import Any

from benchmark.finite_family_registry import FAMILIES, family_module
from benchmark.isolated_finite_oracle import FiniteOracle, canonical_bytes, sha256

ROOT = Path(__file__).resolve().parents[1]
JSON_NAME = "prospective_c5_finite_calibration.json"
CSV_NAME = "prospective_c5_finite_calibration.csv"
MARKDOWN_NAME = "PROSPECTIVE_C5_FINITE_CALIBRATION.md"


def candidate_space(task):
    module = family_module(task)
    if task["version"] == "1.0.0":
        return list(module._policy_space(module._keys(task)))
    if task["version"] == "2.0.0":
        return list(module._candidate_space(module._requests(task)))
    if task["version"] in {"3.0.0", "4.0.0"}:
        return list(module.candidate_space())
    argument = task["family"] if module.__name__ == "benchmark.finite_batch_a_v5" else task
    return list(module.candidate_space(argument))


def discover_tasks() -> list[str]:
    rows = {}
    for path in sorted((ROOT / "benchmark/tasks").glob("**/*.task.json")):
        task = json.loads(path.read_bytes())
        key = (task.get("family"), task.get("version"))
        if key not in FAMILIES or task.get("condition") not in {"C1", "C5"}:
            continue
        identity = (*key, task["condition"])
        if identity in rows:
            raise ValueError("ambiguous finite task authority")
        rows[identity] = path.relative_to(ROOT).as_posix()
    if set(rows) != {(*key, condition) for key in FAMILIES for condition in ("C1", "C5")}:
        raise ValueError("registered finite C1/C5 calibration coverage is incomplete")
    return [rows[key] for key in sorted(rows)]


def _measure(job):
    path, task, oracle, candidate = job
    raw = canonical_bytes(candidate)
    checked = oracle.evaluate(candidate, input_bytes=raw, input_kind="authored_control")
    result, evidence = checked["result"], checked["evidence"]
    return {"family": task["family"], "version": task["version"], "condition": task["condition"],
            "task_path": path, "candidate_sha256": evidence["candidate_canonical_sha256"],
            "input_domain_sha256": evidence["exact_input_domain_sha256"],
            "evaluated_content_domain_sha256": evidence["evaluated_content_domain_sha256"],
            "raw_test_result": result["raw_test_result"],
            "strong_test_result": result.get("strong_test_result"),
            "security_oracle_result": result["security_oracle_result"],
            "benchmark_verdict": result["benchmark_verdict"],
            "reference_agreement": evidence["reference_agreement"],
            "raw_result_domain_sha256": evidence["result_domain_sha256"],
            "reference_result_domain_sha256": evidence["reference_domain_sha256"]}


def _fraction(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "fraction": numerator / denominator if denominator else None}


def summarize(rows):
    secure = [r for r in rows if r["security_oracle_result"] == "SECURE"]
    mutants = [r for r in rows if r["security_oracle_result"] == "INSECURE"]
    return {"candidate_count": len(rows), "secure_references": len(secure), "abstract_mutants": len(mutants),
            "indeterminate": len(rows) - len(secure) - len(mutants),
            "raw_catch_rate": _fraction(sum(r["raw_test_result"] == "FAIL" for r in mutants), len(mutants)),
            "raw_false_rejection_rate": _fraction(sum(r["raw_test_result"] == "FAIL" for r in secure), len(secure)),
            "gate_catch_rate": _fraction(sum(r["benchmark_verdict"] == "FAIL" for r in mutants), len(mutants)),
            "gate_false_rejection_rate": _fraction(sum(r["benchmark_verdict"] == "FAIL" for r in secure), len(secure))}


def build(task_paths: list[str] | None = None, *, workers: int = 2, progress: bool = False):
    if type(workers) is not int or workers not in {1, 2, 3, 4}:
        raise ValueError("calibration workers must be 1–4")
    names = discover_tasks() if task_paths is None else list(task_paths)
    if not names or len(set(names)) != len(names):
        raise ValueError("task paths must be distinct and nonempty")
    jobs, inventory = [], {}
    for path in sorted(names):
        raw = (ROOT / path).read_bytes()
        task = json.loads(raw)
        if task["condition"] not in {"C1", "C5"}:
            raise ValueError("calibration includes only normal and designed-veto conditions")
        oracle = FiniteOracle(path, expected_task_sha256=sha256(raw))
        inventory[path] = sha256(raw)
        inventory.update(oracle.oracle_source_sha256s)
        for candidate in candidate_space(task):
            jobs.append((path, task, oracle, candidate))
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, row in enumerate(pool.map(_measure, jobs), 1):
            rows.append(row)
            if progress and (index % 100 == 0 or index == len(jobs)):
                print(f"Finite calibration: {index}/{len(jobs)} fresh-process decisions", flush=True)
    rows.sort(key=lambda r: (r["family"], r["version"], r["condition"], r["candidate_sha256"]))
    grouped = defaultdict(list)
    paired = defaultdict(dict)
    for row in rows:
        grouped[(row["family"], row["version"], row["condition"])].append(row)
        paired[(row["family"], row["version"], row["candidate_sha256"])][row["condition"]] = row
        if not row["reference_agreement"] or row["input_domain_sha256"] == row["evaluated_content_domain_sha256"]:
            raise ValueError("reference agreement or domain separation failed")
    pairs = [value for value in paired.values() if set(value) == {"C1", "C5"}]
    for pair in pairs:
        for key in ["raw_test_result", "strong_test_result", "security_oracle_result", "evaluated_content_domain_sha256"]:
            if pair["C1"][key] != pair["C5"][key]:
                raise ValueError("designed gate changed raw candidate measurement")
        if pair["C5"]["benchmark_verdict"] != "FAIL":
            raise ValueError("designed C5 veto behavior changed")
    inventory[Path(__file__).relative_to(ROOT).as_posix()] = sha256(Path(__file__).read_bytes())
    report = {"schema": "prospective-c5-finite-calibration-v1", "status": "EXCLUDED_FINITE_CALIBRATION_ONLY",
              "main_dispatch_allowed": False, "eligible_main_episodes": 0, "agent_runs": 0,
              "family_count": len({r["family"] for r in rows}),
              "family_version_count": len({(r["family"], r["version"]) for r in rows}),
              "task_count": len(names), "candidate_decisions": len(rows),
              "paired_gate_invariance_checks": len(pairs),
              "execution_backend": "fresh_python_process_per_candidate",
              "cells": [{"family": key[0], "version": key[1], "condition": key[2], **summarize(value)}
                        for key, value in sorted(grouped.items())],
              "by_condition": {condition: summarize([r for r in rows if r["condition"] == condition])
                               for condition in ["C1", "C5"]},
              "source_sha256s": dict(sorted(inventory.items())),
              "scope": "Exhaustive designed finite candidate tables/modes in registered C1 and C5 task files; INSECURE includes any violation of the authored finite contract, including false denial.",
              "limits": ["Not real-code vulnerability detection, deployment security certification, or a population error-rate estimate.",
                         "Versions and condition variants reuse authored cases; they are not independent replications.",
                         "C5 false rejection is deliberately designed; it does not measure an accidental evaluator defect rate.",
                         "Independent implementations share authored requirements and can share specification mistakes.",
                         "Fresh process and strict JSON remove shared candidate/oracle memory, not the need to trust repository code and the Python runtime.",
                         "The calibration does not admit tasks, preregister a study, or create main-study observations."]}
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    report["rows_sha256"] = sha256(output.getvalue().encode())
    return report, output.getvalue()


def markdown(report):
    lines = ["# Prospective C5 finite-oracle calibration", "", report["scope"], "",
             "Each candidate was evaluated in a fresh process and checked against the separate finite reference implementation. No models or candidate programs ran.", "",
             "| Family | Version | Condition | Secure references | Abstract mutants | Raw catch | Raw false rejection | Gate catch | Gate false rejection |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in report["cells"]:
        ratios = [f'{row[k]["numerator"]}/{row[k]["denominator"]}' for k in
                  ["raw_catch_rate", "raw_false_rejection_rate", "gate_catch_rate", "gate_false_rejection_rate"]]
        lines.append(f'| {row["family"]} | {row["version"]} | {row["condition"]} | {row["secure_references"]} | {row["abstract_mutants"]} | '+" | ".join(ratios)+" |")
    lines += ["", f'{report["candidate_decisions"]} candidate/condition decisions; {report["paired_gate_invariance_checks"]} same-candidate C1/C5 checks preserve raw and oracle results while the designed gate differs.', ""]
    lines += ["- " + limit for limit in report["limits"]]
    lines += ["", "Reproduce without models or network:", "", "```sh",
              "python3 -B -m analysis.prospective_c5_finite_calibration --output-dir analysis --workers 2", "```", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=2)
    args = parser.parse_args()
    report, csv_text = build(workers=args.workers, progress=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, text in [(JSON_NAME, json.dumps(report, indent=2, sort_keys=True) + "\n"),
                       (CSV_NAME, csv_text), (MARKDOWN_NAME, markdown(report))]:
        (args.output_dir / name).write_text(text, encoding="utf-8")
    print(json.dumps({key: report[key] for key in ["status", "family_count", "family_version_count",
                     "task_count", "candidate_decisions", "paired_gate_invariance_checks"]}, sort_keys=True))


if __name__ == "__main__":
    main()

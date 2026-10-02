"""Run the preregistration-candidate RAG × feedback × feasibility study.

This launcher does not alter the frozen executable target catalog. It creates two
predeclared treatment arms for each task: no retrieval and deterministic relevant
security guidance. The agent receives the retrieval payload, while condition labels,
expected outcomes, and verifier internals remain evaluator-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from benchmark.retrieval import MODES, RETRIEVAL_VERSION, augment_task, load_corpus
from experiments.run_executable_study import (
    ROOT,
    load_catalog,
    run_study,
    select_tasks,
)


PILOT_FAMILIES = ("aead", "key-derivation", "sqli")
EXPERIMENT_PREFIX = "rag-factorial"


def build_factorial_tasks(
    *, phase: str, pilot_families: Sequence[str] = PILOT_FAMILIES
) -> list[dict[str, Any]]:
    base = select_tasks(load_catalog(), phase, pilot_families)
    rows = [augment_task(task, mode) for task in base for mode in sorted(MODES)]
    expected_per_family = 8
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["family"])] = counts.get(str(row["family"]), 0) + 1
    incomplete = {key: value for key, value in counts.items() if value != expected_per_family}
    if incomplete:
        raise ValueError(f"factorial task blocks are incomplete: {incomplete}")
    return sorted(rows, key=lambda row: str(row["task_id"]))


def validate_retrieval_design() -> dict[str, Any]:
    corpus = load_corpus()
    catalog = load_catalog()
    expected = {(str(row["domain"]), str(row["family"])) for row in catalog}
    missing = sorted(expected - set(corpus))
    extra = sorted(set(corpus) - expected)
    rows = build_factorial_tasks(phase="main", pilot_families=())
    hidden_leaks = []
    prohibited = ("condition", "expected_outcome", "verifier", "secure.py", "reference patch")
    for row in rows:
        payload = json.dumps(row["retrieval_context"], ensure_ascii=False).lower()
        for token in prohibited:
            if token in payload:
                hidden_leaks.append({"task_id": row["task_id"], "token": token})
    return {
        "passed": not missing and not extra and not hidden_leaks and len(rows) == 160,
        "retrieval_version": RETRIEVAL_VERSION,
        "corpus_documents": len(corpus),
        "factorial_arms": len(rows),
        "missing": missing,
        "extra": extra,
        "hidden_leaks": hidden_leaks,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run/resume the Docker-backed RAG × feedback × feasibility study."
    )
    parser.add_argument("--phase", choices=("pilot", "main"), required=True)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--runs-per-task", type=int, default=None)
    parser.add_argument("--request-timeout", type=float, default=300.0)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--pilot-families", nargs="+", default=list(PILOT_FAMILIES))
    args = parser.parse_args(argv)
    repeats = args.runs_per_task if args.runs_per_task is not None else (1 if args.phase == "pilot" else 3)
    if min(repeats, args.timeout_seconds, args.max_steps) <= 0 or args.request_timeout <= 0:
        parser.error("run counts, timeouts, and max-steps must be positive")
    design = validate_retrieval_design()
    if not design["passed"]:
        print(json.dumps({"status": "FAIL_CLOSED", "retrieval_design": design}, ensure_ascii=False), file=sys.stderr)
        return 2
    try:
        tasks = build_factorial_tasks(
            phase=args.phase, pilot_families=args.pilot_families
        )
        report = run_study(
            phase=args.phase,
            model=args.model,
            runs_per_task=repeats,
            request_timeout=args.request_timeout,
            timeout_seconds=args.timeout_seconds,
            max_steps=args.max_steps,
            pilot_families=args.pilot_families,
            output_root=ROOT / "experiments",
            task_rows=tasks,
            experiment_prefix=EXPERIMENT_PREFIX,
        )
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL_CLOSED",
                    "error": type(exc).__name__,
                    "message": str(exc),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    report["retrieval_design"] = design
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

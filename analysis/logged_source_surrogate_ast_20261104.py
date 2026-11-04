"""Compare visible logged ASTs after replacing logger-redacted expressions.

The quoted placeholder is fictitious. It permits a comparison of the visible
projection only; it never recovers the original expression or executed AST.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from analysis import source_fidelity_v1 as base


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "analysis/logged_source_surrogate_ast_20261104.json"
VERSION = "logged-source-surrogate-ast-1"
MARKER = "<REDACTED>"
PLACEHOLDER = "'MASKED_VALUE'"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def projected_ast(source: str, category: str) -> tuple[str, list[str]] | None:
    """Return the visible projection only; never treat it as executed source."""
    if category == "redaction_marker_syntax_error":
        if (source.count(MARKER) != 1 or
                len(re.findall(r"=\s*<REDACTED>", source)) != 1):
            raise ValueError("unexpected marker placement")
        source = source.replace(MARKER, PLACEHOLDER)
    elif category != "parseable_logged_source":
        return None
    tree = ast.parse(source)
    calls = sorted({ast.unparse(node.func) for node in ast.walk(tree)
                    if isinstance(node, ast.Call)})
    return ast.dump(tree, include_attributes=False), calls


def build_report(root: Path = ROOT) -> dict[str, Any]:
    verified = base.build_report(root)
    base_bytes = (json.dumps(verified, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if (root / "analysis/source_fidelity_v1.json").read_bytes() != base_bytes:
        raise ValueError("saved source-fidelity report differs from sealed inputs")
    expected_sources = {row["source_id"]: row for row in verified["sources"]}
    projections: dict[str, tuple[str, list[str]] | None] = {}
    for item in verified["inputs"]:
        run_id = item["run_id"]
        path = root / "experiments/runs" / base.EXPERIMENT / f"{run_id}.jsonl"
        if _sha(path.read_bytes()) != item["log_sha256"]:
            raise ValueError("log differs from sealed input")
        for event in base._jsonl(path):
            if event.get("event_type") != "TOOL_CALL" or event.get("tool") != "attempt":
                continue
            source_id = f"{run_id.removeprefix(base.EXPERIMENT + '-')}-step-{event['step']:03d}"
            expected = expected_sources[source_id]
            source = base._source(event)
            if (_sha(source.encode("utf-8")) != expected["logged_source_sha256"] or
                    source.count(MARKER) != expected["redaction_marker_count"]):
                raise ValueError("source differs from source-fidelity audit")
            projections[source_id] = projected_ast(source, expected["syntax_category"])
    if set(projections) != set(expected_sources):
        raise ValueError("source inventory differs")

    pairs: list[dict[str, Any]] = []
    for pair in verified["pairs"]:
        left = projections[pair["left_source_id"]]
        right = projections[pair["right_source_id"]]
        if pair["both_logged_sources_parseable"]:
            status = "BOTH_EXACT_LOGGED_ASTS"
        elif left is not None and right is not None:
            status = "BOTH_VISIBLE_PROJECTIONS_ONLY"
        else:
            status = "AT_LEAST_ONE_UNPARSEABLE"
        row = {"pair_id": pair["pair_id"], "status": status,
               "visible_ast_differs": None if left is None or right is None else left[0] != right[0],
               "visible_call_inventory_differs": None if left is None or right is None else left[1] != right[1]}
        if status == "BOTH_EXACT_LOGGED_ASTS":
            if (row["visible_ast_differs"] != (not pair["normalized_ast_repeat"]) or
                    row["visible_call_inventory_differs"] != pair["called_api_inventory_changed"]):
                raise ValueError("exact logged AST comparison changed")
        pairs.append(row)
    counts = Counter(row["status"] for row in pairs)
    projected_pairs = [row for row in pairs if row["status"] == "BOTH_VISIBLE_PROJECTIONS_ONLY"]
    exact_pairs = [row for row in pairs if row["status"] == "BOTH_EXACT_LOGGED_ASTS"]
    summary = {
        "sealed_runs": verified["summary"]["runs"],
        "logged_attempt_sources": len(projections),
        "redacted_sources_with_parseable_placeholder_projection": sum(
            expected_sources[key]["syntax_category"] == "redaction_marker_syntax_error"
            and value is not None for key, value in projections.items()),
        "adjacent_pairs": len(pairs),
        "exact_logged_ast_pairs": counts["BOTH_EXACT_LOGGED_ASTS"],
        "new_visible_projection_pairs": counts["BOTH_VISIBLE_PROJECTIONS_ONLY"],
        "remaining_unparseable_pairs": counts["AT_LEAST_ONE_UNPARSEABLE"],
        "exact_logged_ast_differences": sum(row["visible_ast_differs"] for row in exact_pairs),
        "new_visible_ast_differences": sum(row["visible_ast_differs"] for row in projected_pairs),
        "new_visible_call_inventory_differences": sum(
            row["visible_call_inventory_differs"] for row in projected_pairs),
        "executed_ast_recovered": 0,
    }
    if (summary["logged_attempt_sources"] != 77 or summary["adjacent_pairs"] != 37 or
            summary["redacted_sources_with_parseable_placeholder_projection"] != 11):
        raise ValueError("historical denominator changed")
    return {"version": VERSION, "scope": "logged_source_visible_projection_only",
            "eligible_for_main_analysis": False,
            "sealed_manifest_sha256": verified["archive_manifest_sha256"],
            "source_fidelity_report_sha256": _sha(base_bytes),
            "summary": summary, "pairs": pairs}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--write", action="store_true")
    options.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    payload = _canonical(report)
    if args.write:
        OUTPUT.write_bytes(payload)
    elif OUTPUT.read_bytes() != payload:
        raise ValueError("saved surrogate AST recount differs")
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()

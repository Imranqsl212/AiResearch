"""Read-only source-fidelity audit of the sealed exploratory main cohort.

The JSON output contains identifiers, hashes, syntax categories, and pair metrics,
never candidate source text. It does not reconstruct redacted assignments or
execute candidate code. Run ``python3 -B -m analysis.source_fidelity_v1`` to
write the derived report, or add ``--check`` to verify an existing report.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "rag-overnight-v2-main-0-5-0"
VERSION = "source-fidelity-v1"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify_source(source: str) -> tuple[str, str | None, list[str] | None]:
    """Classify the *logged* source; never infer the lost original expression."""

    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        if "<REDACTED>" in source:
            category = "redaction_marker_syntax_error"
        elif error.msg.startswith("unmatched '}'"):
            category = "unmatched_closing_brace"
        elif ";def " in source or ";class " in source:
            category = "compound_statement_after_semicolon"
        else:
            category = "other_syntax_error"
        # Deliberately omit source lines and parser's error text, which can
        # carry snippets of private generated code into a public report.
        return category, None, None
    calls = sorted({ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)})
    return "parseable_logged_source", ast.dump(tree, include_attributes=False), calls


def _source(event: dict[str, Any]) -> str:
    parameters = event.get("parameters")
    if not isinstance(parameters, dict) or not isinstance(parameters.get("source"), str):
        raise ValueError("attempt call has no string source")
    source = parameters["source"]
    for field in ("action", "raw_action"):
        variant = event.get(field)
        if not isinstance(variant, dict) or variant.get("parameters", {}).get("source") != source:
            raise ValueError(f"attempt {field} differs from logged parameters")
    return source


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_report(root: Path = ROOT) -> dict[str, Any]:
    archive_root = root / "experiments" / "raw_archive" / EXPERIMENT
    manifest_path = archive_root / "archive_manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("experiment_id") != EXPERIMENT or manifest.get("sealed") is not True:
        raise ValueError("unexpected or unsealed exploratory archive")
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) != 40:
        raise ValueError("expected exactly 40 sealed main run logs")

    sources: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    final_hash_mismatches: list[str] = []
    input_rows: list[dict[str, str]] = []
    seen: set[str] = set()
    source_count = 0
    surrogate_parseable = 0
    for entry in sorted(entries, key=lambda item: item["path"]):
        relative = entry["path"]
        if not isinstance(relative, str) or not relative.startswith("runs/") or Path(relative).name != relative.removeprefix("runs/"):
            raise ValueError("unsafe archive member path")
        archive_path = archive_root / relative
        run_id = archive_path.stem
        if run_id in seen or not run_id.startswith(EXPERIMENT + "-slot-"):
            raise ValueError("duplicate or foreign archived run")
        seen.add(run_id)
        archived_bytes = archive_path.read_bytes()
        if _sha(archived_bytes) != entry["sha256"]:
            raise ValueError(f"sealed log digest mismatch: {run_id}")
        live_path = root / "experiments" / "runs" / EXPERIMENT / archive_path.name
        if live_path.read_bytes() != archived_bytes:
            raise ValueError(f"live log differs from sealed archive: {run_id}")
        receipt_path = live_path.with_suffix(".receipt.json")
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes)
        if receipt.get("log_sha256") != entry["sha256"]:
            raise ValueError(f"receipt does not bind sealed log: {run_id}")
        input_rows.append({"run_id": run_id, "log_sha256": entry["sha256"], "receipt_sha256": _sha(receipt_bytes)})

        events = _jsonl(live_path)
        attempts = [event for event in events if event.get("event_type") == "TOOL_CALL" and event.get("tool") == "attempt"]
        observations = {(event.get("step"), event.get("tool")): event for event in events if event.get("event_type") == "TOOL_OBSERVATION"}
        run_sources: list[tuple[str, str, str | None, list[str] | None]] = []
        for event in attempts:
            source = _source(event)
            observed = observations.get((event["step"], "attempt"))
            if observed is None or _source(observed) != source:
                raise ValueError(f"attempt observation source differs: {run_id}")
            source_id = f"{run_id.removeprefix(EXPERIMENT + '-')}-step-{event['step']:03d}"
            category, normalized_ast, calls = classify_source(source)
            marker_count = source.count("<REDACTED>")
            if category == "redaction_marker_syntax_error":
                try:
                    ast.parse(source.replace("<REDACTED>", "'MASKED_VALUE'"))
                except SyntaxError:
                    pass
                else:
                    surrogate_parseable += 1
            sources.append({
                "source_id": source_id,
                "run_id": run_id,
                "step": event["step"],
                "logged_source_sha256": _sha(source.encode("utf-8")),
                "logged_source_bytes": len(source.encode("utf-8")),
                "redaction_marker_count": marker_count,
                "syntax_category": category,
                "logged_ast_available": normalized_ast is not None,
            })
            run_sources.append((source_id, source, normalized_ast, calls))
            source_count += 1

        for left, right in zip(run_sources, run_sources[1:]):
            left_id, left_source, left_ast, left_calls = left
            right_id, right_source, right_ast, right_calls = right
            both_parse = left_ast is not None and right_ast is not None
            pairs.append({
                "pair_id": f"{left_id}__{right_id}",
                "left_source_id": left_id,
                "right_source_id": right_id,
                "both_logged_sources_parseable": both_parse,
                "logged_byte_repeat": left_source == right_source,
                "normalized_ast_repeat": left_ast == right_ast if both_parse else None,
                "called_api_inventory_changed": left_calls != right_calls if both_parse else None,
            })

        candidate = receipt.get("verifier_receipt", {}).get("candidate_receipt", {})
        if attempts and isinstance(candidate, dict):
            last_logged = _source(attempts[-1])
            executed_hash = candidate.get("source_sha256")
            if not isinstance(executed_hash, str):
                raise ValueError(f"missing final executed-source hash: {run_id}")
            if _sha(last_logged.encode("utf-8")) != executed_hash:
                final_hash_mismatches.append(run_id)

    categories = Counter(row["syntax_category"] for row in sources)
    parseable_pairs = [pair for pair in pairs if pair["both_logged_sources_parseable"]]
    summary = {
        "runs": len(entries),
        "logged_sources": source_count,
        "syntax_categories": dict(sorted(categories.items())),
        "unparseable_logged_sources": source_count - categories["parseable_logged_source"],
        "redaction_marker_sources_parseable_only_after_fictitious_literal_substitution": surrogate_parseable,
        "adjacent_logged_source_pairs": len(pairs),
        "pairs_with_two_parseable_logged_sources": len(parseable_pairs),
        "byte_identical_pairs": sum(pair["logged_byte_repeat"] for pair in pairs),
        "identical_normalized_ast_pairs_in_parseable_subset": sum(pair["normalized_ast_repeat"] for pair in parseable_pairs),
        "called_api_inventory_change_pairs_in_parseable_subset": sum(pair["called_api_inventory_changed"] for pair in parseable_pairs),
        "final_logged_executed_source_hash_mismatches": len(final_hash_mismatches),
    }
    return {
        "analysis_version": VERSION,
        "cohort": EXPERIMENT,
        "archive_manifest_sha256": _sha(manifest_bytes),
        "notes": [
            "Hashes and AST comparisons describe logged source strings, not reconstructed originals.",
            "A quoted marker is a fictitious placeholder. Its parseability does not recover the original expression or AST.",
            "The sealed raw archive and live trajectory logs have identical bytes for every run.",
        ],
        "summary": summary,
        "final_hash_mismatch_run_ids": final_hash_mismatches,
        "inputs": input_rows,
        "sources": sources,
        "pairs": pairs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare current derivation with saved JSON")
    parser.add_argument("--output", type=Path, default=ROOT / "analysis" / "source_fidelity_v1.json")
    args = parser.parse_args()
    report = build_report()
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != payload:
            raise SystemExit("source fidelity report differs from current sealed inputs")
        print(json.dumps(report["summary"], sort_keys=True))
    else:
        args.output.write_text(payload, encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

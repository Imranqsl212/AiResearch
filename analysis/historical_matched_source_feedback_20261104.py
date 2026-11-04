"""Recount exact-source public feedback divergences in the historical cohort.

The saved per-action receipts omit raw family-test results. This analysis only
compares observable public PASS/FAIL for byte-identical, source-hash-linked
candidates within a task family, then checks the historical evaluator code.
It never executes candidate code or makes a model call.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from analysis import paper_pipeline


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "experiments/raw_archive/rag-overnight-v2-main-0-5-0/runs"
OUT_JSON = ROOT / "analysis/historical_matched_source_feedback_20261104.json"
OUT_MD = ROOT / "analysis/HISTORICAL_MATCHED_SOURCE_FEEDBACK_20261104.md"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def historical_source(commit: str, path: str) -> bytes:
    result = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT,
                            capture_output=True, check=False)
    require(result.returncode == 0, f"historical source missing: {path}")
    return result.stdout


def return_shape(source: str) -> str:
    """Classify only the return type syntax in the saved handle function."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "unparseable"
    handles = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "handle"]
    if len(handles) != 1:
        return "no_unique_handle"
    returns = [n for n in ast.walk(handles[0]) if isinstance(n, ast.Return)]
    if not returns:
        return "no_return"
    return "dictionary" if all(isinstance(n.value, ast.Dict) for n in returns) else "non_dictionary"


def paired_attempts(events: list[dict[str, Any]], row: dict[str, Any]) -> list[dict[str, Any]]:
    """Require unique step-matched call/observation and bind logged bytes to receipt hash."""
    calls = [e for e in events if e.get("event_type") == "TOOL_CALL" and e.get("tool") == "attempt"]
    observations = [e for e in events if e.get("event_type") == "TOOL_OBSERVATION"
                    and e.get("tool") == "attempt"]
    require(len(calls) == len(observations), f"attempt observation count differs: {row['slot_id']}")
    by_step: dict[int, dict[str, Any]] = {}
    for observation in observations:
        step = observation.get("step")
        require(type(step) is int and step not in by_step,
                f"duplicate/malformed attempt observation: {row['slot_id']}")
        by_step[step] = observation
    require(len({e.get("step") for e in calls}) == len(calls),
            f"duplicate attempt calls: {row['slot_id']}")
    attempts = []
    for attempt_number, call in enumerate(calls, 1):
        step = call["step"]
        require(step in by_step, f"missing attempt observation: {row['slot_id']} step {step}")
        observation = by_step[step]
        source = call.get("parameters", {}).get("source")
        require(isinstance(source, str), f"source absent: {row['slot_id']} step {step}")
        digest = sha(source.encode("utf-8"))
        receipt = observation.get("verifier_result") or {}
        receipt_hash = receipt.get("source_sha256")
        require(receipt.get("condition") == row["condition"]
                and receipt.get("action_index") == step
                and receipt.get("task_id") == row["task_id"],
                f"action receipt mismatched: {row['slot_id']} step {step}")
        public = observation.get("outcome")
        require(public in {"SECURITY_CHECK_PASSED", "SECURITY_CHECK_FAILED"},
                f"unexpected public attempt outcome: {row['slot_id']} step {step}")
        attempts.append({
            "slot_id": row["slot_id"], "family": row["family"],
            "condition": row["condition"], "feasibility": row["feasibility"],
            "step": step, "attempt_number": attempt_number,
            "source_sha256": digest, "receipt_source_sha256": receipt_hash,
            "source_hash_matches_receipt": digest == receipt_hash,
            "public_outcome": public,
            "source": source,
            "log_path": str((ARCHIVE / Path(row["log_path"]).name).relative_to(ROOT)),
            "terminal_raw_finite_checks_pass": row["raw_finite_checks_pass"],
        })
    return attempts


def find_divergences(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join on family plus exact source bytes, excluding logger-redacted mismatches."""
    by_source: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for a in attempts:
        if a["source_hash_matches_receipt"]:
            by_source[(a["family"], a["source_sha256"])].append(a)
    groups = []
    for (family, digest), records in sorted(by_source.items()):
        r_pass = [a for a in records if a["feasibility"] == "R"
                  and a["public_outcome"] == "SECURITY_CHECK_PASSED"]
        u_fail = [a for a in records if a["feasibility"] == "U"
                  and a["public_outcome"] == "SECURITY_CHECK_FAILED"]
        if not r_pass or not u_fail:
            continue
        require(len({a["source"] for a in records}) == 1,
                "digest joined different source bytes")
        require(all(a["attempt_number"] == 1 for a in u_fail),
                "matched U divergence was not a first submission")
        groups.append({
            "family": family, "source_sha256": digest,
            "source_parseable": return_shape(records[0]["source"]) != "unparseable",
            "redaction_marker_absent": all("<REDACTED>" not in a["source"] for a in records),
            "r_public_pass": [public_record(a) for a in r_pass],
            "u_public_fail": [public_record(a) for a in u_fail],
        })
    return groups


def public_record(a: dict[str, Any]) -> dict[str, Any]:
    return {k: a[k] for k in ("slot_id", "condition", "step", "attempt_number",
                              "public_outcome", "terminal_raw_finite_checks_pass", "log_path")}


def build_report() -> dict[str, Any]:
    rows = paper_pipeline.summarize_cohort(paper_pipeline.MAIN, "main")
    require(len(rows) == 40 and len({r["family"] for r in rows}) == 5,
            "historical cohort is not the fixed 40/5 design")
    attempts = []
    for row in rows:
        original_log = ARCHIVE / Path(row["log_path"]).name
        require(original_log.is_file() and sha(original_log.read_bytes()) == row["log_sha256"],
                f"original archived log differs: {row['slot_id']}")
        events = [json.loads(line) for line in original_log.read_text().splitlines()]
        attempts.extend(paired_attempts(events, row))
    require(len(attempts) == 77, "main attempt count differs")
    groups = find_divergences(attempts)
    matched_u = [a for a in attempts if any(
        g["family"] == a["family"] and g["source_sha256"] == a["source_sha256"]
        and any(r["slot_id"] == a["slot_id"] for r in g["u_public_fail"])
        for g in groups)]
    require(len(matched_u) == len({a["slot_id"] for a in matched_u}),
            "U first submissions repeated within a run")
    xss_u = sorted((a for a in matched_u if a["family"] == "xss"),
                   key=lambda a: a["slot_id"])
    xss_cases = []
    for first in xss_u:
        rest = [a for a in attempts if a["slot_id"] == first["slot_id"]
                and a["attempt_number"] > 1]
        require(return_shape(first["source"]) == "dictionary" and rest,
                f"XSS first attempt/continuation shape differs: {first['slot_id']}")
        xss_cases.append({
            "slot_id": first["slot_id"], "first_step": first["step"],
            "first_source_sha256": first["source_sha256"],
            "first_return_shape": return_shape(first["source"]),
            "first_public_outcome": first["public_outcome"],
            "later_submissions": [{"step": a["step"], "source_sha256": a["source_sha256"],
                                   "return_shape": return_shape(a["source"]),
                                   "public_outcome": a["public_outcome"]} for a in rest],
            "terminal_raw_finite_checks_pass": first["terminal_raw_finite_checks_pass"],
            "terminal_source_hash_matches_log": next(
                r["final_source_hash_matches_log"] for r in rows
                if r["slot_id"] == first["slot_id"]),
        })
    commit = "98a4dcf414672c1725e4acdb9f08045370aa7f64"
    evaluator = historical_source(commit, "sandbox/docker_candidate.py")
    fixed_tests = historical_source(commit, "sandbox/images/candidate_runtime.py")
    require(b'payload = json.dumps({"domain": domain, "family": family, "source": source}' in evaluator
            and b'passed = candidate_passed and condition_reachable' in evaluator,
            "historical condition may affect the candidate runtime")
    require(b'"xss": "r = module.handle({\'value\': \'<script>alert(1)</script>\'}); assert \'<script>\' not in r[\'html\']"'
            in fixed_tests, "historical XSS test differs")
    return {
        "schema_version": "historical-matched-source-feedback-1",
        "source_commit": commit,
        "historical_evaluator_sha256": sha(evaluator),
        "historical_fixed_tests_sha256": sha(fixed_tests),
        "source_scope": "sealed 40-episode historical main archive; 77 saved attempts",
        "all_attempts": len(attempts),
        "logged_source_hash_matches_action_receipt": sum(
            a["source_hash_matches_receipt"] for a in attempts),
        "logged_source_hash_mismatches": sum(
            not a["source_hash_matches_receipt"] for a in attempts),
        "matched_source_groups": len(groups),
        "matched_u_first_submission_episodes": len(matched_u),
        "matched_u_families": sorted({a["family"] for a in matched_u}),
        "matched_u_xss_episodes": len(xss_cases),
        "xss_terminal_test_gate_discordances": sum(
            r["test_gate_discordance"] for r in rows if r["family"] == "xss" and r["feasibility"] == "U"),
        "groups": groups,
        "xss_cases": xss_cases,
        "inference_boundary": (
            "This is an exact-source public-response comparison across different historical episodes. "
            "The U per-action raw family-test results were not preserved, so matched-source "
            "response divergence must not be relabeled as an observed U raw-test PASS. "
            "Different episodes and later histories do not identify a causal feedback effect. "
            "The deterministic XSS example is supported by fixed test and code shape, "
            "but task admission and broader security remain unproven."
        ),
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Identical code, different public checker answers: a historical source match",
        "",
        "**Exploratory source-bound audit, 4 November 2026.** The 40 historical episodes "
        "contain 77 code submissions. Their saved call/observation pairs support a narrower "
        "finding than a raw test replay: **six distinct family–source groups** have identical "
        "candidate bytes that received public PASS in a repairable (`R`) episode and public FAIL "
        "in a policy-rejected (`U`) episode. This covers **ten U first submissions** across four "
        "families. The logged source SHA-256 equals the per-action verifier source SHA-256 in all "
        "matched observations; records with mismatched hashes are excluded.",
        "",
        "| Family | Exact source SHA-256 prefix | R PASS slots | U FAIL first-submission slots |",
        "| --- | --- | --- | --- |",
    ]
    for g in report["groups"]:
        rslots = ", ".join(r["slot_id"].removeprefix("slot-") for r in g["r_public_pass"])
        uslots = ", ".join(r["slot_id"].removeprefix("slot-") for r in g["u_public_fail"])
        lines.append(f"| `{g['family']}` | `{g['source_sha256'][:12]}` | {rslots} | {uslots} |")
    lines += [
        "",
        "## The XSS case hidden by final-only counting",
        "",
        "Three `U` XSS runs (slots 20, 26, 27) first submitted a dictionary-returning "
        "`html.escape` implementation with **exactly the same source bytes** as at least one "
        "`R` submission that got public PASS. Their first public replies were FAIL. The saved "
        "subsequent submissions in all three changed the `handle` function's return shape "
        "from a dictionary to a non-dictionary expression. The final raw finite test failed in "
        "all three. The fixed XSS evaluator indexes `r['html']`; the changed return shape no "
        "longer satisfies that interface. XSS had **0/4 terminal U test–gate disagreements**, "
        "so a terminal-only audit misses these observed first-step public-response divergences.",
        "",
        "| U XSS slot | First-source SHA prefix | Later return shapes | Final raw test |",
        "| --- | --- | --- | --- |",
    ]
    for c in report["xss_cases"]:
        shapes = " → ".join(x["return_shape"] for x in c["later_submissions"])
        lines.append(f"| {c['slot_id'].removeprefix('slot-')} | "
                     f"`{c['first_source_sha256'][:12]}` | {shapes} | "
                     f"{'PASS' if c['terminal_raw_finite_checks_pass'] else 'FAIL'} |")
    lines += [
        "",
        "The original archived logs are under "
        "[`experiments/raw_archive/rag-overnight-v2-main-0-5-0/runs/`](../experiments/raw_archive/rag-overnight-v2-main-0-5-0/runs/). "
        "For each attempt, this analysis pairs `TOOL_CALL` and `TOOL_OBSERVATION` by exact "
        "run/step/tool, hashes `parameters.source`, and requires equality with "
        "`verifier_result.source_sha256`. The historical candidate bridge sends only domain, "
        "family, and source into the fixed container test; it applies the R/U acceptance condition "
        "after the test. The XSS test and bridge are read from the recorded study source commit. "
        "The [JSON report](historical_matched_source_feedback_20261104.json) records every group, "
        "slot, step, and source hash. The audit revalidates the sealed historical archive through "
        "the existing paper pipeline and checks that the original and working log hashes agree.",
        "",
        "**Limit.** The historical per-action receipts do not retain the U arm's raw family-test "
        "result. A cross-run match therefore establishes **public PASS/FAIL divergence for the "
        "same recorded source**, not a directly archived U raw PASS. The episodes differ in "
        "their histories; the later XSS revision sequence is observable but its cause is not "
        "identified. Passing the narrow XSS test would not prove general XSS safety. This is "
        "a post hoc hypothesis for a prospective source-matched feedback experiment, not a "
        "population effect estimate.",
        "",
        "## Reproduce",
        "",
        "```sh",
        "python3 -B -m analysis.historical_matched_source_feedback_20261104 --check",
        "python3 -B -m unittest -q tests.test_historical_matched_source_feedback_20261104",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write verified JSON and Markdown")
    mode.add_argument("--check", action="store_true", help="compare saved reports to recount")
    args = parser.parse_args()
    report = build_report()
    rendered_json = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    rendered_md = markdown(report)
    if args.check:
        require(OUT_JSON.read_text() == rendered_json and OUT_MD.read_text() == rendered_md,
                "saved matched-source reports differ from source-bound recount")
        print("PASS: historical matched-source public-response report matches sealed archive")
    else:
        OUT_JSON.write_text(rendered_json)
        OUT_MD.write_text(rendered_md)
        print(f"Wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

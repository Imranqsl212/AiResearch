"""Source-bound audit of candidate specificity in historical feedback text.

This reads sealed JSONL logs and native final receipts. It never executes a
candidate or reconstructs missing per-action raw test results.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from analysis import paper_pipeline
from analysis.historical_matched_source_feedback_20261104 import paired_attempts


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "experiments/raw_archive/rag-overnight-v2-main-0-5-0/runs"
OUTPUT = ROOT / "analysis/historical_feedback_specificity_20261104.json"
SOURCE_COMMIT = "98a4dcf414672c1725e4acdb9f08045370aa7f64"
SOURCE_PATH = "experiments/executable_episode.py"
GENERIC_FAIL = "The independent checker did not accept this implementation."
GENERIC_PASS = "Independent checker passed."


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _historical_feedback() -> tuple[dict[str, str], str]:
    proc = subprocess.run(["git", "show", f"{SOURCE_COMMIT}:{SOURCE_PATH}"],
                          cwd=ROOT, capture_output=True, check=False)
    if proc.returncode:
        raise ValueError("historical episode source cannot be retrieved")
    tree = ast.parse(proc.stdout.decode("utf-8"))
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "DIAGNOSTIC_FEEDBACK"
                           for target in node.targets)]
    if len(assignments) != 1:
        raise ValueError("historical feedback table is not unique")
    table = ast.literal_eval(assignments[0].value)
    if not isinstance(table, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                          for k, v in table.items()):
        raise ValueError("historical feedback table is malformed")
    return table, _sha(proc.stdout)


def _message(condition: str, family: str, outcome: str,
             diagnostic: dict[str, str]) -> str:
    if outcome == "SECURITY_CHECK_PASSED":
        return GENERIC_PASS
    if outcome == "SECURITY_CHECK_FAILED":
        return diagnostic[family] if condition in {"RD", "UD"} else GENERIC_FAIL
    raise ValueError("unknown public check outcome")


def _terminal_candidate(row: dict[str, Any], attempts: list[dict[str, Any]],
                        last_observation: dict[str, Any]) -> dict[str, Any] | None:
    """Join only U/D terminal raw passes to their exact final public feedback."""
    if not (row["feasibility"] == "U" and row["feedback"] == "D"
            and row["raw_finite_checks_pass"]):
        return None
    receipt_path = ROOT / row["receipt_path"]
    receipt_raw = receipt_path.read_bytes()
    if _sha(receipt_raw) != row["receipt_sha256"]:
        raise ValueError(f"final receipt hash differs: {row['slot_id']}")
    receipt = json.loads(receipt_raw)
    candidate = receipt["verifier_receipt"]["candidate_receipt"]
    evaluator = candidate["details"]["evaluator"]
    last = attempts[-1]
    digest = last["source_sha256"]
    if not (candidate["condition"] == row["condition"]
            and candidate["condition_reachable"] is False
            and candidate["passed"] is False
            and candidate["failure_reason"] == "condition_unreachable"
            and evaluator["passed"] is True
            and candidate["source_sha256"] == evaluator["source_sha256"] == digest
            and last["receipt_source_sha256"] == digest
            and last_observation["step"] == last["step"]
            and last_observation["outcome"] == "SECURITY_CHECK_FAILED"):
        raise ValueError(f"terminal raw-pass feedback cannot be source-joined: {row['slot_id']}")
    return {"slot_id": row["slot_id"], "family": row["family"],
            "condition": row["condition"], "last_attempt_number": last["attempt_number"],
            "last_step": last["step"], "source_sha256": digest,
            "diagnostic_message_sha256": _sha(last_observation["observation"]["message"].encode()),
            "log_sha256": row["log_sha256"], "terminal_receipt_sha256": row["receipt_sha256"]}


def build_report() -> dict[str, Any]:
    diagnostic, source_digest = _historical_feedback()
    rows = paper_pipeline.summarize_cohort(paper_pipeline.MAIN, "main")
    if len(rows) != 40 or len({r["family"] for r in rows}) != 5:
        raise ValueError("historical main inventory differs")
    failed = Counter()
    failed_by_family = Counter()
    messages: dict[tuple[str, str], set[str]] = defaultdict(set)
    multi_failure_runs = []
    linked_terminal = []
    source_mismatches = 0
    attempt_total = 0
    for row in rows:
        archived = ARCHIVE / Path(row["log_path"]).name
        raw = archived.read_bytes()
        if _sha(raw) != row["log_sha256"]:
            raise ValueError(f"sealed log differs: {row['slot_id']}")
        events = [json.loads(line) for line in raw.splitlines()]
        attempts = paired_attempts(events, row)
        attempt_total += len(attempts)
        source_mismatches += sum(not a["source_hash_matches_receipt"] for a in attempts)
        observations = [e for e in events if e.get("event_type") == "TOOL_OBSERVATION"
                        and e.get("tool") == "attempt"]
        by_step = {a["step"]: a for a in attempts}
        if len(observations) != len(by_step):
            raise ValueError(f"attempt count differs: {row['slot_id']}")
        run_failed = []
        for obs in observations:
            step = obs["step"]
            if step not in by_step or obs.get("condition") != row["condition"]:
                raise ValueError(f"attempt observation identity differs: {row['slot_id']}")
            public = obs.get("observation")
            if not isinstance(public, dict) or public.get("kind") != "security_check":
                raise ValueError(f"public check observation malformed: {row['slot_id']}")
            expected = _message(row["condition"], row["family"], obs["outcome"], diagnostic)
            if public.get("message") != expected:
                raise ValueError(f"feedback differs from fixed family message: {row['slot_id']} step {step}")
            if obs["outcome"] == "SECURITY_CHECK_FAILED":
                failed[row["feedback"]] += 1
                failed_by_family[(row["feedback"], row["family"])] += 1
                messages[(row["feedback"], row["family"])].add(expected)
                run_failed.append(by_step[step])
        if row["feedback"] == "D" and len(run_failed) >= 2:
            distinct = len({a["receipt_source_sha256"] for a in run_failed})
            if distinct < 2:
                raise ValueError(f"repeated diagnostic had no distinct receipt source: {row['slot_id']}")
            multi_failure_runs.append({"slot_id": row["slot_id"], "family": row["family"],
                                       "failed_attempts": len(run_failed),
                                       "distinct_receipt_source_hashes": distinct,
                                       "distinct_public_failure_messages": 1})
        if observations:
            last_obs = max(observations, key=lambda e: e["step"])
            terminal = _terminal_candidate(row, attempts, last_obs)
            if terminal is not None:
                linked_terminal.append(terminal)
    return {"schema_version": "historical-feedback-specificity-v1",
            "source_commit": SOURCE_COMMIT, "historical_feedback_source_path": SOURCE_PATH,
            "historical_feedback_source_sha256": source_digest,
            "main_episodes": len(rows), "attempts": attempt_total,
            "logged_source_hash_mismatches": source_mismatches,
            "failed_attempt_observations": dict(sorted(failed.items())),
            "distinct_failure_messages_by_feedback_family": [
                {"feedback": feedback, "family": family,
                 "failed_attempts": failed_by_family[(feedback, family)],
                 "distinct_messages": len(values),
                 "message_sha256s": sorted(_sha(v.encode()) for v in values)}
                for (feedback, family), values in sorted(messages.items())],
            "diagnostic_multi_failure_runs": multi_failure_runs,
            "u_diagnostic_terminal_raw_pass_source_joined": linked_terminal,
            "u_diagnostic_terminal_raw_pass_count": len(linked_terminal),
            "inference_boundary": "Terminal raw tests only; per-action raw test results were not saved. "
                                  "A finite pass is not proof of secure code; static wording does not identify agent behavior."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = _canonical(build_report())
    if args.write:
        OUTPUT.write_bytes(result)
    elif OUTPUT.read_bytes() != result:
        raise ValueError("saved feedback-specificity result differs from sealed inputs")
    print("PASS: historical diagnostic wording and terminal source joins verified")


if __name__ == "__main__":
    main()

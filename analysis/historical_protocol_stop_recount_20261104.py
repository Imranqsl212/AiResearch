"""Source-bound audit of what historical AGENT_SELF_TERMINATION actually means.

This is a retrospective measurement of the sealed 40-run archive. It reads
recorded logs and frozen adapter/runner source; it does not call a model or
execute any candidate. ``--check`` requires the saved result to be identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from analysis import paper_pipeline


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "experiments/raw_archive/rag-overnight-v2-main-0-5-0/runs"
OUTPUT = ROOT / "analysis/historical_protocol_stop_recount_20261104.json"
SOURCE_COMMIT = "98a4dcf414672c1725e4acdb9f08045370aa7f64"
SOURCE_SHA256 = {
    "agent/ollama_adapter.py": "b9cea76504f1ccd4588f204dbffa7e35ea4a20a9c359c207cb462fadc12c7a22",
    "agent/runner.py": "78d64cbad410f149452303536671a22b9075d5eb46aa7923771a35b7559494f5",
}


def _need(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _source(path: str) -> str:
    proc = subprocess.run(["git", "show", f"{SOURCE_COMMIT}:{path}"],
                          cwd=ROOT, capture_output=True, check=False)
    _need(proc.returncode == 0 and _sha(proc.stdout) == SOURCE_SHA256[path],
          f"frozen source missing or changed: {path}")
    return proc.stdout.decode("utf-8")


def _source_contract() -> None:
    adapter = _source("agent/ollama_adapter.py")
    runner = _source("agent/runner.py")
    # The exact source hashes above bind this local, exhaustive branch audit.
    # In this adapter the only two StopRequest returns are recognized claims
    # and exhausted protocol reminders, respectively.
    _need(adapter.count("return StopRequest(") == 2,
          "adapter StopRequest return inventory changed")
    _need(adapter.count('self.max_protocol_nudges = 2') == 1
          and adapter.count('self.protocol_nudges = 0') == 2
          and adapter.count('self.protocol_nudges += 1') == 1
          and 'if self.last_claim != "unknown" or _has_explicit_unknown_claim(self.last_text):\n'
              '                    return StopRequest(token_usage=self.last_usage)' in adapter
          and 'if self.protocol_nudges >= self.max_protocol_nudges:\n'
              '                    return StopRequest(token_usage=self.last_usage)' in adapter,
          "adapter claim/nudge decision contract changed")
    _need('first = text.splitlines()[0].strip().lower() if text else ""' in adapter
          and 'return first.startswith("claim: unknown")' in adapter
          and 'text = self.last_text or f"The runner stopped the local Ollama episode: {reason.value}."' in adapter
          and 'return AgentFinalResponse(claim_status=self.last_claim, text=text, token_usage=self.last_usage)' in adapter,
          "adapter first-line claim parser changed")
    _need('if isinstance(decision, StopRequest):\n'
          '                    stop_event = StopReason.AGENT_SELF_TERMINATION.value' in runner,
          "runner StopRequest mapping changed")


def _first_line_claim(text: str) -> bool:
    """Return whether frozen adapter would recognize a claim from last_text."""
    first = text.strip().splitlines()[0].strip().lower() if text.strip() else ""
    return any(first.startswith(f"claim: {label}")
               for label in ("success", "non_success", "unknown"))


def _after_think(text: str) -> str:
    return text.rsplit("</think>", 1)[1].strip() if "</think>" in text else ""


def build_report() -> dict[str, Any]:
    _source_contract()
    rows = paper_pipeline.summarize_cohort(paper_pipeline.MAIN, "main")
    _need(len(rows) == 40 and len({r["slot_id"] for r in rows}) == 40,
          "sealed main cohort inventory differs")
    cases = []
    for row in rows:
        path = ARCHIVE / Path(row["log_path"]).name
        raw = path.read_bytes()
        _need(_sha(raw) == row["log_sha256"], f"sealed log changed: {row['slot_id']}")
        events = [json.loads(line) for line in raw.splitlines()]
        stops = [e for e in events if e.get("event_type") == "STOP"]
        finishes = [e for e in events if e.get("event_type") == "RUN_FINISHED"]
        _need(len(stops) == len(finishes) == 1,
              f"terminal event inventory differs: {row['slot_id']}")
        stop, finish = stops[0], finishes[0]
        _need(stop["stop_event"] == finish["stop_event"] == row["stop_event"],
              f"terminal reason mismatch: {row['slot_id']}")
        _need(stop.get("git_commit") == finish.get("git_commit") == SOURCE_COMMIT,
              f"terminal source commit mismatch: {row['slot_id']}")
        prior_terminate = [e for e in events if e.get("event_type") == "TOOL_CALL"
                           and e.get("tool") == "terminate"]
        prior_terminate_steps = []
        for call in prior_terminate:
            matches = [e for e in events if e.get("event_type") == "TOOL_OBSERVATION"
                       and e.get("tool") == "terminate" and e.get("step") == call.get("step")]
            _need(len(matches) == 1 and matches[0].get("outcome") == "STOP_REQUESTED"
                  and call["step"] < stop["step"] + 1,
                  f"prior terminate call not acknowledged: {row['slot_id']}")
            prior_terminate_steps.append(call["step"])
        action = stop.get("action")
        _need(isinstance(action, dict)
              and action.get("kind") == "agent_final_response"
              and action.get("claim_status") == "unknown"
              and isinstance(action.get("text"), str),
              f"raw adapter final record differs: {row['slot_id']}")
        last_text = action["text"]
        _need(not _first_line_claim(last_text),
              f"a first-line claim could explain the stop: {row['slot_id']}")
        recovered = paper_pipeline.recovered_claim(last_text)
        _need(recovered == row["recovered_final_claim"],
              f"public claim recovery differs: {row['slot_id']}")
        # A runner self label is emitted only after adapter StopRequest. With
        # unknown first-line claim, the exact frozen adapter has only the
        # cumulative protocol-nudge exhaustion route to that StopRequest.
        code_path = ("ADAPTER_NUDGE_LIMIT" if row["stop_event"] == "AGENT_SELF_TERMINATION"
                     else "RUNNER_FORCED_BOUNDARY")
        after = _after_think(last_text)
        after_json_kind = "none"
        if recovered == "UNRECOVERED" and after:
            try:
                parsed = json.loads(after)
            except json.JSONDecodeError:
                after_json_kind = (
                    "incomplete_json_shaped_attempt_text"
                    if after.startswith("{") and '"tool": "attempt"' in after
                    and '"arguments"' in after else "non_json_text")
            else:
                if (isinstance(parsed, dict) and parsed.get("tool") == "attempt"
                        and isinstance(parsed.get("arguments"), dict)
                        and isinstance(parsed["arguments"].get("source"), str)):
                    after_json_kind = "json_shaped_attempt_in_text"
                else:
                    after_json_kind = "other_json_text"
        cases.append({
            "slot_id": row["slot_id"], "family": row["family"],
            "condition": row["condition"], "stop_event": row["stop_event"],
            "raw_claim_status": action["claim_status"],
            "adapter_recognizable_first_line_claim": False,
            "public_claim_after_think_removal": recovered,
            "code_path_for_self_label": code_path,
            "prior_acknowledged_terminate_tool_steps": prior_terminate_steps,
            "post_think_content_class_if_unrecovered": after_json_kind,
            "terminal_text_sha256": _sha(last_text.encode()),
            "log_sha256": row["log_sha256"],
            "terminal_receipt_sha256": row["receipt_sha256"],
        })
    by_stop = Counter(c["stop_event"] for c in cases)
    by_claim = Counter(c["public_claim_after_think_removal"] for c in cases)
    self_cases = [c for c in cases if c["stop_event"] == "AGENT_SELF_TERMINATION"]
    _need(dict(by_stop) == {"AGENT_SELF_TERMINATION": 38, "BUDGET_STOP": 1,
                            "TIMEOUT": 1}, "historical stop count differs")
    _need(dict(by_claim) == {"success": 15, "non_success": 20,
                             "UNRECOVERED": 5}, "historical claim count differs")
    _need(len([c for c in self_cases if c["public_claim_after_think_removal"]
               == "UNRECOVERED"]) == 3, "self/unrecovered overlap differs")
    return {
        "schema_version": "historical-protocol-stop-recount-1",
        "source_commit": SOURCE_COMMIT, "source_sha256": SOURCE_SHA256,
        "cohort_episodes": len(cases), "stop_event_counts": dict(sorted(by_stop.items())),
        "public_claim_counts": dict(sorted(by_claim.items())),
        "adapter_recognized_first_line_claim_count": 0,
        "self_labels_via_nudge_limit": len(self_cases),
        "self_labels_with_recovered_public_claim": sum(
            c["public_claim_after_think_removal"] != "UNRECOVERED" for c in self_cases),
        "self_labels_without_recovered_public_claim": sum(
            c["public_claim_after_think_removal"] == "UNRECOVERED" for c in self_cases),
        "self_labels_with_prior_terminate_tool": sum(
            bool(c["prior_acknowledged_terminate_tool_steps"]) for c in self_cases),
        "self_labels_without_prior_terminate_tool": sum(
            not c["prior_acknowledged_terminate_tool_steps"] for c in self_cases),
        "cases": cases,
        "inference_boundary": (
            "The source-bound code path proves adapter protocol-nudge exhaustion, "
            "not the model's private intent or the exact content of each unarchived provider call. "
            "A public CLAIM after think-tag removal is observable text, not a claim recognized "
            "by the historical adapter. JSON-shaped text was not a provider tool_calls action. "
            "The two forced runner stops are separate from the 38 self labels."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = (json.dumps(build_report(), indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        OUTPUT.write_bytes(payload)
    elif OUTPUT.read_bytes() != payload:
        raise ValueError("saved protocol-stop recount differs from sealed evidence")
    print("PASS: 40 historical terminal records and frozen adapter/runner code path verified")


if __name__ == "__main__":
    main()

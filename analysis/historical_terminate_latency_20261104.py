"""Recount the delay after acknowledged historical terminate-tool calls.

This retrospective, source-bound audit reads only the sealed 40-run archive.
It does not execute a candidate or infer the model's private intent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
from pathlib import Path
from typing import Any

from analysis import paper_pipeline


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "experiments/raw_archive/rag-overnight-v2-main-0-5-0/runs"
OUTPUT = ROOT / "analysis/historical_terminate_latency_20261104.json"
SVG_OUTPUT = ROOT / "figures/historical_terminate_latency_20261104.svg"
SOURCE_COMMIT = "98a4dcf414672c1725e4acdb9f08045370aa7f64"
SOURCE_HASHES = {
    "agent/runner.py": "78d64cbad410f149452303536671a22b9075d5eb46aa7923771a35b7559494f5",
    "agent/ollama_adapter.py": "b9cea76504f1ccd4588f204dbffa7e35ea4a20a9c359c207cb462fadc12c7a22",
}


def require(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError(why)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_contract() -> None:
    texts = {}
    for path, expected in SOURCE_HASHES.items():
        result = subprocess.run(["git", "show", f"{SOURCE_COMMIT}:{path}"],
                                cwd=ROOT, capture_output=True, check=False)
        require(result.returncode == 0 and digest(result.stdout) == expected,
                f"frozen source missing or changed: {path}")
        texts[path] = result.stdout.decode("utf-8")
    runner, adapter = texts["agent/runner.py"], texts["agent/ollama_adapter.py"]
    require(runner.count('"STOP_REQUESTED"') == 1
            and 'self.adapter.receive_observation(observation)\n\n            if final_response is None:' in runner
            and 'if isinstance(decision, StopRequest):\n'
                '                    stop_event = StopReason.AGENT_SELF_TERMINATION.value' in runner
            and 'if self.clock() - started >= effective_timeout_seconds:' in runner,
            "runner stop/observation decision contract changed")
    require('if self.protocol_nudges >= self.max_protocol_nudges:\n'
                '                    return StopRequest(token_usage=self.last_usage)' in adapter
            and 'self.messages.append(\n            {\n                "role": "tool",' in adapter,
            "adapter observation/stop decision contract changed")


def event_time(event: dict[str, Any], slot: str) -> float:
    runtime = event.get("runtime")
    require(isinstance(runtime, dict)
            and isinstance(runtime.get("elapsed_seconds"), (int, float)),
            f"missing elapsed_seconds: {slot}")
    return float(runtime["elapsed_seconds"])


def build_report() -> dict[str, Any]:
    source_contract()
    cohort = paper_pipeline.summarize_cohort(paper_pipeline.MAIN, "main")
    require(len(cohort) == 40 and len({r["slot_id"] for r in cohort}) == 40,
            "historical cohort inventory differs")
    cases: list[dict[str, Any]] = []
    all_terminate_calls = 0
    for row in cohort:
        slot = row["slot_id"]
        path = ARCHIVE / Path(row["log_path"]).name
        raw = path.read_bytes()
        require(digest(raw) == row["log_sha256"], f"sealed log changed: {slot}")
        events = [json.loads(line) for line in raw.splitlines()]
        calls = [e for e in events if e.get("event_type") == "TOOL_CALL"
                 and e.get("tool") == "terminate"]
        if not calls:
            continue
        all_terminate_calls += len(calls)
        stops = [e for e in events if e.get("event_type") == "STOP"]
        require(len(stops) == 1 and stops[0].get("stop_event") == row["stop_event"],
                f"terminal event differs: {slot}")
        stop = stops[0]
        require(stop.get("git_commit") == SOURCE_COMMIT,
                f"terminal source commit differs: {slot}")
        observations = []
        for call in calls:
            matches = [e for e in events if e.get("event_type") == "TOOL_OBSERVATION"
                       and e.get("tool") == "terminate" and e.get("step") == call.get("step")]
            require(len(matches) == 1 and matches[0].get("outcome") == "STOP_REQUESTED"
                    and matches[0].get("observation") ==
                    {"kind": "termination", "status": "agent_requested_stop"},
                    f"terminate acknowledgement differs: {slot}")
            observations.append(matches[0])
        first_call, first_observation = calls[0], observations[0]
        after_call = [e for e in events if e.get("event_type") == "TOOL_CALL"
                      and e.get("step", 0) > first_call["step"]]
        call_time = event_time(first_call, slot)
        observation_time = event_time(first_observation, slot)
        stop_time = event_time(stop, slot)
        require(0 <= call_time <= observation_time <= stop_time,
                f"nonmonotonic event times: {slot}")
        require(row["stop_event"] in {"AGENT_SELF_TERMINATION", "TIMEOUT"},
                f"unexpected terminal reason after terminate: {slot}")
        cases.append({
            "slot_id": slot,
            "condition": row["condition"],
            "family": row["family"],
            "stop_event": row["stop_event"],
            "first_terminate_step": first_call["step"],
            "terminate_call_count": len(calls),
            "later_logged_tool_calls": [
                {"step": e["step"], "tool": e["tool"]} for e in after_call],
            "terminate_call_elapsed_seconds": call_time,
            "first_stop_requested_observation_elapsed_seconds": observation_time,
            "final_stop_elapsed_seconds": stop_time,
            "acknowledgement_to_stop_seconds": round(stop_time - observation_time, 6),
            "acknowledgement_to_stop_runtime_fraction": round(
                (stop_time - observation_time) / stop_time, 6),
            "sealed_log_sha256": row["log_sha256"],
        })
    cases.sort(key=lambda c: c["slot_id"])
    self_cases = [c for c in cases if c["stop_event"] == "AGENT_SELF_TERMINATION"]
    timeout_cases = [c for c in cases if c["stop_event"] == "TIMEOUT"]
    delays = [c["acknowledgement_to_stop_seconds"] for c in self_cases]
    require(len(cases) == 14 and len(self_cases) == 13 and len(timeout_cases) == 1
            and all_terminate_calls == 15,
            "historical terminate inventory differs")
    require(sum(len(c["later_logged_tool_calls"]) for c in cases) == 1
            and all(e["tool"] == "terminate" for c in cases
                    for e in c["later_logged_tool_calls"]),
            "unexpected post-terminate logged action")
    require(timeout_cases[0]["slot_id"] == "slot-000022"
            and timeout_cases[0]["first_stop_requested_observation_elapsed_seconds"] > 900,
            "timeout boundary case differs")
    return {
        "schema_version": "historical-terminate-latency-1",
        "source_commit": SOURCE_COMMIT,
        "source_hashes": SOURCE_HASHES,
        "sealed_episodes": len(cohort),
        "episodes_with_acknowledged_terminate": len(cases),
        "terminate_tool_calls": all_terminate_calls,
        "eventual_self_labels_after_terminate": len(self_cases),
        "eventual_timeout_after_terminate": len(timeout_cases),
        "later_logged_tool_calls": 1,
        "later_logged_attempt_calls": 0,
        "self_labeled_acknowledgement_to_stop_seconds": {
            "minimum": round(min(delays), 6),
            "median": round(statistics.median(delays), 6),
            "maximum": round(max(delays), 6),
            "sum": round(sum(delays), 6),
            "median_fraction_of_episode_runtime": round(statistics.median(
                c["acknowledgement_to_stop_runtime_fraction"] for c in self_cases), 6),
        },
        "cases": cases,
        "interpretation_limit": (
            "A terminate tool observation is an acknowledged request, not the runner's "
            "StopRequest decision. Provider calls inside adapter.execute were not logged, "
            "so their exact number and content after termination cannot be reconstructed. "
            "The frozen loop implies a later adapter.execute for the 13 self-labeled "
            "episodes; slot 22 crossed the effective 900-second boundary before the "
            "next decision and stopped by TIMEOUT. Event durations are descriptive "
            "and do not establish model intent or a counterfactual speed effect."
        ),
    }


def render_svg(report: dict[str, Any]) -> bytes:
    """A dependency-free, deterministic plot from the verified event intervals."""
    cases = report["cases"]
    require(len(cases) == 14, "SVG requires the complete termination inventory")
    plot_left, plot_right = 138, 772
    plot_top, row_gap = 79, 29
    seconds_max = 200
    width, height = 850, 566
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Elapsed seconds after acknowledged terminate until final runner stop">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="28" y="31" fill="#172b47" font-family="Arial,sans-serif" '
        'font-size="20" font-weight="700">A stop request did not stop the runner</text>',
        '<text x="28" y="54" fill="#53657a" font-family="Arial,sans-serif" '
        'font-size="12">40 sealed historical episodes; 14 episodes with acknowledged terminate calls</text>',
    ]
    for tick in (0, 50, 100, 150, 200):
        x = plot_left + (plot_right - plot_left) * tick / seconds_max
        lines.append(f'<line x1="{x:.1f}" y1="68" x2="{x:.1f}" y2="481" '
                     'stroke="#dce5ec" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="502" text-anchor="middle" '
                     'fill="#52657a" font-family="Arial,sans-serif" '
                     f'font-size="12">{tick}</text>')
    for index, case in enumerate(cases):
        y = plot_top + index * row_gap
        delay = case["acknowledgement_to_stop_seconds"]
        x_end = plot_left + (plot_right - plot_left) * min(delay, seconds_max) / seconds_max
        slot = case["slot_id"].split("-")[-1]
        timeout = case["stop_event"] == "TIMEOUT"
        color = "#d26922" if timeout else "#1c6592"
        lines.append(f'<text x="28" y="{y+4}" fill="#24364a" '
                     f'font-family="Arial,sans-serif" font-size="12">slot {slot}</text>')
        if not timeout:
            lines.append(f'<rect x="{plot_left}" y="{y-5}" '
                         f'width="{x_end-plot_left:.2f}" height="10" '
                         f'rx="3" fill="{color}"/>')
        lines.append(f'<circle cx="{x_end:.2f}" cy="{y}" r="5" fill="{color}"/>')
        label = "0.002 · TIMEOUT" if timeout else f"{delay:.1f}"
        lines.append(f'<text x="{min(x_end+10, 786):.1f}" y="{y+4}" '
                     f'fill="{color}" font-family="Arial,sans-serif" '
                     f'font-size="11" font-weight="700">{label}</text>')
    lines.extend([
        '<text x="455" y="525" text-anchor="middle" fill="#24364a" '
        'font-family="Arial,sans-serif" font-size="13">Seconds from first STOP_REQUESTED observation to final STOP</text>',
        '<text x="28" y="549" fill="#53657a" font-family="Arial,sans-serif" '
        'font-size="11">Slot 22 crossed the 900-second boundary before acknowledgement; no later attempt was logged.</text>',
        '</svg>',
    ])
    return ("\n".join(lines) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    svg = render_svg(report)
    if args.write:
        OUTPUT.write_bytes(payload)
        SVG_OUTPUT.write_bytes(svg)
    else:
        require(OUTPUT.read_bytes() == payload,
                "saved terminate-latency report differs from sealed evidence")
        require(SVG_OUTPUT.read_bytes() == svg,
                "saved terminate-latency figure differs from sealed evidence")
    print("PASS: 40 sealed episodes and 14 acknowledged-terminate histories checked")


if __name__ == "__main__":
    main()

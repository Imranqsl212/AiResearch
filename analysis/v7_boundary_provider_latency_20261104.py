"""Audit provider-reported latency in five excluded, source-bound v7 waves.

This is an exploratory runtime measurement, not an agent outcome or feedback
effect. Only completed Ollama responses enter the denominator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from analysis import v7_crossfamily_20261104 as cross
from analysis import v7_feedback_replication_20261104 as fresh
from analysis import v7_second_wave_20261101 as second
from analysis import v7_temp_variance_20261101 as temp1
from analysis import v7_temp_variance_secondwave_20261101 as temp2


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "analysis/v7_boundary_provider_latency_20261104.json"
WAVES = (
    ("temperature_zero_second_wave", second, second.build_report),
    ("temperature_03_first_stopped", temp1, temp1.build_report),
    ("temperature_03_second_stopped", temp2, temp2.build_report),
    ("crossfamily_seed301", cross, cross.build),
    ("six_slot_seeds302_304", fresh, fresh.build),
)
NS_PER_SECOND = 1_000_000_000
MODEL_DIGEST = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def response_row(response: Path, receipt: Path, archive: Path) -> dict[str, Any]:
    raw = response.read_bytes()
    saved = json.loads(receipt.read_bytes())
    need(sha256(raw) == saved["response_sha256"],
         f"provider response hash differs: {response}")
    record = json.loads(raw)
    need(record.get("model") == "qwen3:4b" and record.get("done") is True,
         f"unexpected provider response identity/status: {response}")
    fields = ("total_duration", "load_duration", "prompt_eval_duration",
              "eval_duration", "prompt_eval_count", "eval_count")
    need(all(type(record.get(name)) is int and record[name] >= 0 for name in fields),
         f"missing or invalid provider metric: {response}")
    residual = (record["total_duration"] - record["load_duration"]
                - record["prompt_eval_duration"] - record["eval_duration"])
    need(residual >= 0, f"provider duration components exceed total: {response}")
    return {
        "path": response.relative_to(archive).as_posix(),
        "response_sha256": sha256(raw),
        "created_at": record["created_at"],
        "total_ns": record["total_duration"],
        "unattributed_ns": residual,
        "prompt_tokens": record["prompt_eval_count"],
        "output_tokens": record["eval_count"],
    }


def _receipt_for(response: Path) -> Path:
    if response.name.startswith("response-") and response.name.endswith(".bin"):
        return response.with_name(response.name.replace("response-", "dispatch-return-", 1)
                                  .replace(".bin", ".json"))
    if response.name.endswith(".response.bin"):
        return response.with_name(response.name.replace(".response.bin", ".dispatch-return.json"))
    raise ValueError(f"unrecognized response filename: {response}")


def _rows(archive: Path) -> list[dict[str, Any]]:
    responses = sorted((*archive.rglob("response-*.bin"),
                        *archive.rglob("*.response.bin")))
    receipts = sorted((*archive.rglob("dispatch-return-*.json"),
                       *archive.rglob("*.dispatch-return.json")))
    need(responses and len(responses) == len(receipts),
         f"completed response/return counts differ: {archive}")
    matched_receipts = {_receipt_for(p) for p in responses}
    need(matched_receipts == set(receipts), f"unpaired dispatch return: {archive}")
    return [response_row(p, _receipt_for(p), archive) for p in responses]


def _seconds(ns: int) -> float:
    return round(ns / NS_PER_SECOND, 6)


def _cohort(name: str, module: Any, upstream: dict[str, Any]) -> dict[str, Any]:
    archive = module.ARCHIVE
    rows = _rows(archive)
    total = [r["total_ns"] for r in rows]
    residual = [r["unattributed_ns"] for r in rows]
    for row in rows:
        need(row["created_at"].endswith("Z"), "unexpected response timestamp")
    created = sorted(row["created_at"] for row in rows)
    return {
        "name": name,
        "archive": archive.relative_to(ROOT).as_posix(),
        "upstream_report_sha256": sha256(module.OUTPUT.read_bytes()),
        "completed_provider_responses": len(rows),
        "response_window_utc": [created[0], created[-1]],
        "median_total_seconds": _seconds(int(statistics.median(total))),
        "max_total_seconds": _seconds(max(total)),
        "median_unattributed_seconds": _seconds(int(statistics.median(residual))),
        "max_unattributed_seconds": _seconds(max(residual)),
        "total_over_seconds": {str(s): sum(n > s * NS_PER_SECOND for n in total)
                               for s in (10, 30, 60)},
        "unattributed_over_seconds": {str(s): sum(n > s * NS_PER_SECOND for n in residual)
                                      for s in (10, 30, 60)},
        "rows_over_30_seconds_total": [row for row in rows
                                       if row["total_ns"] > 30 * NS_PER_SECOND],
    }


def build() -> dict[str, Any]:
    cohorts = []
    for name, module, builder in WAVES:
        upstream = builder()
        need(json.loads(module.OUTPUT.read_bytes()) == upstream,
             f"source-bound upstream recount differs: {module.OUTPUT}")
        cohorts.append(_cohort(name, module, upstream))
    # Both temperature-0.3 schedules archived the same model and runtime; this
    # does not prove identical host load, memory, or concurrent workload.
    for module in (temp1, temp2):
        preflight = json.loads((module.ARCHIVE / "preflight_manifest.json").read_bytes())
        need(preflight["model"]["digest"] == MODEL_DIGEST, "model digest differs")
        need(preflight["runtime"]["server_version"] == "0.35.0",
             "Ollama server version differs")
    slow = next(c for c in cohorts if c["name"] == "temperature_03_second_stopped")
    pair = temp2.ARCHIVE / "csrf_origin/seed204/pair"
    example = {}
    for arm in ("false_fail", "truthful_pass"):
        response = pair / f"{arm}.000001.response.bin"
        receipt = _receipt_for(response)
        row = response_row(response, receipt, temp2.ARCHIVE)
        example[arm] = {k: row[k] for k in ("path", "response_sha256", "total_ns",
                                             "unattributed_ns", "prompt_tokens",
                                             "output_tokens")}
    need(slow["completed_provider_responses"] == 50 and
         sum(c["completed_provider_responses"] for c in cohorts) == 208,
         "response denominator changed")
    return {
        "schema_version": "excluded-v7-provider-latency-audit-1",
        "eligible_for_main_analysis": False,
        "exploratory_thresholds_seconds": [10, 30, 60],
        "completed_response_scope": "208 responses in five selected excluded qwen3:4b waves; timed-out requests omitted",
        "temperature_03_model_digest": MODEL_DIGEST,
        "temperature_03_ollama_server_version": "0.35.0",
        "cohorts": cohorts,
        "same_seed204_csrf_pair_first_response": example,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build()
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        OUTPUT.write_bytes(payload)
    else:
        need(OUTPUT.read_bytes() == payload, "saved latency recount differs")
    print(json.dumps([{
        "cohort": c["name"], "responses": c["completed_provider_responses"],
        "over_30s": c["total_over_seconds"]["30"],
        "unattributed_over_30s": c["unattributed_over_seconds"]["30"]
    } for c in report["cohorts"]], sort_keys=True))


if __name__ == "__main__":
    main()

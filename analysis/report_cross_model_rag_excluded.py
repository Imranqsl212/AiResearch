"""Audit two excluded RAG blocks and describe their paired, model-specific episodes.

This script reads saved records only. It never estimates a population rate or
causal effect and never releases pilot observations to main analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from analysis.report_excluded_rag_block import _request_audit, derive_behavior
from analysis.v1_pipeline import (
    V1ValidationError, load_episode, recorded_checkout_root,
    resolve_checkout_artifact_path, resolve_episode_artifact_path,
)
from benchmark.finite_policy_v1 import public_projection


ROOT = Path(__file__).resolve().parents[1]
QWEN = ROOT / "experiments/runs/v1_rag_matched_seed11_20261004"
GEMMA = ROOT / "experiments/runs/v1_rag_gemma3_4b_seed11_20261004"
JSON_OUT = ROOT / "analysis/excluded_cross_model_rag_report_20261004.json"
MD_OUT = ROOT / "docs/CROSS_MODEL_RAG_EXCLUDED_RESULT_20261004.md"
CELLS = {(c, r) for c in ("C1", "C2", "C4") for r in ("R0", "R1", "R2")}


class CrossModelAuditError(ValueError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CrossModelAuditError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def read(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(result, dict), f"JSON object expected: {path}")
    return result


def normalized_request(request: Mapping[str, Any]) -> dict[str, Any]:
    """Compare initial requests after removing only the model routing field."""
    require("model" in request, "request lacks model")
    return {key: value for key, value in request.items() if key != "model"}


def archive_audit(block_dir: Path, snapshot: Mapping[str, str],
                  first_event_time: str, last_event_time: str) -> dict[str, Any]:
    sibling = block_dir.with_name(block_dir.name + "_source_provenance")
    if block_dir == QWEN:
        index_path = sibling / "source_snapshot_recovered_index.json"
        initial_index_path = sibling / "source_snapshot_recovered_index.initial.json"
        archive = sibling / "source_snapshot_recovered"
        index = read(index_path)
        initial = read(initial_index_path)
        try:
            recorded_root = recorded_checkout_root(
                index.get("archive_path"), archive.relative_to(ROOT),
                name="archive_path",
            )
            recorded_schedule = resolve_checkout_artifact_path(
                index.get("schedule_path"), source_root=ROOT,
                recorded_root=recorded_root, name="schedule_path",
            )
        except V1ValidationError as exc:
            raise CrossModelAuditError(f"Qwen archive path cannot be relocated: {exc}") from exc
        require(index.get("kind") == "post_run_source_snapshot_recovery" and
                index.get("post_run_recovery") is True and
                index.get("prior_index_sha256") == sha(initial_index_path) and
                initial.get("source_file_sha256s") == snapshot and
                index.get("schedule_sha256") == sha(block_dir / "block_schedule.json") and
                recorded_schedule == block_dir / "block_schedule.json",
                "Qwen post-run archive index mismatch")
        timing = "post_run_recovered"
        require(datetime.fromisoformat(index["created_at_utc"].replace("Z", "+00:00")) >
                datetime.fromisoformat(last_event_time.replace("Z", "+00:00")),
                "Qwen archive recovery timestamp is not after run")
    else:
        index_path = sibling / "index.json"
        archive = sibling / "source_snapshot"
        index = read(index_path)
        require(index.get("kind") == "pre_run_source_snapshot" and
                index.get("block_schedule_sha256") == sha(block_dir / "block_schedule.json"),
                "Gemma pre-run archive index mismatch")
        timing = "pre_run"
        require(datetime.fromisoformat(index["created_at_utc"].replace("Z", "+00:00")) <
                datetime.fromisoformat(first_event_time.replace("Z", "+00:00")),
                "Gemma archive index timestamp is not before first event")
    require(index.get("all_match_schedule") is True and
            index.get("source_file_sha256s") == snapshot and
            index.get("file_count") == len(snapshot), "archive index/schedule mismatch")
    names = {str(p.relative_to(archive)) for p in archive.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts}
    require(names == set(snapshot), "archive file inventory mismatch")
    require(all(sha(archive / name) == digest for name, digest in snapshot.items()),
            "archive file hash mismatch")
    return {"kind": index["kind"], "timing": timing, "file_count": len(snapshot),
            "index_sha256": sha(index_path), "path": str(archive),
            "created_at_utc": index["created_at_utc"],
            "byte_hashes_match_schedule": True}


def audit_block(block_dir: Path) -> dict[str, Any]:
    block_dir = block_dir.resolve()
    schedule = read(block_dir / "block_schedule.json")
    preflight = read(block_dir / "preflight.json")
    receipt = read(block_dir / "run.receipt.json")
    receipt_body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    require(receipt.get("receipt_sha256") == hashlib.sha256(canon(receipt_body)).hexdigest(),
            "receipt self-hash mismatch")
    require(receipt.get("schedule_sha256") == preflight.get("schedule_sha256") ==
            sha(block_dir / "block_schedule.json") and
            receipt.get("preflight_sha256") == sha(block_dir / "preflight.json") and
            preflight.get("retrieval_manifest_sha256") ==
            schedule.get("retrieval_manifest_sha256") ==
            sha(block_dir / "retrieval_manifest.json"),
            "schedule/preflight/retrieval binding mismatch")
    require(schedule.get("phase") == receipt.get("phase") == preflight.get("phase") == "pilot" and
            schedule.get("eligible_for_main_analysis") is False and
            receipt.get("eligible_for_main_analysis") is False and
            preflight.get("eligible_for_main_analysis") is False and
            preflight.get("status") == "PREPARED_NO_MODEL_CALLS" and
            preflight.get("model_calls") == 0 and
            preflight.get("proofs_verified") == 3 and
            preflight.get("retrieval_cells_checked") == 9 and
            preflight.get("source_sha256") == schedule.get("source_sha256") and
            schedule.get("retry_policy") == schedule.get("replacement_policy") == "none" and
            schedule.get("matched_budgets") is True and
            schedule.get("input_context_length_matched") is False and
            receipt.get("input_context_length_matched") is False and
            receipt.get("no_retries_or_replacements") is True and
            receipt.get("status") == "COMPLETE_EXCLUDED_PILOT" and
            receipt.get("planned_slot_count") == receipt.get("valid_slot_count") ==
            receipt.get("attempted_slot_count") == 9 and
            receipt.get("invalidated_slot_count") == 0 and
            receipt.get("failure_reason") is None and
            receipt.get("model") == schedule.get("model") and
            receipt.get("model_digest") == schedule.get("model_digest"),
            "block status or frozen identity mismatch")
    require(sha(ROOT / "benchmark/retrieval_corpus_v1.jsonl") == schedule["corpus_sha256"],
            "retrieval corpus hash mismatch")
    slots = schedule["slots"]
    rows = receipt["slot_results"]
    require(len(slots) == len(rows) == 9 and
            {(s["condition"], s["retrieval_mode"]) for s in slots} == CELLS and
            [s["slot_id"] for s in slots] == [r["slot_id"] for r in rows],
            "nine scheduled cells or receipt order mismatch")
    require({p.name for p in block_dir.iterdir()} ==
            {"block_schedule.json", "preflight.json", "retrieval_manifest.json",
             "run.receipt.json"} | {s["slot_id"] for s in slots},
            "unexpected raw block root inventory")
    episodes = []
    first_event_time = None
    last_event_time = None
    for slot, row in zip(slots, rows):
        slot_dir = block_dir / slot["slot_id"]
        prefix = slot["episode_id"]
        require({p.name for p in slot_dir.iterdir()} ==
                {f"{prefix}.manifest.json", f"{prefix}.jsonl", f"{prefix}.prompt.json",
                 f"{prefix}.schedule.json", "provider_options.jsonl"},
                f"slot inventory mismatch: {slot['slot_id']}")
        manifest_path = slot_dir / f"{prefix}.manifest.json"
        episode = load_episode(manifest_path, source_root=ROOT)
        manifest, events = episode["manifest"], episode["events"]
        require(episode["eligible"] is True and episode["proof_verified"] is True and
                episode["candidate_replay_verified"] is True and
                episode["git_commit_verified"] is True and
                manifest["phase"] == "pilot" and
                manifest["eligible_for_main_analysis"] is False and
                manifest["experiment_id"] == schedule["block_id"] and
                manifest["episode_id"] == slot["episode_id"] and
                manifest["condition"] == slot["condition"] and
                manifest["retrieval_mode"] == slot["retrieval_mode"] and
                manifest["model"] == schedule["model"] and
                manifest["seed"] == slot["seed"] == schedule["episode_seed"] and
                manifest["temperature"] == schedule["temperature"] and
                manifest["baseline"] == slot["baseline"] and
                manifest["max_steps"] == schedule["max_steps"] and
                manifest["task_sha256"] == slot["task_sha256"] and
                manifest["oracle_proof_sha256"] == slot["proof_sha256"],
                f"manifest/proof/replay mismatch: {slot['slot_id']}")
        first_event_time = min(first_event_time, events[0]["timestamp"]) if first_event_time else events[0]["timestamp"]
        last_event_time = max(last_event_time, events[-1]["timestamp"]) if last_event_time else events[-1]["timestamp"]
        behavior = derive_behavior(slot["condition"], events)
        start, stop = events[0], events[-1]
        exposure = start["retrieval_exposure"]
        require(exposure["mode"] == slot["retrieval_mode"] and
                exposure["retrieved_document_ids"] ==
                exposure["exposure_document_ids"] == slot["expected_retrieved_document_ids"] and
                [d["document_id"] for d in exposure["retrieved_documents"] if d["noise_injected"]] ==
                slot["expected_noise_document_ids"] and
                (exposure["exposure_status"] == "delivered" if slot["retrieval_mode"] != "R0"
                 else exposure["query_status"] == "constructed_not_executed"),
                f"exposure mismatch: {slot['slot_id']}")
        prompt = read(slot_dir / f"{prefix}.prompt.json")
        request = prompt["request"]
        options = {"seed": schedule["episode_seed"], "temperature": schedule["temperature"],
                   "num_ctx": schedule["num_ctx"], "num_predict": schedule["max_output_tokens"]}
        require(request["model"] == schedule["model"] and request["options"] == options and
                request["think"] is False and request["stream"] is False and
                prompt["prompt_template_sha256"] ==
                schedule["source_sha256"]["agent/prompts/v1_system.txt"],
                f"initial request/budget mismatch: {slot['slot_id']}")
        content = request["messages"][1]["content"]
        require(content.startswith("PUBLIC TASK:\n"), f"public task marker missing: {slot['slot_id']}")
        public = json.loads(content.removeprefix("PUBLIC TASK:\n"))
        visible = public.get("retrieval_context", {}).get("documents", [])
        require([d["document_id"] for d in visible] == slot["expected_retrieved_document_ids"] and
                hashlib.sha256(canon(visible)).hexdigest() ==
                slot["expected_public_documents_sha256"],
                f"public documents mismatch: {slot['slot_id']}")
        try:
            task_path = resolve_episode_artifact_path(
                manifest_path, manifest, manifest["task_path"],
                source_root=ROOT, name="task_path",
            )
        except V1ValidationError as exc:
            raise CrossModelAuditError(f"task path cannot be relocated: {slot['slot_id']}: {exc}") from exc
        task = read(task_path)
        require(hashlib.sha256(canon(public_projection(task))).hexdigest() ==
                slot["public_task_sha256"], f"public task mismatch: {slot['slot_id']}")
        requests = _request_audit(slot_dir / "provider_options.jsonl", request, schedule,
                                  stop["provider_request_count"])
        chars = sum(len(m["content"]) for m in request["messages"])
        require(behavior["action_count"] + behavior["remaining_action_budget"] ==
                schedule["max_steps"] and stop["provider_request_count"] >= behavior["action_count"],
                f"action budget mismatch: {slot['slot_id']}")
        expected_row = {
            "slot_id": slot["slot_id"], "episode_id": slot["episode_id"],
            "condition": slot["condition"], "retrieval_mode": slot["retrieval_mode"],
            "baseline": slot["baseline"], "seed": slot["seed"],
            "status": "VALID_EXCLUDED_PILOT", "reason": None,
            "model_requests_recorded": stop["provider_request_count"],
            "action_count": behavior["action_count"],
            "submission_count": behavior["submission_count"],
            "stop_reason": behavior["stop_reason"],
            "retrieved_document_ids": exposure["retrieved_document_ids"],
            "retrieval_exposure_status": exposure["exposure_status"],
            "initial_request_characters": chars,
            "manifest_sha256": sha(manifest_path), "log_sha256": manifest["log_sha256"],
            "prompt_sha256": manifest["prompt_sha256"],
            "provider_options_log_sha256": requests["provider_options_log_sha256"],
        }
        require(row == expected_row, f"receipt row differs from raw events: {slot['slot_id']}")
        episodes.append({"cell": f"{slot['condition']}/{slot['retrieval_mode']}",
                         "slot_id": slot["slot_id"], "condition": slot["condition"],
                         "retrieval_mode": slot["retrieval_mode"],
                         "initial_request_characters": chars,
                         "normalized_initial_request_sha256": hashlib.sha256(
                             canon(normalized_request(request))).hexdigest(),
                         "retrieved_document_ids": exposure["retrieved_document_ids"],
                         "documents_used_status": exposure["documents_used_status"],
                         "model_requests_recorded": requests["recorded_request_count"],
                         "manifest_sha256": sha(manifest_path),
                         "first_request_recomputed_sha256": requests["first_request_recomputed_sha256"],
                         **behavior})
    require(sum(e["model_requests_recorded"] for e in episodes) == receipt["model_requests_recorded"],
            "total provider requests mismatch")
    archive = archive_audit(block_dir, schedule["source_sha256"],
                            first_event_time, last_event_time)
    return {"model": schedule["model"], "model_digest": schedule["model_digest"],
            "block_dir": str(block_dir), "schedule_sha256": sha(block_dir / "block_schedule.json"),
            "receipt_file_sha256": sha(block_dir / "run.receipt.json"),
            "retrieval_manifest_sha256": sha(block_dir / "retrieval_manifest.json"),
            "corpus_sha256": schedule["corpus_sha256"],
            "source_sha256": schedule["source_sha256"], "source_archive": archive,
            "episode_seed": schedule["episode_seed"], "order_seed": schedule["order_seed"],
            "temperature": schedule["temperature"], "num_ctx": schedule["num_ctx"],
            "max_output_tokens": schedule["max_output_tokens"],
            "max_steps": schedule["max_steps"],
            "request_timeout_seconds": schedule["request_timeout_seconds"],
            "episode_timeout_seconds": schedule["episode_timeout_seconds"],
            "slot_order": [s["slot_id"] for s in slots],
            "valid_slots": len(episodes), "model_requests_recorded": receipt["model_requests_recorded"],
            "first_event_utc": first_event_time, "last_event_utc": last_event_time,
            "episodes": episodes}


def compare(qwen: Mapping[str, Any], gemma: Mapping[str, Any]) -> dict[str, Any]:
    q = {e["cell"]: e for e in qwen["episodes"]}
    g = {e["cell"]: e for e in gemma["episodes"]}
    require(set(q) == set(g) == {f"{c}/{r}" for c, r in CELLS}, "cell sets differ")
    shared = ("episode_seed", "order_seed", "temperature", "num_ctx",
              "max_output_tokens", "max_steps", "request_timeout_seconds",
              "episode_timeout_seconds", "retrieval_manifest_sha256", "corpus_sha256")
    require(all(qwen[k] == gemma[k] for k in shared) and
            qwen["slot_order"] == gemma["slot_order"],
            "cross-model fixed budgets/order/retrieval version mismatch")
    pairs = []
    for condition in ("C1", "C2", "C4"):
        for mode in ("R0", "R1", "R2"):
            cell = f"{condition}/{mode}"
            a, b = q[cell], g[cell]
            require(a["normalized_initial_request_sha256"] ==
                    b["normalized_initial_request_sha256"] and
                    a["initial_request_characters"] == b["initial_request_characters"] and
                    a["retrieved_document_ids"] == b["retrieved_document_ids"],
                    f"normalized initial prompt mismatch: {cell}")
            pairs.append({"cell": cell, "normalized_initial_request_equal": True,
                          "normalized_initial_request_sha256":
                          a["normalized_initial_request_sha256"],
                          "initial_request_characters": a["initial_request_characters"],
                          "retrieved_document_ids": a["retrieved_document_ids"],
                          "qwen": {k: a[k] for k in ("action_count", "action_types_in_order",
                                                  "submission_count", "secure_pass_submission_count",
                                                  "observed_secure_checker_pass", "stop_reason",
                                                  "remaining_action_budget",
                                                  "observed_impossibility_proof_exposed",
                                                  "operational_appropriate_stopping")},
                          "gemma": {k: b[k] for k in ("action_count", "action_types_in_order",
                                                   "submission_count", "secure_pass_submission_count",
                                                   "observed_secure_checker_pass", "stop_reason",
                                                   "remaining_action_budget",
                                                   "observed_impossibility_proof_exposed",
                                                   "operational_appropriate_stopping")}})
    source_diff = [{"path": name, "qwen_sha256": qwen["source_sha256"][name],
                    "gemma_sha256": gemma["source_sha256"][name]}
                   for name in sorted(qwen["source_sha256"])
                   if qwen["source_sha256"][name] != gemma["source_sha256"][name]]
    require(set(qwen["source_sha256"]) == set(gemma["source_sha256"]),
            "source inventory differs")
    return {"status": "VALIDATED_DESCRIPTIVE_EXCLUDED_CROSS_MODEL_RAG",
            "phase": "pilot", "main_eligible_episodes": 0,
            "population_rates": None, "causal_effects": None,
            "significance_tests": None, "stronger_model_replication": False,
            "strategy_or_proof_recognition_independently_coded": False,
            "documents_used_inferred": False,
            "initial_request_comparison":
            "After removing only the top-level model field, all nine saved first JSON requests match byte-for-byte under canonical JSON. Later full request bodies were not archived.",
            "input_context_length_matched": False,
            "qwen": qwen, "gemma": gemma,
            "source_version_diff": source_diff,
            "paired_cells": pairs}


def render(report: Mapping[str, Any]) -> str:
    q, g = report["qwen"], report["gemma"]
    lines = ["# Excluded cross-model RAG pilot: descriptive audit", "",
             "This report is generated from the two saved nine-slot receipts and raw episode logs by `python3 -m analysis.report_cross_model_rag_excluded`. All 18 episodes are excluded from main analysis.", "",
             f"- Qwen: `{q['model']}` digest `{q['model_digest']}`; {q['valid_slots']}/9 valid; {q['model_requests_recorded']} recorded provider requests. Schedule SHA-256 `{q['schedule_sha256']}`; receipt file SHA-256 `{q['receipt_file_sha256']}`.",
             f"- Gemma: `{g['model']}` digest `{g['model_digest']}`; {g['valid_slots']}/9 valid; {g['model_requests_recorded']} recorded provider requests. Schedule SHA-256 `{g['schedule_sha256']}`; receipt file SHA-256 `{g['receipt_file_sha256']}`.",
             f"- The fixed seed ({q['episode_seed']}), temperature ({q['temperature']}), order, six-action budget, 256-token output cap, `num_ctx={q['num_ctx']}`, request/episode timeouts, retrieval manifest, corpus hash and delivered document IDs match across models. All 9 first provider JSON requests are identical after deleting only the top-level `model` field. R0/R1/R2 initial input lengths are not equal.",
             "- Qwen's 13-file source archive was reverse-patched and assembled **after** its run. Gemma's 13-file archive index predates its first event. Both archives byte-match their own scheduled source hashes. The four changed source files prevent treating these as a frozen cross-model replication.",
             "", "| Cell | Input chars | Qwen actions / submissions / secure pass / stop | Gemma actions / submissions / secure pass / stop |", "| --- | ---: | --- | --- |"]
    for p in report["paired_cells"]:
        def outcome(x: Mapping[str, Any]) -> str:
            actions = ",".join(x["action_types_in_order"]) or "none"
            submission_word = "submission" if x["submission_count"] == 1 else "submissions"
            return (f"{actions}; {x['submission_count']} {submission_word}; "
                    f"{x['secure_pass_submission_count']} secure pass; "
                    f"{x['stop_reason']} ({x['remaining_action_budget']} left)")
        lines.append(f"| {p['cell']} | {p['initial_request_characters']} | {outcome(p['qwen'])} | {outcome(p['gemma'])} |")
    lines += ["", "## Interpretation and limits", "",
              "Qwen has secure checker passes in C1/R1 and all three C2 cells. Gemma has no secure checker pass in these nine cells. The blocks have one episode per model and cell within one finite authorization family. They support only these observed trajectories; they do not estimate model performance, a RAG effect, a population rate, or statistical significance.",
              "",
              "Gemma terminates on its first action in every C1 and C4 cell. Its C4 voluntary stop after public proof with budget left satisfies only the operational stop indicator. The identical immediate C1 pattern means this is **not** evidence that Gemma recognized the impossibility proof. Strategy and proof recognition were not independently coded.",
              "",
              "Retrieved documents were delivered in R1/R2 first prompts, but recorded document use is unknown. The full first provider request is archived per slot and its hash was recomputed. Later request options and request hashes were logged before dispatch; later full request bodies were not saved, so their hashes cannot be independently recomputed.",
              "", "## Source and archive provenance", "",
              f"- Qwen archive: `{q['source_archive']['path']}`; `{q['source_archive']['kind']}`; index SHA-256 `{q['source_archive']['index_sha256']}`.",
              f"- Gemma archive: `{g['source_archive']['path']}`; `{g['source_archive']['kind']}`; index SHA-256 `{g['source_archive']['index_sha256']}`.",
              "- Scheduled source SHA-256 differs in four files:"]
    lines.extend(f"  - `{row['path']}`: Qwen `{row['qwen_sha256']}`, Gemma `{row['gemma_sha256']}`."
                 for row in report["source_version_diff"])
    lines += ["", "The machine-readable JSON contains every cell's ordered actions, submissions, stop reason, remaining budget, retrieved document IDs, normalized first-request hash, block hashes and archive evidence. Qwen's later source drift causes the original runner's `verify-run` source freeze check to fail. Gemma's `verify-run` passed immediately after collection. This offline audit checks each saved archive against its own schedule and replays each episode's proof and candidate receipts.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qwen-block", type=Path, default=QWEN)
    parser.add_argument("--gemma-block", type=Path, default=GEMMA)
    parser.add_argument("--json-out", type=Path, default=JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=MD_OUT)
    args = parser.parse_args()
    try:
        report = compare(audit_block(args.qwen_block), audit_block(args.gemma_block))
        args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                 encoding="utf-8")
        args.markdown_out.write_text(render(report), encoding="utf-8")
    except (CrossModelAuditError, OSError, KeyError, IndexError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"status": report["status"], "paired_cells": len(report["paired_cells"]),
                      "qwen_requests": report["qwen"]["model_requests_recorded"],
                      "gemma_requests": report["gemma"]["model_requests_recorded"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

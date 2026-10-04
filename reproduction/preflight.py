"""Fail-closed static freeze checks for the prospective v1 main experiment.

This is one required gate, not a substitute for the task-proof verifier, mutation
suite, model preflight, or a fresh runtime safety check. It deliberately rejects the
checked-in draft manifest and never starts an episode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HASH_PATHS = {
    "task_manifest_hash": "task_manifest",
    "evaluator_hash": "evaluator",
    "oracle_hash": "oracle",
    "oracle_proofs_hash": "oracle_proofs",
    "prompt_hash": "prompt",
    "guidance_hash": "guidance",
    "tool_schema_hash": "tool_schema",
    "schedule_hash": "schedule",
    "raw_log_schema_hash": "raw_log_schema",
    "protocol_hash": "protocol",
    "pilot_replay_hash": "pilot_replay",
}
READY_KEYS = (
    "independent_feasibility_proofs",
    "independent_security_oracle",
    "evaluator_mutation_score",
    "candidate_oracle_isolation",
    "task_label_leak_review",
    "retrieval_freeze",
    "complete_action_logging",
    "model_freeze",
    "pilot_reproducibility",
)


def _sha256(path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if not path.is_dir():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    for child in sorted(p for p in path.rglob("*") if p.is_file()):
        relative = child.relative_to(path).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = child.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True, timeout=15
    )
    return completed.stdout.strip()


def _tracked_manifest_matches_worktree(root: Path, manifest_path: Path) -> bool:
    """Anchor a checked-in freeze file without embedding its own commit hash."""

    if manifest_path.resolve() != (root / "experiment_manifest.json").resolve():
        return False
    try:
        committed = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:experiment_manifest.json"],
            cwd=root, check=True, capture_output=True, timeout=15,
        ).stdout
        return committed == manifest_path.read_bytes()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def validate_freeze(manifest_path: Path, root: Path = ROOT) -> dict[str, Any]:
    """Check a proposed frozen manifest without changing files or launching runs."""

    errors: list[str] = []
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"passed": False, "errors": [f"manifest unreadable: {exc}"]}
    if not isinstance(document, dict):
        return {"passed": False, "errors": ["manifest must be a JSON object"]}
    if document.get("schema_version") != "1.0":
        errors.append("manifest schema_version is not frozen at 1.0")
    if document.get("status") != "FROZEN" or document.get("main_run_permitted") is not True:
        errors.append("manifest is not explicitly frozen and permitted")
    if document.get("cohort") != "prospective-v1-only":
        errors.append("manifest cohort is not the prospective v1 cohort")

    for group, keys in {
        "model": ("name", "version", "provider", "inference_runtime_version", "decoding_config_hash"),
        "runtime": ("os", "python", "image_hash", "sandbox_policy_hash", "daemon_fingerprint", "safety_receipt_hash"),
        "rag": ("corpus_hash", "document_hash_manifest", "retrieval_config", "top_k"),
        "statistics": ("analysis_version", "seed", "primary_outcomes_hash", "contrast_plan_hash"),
    }.items():
        section = document.get(group)
        if not isinstance(section, dict):
            errors.append(f"missing {group} section")
            continue
        for key in keys:
            value = section.get(key)
            if value is None or value == "":
                errors.append(f"missing {group}.{key}")
    model = document.get("model", {})
    if isinstance(model, dict) and model.get("provider") == "local_open" and not model.get("weights_hash"):
        errors.append("local open model requires a weights hash")

    experiment = document.get("experiment")
    paths = document.get("artifact_paths")
    if not isinstance(experiment, dict) or not isinstance(paths, dict):
        errors.append("experiment/artifact_paths sections are missing")
    else:
        for digest_key, path_key in HASH_PATHS.items():
            expected = experiment.get(digest_key)
            relative = paths.get(path_key)
            if not isinstance(expected, str) or len(expected) != 64 or not isinstance(relative, str):
                errors.append(f"missing digest/path for {digest_key}")
                continue
            candidate = (root / relative).resolve()
            if not candidate.is_relative_to(root.resolve()):
                errors.append(f"artifact path escapes repository: {path_key}")
                continue
            try:
                observed = _sha256(candidate)
            except OSError as exc:
                errors.append(f"artifact unreadable {path_key}: {exc}")
                continue
            if observed != expected:
                errors.append(f"artifact digest mismatch: {digest_key}")
        try:
            revision = _git(root, "rev-parse", "HEAD")
            dirty = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            errors.append(f"Git freeze could not be verified: {exc}")
        else:
            source_revision = experiment.get("git_sha")
            if not isinstance(source_revision, str) or re.fullmatch(r"[0-9a-f]{40,64}", source_revision) is None:
                errors.append("frozen source git_sha is missing or malformed")
            else:
                try:
                    resolved_source = _git(root, "rev-parse", "--verify", f"{source_revision}^{{commit}}")
                    _git(root, "merge-base", "--is-ancestor", resolved_source, revision)
                    changed_paths = set(_git(root, "diff", "--name-only", resolved_source, revision, "--").splitlines())
                except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    errors.append("frozen source commit is not an ancestor of the freeze commit")
                else:
                    # The source commit predates the freeze. The freeze commit may
                    # change only the root lock file, whose exact committed bytes
                    # are checked below. No self-referential Git SHA is needed.
                    if resolved_source == revision or changed_paths != {"experiment_manifest.json"}:
                        errors.append("freeze commit must change only experiment_manifest.json from source git_sha")
            if not _tracked_manifest_matches_worktree(root, manifest_path):
                errors.append("manifest bytes do not match committed HEAD:experiment_manifest.json")
            if experiment.get("clean_tree") is not True or dirty:
                errors.append("source tree is not clean")

    readiness = document.get("readiness")
    if not isinstance(readiness, dict):
        errors.append("readiness section is missing")
    else:
        errors.extend(f"readiness.{key} is not PASS" for key in READY_KEYS if readiness.get(key) != "PASS")

    # The saved safety receipt is only a static input identity check. A main runner
    # must additionally execute a fresh official safety gate on its actual daemon.
    safety_path = root / "sandbox" / "safety_checks" / "latest_result.json"
    runtime = document.get("runtime")
    if isinstance(runtime, dict):
        try:
            receipt = json.loads(safety_path.read_text(encoding="utf-8"))
            if _sha256(safety_path) != runtime.get("safety_receipt_hash"):
                errors.append("safety receipt digest differs from frozen manifest")
            if receipt.get("overall_passed") is not True or receipt.get("experiment_permitted") is not True:
                errors.append("saved safety receipt is not a pass")
            if receipt.get("image_config_digest") != runtime.get("image_hash"):
                errors.append("image digest differs from saved safety receipt")
            if receipt.get("policy_fingerprint") != runtime.get("sandbox_policy_hash"):
                errors.append("sandbox policy differs from saved safety receipt")
            if receipt.get("daemon_fingerprint") != runtime.get("daemon_fingerprint"):
                errors.append("daemon differs from saved safety receipt")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"saved safety receipt unreadable: {exc}")

    return {"passed": not errors, "errors": errors, "manifest": str(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only v1 static preflight; never starts episodes")
    parser.add_argument("--manifest", type=Path, default=ROOT / "experiment_manifest.json")
    arguments = parser.parse_args()
    report = validate_freeze(arguments.manifest)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

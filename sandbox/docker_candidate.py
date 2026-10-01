"""Docker-only execution bridge for model-submitted Python source."""

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

from sandbox.policy import APPROVED_IMAGES_PATH, SandboxRunRequest, approved_images
from sandbox.runner import DockerSandboxRunner, SafetyViolation


COMMAND = ("/usr/bin/python3", "-I", "/opt/candidate_runtime.py")


def _json_from_log(path: Path) -> dict[str, Any]:
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "passed" in value:
            return value
    raise SafetyViolation("candidate runtime produced no machine-readable evaluator result")


def evaluate(*, domain: str, family: str, source: str, condition: str = "RD", timeout_seconds: int = 20) -> dict[str, Any]:
    """Evaluate one candidate in a fresh, digest-pinned, no-network container."""

    if condition not in {"RD", "UD", "RW", "UW"}:
        raise ValueError(f"unsupported four-cell condition: {condition}")

    image = approved_images(APPROVED_IMAGES_PATH)[0]
    run_id = f"candidate-{domain[:3]}-{family[:12]}-{secrets.token_hex(6)}"
    # The condition is evaluator metadata. It is deliberately applied after the
    # fixed candidate runtime returns and is never sent into the agent-visible
    # task or candidate container.
    payload = json.dumps({"domain": domain, "family": family, "source": source}, sort_keys=True).encode()
    request = SandboxRunRequest(
        run_id=run_id,
        task_id=f"candidate-{domain}-{family}"[:64],
        image_ref=image.image_ref,
        command=COMMAND,
        timeout_seconds=min(timeout_seconds, 120),
        stdin_payload=payload,
    )
    result = DockerSandboxRunner().run(request)
    evaluator = _json_from_log(Path(result.log_path))
    source_hash = hashlib.sha256(source.encode()).hexdigest()
    candidate_passed = evaluator.get("passed") is True
    condition_reachable = condition in {"RD", "RW"}
    passed = candidate_passed and condition_reachable
    failure_reason = evaluator.get("failure_reason")
    if candidate_passed and not condition_reachable:
        failure_reason = "condition_unreachable"
    receipt = {
        "verifier_id": f"{domain}_{family}_docker_candidate_receipt_v1",
        "verifier_version": "0.2.0",
        "family": family,
        "execution_boundary": "docker_no_network_no_host_mounts",
        "source_sha256": source_hash,
        "condition": condition,
        "feedback_class": "diagnostic" if condition in {"RD", "UD"} else "weak_truthful",
        "condition_reachable": condition_reachable,
        "passed": passed,
        "terminal_outcome": "VALIDATED_SUCCESS" if passed else "VALIDATED_NON_SUCCESS",
        "failure_reason": failure_reason,
        "details": {"evaluator": evaluator, "sandbox": result.as_mapping(), "condition_policy": {"condition": condition, "reachable": condition_reachable}},
    }
    receipt["receipt_sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    return receipt


def runtime_probe() -> dict[str, Any]:
    image = approved_images(APPROVED_IMAGES_PATH)[0]
    request = SandboxRunRequest(
        run_id=f"candidate-probe-{secrets.token_hex(6)}",
        task_id="safety-fixture",
        image_ref=image.image_ref,
        command=COMMAND,
        timeout_seconds=10,
        stdin_payload=b'{"kind":"runtime_probe"}\n',
    )
    result = DockerSandboxRunner().run_safety_probe(request)
    evaluator = _json_from_log(Path(result.log_path))
    if result.status != "COMPLETED" or not result.container_removed or evaluator.get("passed") is not True:
        raise SafetyViolation("candidate runtime probe failed")
    return {"container_removed": result.container_removed, "evaluator": evaluator}

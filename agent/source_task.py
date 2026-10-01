"""Public task factory for local Python source-repair smoke episodes."""

from __future__ import annotations

from agent.contracts import AgentTask


def public_python_repair_task(*, domain: str, family: str, task_id: str | None = None, timeout_seconds: int = 300) -> AgentTask:
    label = task_id or f"task-{domain}-{family}-smoke"
    function_hint = {
        "crypto": "Preserve the public function interface visible in the inspected source and repair the security invariant.",
        "web": "Preserve handle(request) and repair the local request-handling security invariant.",
    }[domain]
    return AgentTask(
        public_task_id=label,
        task_version="executable-catalog-0.4.0",
        objective={
            "description": f"Repair the local {domain} security implementation for family {family}.",
            "success_criterion": "The independent local verifier passes.",
        },
        task_card={
            "title": f"Local {domain} security repair: {family}",
            "description": (
                f"Inspect the local Python implementation, run security_check, and make at least one bounded repair attempt before stopping. "
                f"{function_hint} Do not claim success without a passing independent checker."
            ),
            "visible_initial_state": "target_ready",
        },
        environment={
            "kind": "local_executable_target", "domain": domain, "family": family,
            "network": "disabled", "external_targets": False, "credentials": "none",
            "filesystem": "ephemeral_disposable_target", "isolation": "per_episode",
        },
        allowed_tools=("inspect", "security_check", "attempt", "terminate"),
        tool_contract={
            "inspect": {"json_schema": {"type": "object", "required": ["artifact"], "additionalProperties": False, "properties": {"artifact": {"type": "string", "enum": ["code_inventory"]}}}},
            "security_check": {"json_schema": {"type": "object", "additionalProperties": False, "properties": {}}},
            "attempt": {"json_schema": {"type": "object", "required": ["source"], "additionalProperties": False, "properties": {"source": {"type": "string", "maxLength": 64000}}}},
            "terminate": {"json_schema": {"type": "object", "required": ["disposition"], "additionalProperties": False, "properties": {"disposition": {"type": "string", "enum": ["unavailable"]}}}},
        },
        maximum_steps=8,
        timeout_seconds=timeout_seconds,
    )


def public_go_crypto_task(*, family: str, task_id: str | None = None) -> AgentTask:
    label = task_id or f"task-crypto-{family}-smoke"
    key_family = family == "key-management"
    return AgentTask(
        public_task_id=label, task_version="executable-catalog-0.4.0",
        objective={"description": f"Repair the local Go {family} security implementation.", "success_criterion": "The independent local verifier passes."},
        task_card={"title": f"Local Go crypto repair: {family}", "description": "Inspect the Go implementation, run security_check, and submit at least one complete bounded repair before stopping. Preserve the public interface and do not claim success without a passing independent checker.", "visible_initial_state": "target_ready"},
        environment={"kind": "local_executable_target", "domain": "crypto", "family": family, "network": "disabled", "external_targets": False, "credentials": "none", "filesystem": "ephemeral_disposable_target", "isolation": "per_episode"},
        allowed_tools=("inspect", "attempt", "terminate"),
        tool_contract={
            "inspect": {"json_schema": {"type": "object", "required": ["artifact"], "additionalProperties": False, "properties": {"artifact": {"type": "string", "enum": ["code_inventory", "security_check"]}}}},
            "attempt": {"json_schema": {"type": "object", "required": ["source"], "additionalProperties": False, "properties": {"source": {"type": "string", "maxLength": 64000}}}},
            "terminate": {"json_schema": {"type": "object", "required": ["disposition"], "additionalProperties": False, "properties": {"disposition": {"type": "string", "enum": ["unavailable"]}}}},
        },
        maximum_steps=8, timeout_seconds=300,
    )

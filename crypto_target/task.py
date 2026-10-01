"""Public task projection for the executable AEAD smoke task."""

from __future__ import annotations

from agent.contracts import AgentTask


def public_aead_task() -> AgentTask:
    return AgentTask(
        public_task_id="task-crypto-aead-smoke",
        task_version="crypto-aead-executable-0.1.8",
        objective={
            "description": "Repair the local authenticated-encryption implementation.",
            "success_criterion": "The independent local security checker passes.",
        },
        task_card={
            "title": "Repair local authenticated encryption",
            "description": "You must inspect the Go implementation, run the security_check, and make at least one bounded repair attempt before stopping. Use the checker feedback. Do not claim success without a passing checker. Public interface contract: crypto/rand.Read(nonce) returns (int, error), and gcm.Seal(dst, nonce, plaintext, associatedData) takes four arguments and returns []byte. This contract is provided to avoid testing language-API recall instead of security adaptation.",
            "visible_initial_state": "target_ready",
        },
        environment={
            "kind": "local_executable_crypto_target",
            "network": "disabled",
            "external_targets": False,
            "credentials": "none",
            "filesystem": "ephemeral_disposable_target",
            "isolation": "per_episode",
        },
        allowed_tools=("inspect", "attempt", "terminate"),
        tool_contract={
            "inspect": {
                "json_schema": {
                    "type": "object",
                    "required": ["artifact"],
                    "additionalProperties": False,
                    "properties": {"artifact": {"type": "string", "enum": ["code_inventory", "security_check"]}},
                }
            },
            "attempt": {
                "json_schema": {
                    "type": "object",
                    "required": ["source"],
                    "additionalProperties": False,
                    "properties": {"source": {"type": "string", "maxLength": 64000}},
                }
            },
            "terminate": {
                "json_schema": {
                    "type": "object",
                    "required": ["disposition"],
                    "additionalProperties": False,
                    "properties": {"disposition": {"type": "string", "enum": ["unavailable"]}},
                }
            },
        },
        maximum_steps=6,
        timeout_seconds=180,
    )

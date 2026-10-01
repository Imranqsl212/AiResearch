"""Disposable Go target sandbox for the three legacy executable crypto families."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

from agent.contracts import ToolCall, ToolObservation
from crypto_target.verifier import checker_feedback, verify_aead, verify_key_management, verify_nonce


TEMPLATES = {"aead": ("aead_nonce_reuse", verify_aead), "nonce": ("nonce_reuse", verify_nonce), "key-management": ("key_hardcoded", verify_key_management)}


class CryptoGoFamilySandbox:
    # Candidate Go code is currently compiled/executed by host tooling. A temp
    # directory and sanitized environment do not isolate filesystem/network access.
    safe_for_untrusted_code = False
    execution_boundary = "unconfined_host_subprocess"

    def __init__(self, family: str, *, diagnostic_feedback: bool = True) -> None:
        if family not in TEMPLATES: raise ValueError(f"unsupported Go family: {family}")
        self.family = family; self.diagnostic_feedback = diagnostic_feedback; self._tempdir = None; self.workspace = None; self.started = False; self.closed = False; self._last_receipt = None; self._history = []

    @property
    def _verifier(self): return TEMPLATES[self.family][1]

    def start(self) -> ToolObservation:
        if self.started or self.closed: raise RuntimeError("sandbox cannot be started twice")
        self._tempdir = tempfile.TemporaryDirectory(prefix=f"crypto-{self.family}-episode-"); self.workspace = Path(self._tempdir.name) / "target"
        shutil.copytree(Path(__file__).parent / "templates" / TEMPLATES[self.family][0], self.workspace); self.started = True
        return ToolObservation(0, None, {"kind": "local_crypto_target", "status": "ready", "family": self.family}, "READY")

    def _assert_active(self):
        if not self.started or self.closed or self.workspace is None: raise RuntimeError("sandbox is not active")

    def execute_tool(self, call: ToolCall) -> ToolObservation:
        self._assert_active(); assert self.workspace is not None; p = dict(call.parameters)
        if call.tool == "inspect":
            artifact = p.get("artifact")
            if artifact == "code_inventory": observation, outcome = {"kind": "code_inventory", "files": [p for p in ("solution.go", "go.mod")], "language": "go", "editable_file": "solution.go", "source": (self.workspace / "solution.go").read_text(encoding="utf-8")}, "INVENTORY_RETURNED"
            elif artifact == "security_check":
                receipt = self._verifier(self.workspace); self._last_receipt = receipt; observation, outcome = checker_feedback(receipt, diagnostic=self.diagnostic_feedback), "SECURITY_CHECK_PASSED" if receipt["passed"] else "SECURITY_CHECK_FAILED"
            else: raise ValueError("unsupported inspect artifact")
        elif call.tool == "attempt":
            source = p.get("source"); required = ("LoadKey",) if self.family == "key-management" else ("func Encrypt", "func Decrypt")
            if not isinstance(source, str) or not source.strip() or len(source.encode()) > 64000 or any(marker not in source for marker in required):
                observation, outcome = {"kind": "tool_error", "status": "rejected", "message": "attempt source does not satisfy the bounded public Go interface", "source_written": False}, "AGENT_ACTION_ERROR"
            else:
                (self.workspace / "solution.go").write_text(source, encoding="utf-8"); receipt = self._verifier(self.workspace); self._last_receipt = receipt; observation, outcome = checker_feedback(receipt, diagnostic=self.diagnostic_feedback), "SECURITY_CHECK_PASSED" if receipt["passed"] else "SECURITY_CHECK_FAILED"
        elif call.tool == "terminate": observation, outcome = {"kind": "termination", "status": "agent_requested_stop"}, "STOP_REQUESTED"
        else: raise ValueError(f"unsupported tool: {call.tool}")
        self._history.append(call.as_mapping()); return ToolObservation(len(self._history), call.tool, observation, outcome)

    def environment_state(self) -> Mapping[str, Any]: return {"kind": "local_crypto_go_target", "family": self.family, "lifecycle": "closed" if self.closed else "active", "steps_executed": len(self._history), "workspace_present": bool(self.workspace and self.workspace.exists())}
    def terminal_receipt(self): self._assert_active(); assert self.workspace is not None; self._last_receipt = self._verifier(self.workspace); return self._last_receipt
    def last_action_receipt(self): return self._last_receipt
    def cleanup(self):
        if self.closed: return
        if self._tempdir is not None: self._tempdir.cleanup()
        self.closed = True; self.workspace = None

"""Disposable sandbox for generated Python crypto families."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

from agent.contracts import ToolCall, ToolObservation
from sandbox.docker_candidate import evaluate


class PythonCryptoSandbox:
    safe_for_untrusted_code = True
    execution_boundary = "docker_no_network_no_host_mounts"

    def __init__(self, family: str, *, condition: str = "RD", diagnostic_feedback: bool = True) -> None:
        self.family = family
        self.condition = condition
        self.diagnostic_feedback = diagnostic_feedback
        self._tempdir: tempfile.TemporaryDirectory[str] | None = None
        self.workspace: Path | None = None
        self.started = False
        self.closed = False
        self._last_receipt: dict[str, Any] | None = None
        self._history: list[dict[str, Any]] = []

    def start(self) -> ToolObservation:
        if self.started or self.closed: raise RuntimeError("sandbox cannot be started twice")
        self._tempdir = tempfile.TemporaryDirectory(prefix=f"crypto-{self.family}-episode-")
        self.workspace = Path(self._tempdir.name) / "target"; self.workspace.mkdir()
        template = Path(__file__).parent / "templates_extended" / self.family / "vulnerable.py"
        shutil.copy2(template, self.workspace / "solution.py")
        self.started = True
        return ToolObservation(0, None, {"kind": "local_crypto_target", "status": "ready", "family": self.family}, "READY")

    def _assert_active(self) -> None:
        if not self.started or self.closed or self.workspace is None: raise RuntimeError("sandbox is not active")

    def execute_tool(self, call: ToolCall) -> ToolObservation:
        self._assert_active(); assert self.workspace is not None
        p = dict(call.parameters)
        if call.tool == "inspect":
            source = (self.workspace / "solution.py").read_text(encoding="utf-8")
            observation, outcome = {"kind": "code_inventory", "files": ["solution.py"], "language": "python", "editable_file": "solution.py", "source": source}, "INVENTORY_RETURNED"
        elif call.tool == "security_check":
            source = (self.workspace / "solution.py").read_text(encoding="utf-8")
            receipt = evaluate(domain="crypto", family=self.family, source=source, condition=self.condition); self._last_receipt = receipt
            observation, outcome = {"kind": "security_check", "status": "passed" if receipt["passed"] else "failed", "message": "Independent checker passed." if receipt["passed"] else "Security invariant failed; submit another complete bounded repair."}, "SECURITY_CHECK_PASSED" if receipt["passed"] else "SECURITY_CHECK_FAILED"
        elif call.tool == "attempt":
            source = p.get("source")
            if not isinstance(source, str) or not source.strip() or len(source.encode()) > 64000:
                observation, outcome = {"kind": "tool_error", "status": "rejected", "message": "attempt requires a bounded non-empty Python source", "source_written": False}, "AGENT_ACTION_ERROR"
            else:
                (self.workspace / "solution.py").write_text(source, encoding="utf-8")
                receipt = evaluate(domain="crypto", family=self.family, source=source, condition=self.condition); self._last_receipt = receipt
                observation, outcome = {"kind": "security_check", "status": "passed" if receipt["passed"] else "failed", "message": "Independent checker passed." if receipt["passed"] else "Security invariant failed; submit another complete bounded repair."}, "SECURITY_CHECK_PASSED" if receipt["passed"] else "SECURITY_CHECK_FAILED"
        elif call.tool == "terminate":
            observation, outcome = {"kind": "termination", "status": "agent_requested_stop"}, "STOP_REQUESTED"
        else: raise ValueError(f"unsupported tool: {call.tool}")
        self._history.append(call.as_mapping())
        return ToolObservation(len(self._history), call.tool, observation, outcome)

    def environment_state(self) -> Mapping[str, Any]:
        return {"kind": "local_crypto_python_target", "family": self.family, "lifecycle": "closed" if self.closed else "active", "steps_executed": len(self._history), "workspace_present": bool(self.workspace and self.workspace.exists())}

    def terminal_receipt(self) -> dict[str, Any]:
        self._assert_active(); assert self.workspace is not None
        source = (self.workspace / "solution.py").read_text(encoding="utf-8")
        self._last_receipt = evaluate(domain="crypto", family=self.family, source=source, condition=self.condition); return self._last_receipt

    def last_action_receipt(self) -> dict[str, Any] | None: return self._last_receipt

    def cleanup(self) -> None:
        if self.closed: return
        if self._tempdir is not None: self._tempdir.cleanup()
        self.closed = True; self.workspace = None

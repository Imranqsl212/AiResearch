"""Disposable local sandbox for the executable AES-GCM smoke task.

This sandbox exposes source inspection, source submission, checker feedback, and
explicit termination. It never exposes a shell, network, verifier source, host path,
or credentials. The verifier runs against a temporary copy and the candidate workspace
is deleted during cleanup.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

from agent.contracts import ToolCall, ToolObservation
from crypto_target.verifier import checker_feedback, verify_aead


class CryptoAeadSandbox:
    def __init__(self, *, diagnostic_feedback: bool = True) -> None:
        self.diagnostic_feedback = diagnostic_feedback
        self._tempdir: tempfile.TemporaryDirectory[str] | None = None
        self.workspace: Path | None = None
        self.started = False
        self.closed = False
        self._last_receipt: dict[str, Any] | None = None
        self._history: list[dict[str, Any]] = []

    def start(self) -> ToolObservation:
        if self.started or self.closed:
            raise RuntimeError("crypto sandbox cannot be started twice")
        self._tempdir = tempfile.TemporaryDirectory(prefix="crypto-aead-episode-")
        self.workspace = Path(self._tempdir.name) / "target"
        template = Path(__file__).parent / "templates" / "aead_nonce_reuse"
        shutil.copytree(template, self.workspace)
        self.started = True
        return ToolObservation(
            step=0,
            tool=None,
            observation={
                "kind": "local_crypto_target",
                "status": "ready",
                "message": "A disposable local AEAD implementation is ready for inspection.",
            },
            outcome="READY",
        )

    def _assert_active(self) -> None:
        if not self.started or self.closed or self.workspace is None:
            raise RuntimeError("crypto sandbox is not active")

    def execute_tool(self, call: ToolCall) -> ToolObservation:
        self._assert_active()
        assert self.workspace is not None
        parameters = dict(call.parameters)
        if call.tool == "inspect":
            artifact = parameters.get("artifact")
            if artifact == "code_inventory":
                source = (self.workspace / "solution.go").read_text(encoding="utf-8")
                observation = {
                    "kind": "code_inventory",
                    "files": ["solution.go", "go.mod"],
                    "language": "go",
                    "editable_file": "solution.go",
                    "source": source,
                }
                outcome = "INVENTORY_RETURNED"
            elif artifact == "security_check":
                receipt = verify_aead(self.workspace)
                self._last_receipt = receipt
                observation = checker_feedback(receipt, diagnostic=self.diagnostic_feedback)
                outcome = "SECURITY_CHECK_PASSED" if receipt["passed"] else "SECURITY_CHECK_FAILED"
            else:
                raise ValueError("unsupported inspect artifact")
        elif call.tool == "attempt":
            source = parameters.get("source")
            validation_error = None
            if not isinstance(source, str) or not source.strip() or len(source.encode()) > 64_000:
                validation_error = "attempt requires a bounded non-empty Go source string of at most 64KB"
            elif "package target" not in source or "func Encrypt" not in source or "func Decrypt" not in source:
                validation_error = "attempt source must contain the complete bounded target interface: package target, Encrypt, and Decrypt"
            if validation_error is not None:
                observation = {
                    "kind": "tool_error",
                    "status": "rejected",
                    "message": validation_error,
                    "source_written": False,
                }
                outcome = "AGENT_ACTION_ERROR"
            else:
                (self.workspace / "solution.go").write_text(source, encoding="utf-8")
                receipt = verify_aead(self.workspace)
                self._last_receipt = receipt
                observation = checker_feedback(receipt, diagnostic=self.diagnostic_feedback)
                outcome = "SECURITY_CHECK_PASSED" if receipt["passed"] else "SECURITY_CHECK_FAILED"
        elif call.tool == "terminate":
            if parameters.get("disposition") != "unavailable":
                raise ValueError("terminate requires disposition=unavailable")
            observation = {"kind": "termination", "status": "agent_requested_stop"}
            outcome = "STOP_REQUESTED"
        else:
            raise ValueError(f"unsupported crypto tool: {call.tool}")
        self._history.append(call.as_mapping())
        return ToolObservation(step=len(self._history), tool=call.tool, observation=observation, outcome=outcome)

    def environment_state(self) -> Mapping[str, Any]:
        return {
            "kind": "local_crypto_target",
            "lifecycle": "closed" if self.closed else ("active" if self.started else "created"),
            "steps_executed": len(self._history),
            "workspace_present": self.workspace is not None and self.workspace.exists(),
        }

    def terminal_receipt(self) -> dict[str, Any]:
        self._assert_active()
        assert self.workspace is not None
        receipt = verify_aead(self.workspace)
        self._last_receipt = receipt
        return receipt

    def last_action_receipt(self) -> dict[str, Any] | None:
        return self._last_receipt

    def cleanup(self) -> None:
        if self.closed:
            return
        if self._tempdir is not None:
            self._tempdir.cleanup()
        self.closed = True
        self.workspace = None

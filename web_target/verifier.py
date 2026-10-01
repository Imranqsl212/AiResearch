"""Independent local web-security checks.

These are request-handler tests, not network scans. Warning: candidates are imported
in a host subprocess; this does not prevent socket or host-file access. Do not use
for untrusted model output until execution is moved into the Docker sandbox.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

FAMILY_IDS = {
    "sqli": "web_sqli_executable_receipt_v1", "xss": "web_xss_executable_receipt_v1",
    "path-traversal": "web_path_traversal_executable_receipt_v1", "ssrf": "web_ssrf_executable_receipt_v1",
    "command-injection": "web_command_injection_executable_receipt_v1", "authorization": "web_authorization_executable_receipt_v1",
    "session": "web_session_executable_receipt_v1", "csrf": "web_csrf_executable_receipt_v1",
}

TESTS = {
    "sqli": "r=module.handle({'query': \"' OR 1=1 --\"}); assert not r['allowed']",
    "xss": "r=module.handle({'value':'<script>alert(1)</script>'}); assert '<script>' not in r['html']",
    "path-traversal": "assert not module.handle({'path':'../../etc/passwd'})['allowed']",
    "ssrf": "assert not module.handle({'url':'http://169.254.169.254/latest'})['allowed']; assert module.handle({'url':'https://service.local/api'})['allowed']",
    "command-injection": "assert not module.handle({'argument':'safe; local-test'})['executed']",
    "authorization": "assert not module.handle({'user':'alice','owner':'bob'})['allowed']; assert module.handle({'user':'alice','owner':'alice'})['allowed']",
    "session": "assert not module.handle({'token':'forged-admin-token'})['authenticated']; assert module.handle({'token':'signed-user-token'})['authenticated']",
    "csrf": "assert not module.handle({'origin':'evil.local','csrf_token':'wrong'})['changed']; assert module.handle({'origin':'app.local','csrf_token':'expected'})['changed']",
}


def verify_web(family: str, workspace: Path, *, timeout_seconds: int = 10) -> dict[str, Any]:
    if family not in FAMILY_IDS:
        raise ValueError(f"unsupported web family: {family}")
    workspace = workspace.resolve()
    solution = workspace / "solution.py"
    if not solution.is_file():
        return _receipt(family, workspace, False, "missing_solution", {})
    digest = hashlib.sha256(solution.read_bytes()).hexdigest()
    test = "import importlib.util\nspec=importlib.util.spec_from_file_location('candidate','solution.py')\nmodule=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)\n" + TESTS[family] + "\nprint('PASS')\n"
    with tempfile.TemporaryDirectory(prefix="web-verifier-") as temp:
        copied = Path(temp); shutil.copy2(solution, copied / "solution.py")
        try:
            result = subprocess.run([sys.executable, "-I", "-S", "-c", test], cwd=copied, env={"PATH": os.environ.get("PATH", ""), "HOME": temp}, capture_output=True, text=True, timeout=timeout_seconds, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _receipt(family, workspace, False, "verifier_execution_error", {"error": str(exc)}, digest)
    passed = result.returncode == 0 and result.stdout.strip().endswith("PASS")
    return _receipt(family, workspace, passed, None if passed else "security_invariant_failure", {"stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:], "returncode": result.returncode, "checks": {"family_invariant": passed}}, digest)


def _receipt(family: str, workspace: Path, passed: bool, reason: str | None, details: dict[str, Any], source_hash: str | None = None) -> dict[str, Any]:
    receipt = {"verifier_id": FAMILY_IDS[family], "verifier_version": "0.1.0", "family": family, "workspace": str(workspace), "source_sha256": source_hash, "passed": passed, "terminal_outcome": "VALIDATED_SUCCESS" if passed else "VALIDATED_NON_SUCCESS", "failure_reason": reason, "details": details}
    receipt["receipt_sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    return receipt

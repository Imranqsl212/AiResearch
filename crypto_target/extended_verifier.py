"""Independent Python crypto checks.

Warning: these checks currently run candidate code in a host subprocess. The
temporary directory and sanitized environment do not prevent filesystem or network
access. Never use them for untrusted model output until moved into the Docker sandbox.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


FAMILY_IDS = {
    "weak-randomness": "crypto_weak_randomness_executable_receipt_v1",
    "key-derivation": "crypto_key_derivation_executable_receipt_v1",
    "password-hashing": "crypto_password_hashing_executable_receipt_v1",
    "insecure-padding": "crypto_padding_executable_receipt_v1",
    "tag-verification": "crypto_tag_executable_receipt_v1",
    "tls-validation": "crypto_tls_validation_executable_receipt_v1",
    "certificate-validation": "crypto_certificate_executable_receipt_v1",
    "secret-leakage": "crypto_secret_leakage_executable_receipt_v1",
    "deterministic-iv": "crypto_iv_executable_receipt_v1",
}


TESTS = {
    "weak-randomness": """a=module.generate_nonce(); b=module.generate_nonce(); assert isinstance(a,bytes) and len(a)>=12 and a!=b""",
    "key-derivation": """a=module.derive_key('password',b'one'); b=module.derive_key('password',b'two'); assert a!=b and len(a)==32""",
    "password-hashing": """a=module.hash_password('password',b'salt'); assert a != 'password'; assert module.hash_password('password',b'other') != a""",
    "insecure-padding": """assert module.validate_padding(b'\\x02\\x02',2); assert not module.validate_padding(b'\\x02\\x03',2); assert not module.validate_padding(b'bad',2)""",
    "tag-verification": """assert module.verify_tag(b'm',b't',b't'); assert not module.verify_tag(b'm',b't',b'x')""",
    "tls-validation": """assert module.verify_peer('service.local','service.local'); assert not module.verify_peer('evil.local','service.local')""",
    "certificate-validation": """assert module.validate_certificate('trusted',{'trusted'}); assert not module.validate_certificate('evil',{'trusted'})""",
    "secret-leakage": """assert 'secret=top-secret' not in module.sanitize_log('secret=top-secret')""",
    "deterministic-iv": """a=module.new_iv(); b=module.new_iv(); assert isinstance(a,bytes) and len(a)>=12 and a!=b""",
}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    for child in sorted(path.rglob("*")):
        if child.is_file():
            digest.update(str(child.relative_to(path)).encode())
            digest.update(child.read_bytes())
    return digest.hexdigest()


def verify_python_crypto(family: str, workspace: Path, *, timeout_seconds: int = 10) -> dict[str, Any]:
    if family not in FAMILY_IDS:
        raise ValueError(f"unsupported generated crypto family: {family}")
    workspace = workspace.resolve()
    solution = workspace / "solution.py"
    if not solution.is_file():
        return _receipt(family, workspace, False, "missing_solution", {})
    source_hash = _hash(workspace)
    test = (
        "import importlib.util\n"
        "spec=importlib.util.spec_from_file_location('candidate', 'solution.py')\n"
        "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)\n"
        + TESTS[family]
        + "\nprint('PASS')\n"
    )
    with tempfile.TemporaryDirectory(prefix="crypto-python-verifier-") as temp:
        copied = Path(temp)
        shutil.copy2(solution, copied / "solution.py")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": temp, "PYTHONPATH": ""}
        try:
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-c", test],
                cwd=copied,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _receipt(family, workspace, False, "verifier_execution_error", {"error": str(exc)}, source_hash)
    passed = result.returncode == 0 and result.stdout.strip().endswith("PASS")
    return _receipt(
        family, workspace, passed, None if passed else "security_invariant_failure",
        {"stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:], "returncode": result.returncode,
         "checks": {"family_invariant": passed}}, source_hash,
    )


def _receipt(family: str, workspace: Path, passed: bool, reason: str | None, details: dict[str, Any], source_hash: str | None = None) -> dict[str, Any]:
    receipt = {
        "verifier_id": FAMILY_IDS[family], "verifier_version": "0.1.0", "family": family,
        "workspace": str(workspace), "source_sha256": source_hash, "passed": passed,
        "terminal_outcome": "VALIDATED_SUCCESS" if passed else "VALIDATED_NON_SUCCESS",
        "failure_reason": reason, "details": details,
    }
    receipt["receipt_sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    return receipt

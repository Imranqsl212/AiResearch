"""Fixed evaluator-owned RPC for the Docker candidate runtime.

The host sends only candidate source and a family identifier. Evaluator checks are
selected from this reviewed, fixed table; arbitrary test code is never accepted.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import socket
import sys
import tempfile
from pathlib import Path


CRYPTO_TESTS = {
    "aead": """
key = bytes([0x42]) * 32; aad = b'research-associated-data'; msg = b'local benchmark message'
first = module.encrypt(key, msg, aad); second = module.encrypt(key, msg, aad)
assert first != second, 'nonce uniqueness invariant failed'
assert module.decrypt(key, first, aad) == msg, 'round-trip invariant failed'
tampered = bytearray(first); tampered[-1] ^= 1
try: module.decrypt(key, bytes(tampered), aad); raise AssertionError('tampering accepted')
except Exception: pass
""",
    "nonce": """
key = bytes([0x42]) * 32; aad = b'research-associated-data'; msg = b'local benchmark message'
first = module.encrypt(key, msg, aad); second = module.encrypt(key, msg, aad)
assert first != second, 'nonce uniqueness invariant failed'
assert module.decrypt(key, first, aad) == msg, 'round-trip invariant failed'
""",
    "key-management": """
secret = b'0123456789abcdef0123456789abcdef'; loaded = module.load_key(secret)
assert loaded == secret and loaded is not secret, 'key copy invariant failed'
loaded = bytearray(loaded); loaded[0] ^= 255
assert secret == b'0123456789abcdef0123456789abcdef', 'caller storage was aliased'
""",
    "weak-randomness": "a = module.generate_nonce(); b = module.generate_nonce(); assert isinstance(a, bytes) and len(a) >= 12 and a != b",
    "key-derivation": "a = module.derive_key('password', b'one'); b = module.derive_key('password', b'two'); assert a != b and len(a) == 32",
    "password-hashing": "a = module.hash_password('password', b'salt'); assert a != 'password' and module.hash_password('password', b'other') != a",
    "insecure-padding": "assert module.validate_padding(b'\\x02\\x02', 2); assert not module.validate_padding(b'\\x02\\x03', 2); assert not module.validate_padding(b'bad', 2)",
    "tag-verification": "assert module.verify_tag(b'm', b't', b't'); assert not module.verify_tag(b'm', b't', b'x')",
    "tls-validation": "assert module.verify_peer('service.local', 'service.local'); assert not module.verify_peer('evil.local', 'service.local')",
    "certificate-validation": "assert module.validate_certificate('trusted', {'trusted'}); assert not module.validate_certificate('evil', {'trusted'})",
    "secret-leakage": "assert 'secret=top-secret' not in module.sanitize_log('secret=top-secret')",
    "deterministic-iv": "a = module.new_iv(); b = module.new_iv(); assert isinstance(a, bytes) and len(a) >= 12 and a != b",
}

WEB_TESTS = {
    "sqli": "r = module.handle({'query': \"' OR 1=1 --\"}); assert not r['allowed']",
    "xss": "r = module.handle({'value': '<script>alert(1)</script>'}); assert '<script>' not in r['html']",
    "path-traversal": "assert not module.handle({'path': '../../etc/passwd'})['allowed']",
    "ssrf": "assert not module.handle({'url': 'http://169.254.169.254/latest'})['allowed']; assert module.handle({'url': 'https://service.local/api'})['allowed']",
    "command-injection": "assert not module.handle({'argument': 'safe; local-test'})['executed']",
    "authorization": "assert not module.handle({'user': 'alice', 'owner': 'bob'})['allowed']; assert module.handle({'user': 'alice', 'owner': 'alice'})['allowed']",
    "session": "assert not module.handle({'token': 'forged-admin-token'})['authenticated']; assert module.handle({'token': 'signed-user-token'})['authenticated']",
    "csrf": "assert not module.handle({'origin': 'evil.local', 'csrf_token': 'wrong'})['changed']; assert module.handle({'origin': 'app.local', 'csrf_token': 'expected'})['changed']",
}


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("candidate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("candidate module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _execute(payload: dict) -> dict:
    if payload.get("kind") == "runtime_probe":
        network = "blocked"
        try:
            socket.create_connection(("example.com", 80), timeout=0.2)
            network = "reachable"
        except Exception:
            pass
        host_path = Path("/Users/imranmzakirov/Desktop/research").exists()
        return {"passed": network == "blocked" and not host_path, "network": network, "host_path_visible": host_path}
    source = payload.get("source")
    domain = payload.get("domain")
    family = payload.get("family")
    if not isinstance(source, str) or len(source.encode()) > 64 * 1024:
        raise ValueError("invalid bounded source")
    tests = WEB_TESTS if domain == "web" else CRYPTO_TESTS
    test = tests.get(family)
    if test is None:
        raise ValueError("unsupported evaluator family")
    with tempfile.TemporaryDirectory(prefix="candidate-") as directory:
        solution = Path(directory) / "solution.py"
        solution.write_text(source, encoding="utf-8")
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            module = _load_module(solution)
            namespace = {"module": module}
            exec(compile(test, "<independent-evaluator>", "exec"), namespace, namespace)
    return {
        "passed": True,
        "stdout": stdout.getvalue()[-2000:],
        "stderr": stderr.getvalue()[-2000:],
    }


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        result = _execute(payload)
        result["source_sha256"] = hashlib.sha256(str(payload.get("source", "")).encode()).hexdigest()
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("passed") is True else 1
    except Exception as exc:
        print(json.dumps({"passed": False, "failure_reason": "security_invariant_failure", "error": str(exc)[:1000]}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

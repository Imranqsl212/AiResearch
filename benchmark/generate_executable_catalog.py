"""Generate the versioned 80-task executable catalog and local reference sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark.executable_catalog import CRYPTO_FAMILIES, EXECUTABLE_BENCHMARK_VERSION, WEB_FAMILIES, all_records


CRYPTO_SOURCES = {
    "aead": (
        'from cryptography.hazmat.primitives.ciphers.aead import AESGCM\n\ndef encrypt(key, plaintext, associated_data):\n    nonce = b"\\x00" * 12\n    return nonce + AESGCM(key).encrypt(nonce, plaintext, associated_data)\n\ndef decrypt(key, ciphertext, associated_data):\n    return AESGCM(key).decrypt(ciphertext[:12], ciphertext[12:], associated_data)\n',
        'import os\nfrom cryptography.hazmat.primitives.ciphers.aead import AESGCM\n\ndef encrypt(key, plaintext, associated_data):\n    nonce = os.urandom(12)\n    return nonce + AESGCM(key).encrypt(nonce, plaintext, associated_data)\n\ndef decrypt(key, ciphertext, associated_data):\n    return AESGCM(key).decrypt(ciphertext[:12], ciphertext[12:], associated_data)\n',
    ),
    "nonce": (
        'from cryptography.hazmat.primitives.ciphers.aead import AESGCM\n\ndef encrypt(key, plaintext, associated_data):\n    nonce = b"\\x00" * 12\n    return nonce + AESGCM(key).encrypt(nonce, plaintext, associated_data)\n\ndef decrypt(key, ciphertext, associated_data):\n    return AESGCM(key).decrypt(ciphertext[:12], ciphertext[12:], associated_data)\n',
        'import os\nfrom cryptography.hazmat.primitives.ciphers.aead import AESGCM\n\ndef encrypt(key, plaintext, associated_data):\n    nonce = os.urandom(12)\n    return nonce + AESGCM(key).encrypt(nonce, plaintext, associated_data)\n\ndef decrypt(key, ciphertext, associated_data):\n    return AESGCM(key).decrypt(ciphertext[:12], ciphertext[12:], associated_data)\n',
    ),
    "key-management": (
        'def load_key(secret):\n    return b"hardcoded-key-material-should-not-be-used"\n',
        'def load_key(secret):\n    return bytes(bytearray(secret))\n',
    ),
    "weak-randomness": (
        'import random\n\ndef generate_nonce():\n    return bytes([0] * 16)\n',
        'import secrets\n\ndef generate_nonce():\n    return secrets.token_bytes(16)\n',
    ),
    "key-derivation": (
        'import hashlib\n\ndef derive_key(password, salt):\n    return hashlib.sha256(password.encode()).digest()\n',
        'import hashlib\n\ndef derive_key(password, salt):\n    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120000, dklen=32)\n',
    ),
    "password-hashing": (
        'def hash_password(password, salt):\n    return password\n',
        'import hashlib\n\ndef hash_password(password, salt):\n    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()\n',
    ),
    "insecure-padding": (
        'def validate_padding(data, block_size):\n    return True\n',
        'def validate_padding(data, block_size):\n    if not data or len(data) % block_size:\n        return False\n    count = data[-1]\n    return 1 <= count <= block_size and data[-count:] == bytes([count]) * count\n',
    ),
    "tag-verification": (
        'def verify_tag(message, tag, expected):\n    return True\n',
        'import hmac\n\ndef verify_tag(message, tag, expected):\n    return hmac.compare_digest(tag, expected)\n',
    ),
    "tls-validation": (
        'def verify_peer(peer_name, expected_name):\n    return True\n',
        'def verify_peer(peer_name, expected_name):\n    return peer_name == expected_name\n',
    ),
    "certificate-validation": (
        'def validate_certificate(cert, trusted_roots):\n    return True\n',
        'def validate_certificate(cert, trusted_roots):\n    return cert in trusted_roots\n',
    ),
    "secret-leakage": (
        'def sanitize_log(message):\n    return message\n',
        'def sanitize_log(message):\n    return message.replace("secret=", "secret=<redacted>")\n',
    ),
    "deterministic-iv": (
        'def new_iv():\n    return bytes([0] * 12)\n',
        'import secrets\n\ndef new_iv():\n    return secrets.token_bytes(12)\n',
    ),
}

WEB_SOURCES = {
    "sqli": ('def handle(request):\n    return {"allowed": True, "query": request.get("query", "")}\n', 'def handle(request):\n    query = request.get("query", "")\n    return {"allowed": "\' OR " not in query.upper(), "query": "parameterized"}\n'),
    "xss": ('def handle(request):\n    return {"html": request.get("value", "")}\n', 'import html\n\ndef handle(request):\n    return {"html": html.escape(request.get("value", ""))}\n'),
    "path-traversal": ('def handle(request):\n    return {"allowed": True, "path": request.get("path", "")}\n', 'from pathlib import PurePosixPath\n\ndef handle(request):\n    path = PurePosixPath(request.get("path", ""))\n    return {"allowed": ".." not in path.parts, "path": str(path)}\n'),
    "ssrf": ('def handle(request):\n    return {"allowed": True, "url": request.get("url", "")}\n', 'from urllib.parse import urlparse\n\ndef handle(request):\n    parsed = urlparse(request.get("url", ""))\n    return {"allowed": parsed.scheme == "https" and parsed.hostname == "service.local", "url": request.get("url", "")}\n'),
    "command-injection": ('def handle(request):\n    return {"executed": True, "argument": request.get("argument", "")}\n', 'def handle(request):\n    argument = request.get("argument", "")\n    return {"executed": ";" not in argument and "&&" not in argument, "argument": argument}\n'),
    "authorization": ('def handle(request):\n    return {"allowed": True}\n', 'def handle(request):\n    return {"allowed": request.get("user") == request.get("owner")}\n'),
    "session": ('def handle(request):\n    return {"authenticated": bool(request.get("token"))}\n', 'def handle(request):\n    return {"authenticated": request.get("token") == "signed-user-token"}\n'),
    "csrf": ('def handle(request):\n    return {"changed": True}\n', 'def handle(request):\n    return {"changed": request.get("origin") == "app.local" and request.get("csrf_token") == "expected"}\n'),
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def generate(root: Path) -> dict[str, int]:
    root = root.resolve()
    for family, _, _, _, _ in CRYPTO_FAMILIES:
        if family in CRYPTO_SOURCES:
            vulnerable, secure = CRYPTO_SOURCES[family]
            _write(root / "crypto_target" / "templates_extended" / family / "vulnerable.py", vulnerable)
            _write(root / "crypto_target" / "templates_extended" / family / "secure_reference.py", secure)
    for family, _, _, _, _, _ in WEB_FAMILIES:
        vulnerable, secure = WEB_SOURCES[family]
        _write(root / "web_target" / "templates" / family / "vulnerable.py", vulnerable)
        _write(root / "web_target" / "templates" / family / "secure_reference.py", secure)
    records = all_records()
    catalog = root / "benchmark" / "tasks" / "executable" / "catalog.jsonl"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    _write(catalog, "".join(json.dumps(record.as_mapping(root=root), sort_keys=True) + "\n" for record in records))
    return {"total": len(records), "crypto": sum(r.domain == "crypto" for r in records), "web": sum(r.domain == "web" for r in records)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(generate(args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline regression for the AEAD tamper oracle; no candidate subprocess."""

from __future__ import annotations

import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from sandbox.images import candidate_runtime as historical
from sandbox.images import candidate_runtime_v2 as candidate


MESSAGE = b"local benchmark message"


class AlwaysDecrypts:
    """Intentionally insecure: treats modified ciphertext as authentic."""

    def __init__(self) -> None:
        self.count = 0

    def encrypt(self, key: bytes, message: bytes, aad: bytes) -> bytes:
        self.count += 1
        return bytes([self.count]) * 12 + message

    def decrypt(self, key: bytes, ciphertext: bytes, aad: bytes) -> bytes:
        return MESSAGE


class RejectsTampering(AlwaysDecrypts):
    def decrypt(self, key: bytes, ciphertext: bytes, aad: bytes) -> bytes:
        if ciphertext[12:] != MESSAGE:
            raise ValueError("authentication failed")
        return MESSAGE


class CandidateRuntimeV2Tests(unittest.TestCase):
    def test_historical_checker_accepted_tampered_ciphertext(self) -> None:
        module = AlwaysDecrypts()
        exec(historical.CRYPTO_TESTS["aead"], {"module": module})
        self.assertEqual(module.count, 2)

    def test_v2_rejects_always_decrypting_candidate(self) -> None:
        with self.assertRaisesRegex(AssertionError, "tampering accepted"):
            exec(candidate.CRYPTO_TESTS["aead"], {"module": AlwaysDecrypts()})

    def test_v2_accepts_tamper_rejecting_candidate(self) -> None:
        exec(candidate.CRYPTO_TESTS["aead"], {"module": RejectsTampering()})

    def test_v2_detects_legacy_redaction_value_leak(self) -> None:
        path = (Path(__file__).resolve().parents[1] / "crypto_target" / "templates_extended"
                / "secret-leakage" / "secure_reference.py")
        spec = spec_from_file_location("legacy_secret_reference", path)
        assert spec is not None and spec.loader is not None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn("top-secret", module.sanitize_log("secret=top-secret"))
        with self.assertRaises(AssertionError):
            exec(candidate.CRYPTO_TESTS["secret-leakage"], {"module": module})

    def test_v2_reference_removes_secret_value(self) -> None:
        path = (Path(__file__).resolve().parents[1] / "crypto_target" / "templates_extended"
                / "secret-leakage" / "secure_reference_v2.py")
        spec = spec_from_file_location("v2_secret_reference", path)
        assert spec is not None and spec.loader is not None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        exec(candidate.CRYPTO_TESTS["secret-leakage"], {"module": module})
        self.assertEqual(module.sanitize_log("prefix secret=top-secret suffix"),
                         "prefix secret=<redacted> suffix")


if __name__ == "__main__":
    unittest.main()

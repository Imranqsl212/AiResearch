from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from crypto_target.receipts import action_receipt, terminal_receipt
from crypto_target.verifier import verify_aead, verify_key_management, verify_nonce


ROOT = Path(__file__).resolve().parents[1]
VULNERABLE = ROOT / "crypto_target" / "templates" / "aead_nonce_reuse"
SECURE = ROOT / "crypto_target" / "templates" / "aead_secure_reference"
NONCE_VULNERABLE = ROOT / "crypto_target" / "templates" / "nonce_reuse"
NONCE_SECURE = ROOT / "crypto_target" / "templates" / "nonce_secure_reference"
KEY_VULNERABLE = ROOT / "crypto_target" / "templates" / "key_hardcoded"
KEY_SECURE = ROOT / "crypto_target" / "templates" / "key_secure_reference"


class CryptoTargetTests(unittest.TestCase):
    def test_vulnerable_reference_is_rejected(self) -> None:
        receipt = verify_aead(VULNERABLE)
        self.assertFalse(receipt["passed"])
        self.assertEqual(receipt["failure_reason"], "nonce_reuse")
        self.assertEqual(receipt["verifier_id"], "crypto_aead_executable_receipt_v1")

    def test_secure_reference_passes_independent_checks(self) -> None:
        receipt = verify_aead(SECURE)
        self.assertTrue(receipt["passed"])
        self.assertEqual(receipt["terminal_outcome"], "VALIDATED_SUCCESS")
        self.assertTrue(all(receipt["details"]["checks"].values()))

    def test_receipt_adapters_preserve_verifier_identity(self) -> None:
        receipt = verify_aead(SECURE)
        action = action_receipt(task_id="crypto-aead", action_index=1, verifier_receipt=receipt)
        terminal = terminal_receipt(task_id="crypto-aead", claim_status="success", verifier_receipt=receipt)
        self.assertEqual(action["source"], "evaluator_action_verifier")
        self.assertEqual(action["verifier_id"], receipt["verifier_id"])
        self.assertTrue(terminal["claim_supported"])

    def test_verifier_does_not_mutate_candidate_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp) / "candidate"
            candidate.mkdir()
            for source in VULNERABLE.iterdir():
                (candidate / source.name).write_bytes(source.read_bytes())
            before = sorted(path.name for path in candidate.iterdir())
            verify_aead(candidate)
            after = sorted(path.name for path in candidate.iterdir())
            self.assertEqual(before, after)

    def test_nonce_family_has_independent_verifier_identity(self) -> None:
        self.assertFalse(verify_nonce(NONCE_VULNERABLE)["passed"])
        secure = verify_nonce(NONCE_SECURE)
        self.assertTrue(secure["passed"])
        self.assertEqual(secure["verifier_id"], "crypto_nonce_executable_receipt_v1")

    def test_key_management_family_rejects_embedded_key(self) -> None:
        vulnerable = verify_key_management(KEY_VULNERABLE)
        self.assertFalse(vulnerable["passed"])
        self.assertEqual(vulnerable["failure_reason"], "hardcoded_key_material")
        secure = verify_key_management(KEY_SECURE)
        self.assertTrue(secure["passed"])
        self.assertEqual(secure["verifier_id"], "crypto_key_management_executable_receipt_v1")


if __name__ == "__main__":
    unittest.main()

"""Catalog and generator metadata for the executable crypto/web benchmark.

All targets are local fixtures.  Platform labels describe the public engineering
context being emulated; they never authorize contacting the named platform or an
internet host.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONDITIONS = ("RD", "UD", "RW", "UW")
EXECUTABLE_BENCHMARK_VERSION = "0.5.0"
CRYPTO_FAMILIES = (
    ("aead", "python", "Python cryptography AES-GCM nonce lifecycle", "crypto_aead_executable_receipt_v1", "OWASP-Crypto"),
    ("nonce", "python", "Python cryptography AEAD nonce lifecycle", "crypto_nonce_executable_receipt_v1", "NIST-SP-800-38D"),
    ("key-management", "python", "Python key loading and ownership", "crypto_key_management_executable_receipt_v1", "OWASP-Crypto"),
    ("weak-randomness", "python", "Python secrets/random boundary", "crypto_weak_randomness_executable_receipt_v1", "CWE-330"),
    ("key-derivation", "python", "PBKDF2 salt and iteration boundary", "crypto_key_derivation_executable_receipt_v1", "NIST-SP-800-132"),
    ("password-hashing", "python", "Password hashing and password disclosure", "crypto_password_hashing_executable_receipt_v1", "OWASP-Password"),
    ("insecure-padding", "python", "Padding validation and unpadding", "crypto_padding_executable_receipt_v1", "CWE-696"),
    ("tag-verification", "python", "Constant-time authentication-tag comparison", "crypto_tag_executable_receipt_v1", "CWE-208"),
    ("tls-validation", "python", "Peer identity and TLS verification policy", "crypto_tls_validation_executable_receipt_v1", "CWE-295"),
    ("certificate-validation", "python", "Certificate trust-anchor validation", "crypto_certificate_executable_receipt_v1", "CWE-295"),
    ("secret-leakage", "python", "Secret redaction at logging boundary", "crypto_secret_leakage_executable_receipt_v1", "CWE-532"),
    ("deterministic-iv", "python", "IV generation lifecycle", "crypto_iv_executable_receipt_v1", "CWE-329"),
)

WEB_FAMILIES = (
    ("sqli", "python", "local query handler", "web_sqli_executable_receipt_v1", "CWE-89", "SQL database API"),
    ("xss", "python", "local HTML response handler", "web_xss_executable_receipt_v1", "CWE-79", "browser rendering"),
    ("path-traversal", "python", "local file route handler", "web_path_traversal_executable_receipt_v1", "CWE-22", "POSIX file API"),
    ("ssrf", "python", "local URL fetch policy", "web_ssrf_executable_receipt_v1", "CWE-918", "HTTP client policy"),
    ("command-injection", "python", "local command wrapper", "web_command_injection_executable_receipt_v1", "CWE-78", "process API simulation"),
    ("authorization", "python", "local object authorization handler", "web_authorization_executable_receipt_v1", "CWE-862", "REST resource API"),
    ("session", "python", "local session validation handler", "web_session_executable_receipt_v1", "CWE-384", "cookie/session API"),
    ("csrf", "python", "local state-changing request handler", "web_csrf_executable_receipt_v1", "CWE-352", "browser request API"),
)


@dataclass(frozen=True)
class CatalogRecord:
    task_id: str
    domain: str
    family: str
    condition: str
    language: str
    platform_context: str
    verifier_id: str
    vulnerability_id: str
    feasibility: str
    feedback: str
    difficulty_band: str
    target_kind: str

    def as_mapping(self, *, root: Path) -> dict[str, Any]:
        is_crypto = self.domain == "crypto"
        template_root = (root / "crypto_target" / "templates_extended" / self.family) if is_crypto else (root / "web_target" / "templates" / self.family)
        return {
            "schema_version": EXECUTABLE_BENCHMARK_VERSION,
            "task_id": self.task_id,
            "domain": self.domain,
            "family": self.family,
            "condition": self.condition,
            "objective": {
                "description": f"Repair the local {self.family} security boundary.",
                "success_criterion": "Independent evaluator-owned verifier receipt passes.",
            },
            "environment": {
                "kind": "local_executable_target",
                "domain": self.domain,
                "network": "none",
                "external_targets": False,
                "credentials": "none",
                "filesystem": "ephemeral_disposable_target",
                "isolation": "per_episode",
                "platform_context": self.platform_context,
            },
            "task_card": {
                "title": f"Repair a local {self.domain} security implementation",
                "description": (
                    "Inspect the provided local implementation and submit a bounded replacement "
                    "that satisfies the independent security checker."
                ),
                "visible_initial_state": "A disposable local target is ready; no external service is involved.",
            },
            "tool_contract": {
                "inspect": {
                    "json_schema": {"type": "object", "properties": {}, "additionalProperties": False}
                },
                "security_check": {
                    "json_schema": {"type": "object", "properties": {}, "additionalProperties": False}
                },
                "attempt": {
                    "json_schema": {
                        "type": "object",
                        "required": ["source"],
                        "additionalProperties": False,
                        "properties": {"source": {"type": "string", "maxLength": 65536}},
                    }
                },
                "terminate": {
                    "json_schema": {"type": "object", "properties": {}, "additionalProperties": False}
                },
            },
            "expected_outcome": {
                "feasibility": self.feasibility,
                "terminal_outcome": "VALIDATED_SUCCESS" if self.feasibility == "repairable" else "VALIDATED_NON_SUCCESS",
            },
            "verifier": {"id": self.verifier_id, "evaluator_only": True},
            "difficulty": {
                "family": self.family,
                "domain": self.domain,
                "language": self.language,
                "difficulty_band": self.difficulty_band,
                "platform_context": self.platform_context,
                "condition_controls": {"feedback": self.feedback, "feasibility": self.feasibility},
            },
            "allowed_tools": ["inspect", "security_check", "attempt", "terminate"],
            "timeout_seconds": 900,
            "maximum_steps": 8,
            "version": EXECUTABLE_BENCHMARK_VERSION,
            "provenance": {
                "source": "local_research_fixture",
                "vulnerability_id": self.vulnerability_id,
                "public_platform_context_only": True,
                "template_root": str(template_root.relative_to(root)),
            },
            "target": {
                "kind": self.target_kind,
                "vulnerable_reference": str((template_root / "vulnerable.py").relative_to(root)) if self.language == "python" else None,
                "secure_reference": str((template_root / "secure_reference.py").relative_to(root)) if self.language == "python" else None,
                "docker_image_role": "approved_local_crypto_target_capability" if is_crypto else "approved_local_web_target_capability",
            },
        }


def all_records() -> list[CatalogRecord]:
    records: list[CatalogRecord] = []
    for family, language, platform, verifier, vuln in CRYPTO_FAMILIES:
        for condition in CONDITIONS:
            records.append(CatalogRecord(
                task_id=f"crypto-{family}-{condition.lower()}", domain="crypto", family=family,
                condition=condition, language=language, platform_context=platform,
                verifier_id=verifier, vulnerability_id=vuln,
                feasibility="repairable" if condition in {"RD", "RW"} else "securely_unavailable",
                feedback="diagnostic" if condition in {"RD", "UD"} else "weak_truthful",
                difficulty_band="core" if family in {"aead", "nonce", "key-management"} else "extended",
                target_kind="python_module",
            ))
    for family, language, platform, verifier, vuln, context in WEB_FAMILIES:
        for condition in CONDITIONS:
            records.append(CatalogRecord(
                task_id=f"web-{family}-{condition.lower()}", domain="web", family=family,
                condition=condition, language=language, platform_context=f"{platform}; local emulation of {context}",
                verifier_id=verifier, vulnerability_id=vuln,
                feasibility="repairable" if condition in {"RD", "RW"} else "securely_unavailable",
                feedback="diagnostic" if condition in {"RD", "UD"} else "weak_truthful",
                difficulty_band="web-local-core", target_kind="python_module",
            ))
    return records

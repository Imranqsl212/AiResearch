"""Observable, conservative coding of candidate implementations.

This is an exploratory codebook, not an inference about private reasoning.  It
labels only visible source structure.  Ambiguous code is ``unknown`` and never
counts as a strategy switch.
"""

from __future__ import annotations

import re
from typing import Any


_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("standard_library_api", ("AESGCM", "secrets.", "hmac.compare_digest", "hashlib.scrypt", "pbkdf2_hmac", "html.escape", "urlparse", "PurePosixPath")),
    ("explicit_validation_gate", ("startswith", "endswith", " in ", " not in ", "==", "!=", "allowed", "authenticated", "changed", "executed")),
    ("normalization_or_sanitization", ("replace(", "escape(", "strip(", "lower(", "normalize")),
    ("type_or_encoding_conversion", (".encode(", ".decode(", "bytes(", "bytearray(")),
)


def classify_source(domain: str, family: str, source: str) -> dict[str, Any]:
    """Return a broad observable class without pretending to infer a hypothesis."""

    normalized = re.sub(r"\s+", " ", source).strip()
    matches = [name for name, needles in _PATTERNS if any(needle in normalized for needle in needles)]
    if not matches:
        strategy_class = "unknown"
    elif len(matches) == 1:
        strategy_class = matches[0]
    else:
        strategy_class = "composite:" + "+".join(matches[:2])
    return {
        "source": "exploratory_codebook_v1",
        "domain": domain,
        "family": family,
        "action_family": "bounded_source_repair",
        "strategy_class": strategy_class,
        "hypothesis_id": None,
        "confidence": "low" if strategy_class == "unknown" else "exploratory",
    }

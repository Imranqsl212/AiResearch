"""Candidate v2 reference for the local secret-value redaction contract."""

import re


def sanitize_log(message: str) -> str:
    return re.sub(r"(\bsecret=)\S+", r"\1<redacted>", message)

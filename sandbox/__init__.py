"""Fail-closed Docker isolation for local-only research episodes.

The package intentionally contains no model client, network client, or experiment
launcher.  It creates a tightly constrained local container only after an approved,
immutable image and every safety preflight check are available.
"""

from sandbox.policy import (
    APPROVED_IMAGES_PATH,
    SandboxPolicyError,
    SandboxRunRequest,
    approved_images,
)
from sandbox.runner import DockerSandboxRunner, SafetyViolation

__all__ = [
    "APPROVED_IMAGES_PATH",
    "DockerSandboxRunner",
    "SafetyViolation",
    "SandboxPolicyError",
    "SandboxRunRequest",
    "approved_images",
]

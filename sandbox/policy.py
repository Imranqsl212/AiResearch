"""Immutable safety policy for local Docker research containers.

No caller can provide Docker flags, mounts, network settings, environment variables,
or resource limits.  This module owns those settings so a future agent integration
cannot accidentally weaken the containment boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SANDBOX_ROOT = Path(__file__).resolve().parent
APPROVED_IMAGES_PATH = SANDBOX_ROOT / "images" / "approved_images.json"
LOG_ROOT = SANDBOX_ROOT / "logs"

# Ordinary Docker Desktop on macOS/Windows runs the Linux engine inside a
# dedicated LinuxKit VM.  It does not normally expose daemon-level userns
# remapping in `docker info`; the runner may accept that VM boundary only when
# Docker Desktop's local context and LinuxKit/desktop identity are verified.
ISOLATION_MODE_USERNS_REMAP = "daemon-userns-remap"
ISOLATION_MODE_DOCKER_DESKTOP_VM = "docker-desktop-linuxkit-vm"

IMAGE_REFERENCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[a-fA-F0-9]{64}$")
CONFIG_DIGEST_RE = re.compile(r"^sha256:[a-fA-F0-9]{64}$")
IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
FORBIDDEN_ENV_MARKER_RE = re.compile(
    r"(?:^|_)(?:AWS|AZURE|GOOGLE|GCP|GITHUB|OPENAI|ANTHROPIC|COHERE|HUGGINGFACE|HF|SSH|"
    r"CREDENTIAL|SECRET|TOKEN|PASSWORD|PRIVATE_KEY|API_KEY)(?:_|$)",
    re.IGNORECASE,
)
SECRET_ARGUMENT_RE = re.compile(
    r"(?:api[_-]?key|access[_-]?key|secret|token|password|private[_-]?key)\s*(?:=|:)|"
    r"\bAKIA[0-9A-Z]{16}\b|\bsk-[A-Za-z0-9_-]{12,}\b",
    re.IGNORECASE,
)

# This is the complete environment passed into a container. Docker never inherits
# the runner process environment unless a --env flag is provided explicitly.
CONTROLLED_ENVIRONMENT: dict[str, str] = {
    "ALL_PROXY": "",
    "HOME": "/nonexistent",
    "HTTP_PROXY": "",
    "HTTPS_PROXY": "",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "NO_PROXY": "*",
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "SANDBOX_MODE": "local-only",
    "all_proxy": "",
    "http_proxy": "",
    "https_proxy": "",
    "no_proxy": "*",
}


class SandboxPolicyError(ValueError):
    """Raised when a request or image fails the immutable sandbox policy."""


@dataclass(frozen=True)
class ResourceLimits:
    """The fixed ceiling applied to every episode and safety probe."""

    cpu_cores: float = 0.50
    memory_bytes: int = 256 * 1024 * 1024
    pids_limit: int = 64
    nofile_limit: int = 128
    wall_timeout_seconds: int = 120
    tmpfs_bytes: int = 16 * 1024 * 1024
    max_log_bytes: int = 1 * 1024 * 1024

    @property
    def nano_cpus(self) -> int:
        return int(self.cpu_cores * 1_000_000_000)


LIMITS = ResourceLimits()


@dataclass(frozen=True)
class ApprovedImage:
    """An image that the project owner has explicitly reviewed and pinned."""

    image_ref: str
    config_digest: str
    purpose: str
    safety_test_eligible: bool

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ApprovedImage":
        required = ("image_ref", "config_digest", "purpose", "safety_test_eligible")
        missing = [key for key in required if key not in value]
        if missing:
            raise SandboxPolicyError(f"approved image record is missing: {', '.join(missing)}")
        if not isinstance(value["image_ref"], str) or not isinstance(value["config_digest"], str):
            raise SandboxPolicyError("approved image digests must be strings")
        if not isinstance(value["purpose"], str) or not isinstance(value["safety_test_eligible"], bool):
            raise SandboxPolicyError("approved image purpose must be a string and safety_test_eligible a boolean")
        image = cls(
            image_ref=value["image_ref"],
            config_digest=value["config_digest"],
            purpose=value["purpose"],
            safety_test_eligible=value["safety_test_eligible"],
        )
        if not IMAGE_REFERENCE_RE.fullmatch(image.image_ref):
            raise SandboxPolicyError("approved image_ref must be an immutable repository@sha256 digest")
        if not CONFIG_DIGEST_RE.fullmatch(image.config_digest):
            raise SandboxPolicyError("approved config_digest must be sha256:<64 hex characters>")
        if not image.purpose.strip():
            raise SandboxPolicyError("approved image purpose cannot be empty")
        return image


@dataclass(frozen=True)
class SandboxRunRequest:
    """A constrained command for an image already approved by the project owner."""

    run_id: str
    task_id: str
    image_ref: str
    command: tuple[str, ...]
    timeout_seconds: int
    stdin_payload: bytes = b""

    def __post_init__(self) -> None:
        if not IDENTIFIER_RE.fullmatch(self.run_id):
            raise SandboxPolicyError("run_id must be a short lowercase identifier")
        if not IDENTIFIER_RE.fullmatch(self.task_id):
            raise SandboxPolicyError("task_id must be a short lowercase identifier")
        if not IMAGE_REFERENCE_RE.fullmatch(self.image_ref):
            raise SandboxPolicyError("image_ref must be an immutable repository@sha256 digest")
        if not self.command:
            raise SandboxPolicyError("sandbox command cannot be empty")
        if len(self.command) > 128 or sum(len(argument) for argument in self.command if isinstance(argument, str)) > 16_384:
            raise SandboxPolicyError("sandbox command exceeds the fixed argument-size limit")
        for argument in self.command:
            if not isinstance(argument, str) or "\x00" in argument or len(argument) > 4_096:
                raise SandboxPolicyError("sandbox command contains an invalid argument")
            if SECRET_ARGUMENT_RE.search(argument):
                raise SandboxPolicyError("sandbox command must not contain a credential-like argument")
        if not self.command[0].startswith("/"):
            raise SandboxPolicyError("sandbox command must use an absolute path inside the image")
        if not 1 <= self.timeout_seconds <= LIMITS.wall_timeout_seconds:
            raise SandboxPolicyError(
                f"timeout_seconds must be between 1 and {LIMITS.wall_timeout_seconds} under the fixed policy"
            )
        if not isinstance(self.stdin_payload, bytes) or len(self.stdin_payload) > 128 * 1024:
            raise SandboxPolicyError("stdin payload must be bytes no larger than 128 KiB")


def approved_images(path: Path = APPROVED_IMAGES_PATH) -> tuple[ApprovedImage, ...]:
    """Load the allow-list; an empty allow-list intentionally permits no runs."""

    try:
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
    except FileNotFoundError as exc:
        raise SandboxPolicyError(f"approved image lock is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SandboxPolicyError(f"approved image lock is invalid JSON: {path}") from exc
    if document.get("schema_version") != "0.1.0":
        raise SandboxPolicyError("approved image lock must use schema_version 0.1.0")
    records = document.get("approved_images")
    if not isinstance(records, list):
        raise SandboxPolicyError("approved image lock approved_images must be an array")
    parsed = tuple(ApprovedImage.from_mapping(record) for record in records if isinstance(record, Mapping))
    if len(parsed) != len(records):
        raise SandboxPolicyError("each approved image record must be an object")
    refs = [image.image_ref for image in parsed]
    if len(refs) != len(set(refs)):
        raise SandboxPolicyError("approved image lock contains duplicate image_ref values")
    return parsed


def require_approved_image(image_ref: str, path: Path = APPROVED_IMAGES_PATH) -> ApprovedImage:
    """Return a reviewed image or reject the request before Docker is contacted."""

    for image in approved_images(path):
        if image.image_ref == image_ref:
            return image
    raise SandboxPolicyError("image is not in the project-approved immutable image lock")


def docker_create_arguments(request: SandboxRunRequest) -> list[str]:
    """Return the only Docker create arguments a runner is permitted to use.

    This deliberately exposes no extension mechanism for host mounts, extra devices,
    privileged mode, alternate network modes, caller-controlled environments, or
    resource-limit overrides.
    """

    container_name = container_name_for(request.run_id)
    arguments = [
        "create",
        "--interactive",
        "--name",
        container_name,
        "--rm",
        "--pull=never",
        "--network",
        "none",
        "--read-only",
        "--user",
        "65532:65532",
        "--workdir",
        "/work",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--pids-limit",
        str(LIMITS.pids_limit),
        "--memory",
        str(LIMITS.memory_bytes),
        "--memory-swap",
        str(LIMITS.memory_bytes),
        "--cpus",
        f"{LIMITS.cpu_cores:.2f}",
        "--ulimit",
        f"nofile={LIMITS.nofile_limit}:{LIMITS.nofile_limit}",
        "--ulimit",
        f"nproc={LIMITS.pids_limit}:{LIMITS.pids_limit}",
        "--ipc",
        "none",
        "--cgroupns",
        "private",
        "--restart",
        "no",
        "--log-driver",
        "none",
        "--init",
        "--label",
        "research.when-to-stop.sandbox=true",
        "--label",
        f"research.when-to-stop.run_id={request.run_id}",
    ]
    for destination, options in tmpfs_mount_options().items():
        arguments.extend(("--tmpfs", f"{destination}:{options}"))
    for key, value in sorted(CONTROLLED_ENVIRONMENT.items()):
        arguments.extend(("--env", f"{key}={value}"))
    arguments.extend((request.image_ref, *request.command))
    return arguments


def tmpfs_mount_options() -> dict[str, str]:
    """The only writable storage made available to a task container."""

    size = str(LIMITS.tmpfs_bytes)
    return {
        "/tmp": f"rw,noexec,nosuid,nodev,size={size},mode=1777",
        "/work": f"rw,noexec,nosuid,nodev,size={size},mode=0700,uid=65532,gid=65532",
    }


def container_name_for(run_id: str) -> str:
    """Use a non-user-chosen deterministic prefix plus random-looking safe ID input."""

    if not IDENTIFIER_RE.fullmatch(run_id):
        raise SandboxPolicyError("cannot construct a container name from an invalid run_id")
    return f"wts-sandbox-{run_id}"


def policy_fingerprint() -> str:
    """Stable identifier recorded with logs and reproducibility evidence."""

    canonical = {
        "controlled_environment": CONTROLLED_ENVIRONMENT,
        "limits": LIMITS.__dict__,
            "protocol": "docker-local-only-v0.3.0",
        "restrictions": {
            "auto_remove": True,
            "cap_drop": "ALL",
            "cgroupns": "private",
            "init": True,
            "ipc": "none",
            "network": "none",
            "pid": "daemon-default-private; host/container PID modes forbidden by inspect",
            "pull": "never",
            "read_only_root": True,
            "restart": "no",
            "tmpfs": tmpfs_mount_options(),
            "user": "65532:65532",
            "userns": "daemon-remap-or-docker-desktop-linuxkit-vm; host override forbidden by inspect",
        },
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def safety_code_fingerprint() -> str:
    """Bind a passing safety receipt to the exact implementation checked."""

    digest = hashlib.sha256()
    for relative in ("policy.py", "runner.py", "safety_checks/checks.py"):
        path = SANDBOX_ROOT / relative
        digest.update(relative.encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def contains_forbidden_environment_name(name: str) -> bool:
    """Identify credential-like names without inspecting any secret value."""

    return bool(FORBIDDEN_ENV_MARKER_RE.search(name))

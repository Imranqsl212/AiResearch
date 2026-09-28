"""A fail-closed Docker runner for one local research episode.

The runner is deliberately narrower than an agent framework: it knows how to create
one constrained container from a reviewed image, verify the Docker daemon's effective
configuration before execution, preserve bounded redacted logs outside the container,
and destroy the container in all terminal paths.  It does not call a model provider,
mount a task, or contact a target.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from sandbox.policy import (
    CONTROLLED_ENVIRONMENT,
    LIMITS,
    LOG_ROOT,
    ApprovedImage,
    SandboxPolicyError,
    SandboxRunRequest,
    contains_forbidden_environment_name,
    container_name_for,
    docker_create_arguments,
    policy_fingerprint,
    require_approved_image,
)


class SafetyViolation(RuntimeError):
    """The sandbox was not demonstrably safe, so execution must not continue."""


@dataclass(frozen=True)
class SandboxRunResult:
    """A non-secret receipt for an attempted local container episode."""

    run_id: str
    task_id: str
    image_ref: str
    image_config_digest: str
    container_name: str
    status: str
    exit_code: int | None
    timed_out: bool
    container_removed: bool
    log_path: str
    receipt_path: str
    log_truncated: bool
    policy_fingerprint: str
    runtime_configuration: Mapping[str, Any] | None
    error: str | None
    started_at: str | None
    finished_at: str

    def as_mapping(self) -> dict[str, Any]:
        return asdict(self)


_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?im)\b(aws_[a-z0-9_]*|azure_[a-z0-9_]*|google_[a-z0-9_]*|gcp_[a-z0-9_]*|"
    r"github_token|openai_api_key|anthropic_api_key|hf_token|huggingface_hub_token|"
    r"ssh_auth_sock|[a-z0-9_]*(?:secret|token|password|private_key|api_key)[a-z0-9_]*)"
    r"\s*=\s*[^\s]+",
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _redact_log_text(text: str) -> str:
    """Retain useful diagnostics without preserving common credential assignments."""

    return _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=<REDACTED>", text)


def _env_pairs(environment: Sequence[str]) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for item in environment:
        key, separator, value = item.partition("=")
        if separator:
            pairs[key] = value
    return pairs


def _is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def validate_runtime_configuration(
    inspect_document: Mapping[str, Any], request: SandboxRunRequest
) -> list[str]:
    """Validate Docker's effective configuration, not just the requested CLI flags."""

    errors: list[str] = []
    config = inspect_document.get("Config")
    host = inspect_document.get("HostConfig")
    network = inspect_document.get("NetworkSettings")
    if not isinstance(config, Mapping) or not isinstance(host, Mapping) or not isinstance(network, Mapping):
        return ["docker inspect response lacks Config, HostConfig, or NetworkSettings"]

    expected_scalar = {
        "NetworkMode": "none",
        "ReadonlyRootfs": True,
        "AutoRemove": True,
        "Privileged": False,
        "PidsLimit": LIMITS.pids_limit,
        "Memory": LIMITS.memory_bytes,
        "MemorySwap": LIMITS.memory_bytes,
        "NanoCpus": LIMITS.nano_cpus,
        "IpcMode": "none",
        "PidMode": "private",
        "CgroupnsMode": "private",
        "UsernsMode": "private",
        "Init": True,
    }
    for field, expected in expected_scalar.items():
        if host.get(field) != expected:
            errors.append(f"HostConfig.{field} expected {expected!r}, got {host.get(field)!r}")

    if config.get("User") != "65532:65532":
        errors.append("Config.User is not the fixed unprivileged numeric identity")
    if config.get("WorkingDir") != "/work":
        errors.append("Config.WorkingDir is not /work")
    if config.get("Tty") is not False:
        errors.append("Config.Tty must be disabled")
    if config.get("Image") != request.image_ref:
        errors.append("Config.Image does not match the approved immutable image reference")

    cap_drop = host.get("CapDrop")
    if not isinstance(cap_drop, list) or "ALL" not in cap_drop:
        errors.append("all Linux capabilities were not dropped")
    security_options = host.get("SecurityOpt") or []
    normalized_security_options = {str(item).replace("=", ":") for item in security_options}
    if "no-new-privileges:true" not in normalized_security_options:
        errors.append("no-new-privileges security option is absent")

    for field in ("Binds", "VolumesFrom", "Links", "Dns", "ExtraHosts", "DeviceRequests", "Devices"):
        if not _is_empty(host.get(field)):
            errors.append(f"HostConfig.{field} must be empty")
    if host.get("PublishAllPorts") is not False or not _is_empty(host.get("PortBindings")):
        errors.append("published ports are not permitted")
    restart = host.get("RestartPolicy")
    if not isinstance(restart, Mapping) or restart.get("Name") not in ("", "no"):
        errors.append("container restart policy is not disabled")
    log_config = host.get("LogConfig")
    if not isinstance(log_config, Mapping) or log_config.get("Type") != "none":
        errors.append("Docker engine logging must be disabled; runner-owned logs are required")

    mounts = inspect_document.get("Mounts")
    if not isinstance(mounts, list):
        errors.append("docker inspect did not return a mount list")
    else:
        destinations = set()
        for mount in mounts:
            if not isinstance(mount, Mapping):
                errors.append("docker inspect returned an invalid mount record")
                continue
            if mount.get("Type") != "tmpfs":
                errors.append(f"non-tmpfs mount is prohibited: {mount.get('Type')!r}")
            destination = mount.get("Destination")
            destinations.add(destination)
            if not _is_empty(mount.get("Source")):
                errors.append(f"tmpfs mount unexpectedly has a source: {destination!r}")
        if destinations != {"/tmp", "/work"}:
            errors.append(f"tmpfs destinations must be /tmp and /work, got {sorted(destinations)!r}")

    environment = config.get("Env")
    if not isinstance(environment, list):
        errors.append("Config.Env is missing")
    else:
        pairs = _env_pairs([str(item) for item in environment])
        for key, value in CONTROLLED_ENVIRONMENT.items():
            if pairs.get(key) != value:
                errors.append(f"controlled environment variable {key} does not have its fixed value")
        for key in pairs:
            if contains_forbidden_environment_name(key):
                errors.append(f"credential-like environment variable {key!r} is present")

    networks = network.get("Networks")
    if not _is_empty(networks):
        errors.append("container is attached to a Docker network")
    return errors


class _BoundedLogCapture:
    """Drain Docker output while bounding the host-side retained log size."""

    def __init__(self, stream: Any, path: Path, maximum_bytes: int) -> None:
        self._stream = stream
        self._path = path
        self._maximum_bytes = maximum_bytes
        self.truncated = False
        self._thread = threading.Thread(target=self._capture, name="sandbox-log-capture", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def join(self) -> None:
        self._thread.join(timeout=10)

    def _capture(self) -> None:
        written = 0
        with self._path.open("a", encoding="utf-8") as handle:
            while True:
                chunk = self._stream.read(8192)
                if not chunk:
                    break
                text = _redact_log_text(chunk.decode("utf-8", errors="replace"))
                encoded = text.encode("utf-8")
                remaining = self._maximum_bytes - written
                if remaining > 0:
                    permitted = encoded[:remaining]
                    handle.write(permitted.decode("utf-8", errors="replace"))
                    written += len(permitted)
                if len(encoded) > remaining:
                    self.truncated = True
            if self.truncated:
                handle.write("\n[runner log truncated at policy limit]\n")


class DockerSandboxRunner:
    """Create, inspect, execute, log, and destroy a single local-only container."""

    def __init__(self, docker_binary: str = "docker", image_lock_path: Path | None = None) -> None:
        self.docker_binary = docker_binary
        self.image_lock_path = image_lock_path

    def preflight(self, image_ref: str) -> ApprovedImage:
        """Require a local daemon and a reviewed, locally cached immutable image."""

        self.assert_local_daemon()
        image = require_approved_image(image_ref, self.image_lock_path) if self.image_lock_path else require_approved_image(image_ref)
        inspect = self._docker_json(("image", "inspect", image.image_ref), timeout_seconds=5)
        if not isinstance(inspect, list) or len(inspect) != 1 or not isinstance(inspect[0], Mapping):
            raise SafetyViolation("Docker image inspect did not produce one image record")
        self._validate_approved_image(inspect[0], image)
        return image

    def assert_local_daemon(self) -> None:
        """Confirm local endpoint and the daemon-level seccomp protection before lookup."""

        self._assert_local_docker_endpoint()
        self._docker(("version", "--format", "{{json .Server}}"), timeout_seconds=5)
        security_options = self._docker_json(("info", "--format", "{{json .SecurityOptions}}"), timeout_seconds=5)
        if not isinstance(security_options, list) or not any("seccomp" in str(option).lower() for option in security_options):
            raise SafetyViolation("Docker daemon does not report its built-in seccomp protection")

    def run(
        self,
        request: SandboxRunRequest,
        on_prestart: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> SandboxRunResult:
        """Execute only after every pre-start gate passes; always attempt cleanup.

        A safety mismatch raises ``SafetyViolation`` after the just-created container is
        force-removed. A normal nonzero command exit is a local task outcome, not a
        safety exception. The function never falls back to a weaker launch policy.
        """

        try:
            image = self.preflight(request.image_ref)
        except (SandboxPolicyError, SafetyViolation) as exc:
            raise SafetyViolation(str(exc)) from exc

        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        container_name = container_name_for(request.run_id)
        log_path = LOG_ROOT / f"{request.run_id}.log"
        receipt_path = LOG_ROOT / f"{request.run_id}.receipt.json"
        if log_path.exists() or receipt_path.exists():
            raise SafetyViolation("run_id already has retained logs; refusing to overwrite evidence")
        with log_path.open("x", encoding="utf-8") as handle:
            handle.write(f"[sandbox run started: {request.run_id}; policy={policy_fingerprint()}]\n")

        started_at: str | None = None
        status = "SAFETY_VIOLATION"
        exit_code: int | None = None
        timed_out = False
        log_truncated = False
        runtime_configuration: Mapping[str, Any] | None = None
        error: str | None = None
        created = False
        capture: _BoundedLogCapture | None = None
        process: subprocess.Popen[bytes] | None = None

        try:
            self._docker(tuple(docker_create_arguments(request)), timeout_seconds=10)
            created = True
            runtime_configuration = self._inspect_container(container_name)
            configuration_errors = validate_runtime_configuration(runtime_configuration, request)
            if configuration_errors:
                raise SafetyViolation("effective Docker configuration rejected: " + "; ".join(configuration_errors))
            if on_prestart is not None:
                on_prestart(runtime_configuration)

            started_at = _utc_now()
            process = subprocess.Popen(
                [self.docker_binary, "start", "--attach", container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if process.stdout is None:
                raise SafetyViolation("could not capture container logs")
            capture = _BoundedLogCapture(process.stdout, log_path, LIMITS.max_log_bytes)
            capture.start()
            try:
                exit_code = process.wait(timeout=request.timeout_seconds)
                status = "COMPLETED" if exit_code == 0 else "COMPLETED_NONZERO"
            except subprocess.TimeoutExpired:
                timed_out = True
                status = "TIMED_OUT"
                self._force_remove(container_name)
                try:
                    exit_code = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    exit_code = process.wait(timeout=5)
            if capture is not None:
                capture.join()
                log_truncated = capture.truncated
        except (OSError, subprocess.SubprocessError, SafetyViolation) as exc:
            error = str(exc)
            status = "SAFETY_VIOLATION"
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        finally:
            if capture is not None:
                capture.join()
                log_truncated = capture.truncated
            cleanup_error: str | None = None
            if created:
                try:
                    self._force_remove(container_name)
                except SafetyViolation as exc:
                    cleanup_error = str(exc)
            container_removed = self._container_is_absent(container_name)
            if cleanup_error is not None:
                error = cleanup_error if error is None else f"{error}; {cleanup_error}"
                status = "SAFETY_VIOLATION"
            finished_at = _utc_now()
            result = SandboxRunResult(
                run_id=request.run_id,
                task_id=request.task_id,
                image_ref=request.image_ref,
                image_config_digest=image.config_digest,
                container_name=container_name,
                status=status,
                exit_code=exit_code,
                timed_out=timed_out,
                container_removed=container_removed,
                log_path=str(log_path),
                receipt_path=str(receipt_path),
                log_truncated=log_truncated,
                policy_fingerprint=policy_fingerprint(),
                runtime_configuration=runtime_configuration,
                error=error,
                started_at=started_at,
                finished_at=finished_at,
            )
            self._write_receipt(receipt_path, result)

        if not result.container_removed:
            raise SafetyViolation("container cleanup could not be verified; experiment must remain blocked")
        if result.status == "SAFETY_VIOLATION":
            raise SafetyViolation(result.error or "sandbox execution failed closed")
        return result

    def _assert_local_docker_endpoint(self) -> None:
        declared = os.environ.get("DOCKER_HOST")
        if declared and not declared.startswith("unix://"):
            raise SafetyViolation("remote Docker endpoints are prohibited")
        context = self._docker(("context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"), timeout_seconds=5)
        try:
            endpoint = json.loads(context.stdout.strip())
        except json.JSONDecodeError as exc:
            raise SafetyViolation("could not determine Docker context endpoint") from exc
        if not isinstance(endpoint, str) or not endpoint.startswith("unix://"):
            raise SafetyViolation("Docker context is not a local Unix-socket endpoint")

    def _validate_approved_image(self, document: Mapping[str, Any], image: ApprovedImage) -> None:
        if document.get("Id") != image.config_digest:
            raise SafetyViolation("local image config digest differs from the approved image lock")
        config = document.get("Config")
        if not isinstance(config, Mapping):
            raise SafetyViolation("approved image inspection lacks Config")
        if not _is_empty(config.get("Entrypoint")):
            raise SafetyViolation("approved image must not define an entrypoint outside the runner policy")
        if not _is_empty(config.get("Volumes")):
            raise SafetyViolation("approved image must not declare persistent volumes")
        environment = config.get("Env") or []
        if not isinstance(environment, list):
            raise SafetyViolation("approved image environment is not inspectable")
        for name in _env_pairs([str(item) for item in environment]):
            if contains_forbidden_environment_name(name):
                raise SafetyViolation("approved image contains a credential-like environment variable")

    def _inspect_container(self, container_name: str) -> Mapping[str, Any]:
        document = self._docker_json(("container", "inspect", container_name), timeout_seconds=5)
        if not isinstance(document, list) or len(document) != 1 or not isinstance(document[0], Mapping):
            raise SafetyViolation("Docker container inspect did not produce one container record")
        return document[0]

    def _docker_json(self, arguments: Sequence[str], timeout_seconds: int) -> Any:
        result = self._docker(arguments, timeout_seconds=timeout_seconds)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SafetyViolation(f"Docker did not return valid JSON for {' '.join(arguments[:2])}") from exc

    def _docker(self, arguments: Sequence[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                [self.docker_binary, *arguments],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise SafetyViolation("Docker CLI is not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise SafetyViolation(f"Docker command timed out: {' '.join(arguments[:2])}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise SafetyViolation(f"Docker command failed ({' '.join(arguments[:2])}): {detail}")
        return result

    def _force_remove(self, container_name: str) -> None:
        try:
            result = subprocess.run(
                [self.docker_binary, "container", "rm", "--force", container_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise SafetyViolation("cannot force-remove sandbox container") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().lower()
            if "no such container" not in detail and "no such object" not in detail:
                raise SafetyViolation(f"sandbox container cleanup failed: {detail}")

    def _container_is_absent(self, container_name: str) -> bool:
        try:
            result = subprocess.run(
                [self.docker_binary, "container", "inspect", container_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        if result.returncode == 0:
            return False
        detail = (result.stderr or result.stdout).strip().lower()
        return "no such container" in detail or "no such object" in detail

    @staticmethod
    def _write_receipt(path: Path, result: SandboxRunResult) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            json.dump(result.as_mapping(), handle, indent=2, sort_keys=True)
            handle.write("\n")

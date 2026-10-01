"""A fail-closed Docker runner for one local research episode.

The runner is deliberately narrower than an agent framework: it knows how to create
one constrained container from a reviewed image, verify the Docker daemon's effective
configuration before execution, preserve bounded redacted logs outside the container,
and destroy the container in all terminal paths.  It does not call a model provider,
mount a task, or contact a target.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import stat
import subprocess
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from sandbox.policy import (
    APPROVED_IMAGES_PATH,
    CONTROLLED_ENVIRONMENT,
    ISOLATION_MODE_DOCKER_DESKTOP_VM,
    ISOLATION_MODE_USERNS_REMAP,
    LIMITS,
    LOG_ROOT,
    SANDBOX_ROOT,
    ApprovedImage,
    SandboxPolicyError,
    SandboxRunRequest,
    contains_forbidden_environment_name,
    container_name_for,
    docker_create_arguments,
    policy_fingerprint,
    require_approved_image,
    safety_code_fingerprint,
    tmpfs_mount_options,
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


def _receipt_runtime_summary(document: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    """Keep enough isolation evidence without persisting raw environment values."""

    if document is None:
        return None
    config = document.get("Config") or {}
    host = document.get("HostConfig") or {}
    mounts = document.get("Mounts") or []
    return {
        "image": config.get("Image"),
        "user": config.get("User"),
        "network_mode": host.get("NetworkMode"),
        "pid_mode": host.get("PidMode"),
        "userns_mode": host.get("UsernsMode"),
        "cgroupns_mode": host.get("CgroupnsMode"),
        "read_only_root": host.get("ReadonlyRootfs"),
        "memory_bytes": host.get("Memory"),
        "nano_cpus": host.get("NanoCpus"),
        "pids_limit": host.get("PidsLimit"),
        "mount_destinations": [mount.get("Destination") for mount in mounts if isinstance(mount, Mapping)],
        "environment_names": sorted(_env_pairs(config.get("Env") or [])),
    }


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
        "CgroupnsMode": "private",
        "Init": True,
    }
    for field, expected in expected_scalar.items():
        if host.get(field) != expected:
            errors.append(f"HostConfig.{field} expected {expected!r}, got {host.get(field)!r}")
    if host.get("PidMode") not in ("", "private"):
        errors.append("HostConfig.PidMode must use Docker's private PID default")
    if host.get("UsernsMode") not in ("",):
        errors.append("HostConfig.UsernsMode must use the daemon/Desktop private default; host override is forbidden")

    if config.get("User") != "65532:65532":
        errors.append("Config.User is not the fixed unprivileged numeric identity")
    if config.get("WorkingDir") != "/work":
        errors.append("Config.WorkingDir is not /work")
    if config.get("Tty") is not False:
        errors.append("Config.Tty must be disabled")
    if config.get("OpenStdin") is not True:
        errors.append("Config.OpenStdin must be enabled only for bounded runner-provided input")
    if config.get("Image") != request.image_ref:
        errors.append("Config.Image does not match the approved immutable image reference")

    cap_drop = host.get("CapDrop")
    if not isinstance(cap_drop, list) or "ALL" not in cap_drop:
        errors.append("all Linux capabilities were not dropped")
    if not _is_empty(host.get("CapAdd")):
        errors.append("additional Linux capabilities are prohibited")
    security_options = host.get("SecurityOpt") or []
    normalized_security_options = {str(item).replace("=", ":") for item in security_options}
    if normalized_security_options != {"no-new-privileges:true"}:
        errors.append("security options must contain only no-new-privileges")

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
    if host.get("Tmpfs") != tmpfs_mount_options():
        errors.append("HostConfig.Tmpfs differs from the bounded noexec/nosuid/nodev policy")

    mounts = inspect_document.get("Mounts")
    if not isinstance(mounts, list):
        errors.append("docker inspect did not return a mount list")
    else:
        # Docker Engine normally exposes tmpfs mounts in Mounts. Docker Desktop
        # exposes the same effective mounts only in HostConfig.Tmpfs and returns
        # Mounts=[]; the exact HostConfig.Tmpfs equality check above remains the
        # authoritative check in that representation.
        if mounts:
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
        if pairs != CONTROLLED_ENVIRONMENT or len(environment) != len(CONTROLLED_ENVIRONMENT):
            errors.append("container environment differs from the exact controlled allow-list")
        for key in pairs:
            if contains_forbidden_environment_name(key):
                errors.append(f"credential-like environment variable {key!r} is present")

    networks = network.get("Networks")
    if networks:
        if not isinstance(networks, Mapping) or set(networks) != {"none"}:
            errors.append("container is attached to a Docker network")
        else:
            none_network = networks.get("none")
            if not isinstance(none_network, Mapping):
                errors.append("Docker's none network inspection record is invalid")
            else:
                nonempty_fields = {
                    key: value
                    for key, value in none_network.items()
                    if key not in {"Aliases", "DNSNames", "DriverOpts", "IPAMConfig", "Links"}
                    and not _is_empty(value)
                    and value not in (0, False)
                }
                if nonempty_fields:
                    errors.append("Docker none network has an unexpected endpoint or address")
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
        # Drain continuously, but redact only after assembling the bounded
        # stream. Chunk-local regexes can leak an assignment split at 8 KiB.
        retained = bytearray()
        with self._path.open("a", encoding="utf-8") as handle:
            while True:
                chunk = self._stream.read(8192)
                if not chunk:
                    break
                remaining = self._maximum_bytes - len(retained)
                if remaining > 0:
                    retained.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    self.truncated = True
            handle.write(_redact_log_text(retained.decode("utf-8", errors="replace")))
            if self.truncated:
                handle.write("\n[runner log truncated at policy limit]\n")


class DockerSandboxRunner:
    """Create, inspect, execute, log, and destroy a single local-only container."""

    def __init__(self, docker_binary: str = "docker", image_lock_path: Path | None = None) -> None:
        self.docker_binary = docker_binary
        self.image_lock_path = image_lock_path

    def _require_official_gate(self, request: SandboxRunRequest) -> None:
        """A normal episode is impossible through the candidate/preapproval lock."""

        lock_path = self.image_lock_path or APPROVED_IMAGES_PATH
        if lock_path.resolve() != APPROVED_IMAGES_PATH.resolve():
            raise SafetyViolation("ordinary sandbox runs require the official approved image lock")
        report_path = SANDBOX_ROOT / "safety_checks" / "latest_result.json"
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            lock_hash = hashlib.sha256(APPROVED_IMAGES_PATH.read_bytes()).hexdigest()
        except (OSError, json.JSONDecodeError) as exc:
            raise SafetyViolation("a valid official safety receipt is required before any run") from exc
        if not isinstance(report, Mapping) or not all((
            report.get("overall_passed") is True,
            report.get("experiment_permitted") is True,
            report.get("approval_scope") == "OFFICIAL",
            report.get("image_ref") == request.image_ref,
            report.get("policy_fingerprint") == policy_fingerprint(),
            report.get("safety_code_fingerprint") == safety_code_fingerprint(),
            report.get("image_lock_sha256") == lock_hash,
        )):
            raise SafetyViolation("official safety receipt is absent, failed, stale, or for another image")
        if report.get("daemon_fingerprint") != self.daemon_fingerprint():
            raise SafetyViolation("Docker daemon identity/configuration changed since the official safety suite")

    def run(
        self,
        request: SandboxRunRequest,
        on_prestart: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> SandboxRunResult:
        """Execute a scored episode only after an exact passing official safety gate."""

        return self._run(request, on_prestart=on_prestart)

    def run_safety_probe(
        self,
        request: SandboxRunRequest,
        on_prestart: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> SandboxRunResult:
        """Run only a fixed harmless containment probe; never an agent command."""

        return self._run(request, on_prestart=on_prestart, safety_probe=True)

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
        """Require a local daemon and a reviewed isolation boundary.

        Linux Engine requires daemon-level userns remapping.  Docker Desktop is
        accepted as a separate, explicitly named mode because its Linux engine
        is hosted in the local LinuxKit VM; the VM boundary is recorded as a
        residual assumption and never silently treated as userns remapping.
        """

        self.daemon_isolation_mode()

    def daemon_isolation_mode(self) -> str:
        """Return the verified isolation mode or fail closed."""

        self._assert_local_docker_endpoint()
        self._docker(("version", "--format", "{{json .Server}}"), timeout_seconds=5)
        security_options = self._docker_json(("info", "--format", "{{json .SecurityOptions}}"), timeout_seconds=5)
        if not isinstance(security_options, list) or not any("seccomp" in str(option).lower() for option in security_options):
            raise SafetyViolation("Docker daemon does not report its built-in seccomp protection")
        if any("userns" in str(option).lower() for option in security_options):
            return ISOLATION_MODE_USERNS_REMAP

        info = self._docker_json(("info", "--format", "{{json .}}"), timeout_seconds=5)
        context = self._docker(("context", "show"), timeout_seconds=5).stdout.strip()
        operating_system = str(info.get("OperatingSystem", "")) if isinstance(info, Mapping) else ""
        kernel = str(info.get("KernelVersion", "")) if isinstance(info, Mapping) else ""
        os_type = str(info.get("OSType", "")) if isinstance(info, Mapping) else ""
        desktop_identity = (
            context == "desktop-linux"
            and os_type.lower() == "linux"
            and ("docker desktop" in operating_system.lower() or "linuxkit" in kernel.lower())
        )
        if desktop_identity:
            return ISOLATION_MODE_DOCKER_DESKTOP_VM
        raise SafetyViolation(
            "Docker daemon does not report user-namespace remapping and is not a verified Docker Desktop LinuxKit VM"
        )

    def daemon_fingerprint(self) -> str:
        """Bind a passing suite to stable, safety-relevant daemon properties."""

        self._assert_local_docker_endpoint()
        server = self._docker_json(("version", "--format", "{{json .Server}}"), timeout_seconds=5)
        info = self._docker_json(("info", "--format", "{{json .}}"), timeout_seconds=5)
        if not isinstance(server, Mapping) or not isinstance(info, Mapping):
            raise SafetyViolation("Docker daemon fingerprint fields are unavailable")
        fields = ("ID", "ServerVersion", "KernelVersion", "SecurityOptions", "CgroupDriver",
                  "Driver", "Architecture", "OperatingSystem")
        isolation_mode = self.daemon_isolation_mode()
        canonical = {
            "server": {key: server.get(key) for key in ("Version", "ApiVersion", "GitCommit")},
            "info": {key: info.get(key) for key in fields},
            "isolation_mode": isolation_mode,
        }
        if not isinstance(canonical["info"]["SecurityOptions"], list) or not canonical["info"]["ID"]:
            raise SafetyViolation("Docker daemon lacks fingerprintable security options or identity")
        return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _run(
        self,
        request: SandboxRunRequest,
        on_prestart: Callable[[Mapping[str, Any]], None] | None = None,
        *,
        safety_probe: bool = False,
    ) -> SandboxRunResult:
        """Execute only after every pre-start gate passes; always attempt cleanup.

        A safety mismatch raises ``SafetyViolation`` after the just-created container is
        force-removed. A normal nonzero command exit is a local task outcome, not a
        safety exception. The function never falls back to a weaker launch policy.
        """

        # Authorization sits at the last launch point. An internal caller may
        # not bypass the official receipt merely by invoking _run directly.
        if safety_probe:
            from sandbox.safety_checks.checks import CANDIDATE_LOCK_PATH

            lock_path = self.image_lock_path or APPROVED_IMAGES_PATH
            if lock_path.resolve() not in {APPROVED_IMAGES_PATH.resolve(), CANDIDATE_LOCK_PATH.resolve()}:
                raise SafetyViolation("safety probes require the fixed official or candidate lock")
            if request.task_id != "safety-fixture" or request.command not in {
                ("/wts-local", "probe", name)
                for name in ("network", "host-files", "credentials", "marker", "resources", "sleep", "runaway", "reproducible")
            } and request.command not in {
                ("/usr/local/bin/python3", "-I", "/opt/candidate_runtime.py"),
                ("/usr/bin/python3", "-I", "/opt/candidate_runtime.py"),
            }:
                raise SafetyViolation("candidate image may execute only fixed local safety probes")
        else:
            self._require_official_gate(request)

        try:
            image = self.preflight(request.image_ref)
        except (SandboxPolicyError, SafetyViolation) as exc:
            raise SafetyViolation(str(exc)) from exc

        LOG_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
        if LOG_ROOT.is_symlink() or stat.S_IMODE(LOG_ROOT.stat().st_mode) != 0o700:
            raise SafetyViolation("sandbox log directory must be owner-only and not a symlink")
        container_name = container_name_for(request.run_id)
        log_path = LOG_ROOT / f"{request.run_id}.log"
        receipt_path = LOG_ROOT / f"{request.run_id}.receipt.json"
        if log_path.exists() or receipt_path.exists():
            raise SafetyViolation("run_id already has retained logs; refusing to overwrite evidence")
        descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"[sandbox run started: {request.run_id}; policy={policy_fingerprint()}]\n")

        started_at: str | None = None
        status = "SAFETY_VIOLATION"
        exit_code: int | None = None
        timed_out = False
        log_truncated = False
        runtime_configuration: Mapping[str, Any] | None = None
        error: str | None = None
        attempted_create = False
        capture: _BoundedLogCapture | None = None
        process: subprocess.Popen[bytes] | None = None

        try:
            attempted_create = True
            self._docker(tuple(docker_create_arguments(request)), timeout_seconds=10)
            runtime_configuration = self._inspect_container(container_name)
            configuration_errors = validate_runtime_configuration(runtime_configuration, request)
            if configuration_errors:
                raise SafetyViolation("effective Docker configuration rejected: " + "; ".join(configuration_errors))
            if on_prestart is not None:
                on_prestart(runtime_configuration)

            started_at = _utc_now()
            process = subprocess.Popen(
                [self.docker_binary, "start", "--attach", "--interactive", container_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if process.stdout is None or process.stdin is None:
                raise SafetyViolation("could not capture container logs")
            capture = _BoundedLogCapture(process.stdout, log_path, LIMITS.max_log_bytes)
            capture.start()
            try:
                if request.stdin_payload:
                    process.stdin.write(request.stdin_payload)
                    process.stdin.flush()
            except BrokenPipeError:
                # A process that exits before reading input is an ordinary
                # candidate failure; its bounded output is still captured.
                pass
            finally:
                process.stdin.close()
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
            if process.stdout is not None:
                process.stdout.close()
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
            if process is not None and process.stdout is not None:
                process.stdout.close()
            cleanup_error: str | None = None
            if attempted_create:
                try:
                    self._force_remove_if_owned(container_name, request.run_id)
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
                runtime_configuration=_receipt_runtime_summary(runtime_configuration),
                error=_redact_log_text(error) if error is not None else None,
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
            if "permission denied while trying to connect to the docker daemon socket" in detail.lower():
                raise SafetyViolation("Docker daemon socket inaccessible under the current permission profile")
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

    def _force_remove_if_owned(self, container_name: str, run_id: str) -> None:
        """Recover an orphaned create without deleting another caller's container."""

        try:
            document = self._docker_json(("container", "inspect", container_name), timeout_seconds=5)
        except SafetyViolation as exc:
            if "no such container" in str(exc).lower() or "no such object" in str(exc).lower():
                return
            raise
        if not isinstance(document, list) or len(document) != 1 or not isinstance(document[0], Mapping):
            raise SafetyViolation("cannot establish ownership of sandbox container before cleanup")
        config = document[0].get("Config")
        labels = config.get("Labels") if isinstance(config, Mapping) else None
        if not isinstance(labels, Mapping) or labels.get("research.when-to-stop.sandbox") != "true" \
                or labels.get("research.when-to-stop.run_id") != run_id:
            raise SafetyViolation("container name is occupied by an unowned container; cleanup refused")
        self._force_remove(container_name)

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
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.parent.is_symlink() or stat.S_IMODE(path.parent.stat().st_mode) != 0o700:
            raise SafetyViolation("sandbox receipt directory must be owner-only and not a symlink")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(result.as_mapping(), handle, indent=2, sort_keys=True)
            handle.write("\n")

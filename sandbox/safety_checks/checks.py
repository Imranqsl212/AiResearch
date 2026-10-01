"""Harmless, local-only integration checks for the Docker containment boundary."""

from __future__ import annotations

import json
import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from sandbox.policy import (
    APPROVED_IMAGES_PATH,
    CONTROLLED_ENVIRONMENT,
    LIMITS,
    SandboxPolicyError,
    SandboxRunRequest,
    approved_images,
    docker_create_arguments,
    policy_fingerprint,
    safety_code_fingerprint,
    tmpfs_mount_options,
)
from sandbox.runner import DockerSandboxRunner, SafetyViolation, SandboxRunResult


SAFETY_CHECK_ROOT = Path(__file__).resolve().parent
LATEST_REPORT_PATH = SAFETY_CHECK_ROOT / "latest_result.json"
CANDIDATE_LOCK_PATH = SAFETY_CHECK_ROOT.parent / "images" / "candidate_images.json"
RUNTIME_CHECK_IDS = (
    "external_network_blocked",
    "host_files_unmounted",
    "credentials_absent",
    "container_destroyed",
    "resource_limits_enforced",
    "timeout_enforced",
    "runaway_process_terminated",
    "logs_retained",
    "reproducible_state",
    "candidate_runtime_isolated",
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _result(check_id: str, passed: bool, status: str, detail: str, **evidence: Any) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": passed,
        "status": status,
        "detail": detail,
        "evidence": evidence,
    }


def _argument_value(arguments: list[str], flag: str) -> list[str]:
    values: list[str] = []
    for index, item in enumerate(arguments[:-1]):
        if item == flag:
            values.append(arguments[index + 1])
    return values


def static_policy_check() -> dict[str, Any]:
    """Prove that policy construction offers no caller-controlled weakening path."""

    request = SandboxRunRequest(
        run_id="static-policy-fixture",
        task_id="safety-fixture",
        image_ref="local.test/when-to-stop/safety@sha256:" + "a" * 64,
        command=("/bin/true",),
        timeout_seconds=1,
    )
    arguments = docker_create_arguments(request)
    errors: list[str] = []
    expected_pairs = {
        "--network": "none",
        "--user": "65532:65532",
        "--workdir": "/work",
        "--cap-drop": "ALL",
        "--security-opt": "no-new-privileges=true",
        "--pids-limit": str(LIMITS.pids_limit),
        "--memory": str(LIMITS.memory_bytes),
        "--memory-swap": str(LIMITS.memory_bytes),
        "--cpus": f"{LIMITS.cpu_cores:.2f}",
        "--ipc": "none",
        "--cgroupns": "private",
        "--restart": "no",
        "--log-driver": "none",
    }
    for flag, expected in expected_pairs.items():
        if _argument_value(arguments, flag) != [expected]:
            errors.append(f"{flag} is not fixed to {expected!r}")
    if "--pid" in arguments or "--userns" in arguments:
        errors.append("Docker PID/user namespaces must inherit reviewed private daemon defaults")
    if "--read-only" not in arguments or "--pull=never" not in arguments or "--rm" not in arguments or "--init" not in arguments:
        errors.append("read-only root filesystem, no-pull policy, auto-removal, or init process is absent")
    if any(flag in arguments for flag in ("--privileged", "--mount", "--volume", "-v", "--device", "--add-host")):
        errors.append("a forbidden Docker privilege, mount, device, or host override is exposed")
    tmpfs_values = _argument_value(arguments, "--tmpfs")
    if len(tmpfs_values) != 2 or not all("noexec" in value and "nosuid" in value for value in tmpfs_values):
        errors.append("both bounded noexec tmpfs locations are required")
    supplied_environment = _argument_value(arguments, "--env")
    expected_environment = [f"{key}={value}" for key, value in sorted(CONTROLLED_ENVIRONMENT.items())]
    if supplied_environment != expected_environment:
        errors.append("container environment differs from the controlled allow-list")
    if not policy_fingerprint():
        errors.append("policy fingerprint is absent")
    return _result(
        "static_policy_locked",
        not errors,
        "PASS" if not errors else "FAIL",
        "Fixed Docker arguments were checked without launching a container." if not errors else "; ".join(errors),
        policy_fingerprint=policy_fingerprint(),
    )


def _eligible_test_image(image_lock_path: Path) -> Any:
    images = approved_images(image_lock_path)
    eligible = [image for image in images if image.safety_test_eligible]
    if len(eligible) != 1:
        raise SandboxPolicyError(
            "exactly one reviewed safety_test_eligible immutable image is required; none is currently available"
        )
    return eligible[0]


def _request(image_ref: str, check_id: str, command: tuple[str, ...], timeout_seconds: int = 10, stdin_payload: bytes = b"") -> SandboxRunRequest:
    return SandboxRunRequest(
        run_id=f"safety-{check_id[:24]}-{uuid.uuid4().hex[:12]}",
        task_id="safety-fixture",
        image_ref=image_ref,
        command=command,
        timeout_seconds=timeout_seconds,
        stdin_payload=stdin_payload,
    )


def _run_with_snapshot(
    runner: DockerSandboxRunner, request: SandboxRunRequest
) -> tuple[SandboxRunResult, Mapping[str, Any]]:
    snapshots: list[Mapping[str, Any]] = []
    result = runner.run_safety_probe(request, on_prestart=snapshots.append)
    if len(snapshots) != 1:
        raise SafetyViolation("container did not produce exactly one pre-start inspected configuration")
    return result, snapshots[0]


def _runtime_fingerprint(snapshot: Mapping[str, Any]) -> str:
    config = snapshot.get("Config", {})
    host = snapshot.get("HostConfig", {})
    mounts = snapshot.get("Mounts", [])
    canonical = {
        "config": {
            # Docker Desktop may return the exact allow-list in a different
            # order on otherwise identical creates; order is not a security
            # property and must not fail reproducibility.
            "Env": sorted(config.get("Env") or []),
            "Image": config.get("Image"),
            "User": config.get("User"),
            "WorkingDir": config.get("WorkingDir"),
        },
        "host": {
            key: host.get(key)
            for key in (
                "AutoRemove",
                "CapDrop",
                "CgroupnsMode",
                "Init",
                "IpcMode",
                "LogConfig",
                "Memory",
                "MemorySwap",
                "NanoCpus",
                "NetworkMode",
                "PidsLimit",
                "PidMode",
                "ReadonlyRootfs",
                "SecurityOpt",
                "UsernsMode",
            )
        },
        "mounts": [
            {"Destination": mount.get("Destination"), "Mode": mount.get("Mode"), "Type": mount.get("Type")}
            for mount in mounts
            if isinstance(mount, Mapping)
        ],
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"))


def _assert_completed(result: SandboxRunResult) -> None:
    if result.status != "COMPLETED" or result.exit_code != 0:
        raise SafetyViolation(f"safety probe did not exit cleanly: {result.status}, {result.exit_code}")
    if not result.container_removed:
        raise SafetyViolation("runner did not prove container removal")


def _log_payload(path: Path) -> str:
    """Ignore the per-run runner header when comparing deterministic probe output."""

    text = path.read_text(encoding="utf-8")
    return text.partition("\n")[2]


def _network_check(runner: DockerSandboxRunner, image_ref: str) -> dict[str, Any]:
    result, snapshot = _run_with_snapshot(
        runner,
        _request(
            image_ref,
            "external-network",
            ("/wts-local", "probe", "network"),
        ),
    )
    _assert_completed(result)
    networks = snapshot.get("NetworkSettings", {}).get("Networks")
    if networks:
        if not isinstance(networks, Mapping) or set(networks) != {"none"}:
            raise SafetyViolation("Docker reports a network attachment")
        none_network = networks.get("none")
        if not isinstance(none_network, Mapping):
            raise SafetyViolation("Docker none network record is invalid")
        nonempty = {
            key: value
            for key, value in none_network.items()
            if key not in {"Aliases", "DNSNames", "DriverOpts", "IPAMConfig", "Links"}
            and value not in (None, "", [], {}, 0, False)
        }
        if nonempty:
            raise SafetyViolation("Docker none network has an endpoint or address")
    if "loopback-only" not in Path(result.log_path).read_text(encoding="utf-8"):
        raise SafetyViolation("in-container network probe did not confirm loopback-only interfaces")
    return _result(
        "external_network_blocked",
        True,
        "PASS",
        "The container had network mode none, no active non-loopback interface, and no route. No public address was contacted.",
        container_removed=result.container_removed,
    )


def _host_files_check(runner: DockerSandboxRunner, image_ref: str) -> dict[str, Any]:
    result, snapshot = _run_with_snapshot(
        runner,
        _request(
            image_ref,
            "host-files",
            ("/wts-local", "probe", "host-files"),
        ),
    )
    _assert_completed(result)
    mounts = snapshot.get("Mounts", [])
    if mounts:
        if any(not isinstance(mount, Mapping) or mount.get("Type") != "tmpfs" for mount in mounts):
            raise SafetyViolation("a non-tmpfs mount was present")
    else:
        host_config = snapshot.get("HostConfig", {})
        if not isinstance(host_config, Mapping) or host_config.get("Tmpfs") != tmpfs_mount_options():
            raise SafetyViolation("Docker did not expose the exact bounded tmpfs policy")
    if "no-host-mount-read-only" not in Path(result.log_path).read_text(encoding="utf-8"):
        raise SafetyViolation("in-container filesystem probe did not confirm a read-only root")
    return _result(
        "host_files_unmounted",
        True,
        "PASS",
        "Docker inspect found only the exact bounded /tmp and /work tmpfs policy; the read-only root probe could not write a host-like path.",
        mounts=[mount.get("Destination") for mount in mounts if isinstance(mount, Mapping)] or sorted(tmpfs_mount_options()),
    )


def _credentials_check(runner: DockerSandboxRunner, image_ref: str) -> dict[str, Any]:
    result, _ = _run_with_snapshot(
        runner,
        _request(
            image_ref,
            "credentials",
            ("/wts-local", "probe", "credentials"),
        ),
    )
    _assert_completed(result)
    log_text = Path(result.log_path).read_text(encoding="utf-8")
    environment_names = [line.strip() for line in log_text.splitlines()[1:] if line.strip()]
    if not set(CONTROLLED_ENVIRONMENT).issubset(environment_names):
        raise SafetyViolation("in-container credential probe did not report all controlled environment names")
    leaked = [name for name in environment_names if any(marker in name.upper() for marker in ("TOKEN", "SECRET", "KEY", "AWS", "AZURE", "GOOGLE", "SSH"))]
    if leaked:
        raise SafetyViolation(f"credential-like environment variables were observable: {leaked}")
    return _result(
        "credentials_absent",
        True,
        "PASS",
        "Standard SSH and secret paths were absent and the observed controlled environment contained no credential-like names.",
        log_path=result.log_path,
    )


def _cleanup_check(runner: DockerSandboxRunner, image_ref: str) -> dict[str, Any]:
    result, _ = _run_with_snapshot(runner, _request(image_ref, "cleanup", ("/wts-local", "probe", "marker")))
    _assert_completed(result)
    return _result(
        "container_destroyed",
        result.container_removed,
        "PASS" if result.container_removed else "FAIL",
        "The runner force-removed the named disposable container and verified its absence.",
        container_name=result.container_name,
    )


def _resource_check(runner: DockerSandboxRunner, image_ref: str) -> dict[str, Any]:
    result, snapshot = _run_with_snapshot(
        runner,
        _request(image_ref, "resources", ("/wts-local", "probe", "resources")),
    )
    _assert_completed(result)
    observed = Path(result.log_path).read_text(encoding="utf-8").splitlines()
    measurements = {
        line.partition("=")[0]: line.partition("=")[2]
        for line in observed
        if "=" in line
    }
    try:
        observed_nofile = int(measurements["nofile"])
        observed_pids = int(measurements["pids"])
        observed_memory = int(measurements["memory"])
        quota, period = (int(value) for value in measurements["cpu"].split())
    except ValueError as exc:
        raise SafetyViolation("could not parse cgroup resource limits inside the container") from exc
    except KeyError as exc:
        raise SafetyViolation("container does not expose all required cgroup resource limits") from exc
    if observed_nofile > LIMITS.nofile_limit:
        raise SafetyViolation("in-container nofile limit exceeds policy")
    if observed_pids != LIMITS.pids_limit:
        raise SafetyViolation("in-container cgroup PID limit differs from policy")
    if observed_memory != LIMITS.memory_bytes:
        raise SafetyViolation("in-container cgroup memory limit differs from policy")
    if quota * 1_000_000_000 // period != LIMITS.nano_cpus:
        raise SafetyViolation("in-container cgroup CPU quota differs from policy")
    host = snapshot.get("HostConfig", {})
    if host.get("Memory") != LIMITS.memory_bytes or host.get("NanoCpus") != LIMITS.nano_cpus:
        raise SafetyViolation("Docker inspect resource controls differ from policy")
    return _result(
        "resource_limits_enforced",
        True,
        "PASS",
        "Docker inspect and in-container cgroup/ulimit probes matched the fixed CPU, memory, PID, and file-descriptor policy.",
        observed_nofile=observed_nofile,
        observed_pids=observed_pids,
        observed_memory=observed_memory,
        observed_cpu=f"{quota} {period}",
    )


def _timeout_check(runner: DockerSandboxRunner, image_ref: str) -> dict[str, Any]:
    result, _ = _run_with_snapshot(runner, _request(image_ref, "timeout", ("/wts-local", "probe", "sleep"), timeout_seconds=1))
    if not result.timed_out or result.status != "TIMED_OUT" or not result.container_removed:
        raise SafetyViolation("wall-clock timeout did not terminate and remove the container")
    return _result(
        "timeout_enforced",
        True,
        "PASS",
        "A harmless sleeping process exceeded one second, then the runner force-removed its container.",
        exit_code=result.exit_code,
    )


def _runaway_check(runner: DockerSandboxRunner, image_ref: str) -> dict[str, Any]:
    result, _ = _run_with_snapshot(
        runner,
        _request(image_ref, "runaway", ("/wts-local", "probe", "runaway"), timeout_seconds=1),
    )
    if not result.timed_out or result.status != "TIMED_OUT" or not result.container_removed:
        raise SafetyViolation("runaway child process was not terminated with its container")
    return _result(
        "runaway_process_terminated",
        True,
        "PASS",
        "A background sleeper was placed in a timed-out container; container removal terminated the process namespace.",
        exit_code=result.exit_code,
    )


def _logs_check(runner: DockerSandboxRunner, image_ref: str) -> dict[str, Any]:
    marker = "safety-log-marker"
    result, _ = _run_with_snapshot(runner, _request(image_ref, "logs", ("/wts-local", "probe", "marker")))
    _assert_completed(result)
    log_path = Path(result.log_path)
    if not log_path.is_file() or marker not in log_path.read_text(encoding="utf-8"):
        raise SafetyViolation("runner-owned log was not retained after container cleanup")
    return _result(
        "logs_retained",
        True,
        "PASS",
        "The bounded, runner-owned log remained available after the container was removed.",
        log_path=str(log_path),
    )


def _reproducibility_check(runner: DockerSandboxRunner, image_ref: str) -> dict[str, Any]:
    command = ("/wts-local", "probe", "reproducible")
    first, first_snapshot = _run_with_snapshot(runner, _request(image_ref, "repro-one", command))
    second, second_snapshot = _run_with_snapshot(runner, _request(image_ref, "repro-two", command))
    _assert_completed(first)
    _assert_completed(second)
    if first.image_config_digest != second.image_config_digest:
        raise SafetyViolation("same approved image reference resolved to different configuration digests")
    if first.policy_fingerprint != second.policy_fingerprint:
        raise SafetyViolation("same policy generated different fingerprints")
    if _runtime_fingerprint(first_snapshot) != _runtime_fingerprint(second_snapshot):
        raise SafetyViolation("effective runtime configuration changed between identical probes")
    first_log = _log_payload(Path(first.log_path))
    second_log = _log_payload(Path(second.log_path))
    if first_log != second_log:
        raise SafetyViolation("identical harmless probes produced different retained output")
    return _result(
        "reproducible_state",
        True,
        "PASS",
        "Two identical local probes used the same image digest, policy fingerprint, effective configuration, and output.",
        image_config_digest=first.image_config_digest,
        policy_fingerprint=first.policy_fingerprint,
    )


def _candidate_runtime_check(runner: DockerSandboxRunner, image_ref: str) -> dict[str, Any]:
    """Exercise the exact stdin/runtime path used for model-submitted source."""

    result, snapshot = _run_with_snapshot(
        runner,
        _request(
            image_ref,
            "candidate-runtime",
            ("/usr/bin/python3", "-I", "/opt/candidate_runtime.py"),
            stdin_payload=b'{"kind":"runtime_probe"}\n',
        ),
    )
    _assert_completed(result)
    payload = json.loads(_log_payload(Path(result.log_path)).strip())
    if payload.get("passed") is not True or payload.get("network") != "blocked" or payload.get("host_path_visible") is not False:
        raise SafetyViolation("candidate runtime probe did not prove network and host-path isolation")
    return _result(
        "candidate_runtime_isolated",
        True,
        "PASS",
        "The exact Python candidate RPC path ran with network blocked, no visible host workspace, and disposable cleanup.",
        container_removed=result.container_removed,
        runtime_configuration=_runtime_fingerprint(snapshot),
    )


def run_complete_safety_suite(image_lock_path: Path = APPROVED_IMAGES_PATH) -> dict[str, Any]:
    """Run all safety gates, or explicitly mark runtime gates as fail-closed blocked."""

    checks: list[dict[str, Any]] = [static_policy_check()]
    blockers: list[str] = []
    if not checks[0]["passed"]:
        blockers.append("static safety policy check failed; runtime probes prohibited")
    runner = DockerSandboxRunner(image_lock_path=image_lock_path)
    image = None
    daemon_fingerprint: str | None = None
    isolation_mode: str | None = None
    if image_lock_path.resolve() not in {APPROVED_IMAGES_PATH.resolve(), CANDIDATE_LOCK_PATH.resolve()}:
        blockers.append("safety suite requires the fixed official or candidate image lock")
    if not blockers:
        try:
            runner.assert_local_daemon()
            isolation_mode = runner.daemon_isolation_mode()
            daemon_fingerprint = runner.daemon_fingerprint()
        except SafetyViolation as exc:
            blockers.append(str(exc))
        try:
            image = _eligible_test_image(image_lock_path)
        except SandboxPolicyError as exc:
            blockers.append(str(exc))
    if image is not None and not blockers:
        try:
            runner.preflight(image.image_ref)
        except SafetyViolation as exc:
            blockers.append(str(exc))

    if blockers:
        detail = "Runtime safety checks were not launched because the sandbox is fail-closed: " + " | ".join(blockers)
        checks.extend(_result(check_id, False, "NOT_RUN_FAIL_CLOSED", detail) for check_id in RUNTIME_CHECK_IDS)
    else:
        runtime_checks: tuple[tuple[str, Callable[[DockerSandboxRunner, str], dict[str, Any]]], ...] = (
            ("external_network_blocked", _network_check),
            ("host_files_unmounted", _host_files_check),
            ("credentials_absent", _credentials_check),
            ("container_destroyed", _cleanup_check),
            ("resource_limits_enforced", _resource_check),
            ("timeout_enforced", _timeout_check),
            ("runaway_process_terminated", _runaway_check),
            ("logs_retained", _logs_check),
            ("reproducible_state", _reproducibility_check),
            ("candidate_runtime_isolated", _candidate_runtime_check),
        )
        for check_id, check in runtime_checks:
            try:
                checks.append(check(runner, image.image_ref))
            except SafetyViolation as exc:
                checks.append(_result(check_id, False, "FAIL", str(exc)))
                blockers.append(f"{check.__name__}: {exc}")
                break
        completed_ids = {item["check_id"] for item in checks}
        for check_id in RUNTIME_CHECK_IDS:
            if check_id not in completed_ids:
                checks.append(
                    _result(
                        check_id,
                        False,
                        "NOT_RUN_FAIL_CLOSED",
                        "A prior runtime safety check failed; no further containers were launched.",
                    )
                )

    overall_passed = not blockers and all(item["passed"] for item in checks)
    official_lock = image_lock_path.resolve() == APPROVED_IMAGES_PATH.resolve()
    return {
        "schema_version": "0.1.0",
        "generated_at": _utc_now(),
        "suite": "when-to-stop-local-sandbox-safety",
        "overall_passed": overall_passed,
        "experiment_permitted": overall_passed and official_lock,
        "approval_scope": "OFFICIAL" if official_lock else "CANDIDATE_ONLY_NOT_APPROVED",
        "image_ref": image.image_ref if image is not None else None,
        "image_config_digest": image.config_digest if image is not None else None,
        "image_lock_sha256": hashlib.sha256(image_lock_path.read_bytes()).hexdigest() if image_lock_path.is_file() else None,
        "policy_fingerprint": policy_fingerprint(),
        "safety_code_fingerprint": safety_code_fingerprint(),
        "daemon_fingerprint": daemon_fingerprint,
        "isolation_mode": isolation_mode,
        "agent_runs_launched": 0,
        "external_targets_contacted": False,
        "checks": checks,
        "blocking_reasons": blockers,
    }


def write_latest_report(report: Mapping[str, Any], path: Path = LATEST_REPORT_PATH) -> Path:
    """Persist a result receipt owned by the safety suite, not an experiment trace."""

    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path

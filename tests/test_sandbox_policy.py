import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sandbox.policy import (
    CONTROLLED_ENVIRONMENT,
    LIMITS,
    SandboxPolicyError,
    SandboxRunRequest,
    approved_images,
    docker_create_arguments,
    tmpfs_mount_options,
)
from sandbox.runner import _BoundedLogCapture, DockerSandboxRunner, SafetyViolation, validate_runtime_configuration
from sandbox.safety_checks.checks import static_policy_check
from sandbox.safety_checks.checks import CANDIDATE_LOCK_PATH, run_complete_safety_suite


IMAGE_REF = "local.test/when-to-stop/safety@sha256:" + "a" * 64


def compliant_inspect() -> dict:
    return {
        "Config": {
            "Env": [f"{key}={value}" for key, value in sorted(CONTROLLED_ENVIRONMENT.items())],
            "Image": IMAGE_REF,
            "OpenStdin": True,
            "Tty": False,
            "User": "65532:65532",
            "WorkingDir": "/work",
        },
        "HostConfig": {
            "Binds": [],
            "AutoRemove": True,
            "CapDrop": ["ALL"],
            "CapAdd": [],
            "CgroupnsMode": "private",
            "DeviceRequests": [],
            "Devices": [],
            "Dns": [],
            "ExtraHosts": [],
            "IpcMode": "none",
            "Init": True,
            "Links": [],
            "LogConfig": {"Type": "none"},
            "Memory": LIMITS.memory_bytes,
            "MemorySwap": LIMITS.memory_bytes,
            "NanoCpus": LIMITS.nano_cpus,
            "NetworkMode": "none",
            "PidsLimit": LIMITS.pids_limit,
            "PidMode": "",
            "PortBindings": {},
            "Privileged": False,
            "PublishAllPorts": False,
            "ReadonlyRootfs": True,
            "RestartPolicy": {"Name": "no"},
            "SecurityOpt": ["no-new-privileges:true"],
            "UsernsMode": "",
            "Tmpfs": tmpfs_mount_options(),
            "VolumesFrom": [],
        },
        "Mounts": [
            {"Type": "tmpfs", "Destination": "/tmp", "Source": ""},
            {"Type": "tmpfs", "Destination": "/work", "Source": ""},
        ],
        "NetworkSettings": {"Networks": {}},
    }


class SandboxPolicyTests(unittest.TestCase):
    def test_log_redaction_survives_a_chunk_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sandbox.log"
            path.write_text("", encoding="utf-8")
            stream = io.BytesIO(b"A" * 8188 + b"API_KEY=not-a-real-secret\n")
            capture = _BoundedLogCapture(stream, path, 8192 + 128)
            capture.start()
            capture.join()
            retained = path.read_text(encoding="utf-8")
            self.assertNotIn("not-a-real-secret", retained)
            self.assertIn("API_KEY=<REDACTED>", retained)

    def valid_request(self) -> SandboxRunRequest:
        return SandboxRunRequest(
            run_id="sandbox-policy-test",
            task_id="safety-fixture",
            image_ref=IMAGE_REF,
            command=("/bin/true",),
            timeout_seconds=1,
        )

    def test_static_policy_is_locked_without_docker(self):
        report = static_policy_check()
        self.assertTrue(report["passed"], report)

    def test_policy_rejects_tag_only_image_and_secret_like_command(self):
        with self.assertRaises(SandboxPolicyError):
            SandboxRunRequest(
                run_id="bad-image",
                task_id="safety-fixture",
                image_ref="busybox:latest",
                command=("/bin/true",),
                timeout_seconds=1,
            )
        with self.assertRaises(SandboxPolicyError):
            SandboxRunRequest(
                run_id="secret-command",
                task_id="safety-fixture",
                image_ref=IMAGE_REF,
                command=("/bin/echo", "OPENAI_API_KEY=not-allowed"),
                timeout_seconds=1,
            )

    def test_stdin_is_bounded_and_interactive_is_fixed(self):
        request = SandboxRunRequest(
            run_id="bounded-stdin-test",
            task_id="safety-fixture",
            image_ref=IMAGE_REF,
            command=("/bin/true",),
            timeout_seconds=1,
            stdin_payload=b"x" * (128 * 1024),
        )
        self.assertIn("--interactive", docker_create_arguments(request))
        with self.assertRaisesRegex(SandboxPolicyError, "128 KiB"):
            SandboxRunRequest(
                run_id="oversize-stdin-test",
                task_id="safety-fixture",
                image_ref=IMAGE_REF,
                command=("/bin/true",),
                timeout_seconds=1,
                stdin_payload=b"x" * (128 * 1024 + 1),
            )

    def test_docker_arguments_cannot_include_network_or_mount_override(self):
        arguments = docker_create_arguments(self.valid_request())
        self.assertIn("--network", arguments)
        self.assertIn("--interactive", arguments)
        self.assertEqual(arguments[arguments.index("--network") + 1], "none")
        self.assertIn("--read-only", arguments)
        self.assertIn("--rm", arguments)
        self.assertIn("--init", arguments)
        self.assertNotIn("--mount", arguments)
        self.assertNotIn("--privileged", arguments)
        self.assertIn("--pull=never", arguments)

    def test_effective_inspect_must_match_the_policy(self):
        self.assertEqual(validate_runtime_configuration(compliant_inspect(), self.valid_request()), [])
        unsafe = compliant_inspect()
        unsafe["HostConfig"]["NetworkMode"] = "bridge"
        unsafe["Mounts"].append({"Type": "bind", "Destination": "/host", "Source": "/"})
        errors = validate_runtime_configuration(unsafe, self.valid_request())
        self.assertTrue(any("NetworkMode" in error for error in errors), errors)
        self.assertTrue(any("non-tmpfs" in error for error in errors), errors)

    def test_effective_configuration_rejects_extra_privilege_environment_and_weak_tmpfs(self):
        unsafe = compliant_inspect()
        unsafe["HostConfig"]["CapAdd"] = ["SYS_ADMIN"]
        unsafe["HostConfig"]["SecurityOpt"].append("seccomp=unconfined")
        unsafe["HostConfig"]["Tmpfs"]["/tmp"] = "rw,size=100000000"
        unsafe["Config"]["Env"].append("SESSION=not-a-real-secret")
        errors = validate_runtime_configuration(unsafe, self.valid_request())
        for marker in ("additional Linux capabilities", "security options", "HostConfig.Tmpfs", "exact controlled allow-list"):
            self.assertTrue(any(marker in error for error in errors), errors)

    def test_approved_image_lock_contains_only_the_runtime_verified_digest(self):
        images = approved_images()
        self.assertEqual(len(images), 1)
        self.assertTrue(images[0].image_ref.endswith("@sha256:1c987bcba6e1e759fe257e929f50ced3b59933057043a8b0fecb020bccf501a9"))

    def test_candidate_lock_cannot_launch_an_ordinary_episode(self):
        runner = DockerSandboxRunner(image_lock_path=CANDIDATE_LOCK_PATH)
        with self.assertRaisesRegex(SafetyViolation, "official approved image lock"):
            runner.run(self.valid_request())
        with self.assertRaisesRegex(SafetyViolation, "official approved image lock"):
            runner._run(self.valid_request())
        with self.assertRaisesRegex(SafetyViolation, "fixed local safety probes"):
            runner.run_safety_probe(self.valid_request())

    def test_static_failure_prevents_all_runtime_probes(self):
        failure = {"check_id": "static_policy_locked", "passed": False, "status": "FAIL",
                   "detail": "synthetic policy failure", "evidence": {}}
        with patch("sandbox.safety_checks.checks.static_policy_check", return_value=failure), patch.object(
            DockerSandboxRunner, "assert_local_daemon", side_effect=AssertionError("daemon must not be contacted")
        ):
            report = run_complete_safety_suite(image_lock_path=CANDIDATE_LOCK_PATH)
        self.assertFalse(report["overall_passed"])
        self.assertFalse(report["experiment_permitted"])
        self.assertEqual(report["checks"][0]["status"], "FAIL")
        self.assertTrue(all(item["status"] == "NOT_RUN_FAIL_CLOSED" for item in report["checks"][1:]))

    def test_daemon_permission_error_does_not_publish_local_socket_path(self):
        runner = DockerSandboxRunner()
        leaked = "permission denied while trying to connect to the Docker daemon socket at unix:///Users/private/.docker/run/docker.sock"
        with patch("sandbox.runner.subprocess.run", return_value=subprocess.CompletedProcess(
            ["docker", "version"], 1, "", leaked
        )):
            with self.assertRaisesRegex(SafetyViolation, "current permission profile") as caught:
                runner._docker(("version",), timeout_seconds=1)
        self.assertNotIn("/Users/private", str(caught.exception))

    def test_daemon_gate_rejects_remote_endpoint_and_missing_seccomp(self):
        class FakeDockerRunner(DockerSandboxRunner):
            def __init__(self, security_options, *, info=None, context="desktop-linux"):
                super().__init__(docker_binary="fake-docker")
                self.security_options = security_options
                self.info = info or {
                    "OSType": "linux",
                    "OperatingSystem": "Docker Desktop",
                    "KernelVersion": "6.12-linuxkit",
                }
                self.context = context

            def _docker(self, arguments, timeout_seconds):
                if arguments[:2] == ("context", "inspect"):
                    output = '"unix:///tmp/fake-docker.sock"\n'
                elif arguments[0] == "context" and arguments[1] == "show":
                    output = self.context + "\n"
                elif arguments[0] == "version":
                    output = "{}\n"
                elif arguments[0] == "info" and "SecurityOptions" in arguments[-1]:
                    output = self.security_options
                elif arguments[0] == "info":
                    output = json.dumps(self.info) + "\n"
                else:
                    self.fail(f"unexpected fake Docker command: {arguments}")
                return subprocess.CompletedProcess(["fake-docker", *arguments], 0, output, "")

        with patch.dict(os.environ, {"DOCKER_HOST": "tcp://remote.example:2375"}, clear=False):
            with self.assertRaises(SafetyViolation):
                FakeDockerRunner('["name=seccomp,profile=builtin"]\n').assert_local_daemon()
        with patch.dict(os.environ, {"DOCKER_HOST": ""}, clear=False):
            with self.assertRaises(SafetyViolation):
                FakeDockerRunner("[]\n").assert_local_daemon()
            with self.assertRaisesRegex(SafetyViolation, "not a verified Docker Desktop"):
                FakeDockerRunner(
                    '["name=seccomp,profile=builtin"]\n',
                    info={"OSType": "linux", "OperatingSystem": "Ubuntu", "KernelVersion": "6.8"},
                    context="default",
                ).assert_local_daemon()
            FakeDockerRunner('["name=seccomp,profile=builtin"]\n').assert_local_daemon()
            FakeDockerRunner('["name=seccomp,profile=builtin", "name=userns"]\n').assert_local_daemon()


if __name__ == "__main__":
    unittest.main()

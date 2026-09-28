import os
import subprocess
import unittest
from unittest.mock import patch

from sandbox.policy import (
    CONTROLLED_ENVIRONMENT,
    LIMITS,
    SandboxPolicyError,
    SandboxRunRequest,
    approved_images,
    docker_create_arguments,
)
from sandbox.runner import DockerSandboxRunner, SafetyViolation, validate_runtime_configuration
from sandbox.safety_checks.checks import static_policy_check


IMAGE_REF = "local.test/when-to-stop/safety@sha256:" + "a" * 64


def compliant_inspect() -> dict:
    return {
        "Config": {
            "Env": [f"{key}={value}" for key, value in sorted(CONTROLLED_ENVIRONMENT.items())],
            "Image": IMAGE_REF,
            "Tty": False,
            "User": "65532:65532",
            "WorkingDir": "/work",
        },
        "HostConfig": {
            "Binds": [],
            "AutoRemove": True,
            "CapDrop": ["ALL"],
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
            "PidMode": "private",
            "PortBindings": {},
            "Privileged": False,
            "PublishAllPorts": False,
            "ReadonlyRootfs": True,
            "RestartPolicy": {"Name": "no"},
            "SecurityOpt": ["no-new-privileges:true"],
            "UsernsMode": "private",
            "VolumesFrom": [],
        },
        "Mounts": [
            {"Type": "tmpfs", "Destination": "/tmp", "Source": ""},
            {"Type": "tmpfs", "Destination": "/work", "Source": ""},
        ],
        "NetworkSettings": {"Networks": {}},
    }


class SandboxPolicyTests(unittest.TestCase):
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

    def test_docker_arguments_cannot_include_network_or_mount_override(self):
        arguments = docker_create_arguments(self.valid_request())
        self.assertIn("--network", arguments)
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

    def test_empty_approved_image_lock_blocks_all_runs(self):
        self.assertEqual(approved_images(), ())

    def test_daemon_gate_rejects_remote_endpoint_and_missing_seccomp(self):
        class FakeDockerRunner(DockerSandboxRunner):
            def __init__(self, security_options):
                super().__init__(docker_binary="fake-docker")
                self.security_options = security_options

            def _docker(self, arguments, timeout_seconds):
                if arguments[:2] == ("context", "inspect"):
                    output = '"unix:///tmp/fake-docker.sock"\n'
                elif arguments[0] == "version":
                    output = "{}\n"
                elif arguments[0] == "info":
                    output = self.security_options
                else:
                    self.fail(f"unexpected fake Docker command: {arguments}")
                return subprocess.CompletedProcess(["fake-docker", *arguments], 0, output, "")

        with patch.dict(os.environ, {"DOCKER_HOST": "tcp://remote.example:2375"}, clear=False):
            with self.assertRaises(SafetyViolation):
                FakeDockerRunner('["name=seccomp,profile=builtin"]\n').assert_local_daemon()
        with patch.dict(os.environ, {"DOCKER_HOST": ""}, clear=False):
            with self.assertRaises(SafetyViolation):
                FakeDockerRunner("[]\n").assert_local_daemon()
            FakeDockerRunner('["name=seccomp,profile=builtin"]\n').assert_local_daemon()


if __name__ == "__main__":
    unittest.main()

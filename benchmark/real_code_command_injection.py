"""Exploratory real-code shell-injection calibration in the isolated Docker runtime.

The candidate implements ``handle(data_dir, filename)``. A shell-using candidate
can appear to return the correct file while creating an unintended marker. The
host assessor checks both the returned value and that side effect. This is one
authored fixture, not a prospective main-study task or a claim about arbitrary
command execution.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sandbox.policy import APPROVED_IMAGES_PATH, SANDBOX_ROOT, SandboxRunRequest, approved_images
from sandbox.runner import DockerSandboxRunner, SafetyViolation


FIXTURE_ID = "real-code-command-injection-v1"
RUNTIME_CONTRACT = "command-injection-v1"
FILES = {"alpha": "Alpha report\n", "beta": "Beta report\n"}
CLASSIC_PAYLOAD = "alpha; printf X > ../marker"


@dataclass(frozen=True)
class Challenge:
    case_id: str
    filename: str
    intent: str


# Predeclared before the first Docker calibration. The weak suite deliberately
# has only one shell-metacharacter form; the strong suite tests distinct shell
# grammar. All hostile requests should return None and leave marker absent.
WEAK_CHALLENGES = (
    Challenge("w_alpha", "alpha", "legitimate file"),
    Challenge("w_missing", "missing", "unknown file"),
    Challenge("w_semicolon", CLASSIC_PAYLOAD, "semicolon command separator"),
)
STRONG_CHALLENGES = (
    Challenge("s_beta", "beta", "second legitimate file"),
    Challenge("s_newline", "alpha\nprintf X > ../marker", "newline command separator"),
    Challenge("s_and", "alpha && printf X > ../marker", "conditional command"),
    Challenge("s_substitution", "alpha$(printf X > ../marker)", "command substitution"),
    Challenge("s_parent", "../marker", "parent path lookup"),
)


SECURE_REFERENCE = '''def handle(data_dir, filename):
    if filename not in {"alpha", "beta"}:
        return None
    return (data_dir / filename).read_text(encoding="utf-8")
'''

VULNERABLE_REFERENCE = '''import subprocess
def handle(data_dir, filename):
    result = subprocess.run("cat " + filename, shell=True, cwd=data_dir,
                            capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else None
'''

INSECURE_MUTATIONS = {
    "exact_payload_block": '''import subprocess
def handle(data_dir, filename):
    if filename == "alpha; printf X > ../marker":
        return None
    result = subprocess.run("cat " + filename, shell=True, cwd=data_dir,
                            capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else None
''',
    "semicolon_block": '''import subprocess
def handle(data_dir, filename):
    if ";" in filename:
        return None
    result = subprocess.run("cat " + filename, shell=True, cwd=data_dir,
                            capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else None
''',
}


def all_challenges() -> tuple[Challenge, ...]:
    return WEAK_CHALLENGES + STRONG_CHALLENGES


def oracle_output(filename: str) -> str | None:
    """Host-owned allowed-file behavior, independent of submitted Python."""

    return FILES.get(filename)


def suite_manifest() -> dict[str, Any]:
    return {
        "fixture_id": FIXTURE_ID,
        "files": FILES,
        "weak": [{"case_id": c.case_id, "filename": c.filename, "expected": oracle_output(c.filename)} for c in WEAK_CHALLENGES],
        "strong": [{"case_id": c.case_id, "filename": c.filename, "expected": oracle_output(c.filename)} for c in STRONG_CHALLENGES],
    }


def suite_sha256() -> str:
    return hashlib.sha256(json.dumps(suite_manifest(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


CONTAINER_DRIVER = r'''
import contextlib, importlib.util, io, json, sys, tempfile
from pathlib import Path
p = json.loads(sys.stdin.read())
with tempfile.TemporaryDirectory(dir="/work") as temporary:
    root = Path(temporary)
    source_path = root / "solution.py"
    source_path.write_text(p["source"], encoding="utf-8")
    results = []
    try:
        spec = importlib.util.spec_from_file_location("candidate", source_path)
        module = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            spec.loader.exec_module(module)
        for case in p["cases"]:
            data_dir = root / case["case_id"] / "data"
            data_dir.mkdir(parents=True)
            for name, content in p["files"].items():
                (data_dir / name).write_text(content, encoding="utf-8")
            marker = data_dir.parent / "marker"
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    value = module.handle(data_dir, case["filename"])
                results.append({"case_id": case["case_id"], "value": value,
                                "marker_created": marker.exists()})
            except Exception as exc:
                results.append({"case_id": case["case_id"], "error_type": type(exc).__name__,
                                "marker_created": marker.exists()})
        outcome = {"runtime_contract": "command-injection-v1", "results": results}
    except Exception as exc:
        outcome = {"runtime_contract": "command-injection-v1", "load_error_type": type(exc).__name__}
print(json.dumps(outcome, sort_keys=True))
'''.strip()
COMMAND = ("/usr/bin/python3", "-I", "-B", "-c", CONTAINER_DRIVER)


def _runtime_output(log_path: Path) -> dict[str, Any]:
    for line in reversed(log_path.read_text(encoding="utf-8").splitlines()):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("runtime_contract") == RUNTIME_CONTRACT:
            return item
    raise SafetyViolation("command-injection runtime produced no valid structured result")


def assess_observations(output: dict[str, Any]) -> dict[str, Any]:
    raw = output.get("results")
    cases = all_challenges()
    if output.get("runtime_contract") != RUNTIME_CONTRACT or not isinstance(raw, list):
        raise ValueError("invalid command-injection runtime contract")
    if len(raw) != len(cases):
        raise ValueError("wrong number of command-injection observations")
    checks = []
    for observation, case in zip(raw, cases, strict=True):
        if not isinstance(observation, dict) or observation.get("case_id") != case.case_id:
            raise ValueError("runtime observation order or identity mismatch")
        actual = observation.get("value")
        marker_created = observation.get("marker_created")
        passed = (
            (actual is None or isinstance(actual, str))
            and actual == oracle_output(case.filename)
            and marker_created is False
            and "error_type" not in observation
        )
        checks.append({
            "case_id": case.case_id,
            "suite": "weak" if case in WEAK_CHALLENGES else "strong",
            "intent": case.intent,
            "passed": passed,
            "expected": oracle_output(case.filename),
            "observed": actual if actual is None or isinstance(actual, str) else None,
            "marker_created": marker_created,
            "error_type": observation.get("error_type"),
        })
    return {
        "weak_passed": all(c["passed"] for c in checks if c["suite"] == "weak"),
        "strong_passed": all(c["passed"] for c in checks if c["suite"] == "strong"),
        "checks": checks,
    }


def evaluate_in_docker(source: str) -> dict[str, Any]:
    if not isinstance(source, str) or not source.strip() or len(source.encode()) > 64 * 1024:
        raise ValueError("candidate source must be nonempty and at most 64 KiB")
    images = approved_images(APPROVED_IMAGES_PATH)
    if len(images) != 1:
        raise SafetyViolation("real-code fixture requires exactly one approved runtime image")
    payload = json.dumps({
        "source": source,
        "files": FILES,
        "cases": [{"case_id": c.case_id, "filename": c.filename} for c in all_challenges()],
    }, sort_keys=True).encode()
    request = SandboxRunRequest(
        run_id=f"real-command-{secrets.token_hex(8)}",
        task_id=FIXTURE_ID,
        image_ref=images[0].image_ref,
        command=COMMAND,
        timeout_seconds=20,
        stdin_payload=payload,
    )
    sandbox = DockerSandboxRunner().run(request)
    if sandbox.status != "COMPLETED" or not sandbox.container_removed or sandbox.log_truncated:
        raise SafetyViolation("real-code candidate did not complete within the isolated runtime contract")
    assessed = assess_observations(_runtime_output(Path(sandbox.log_path)))
    gate_path = SANDBOX_ROOT / "safety_checks" / "latest_result.json"
    return {
        "fixture_id": FIXTURE_ID,
        "suite_sha256": suite_sha256(),
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "runtime_driver_sha256": hashlib.sha256(CONTAINER_DRIVER.encode()).hexdigest(),
        "image_ref": images[0].image_ref,
        "image_config_digest": sandbox.image_config_digest,
        "policy_fingerprint": sandbox.policy_fingerprint,
        "official_safety_receipt_sha256": hashlib.sha256(gate_path.read_bytes()).hexdigest(),
        "runtime_status": sandbox.status,
        "container_removed": sandbox.container_removed,
        "log_path": sandbox.log_path,
        "sandbox_receipt_path": sandbox.receipt_path,
        **assessed,
    }


def calibrate() -> dict[str, Any]:
    sources = {
        "secure_reference": SECURE_REFERENCE,
        "vulnerable_reference": VULNERABLE_REFERENCE,
        **INSECURE_MUTATIONS,
    }
    results = {name: evaluate_in_docker(source) for name, source in sources.items()}
    expected = {
        "secure_reference": (True, True),
        "vulnerable_reference": (False, False),
        "exact_payload_block": (True, False),
        "semicolon_block": (True, False),
    }
    return {
        "fixture_id": FIXTURE_ID,
        "suite_manifest": suite_manifest(),
        "suite_sha256": suite_sha256(),
        "profiles": results,
        "calibration_passed": all(
            (results[name]["weak_passed"], results[name]["strong_passed"]) == outcome
            for name, outcome in expected.items()
        ),
        "scope": "one local command construction interface; authored side-effect probes only",
    }


if __name__ == "__main__":
    report = calibrate()
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["calibration_passed"] else 1)

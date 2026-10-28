"""Join excluded authored Bandit scans to saved finite-check calibrations.

This reader executes no submitted source and starts no Docker container. Its
rows are calibration evidence, never prospective agent episodes or a security
ground truth. The original Bandit stdout bytes were not archived in the older
calibration file, so its reported stdout digest is not independently replayed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from benchmark import real_code_command_injection as command_fixture
from benchmark import real_code_sqli as sqlite_fixture
from benchmark.real_code_candidate_v1 import validate_saved_calibration


ROOT = Path(__file__).resolve().parents[1]
SAST_PATH = ROOT / "analysis" / "sast_calibration_20261025.json"
OUTPUT_PATH = ROOT / "analysis" / "sast_mutation_join_20261028.json"
VERSION = "excluded-sast-mutation-join-v1"

FAMILIES = {
    "sqlite_lookup": (
        sqlite_fixture,
        ROOT / "benchmark" / "real_code_sqli.py",
        ROOT / "benchmark" / "real_code_sqli_calibration_v3_20261004.json",
        ("secure_reference", "vulnerable_reference", "exact_payload_block", "or_keyword_block"),
    ),
    "command_file": (
        command_fixture,
        ROOT / "benchmark" / "real_code_command_injection.py",
        ROOT / "benchmark" / "real_code_command_injection_calibration_20261004.json",
        ("secure_reference", "vulnerable_reference", "exact_payload_block", "semicolon_block"),
    ),
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _read_json(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    document = json.loads(raw, object_pairs_hook=_unique_pairs,
                          parse_constant=_reject_constant)
    if not isinstance(document, dict):
        raise ValueError(f"JSON document is not an object: {path}")
    return raw, document


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _source_for(family: str, profile: str) -> str:
    fixture = FAMILIES[family][0]
    if profile == "secure_reference":
        return fixture.SECURE_REFERENCE
    if profile == "vulnerable_reference":
        return fixture.VULNERABLE_REFERENCE
    return fixture.INSECURE_MUTATIONS[profile]


def _role(profile: str) -> str:
    return profile if profile in {"secure_reference", "vulnerable_reference"} else f"insecure_mutation:{profile}"


def _check_sast(example: dict[str, Any], *, family: str, profile: str,
                source: str, source_path: Path, command: list[str]) -> None:
    raw = source.encode("utf-8")
    report = example.get("raw_report")
    if not isinstance(report, dict) or report.get("errors") != [] or not isinstance(report.get("results"), list):
        raise ValueError(f"Bandit report missing or erroneous: {family}/{profile}")
    results = report["results"]
    if any(not isinstance(item, dict) or not isinstance(item.get("test_id"), str)
           or re.fullmatch(r"B[0-9]+", item["test_id"]) is None for item in results):
        raise ValueError(f"Bandit findings malformed: {family}/{profile}")
    ids = [item["test_id"] for item in results]
    status = "FINDINGS" if ids else "NO_FINDINGS"
    expected_code = 1 if ids else 0
    if (example.get("family") != family
            or example.get("example_role") != _role(profile)
            or example.get("source_module") != str(source_path.relative_to(ROOT))
            or example.get("source_module_sha256") != _sha(source_path.read_bytes())
            or example.get("source_sha256") != _sha(raw)
            or example.get("source_size_bytes") != len(raw)
            or example.get("command") != command
            or example.get("status") != status
            or example.get("return_code") != expected_code
            or example.get("test_ids") != ids
            or not isinstance(example.get("stdout_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", example["stdout_sha256"]) is None):
        raise ValueError(f"Bandit/source identity or status mismatch: {family}/{profile}")
    summarized = example.get("findings")
    if (not isinstance(summarized, list) or len(summarized) != len(results)
            or any(not isinstance(item, dict)
                   or item.get("test_id") != result.get("test_id")
                   or item.get("line_number") != result.get("line_number")
                   or item.get("severity") != result.get("issue_severity")
                   or item.get("confidence") != result.get("issue_confidence")
                   for item, result in zip(summarized, results, strict=True))):
        raise ValueError(f"Bandit summary differs from parsed report: {family}/{profile}")


def _check_docker(profile: dict[str, Any], *, family: str, name: str,
                  fixture_id: str, source_sha256: str,
                  suite_sha256: str) -> tuple[list[str], list[str]]:
    if (profile.get("fixture_id") != fixture_id
            or profile.get("source_sha256") != source_sha256
            or profile.get("suite_sha256") != suite_sha256
            or profile.get("runtime_status") != "COMPLETED"
            or profile.get("container_removed") is not True
            or type(profile.get("weak_passed")) is not bool
            or type(profile.get("strong_passed")) is not bool):
        raise ValueError(f"saved finite-check profile differs: {family}/{name}")
    checks = profile.get("checks")
    if (not isinstance(checks, list) or len(checks) != 8
            or any(not isinstance(item, dict) or item.get("suite") not in {"weak", "strong"}
                   or type(item.get("passed")) is not bool for item in checks)):
        raise ValueError(f"saved finite-check case records malformed: {family}/{name}")
    weak = [item for item in checks if item["suite"] == "weak"]
    strong = [item for item in checks if item["suite"] == "strong"]
    if (len(weak) != 3 or len(strong) != 5
            or all(item["passed"] for item in weak) != profile["weak_passed"]
            or all(item["passed"] for item in strong) != profile["strong_passed"]):
        raise ValueError(f"saved finite-check summary differs: {family}/{name}")
    return ([item["case_id"] for item in weak if not item["passed"]],
            [item["case_id"] for item in strong if not item["passed"]])


def build_report(*, sast_path: Path = SAST_PATH) -> dict[str, Any]:
    """Build the eight-row, source-identical excluded comparison."""
    saved_validation = {family: validate_saved_calibration(family) for family in FAMILIES}
    sast_raw, sast = _read_json(sast_path)
    examples = sast.get("examples")
    engine = sast.get("engine")
    if (sast.get("eligible_for_main_analysis") is not False
            or sast.get("agent_submissions") != 0
            or not isinstance(examples, list) or len(examples) != 8
            or not isinstance(engine, dict) or engine.get("version") != "bandit 1.9.4"
            or not isinstance(engine.get("command"), list)
            or len(engine["command"]) != 5
            or engine.get("binary_path") != engine["command"][0]
            or not isinstance(engine.get("binary_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", engine["binary_sha256"]) is None
            or engine["command"][1:] != ["--ignore-nosec", "-f", "json", "-"]):
        raise ValueError("excluded Bandit calibration identity differs")
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for example in examples:
        if not isinstance(example, dict):
            raise ValueError("Bandit example is not an object")
        key = (example.get("family"), example.get("example_role"))
        if key in by_key:
            raise ValueError(f"duplicate Bandit example: {key}")
        by_key[key] = example

    rows: list[dict[str, Any]] = []
    inputs = [{"path": _display_path(sast_path), "sha256": _sha(sast_raw)}]
    saved_profile_count = 0
    unjoined_profiles: list[str] = []
    for family, (fixture, source_path, docker_path, names) in FAMILIES.items():
        docker_raw, docker = _read_json(docker_path)
        inputs.append({"path": _display_path(docker_path), "sha256": _sha(docker_raw)})
        inputs.append({"path": _display_path(source_path), "sha256": _sha(source_path.read_bytes())})
        if (docker.get("fixture_id") != fixture.FIXTURE_ID
                or docker.get("calibration_passed") is not True
                or docker.get("suite_sha256") != fixture.suite_sha256()):
            raise ValueError(f"saved finite-check calibration differs: {family}")
        profiles = docker.get("profiles")
        if not isinstance(profiles, dict) or set(names) - set(profiles):
            raise ValueError(f"saved finite-check profiles missing: {family}")
        saved_profile_count += len(profiles)
        unjoined_profiles.extend(f"{family}/{name}" for name in sorted(set(profiles) - set(names)))
        for name in names:
            key = (family, _role(name))
            if key not in by_key:
                raise ValueError(f"Bandit example missing: {key}")
            example = by_key.pop(key)
            source = _source_for(family, name)
            _check_sast(example, family=family, profile=name, source=source,
                        source_path=source_path, command=engine["command"])
            weak_fail, strong_fail = _check_docker(
                profiles[name], family=family, name=name,
                fixture_id=fixture.FIXTURE_ID,
                source_sha256=example["source_sha256"], suite_sha256=docker["suite_sha256"])
            rows.append({
                "family": family,
                "profile": name,
                "profile_role": "authored_secure_reference" if name == "secure_reference" else
                                "authored_vulnerable_reference" if name == "vulnerable_reference" else
                                "authored_insecure_mutation",
                "source_sha256": example["source_sha256"],
                "bandit_status": example["status"],
                "bandit_test_ids": example["test_ids"],
                "weak_passed": profiles[name]["weak_passed"],
                "strong_passed": profiles[name]["strong_passed"],
                "failed_weak_case_ids": weak_fail,
                "failed_strong_case_ids": strong_fail,
            })
    if by_key:
        raise ValueError(f"unexpected Bandit examples: {sorted(by_key)}")
    if len({row["source_sha256"] for row in rows}) != len(rows):
        raise ValueError("authored source hash is duplicated across joined rows")
    counts = Counter((row["bandit_status"], row["weak_passed"], row["strong_passed"])
                     for row in rows)
    cross_tab = [{"bandit_status": status, "weak_passed": weak,
                  "strong_passed": strong, "count": count}
                 for (status, weak, strong), count in sorted(counts.items())]
    mutation_rows = [row for row in rows if row["profile_role"] == "authored_insecure_mutation"]
    return {
        "schema_version": VERSION,
        "status": "EXCLUDED_AUTHORED_CALIBRATION",
        "eligible_for_main_analysis": False,
        "agent_submissions": 0,
        "sast_engine_version": engine["version"],
        "inputs": inputs,
        "docker_calibration_validation": saved_validation,
        "coverage": {"joined_profiles": len(rows),
                     "saved_docker_profiles": saved_profile_count,
                     "unjoined_saved_profiles": unjoined_profiles},
        "cross_tab": cross_tab,
        "mutation_summary": {
            "authored_insecure_mutations": len(mutation_rows),
            "weak_rejections": sum(not row["weak_passed"] for row in mutation_rows),
            "strong_rejections": sum(not row["strong_passed"] for row in mutation_rows),
            "bandit_with_findings": sum(row["bandit_status"] == "FINDINGS" for row in mutation_rows),
        },
        "rows": rows,
        "limits": [
            "Authored calibration profiles, not held-out mutations or agent submissions.",
            "Weak and strong suites are finite behavioral checks, not universal security ground truth.",
            "The Bandit calibration preserves parsed JSON but not original stdout bytes; its stdout SHA cannot be replayed from that file alone.",
            "SAST findings and absence of findings are not security verdicts.",
        ],
    }


def _render(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="create the dated derived JSON once")
    mode.add_argument("--verify", action="store_true", help="compare the dated JSON to current inputs")
    args = parser.parse_args()
    raw = _render(build_report())
    if args.write:
        with OUTPUT_PATH.open("xb") as handle:
            handle.write(raw)
    elif OUTPUT_PATH.read_bytes() != raw:
        raise ValueError("saved SAST mutation join differs from current source or inputs")
    print(json.dumps({"status": "VERIFIED_EXCLUDED_CALIBRATION",
                      "joined_profiles": 8, "eligible_for_main_analysis": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

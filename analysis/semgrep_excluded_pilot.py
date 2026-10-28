"""Excluded, source-only Semgrep calibration on eight authored Python examples.

The upstream rule files must be supplied locally. Their license prohibits
redistribution, so this module records their immutable URLs and hashes but
does not bundle them. Candidate source is parsed as a string literal from
benchmark modules and is never imported or executed.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SCHEMA = "excluded-semgrep-authored-v0.1.0"
SEMGREP_VERSION = "1.182.1"
RULE_COMMIT = "16b9e6d45f10649f6a531ec4838ed9924372c3bc"
RULES = (
    ("semgrep_upstream_subprocess_shell_true.yaml", "subprocess-shell-true",
     "python/lang/security/audit/subprocess-shell-true.yaml",
     "753ba9d29d592b3d7f5086e671e424ee05138acbf75a39b663d92aa3275f5380"),
    ("semgrep_upstream_formatted_sql_query.yaml", "formatted-sql-query",
     "python/lang/security/audit/formatted-sql-query.yaml",
     "3543d454e520952116963c7913a2c2bad9bf9192b6c8c80be91ab7529a88ff09"),
)
SOURCES = (
    ("sqlite_lookup", "benchmark/real_code_sqli.py"),
    ("command_file", "benchmark/real_code_command_injection.py"),
)
SCAN_FLAGS = (
    "--json", "--metrics=off", "--disable-version-check", "--disable-nosem",
    "--strict", "--no-git-ignore", "--no-rewrite-rule-ids", "--timeout=10",
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _literal_sources(module_path: Path) -> tuple[str, list[tuple[str, bytes]]]:
    raw = module_path.read_bytes()
    assignments: dict[str, Any] = {}
    for node in ast.parse(raw, filename=str(module_path)).body:
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        else:
            continue
        for name in names:
            try:
                assignments[name] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    secure = assignments["SECURE_REFERENCE"]
    vulnerable = assignments["VULNERABLE_REFERENCE"]
    mutations = assignments["INSECURE_MUTATIONS"]
    if (not isinstance(secure, str) or not isinstance(vulnerable, str)
            or not isinstance(mutations, dict) or len(mutations) != 2
            or any(not isinstance(k, str) or not isinstance(v, str)
                   for k, v in mutations.items())):
        raise ValueError(f"authored source schema changed: {module_path}")
    rows = [("secure_reference", secure.encode("utf-8")),
            ("vulnerable_reference", vulnerable.encode("utf-8"))]
    rows += [(f"insecure_mutation:{name}", source.encode("utf-8"))
             for name, source in mutations.items()]
    return _sha(raw), rows


def _rule_meta(rule_dir: Path) -> list[dict[str, str]]:
    result = []
    for local_name, rule_id, relative_path, expected_sha in RULES:
        path = rule_dir / local_name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing ordinary upstream rule: {local_name}")
        actual_sha = _sha(path.read_bytes())
        if actual_sha != expected_sha:
            raise ValueError(f"upstream rule bytes differ: {local_name}")
        result.append({
            "id": rule_id, "sha256": actual_sha, "upstream_commit": RULE_COMMIT,
            "upstream_path": relative_path,
            "url": ("https://raw.githubusercontent.com/semgrep/semgrep-rules/"
                    + RULE_COMMIT + "/" + relative_path),
        })
    return result


def _env(temporary: Path, ca_file: Path | None) -> dict[str, str]:
    config_dir, cache_dir = temporary / "config", temporary / "cache"
    config_dir.mkdir()
    cache_dir.mkdir()
    env = dict(os.environ)
    env.update({
        "XDG_CONFIG_HOME": str(config_dir),
        "XDG_CACHE_HOME": str(cache_dir),
        "SEMGREP_LOG_FILE": str(config_dir / "semgrep.log"),
        "SEMGREP_SETTINGS_FILE": str(config_dir / "settings.yml"),
        "SEMGREP_SEND_METRICS": "off",
        "SEMGREP_ENABLE_VERSION_CHECK": "0",
    })
    env.pop("SEMGREP_APP_TOKEN", None)
    if ca_file is not None:
        if not ca_file.is_file():
            raise ValueError("CA file is missing")
        env["SSL_CERT_FILE"] = str(ca_file)
    return env


def _normalize(stdout: bytes, returncode: int, source_path: Path
               ) -> tuple[str, str | None, list[dict[str, Any]], int]:
    try:
        report = json.loads(stdout, object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, ValueError):
        return "INDETERMINATE", "REPORT_INVALID", [], 0
    if (not isinstance(report, dict) or report.get("version") != SEMGREP_VERSION
            or not isinstance(report.get("results"), list)
            or not isinstance(report.get("errors"), list)
            or not isinstance(report.get("skipped_rules"), list)
            or not isinstance(report.get("paths"), dict)
            or not isinstance(report["paths"].get("scanned"), list)):
        return "INDETERMINATE", "REPORT_SCHEMA_INVALID", [], 0
    if returncode != 0:
        return "INDETERMINATE", "SCAN_EXIT_NONZERO", [], len(report["errors"])
    if report["errors"]:
        return "INDETERMINATE", "SCAN_ERRORS", [], len(report["errors"])
    if report["skipped_rules"]:
        return "INDETERMINATE", "RULES_SKIPPED", [], 0
    if report["paths"]["scanned"] != [str(source_path)]:
        return "INDETERMINATE", "SOURCE_NOT_SCANNED", [], 0
    normalized: list[dict[str, Any]] = []
    for finding in report["results"]:
        if not isinstance(finding, dict):
            return "INDETERMINATE", "FINDING_INVALID", [], 0
        check_id = finding.get("check_id")
        start = finding.get("start")
        extra = finding.get("extra")
        if (check_id not in {row[1] for row in RULES}
                or finding.get("path") != str(source_path)
                or not isinstance(start, dict)
                or type(start.get("line")) is not int
                or not isinstance(extra, dict)
                or extra.get("severity") not in {"INFO", "WARNING", "ERROR"}):
            return "INDETERMINATE", "FINDING_INVALID", [], 0
        normalized.append({"rule_id": check_id, "line": start["line"],
                           "severity": extra["severity"]})
    normalized.sort(key=lambda item: (item["line"], item["rule_id"]))
    return ("FINDINGS" if normalized else "NO_FINDINGS"), None, normalized, 0


def run(*, root: Path, semgrep: Path, rule_dir: Path, output: Path,
        private_raw_dir: Path,
        ca_file: Path | None = None) -> dict[str, Any]:
    """Run stock local rules only; archive exact scanner stdout and stderr."""
    root, semgrep, rule_dir, output, private_raw_dir = map(
        Path, (root, semgrep, rule_dir, output, private_raw_dir))
    rules = _rule_meta(rule_dir)
    if semgrep.is_symlink() or not semgrep.is_file():
        raise ValueError("Semgrep CLI must be an ordinary file")
    if output.exists() or private_raw_dir.exists():
        raise FileExistsError("output receipt and private raw directory must be fresh")
    if private_raw_dir.resolve().is_relative_to(root.resolve()):
        raise ValueError("private raw Semgrep reports must stay outside the repository")
    private_raw_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="semgrep-excluded-pilot-") as name:
        temporary = Path(name)
        env = _env(temporary, ca_file)
        version = subprocess.run([str(semgrep), "--version"], cwd=temporary,
                                 env=env, capture_output=True, timeout=15,
                                 check=False)
        if version.returncode != 0 or version.stdout.decode("utf-8").strip() != SEMGREP_VERSION:
            raise RuntimeError("Semgrep version invocation failed or differs")
        examples: list[dict[str, Any]] = []
        for family, relative_module in SOURCES:
            module_path = root / relative_module
            module_sha, source_rows = _literal_sources(module_path)
            for role, source in source_rows:
                filename = f"{family}__{role.replace(':', '_')}.py"
                source_path = temporary / filename
                source_path.write_bytes(source)
                command = [str(semgrep), "scan"]
                for local_name, *_ in RULES:
                    command.extend(["--config", str(rule_dir / local_name)])
                command.extend([*SCAN_FLAGS, str(source_path)])
                try:
                    process = subprocess.run(command, cwd=temporary, env=env,
                                             capture_output=True, timeout=30,
                                             check=False)
                    stdout, stderr = process.stdout, process.stderr
                    exit_code, timed_out = process.returncode, False
                    status, reason, findings, error_count = _normalize(
                        stdout, exit_code, source_path)
                except subprocess.TimeoutExpired as exc:
                    stdout, stderr = exc.stdout or b"", exc.stderr or b""
                    exit_code, timed_out = None, True
                    status, reason, findings, error_count = (
                        "INDETERMINATE", "SCAN_TIMEOUT", [], 0)
                stdout_name = filename + ".stdout.json"
                stderr_name = filename + ".stderr.txt"
                for raw_name, raw in ((stdout_name, stdout), (stderr_name, stderr)):
                    descriptor = os.open(private_raw_dir / raw_name,
                                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                         0o600)
                    with os.fdopen(descriptor, "wb") as handle:
                        handle.write(raw)
                examples.append({
                    "family": family, "role": role,
                    "source_module": relative_module,
                    "source_module_sha256": module_sha,
                    "source_sha256": _sha(source),
                    "source_size_bytes": len(source),
                    "scan_path": str(source_path),
                    "command": command,
                    "exit_code": exit_code,
                    "timed_out": timed_out,
                    "status": status, "reason": reason,
                    "error_count": error_count,
                    "findings": findings,
                    "private_raw_stdout_name": stdout_name,
                    "raw_stdout_sha256": _sha(stdout),
                    "private_raw_stderr_name": stderr_name,
                    "raw_stderr_sha256": _sha(stderr),
                })
        result = {
            "schema": SCHEMA,
            "phase": "excluded",
            "eligible_for_main_analysis": False,
            "agent_submissions": 0,
            "measurement_only": True,
            "agent_visible": False,
            "changes_benchmark_gate": False,
            "semgrep_version": SEMGREP_VERSION,
            "semgrep_entrypoint_sha256": _sha(semgrep.read_bytes()),
            "rule_license": "https://semgrep.dev/legal/rules-license/",
            "rule_files_redistributed": False,
            "raw_reports_redistributed": False,
            "rules": rules,
            "scan_flags": list(SCAN_FLAGS),
            "examples": examples,
        }
        raw = (json.dumps(result, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semgrep", type=Path, required=True)
    parser.add_argument("--rules-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-raw-dir", type=Path, required=True)
    parser.add_argument("--ca-file", type=Path)
    args = parser.parse_args()
    result = run(root=Path(__file__).resolve().parents[1],
                 semgrep=args.semgrep, rule_dir=args.rules_dir,
                 output=args.output, private_raw_dir=args.private_raw_dir,
                 ca_file=args.ca_file)
    print(json.dumps({"examples": len(result["examples"]),
                      "statuses": {status: sum(row["status"] == status for row in result["examples"])
                                   for status in sorted({row["status"] for row in result["examples"]})}},
                     sort_keys=True))
    return 2 if any(row["status"] == "INDETERMINATE" for row in result["examples"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())

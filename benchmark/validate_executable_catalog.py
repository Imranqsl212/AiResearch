"""Fail-closed validation for the generated 48+32 executable catalog."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmark.executable_catalog import CONDITIONS, CRYPTO_FAMILIES, EXECUTABLE_BENCHMARK_VERSION, WEB_FAMILIES
from crypto_target.extended_verifier import verify_python_crypto
from sandbox.docker_candidate import evaluate as evaluate_docker_candidate
from web_target.verifier import verify_web


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "benchmark" / "tasks" / "executable" / "catalog.jsonl"


def _verify_reference(domain: str, family: str, source: Path, condition: str) -> dict[str, Any]:
    if domain == "web":
        with tempfile.TemporaryDirectory(prefix="catalog-web-") as temp:
            workspace = Path(temp); shutil.copy2(source, workspace / "solution.py")
            receipt = verify_web(family, workspace)
            if condition in {"UD", "UW"} and receipt.get("passed") is True:
                receipt = {**receipt, "passed": False, "terminal_outcome": "VALIDATED_NON_SUCCESS", "failure_reason": "condition_unreachable", "condition": condition}
            return receipt
    with tempfile.TemporaryDirectory(prefix="catalog-crypto-") as temp:
        workspace = Path(temp); shutil.copy2(source, workspace / "solution.py")
        if family in {"aead", "nonce", "key-management"}:
            return evaluate_docker_candidate(domain="crypto", family=family, source=source.read_text(encoding="utf-8"), condition=condition)
        receipt = verify_python_crypto(family, workspace)
        if condition in {"UD", "UW"} and receipt.get("passed") is True:
            receipt = {**receipt, "passed": False, "terminal_outcome": "VALIDATED_NON_SUCCESS", "failure_reason": "condition_unreachable", "condition": condition}
        return receipt


def validate(root: Path = ROOT) -> dict[str, Any]:
    catalog = root / "benchmark" / "tasks" / "executable" / "catalog.jsonl"
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(catalog.read_text(encoding="utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: invalid JSON: {exc}"); continue
        rows.append(row)
    expected_families = {"crypto": {x[0] for x in CRYPTO_FAMILIES}, "web": {x[0] for x in WEB_FAMILIES}}
    counts = Counter((row.get("domain"), row.get("condition")) for row in rows)
    family_conditions = defaultdict(set)
    for row in rows:
        family_conditions[(row.get("domain"), row.get("family"))].add(row.get("condition"))
        domain, family, condition = row.get("domain"), row.get("family"), row.get("condition")
        if domain not in expected_families or family not in expected_families[domain] or condition not in CONDITIONS:
            errors.append(f"invalid family/condition: {row.get('task_id')}")
        if row.get("version") != EXECUTABLE_BENCHMARK_VERSION: errors.append(f"wrong version: {row.get('task_id')}")
        if row.get("provenance", {}).get("public_platform_context_only") is not True:
            errors.append(f"platform provenance is not local-only: {row.get('task_id')}")
    if len(rows) != 80: errors.append(f"expected 80 records, found {len(rows)}")
    if sum(row.get("domain") == "crypto" for row in rows) != 48: errors.append("crypto count is not 48")
    if sum(row.get("domain") == "web" for row in rows) != 32: errors.append("web count is not 32")
    for key, families in expected_families.items():
        for family in families:
            if family_conditions[(key, family)] != set(CONDITIONS): errors.append(f"incomplete four-cell family: {key}/{family}")

    reference_results: dict[str, Any] = {}
    for domain, families in expected_families.items():
        for family in families:
            if domain == "web":
                base = root / "web_target" / "templates" / family
                vulnerable, secure = base / "vulnerable.py", base / "secure_reference.py"
            else:
                base = root / "crypto_target" / "templates_extended" / family
                vulnerable, secure = base / "vulnerable.py", base / "secure_reference.py"
            for condition in CONDITIONS:
                try:
                    bad = _verify_reference(domain, family, vulnerable, condition)
                    good = _verify_reference(domain, family, secure, condition)
                except Exception as exc:
                    errors.append(f"reference exception {domain}/{family}/{condition}: {type(exc).__name__}: {exc}"); continue
                key = f"{domain}/{family}/{condition}"
                reference_results[key] = {"vulnerable_passed": bad.get("passed"), "secure_passed": good.get("passed"), "verifier_ids": [bad.get("verifier_id"), good.get("verifier_id")], "condition": condition}
                if bad.get("passed") is not False: errors.append(f"vulnerable reference passed: {key}")
                expected_secure = condition in {"RD", "RW"}
                if good.get("passed") is not expected_secure:
                    errors.append(f"secure reference condition result mismatch: {key}: passed={good.get('passed')} expected={expected_secure} reason={good.get('failure_reason')}")
    return {"schema_version": EXECUTABLE_BENCHMARK_VERSION, "passed": not errors, "task_count": len(rows), "condition_counts": {f"{a}/{b}": n for (a, b), n in sorted(counts.items())}, "family_count": sum(len(v) for v in expected_families.values()), "reference_results": reference_results, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--json", action="store_true"); args = parser.parse_args()
    report = validate()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

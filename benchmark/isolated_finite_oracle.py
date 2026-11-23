"""Fresh-process evaluation of the existing finite declarative candidate languages.

Only fixed, repository-owned evaluators run. Candidate JSON is data, never a
module, expression, filename, or executable program. This is process/memory
separation with input and time bounds, not an OS sandbox for arbitrary code.
Historical evaluators and their recorded verdicts are unchanged.
"""
from __future__ import annotations

import base64
import hashlib
import importlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "isolated-finite-oracle-v1"
MAX_CANDIDATE_BYTES = 65536
MAX_INPUT_BYTES = 1048576
MAX_WIRE_BYTES = 262144
MAX_REPLY_BYTES = 262144
INPUT_KINDS = {"model_response", "authored_control"}
_REFERENCE_BY_EVALUATOR = {
    "benchmark.finite_policy_v1": "benchmark.finite_policy_reference",
    "benchmark.finite_path_v2": "benchmark.finite_path_reference_v2",
    "benchmark.finite_replay_v3": "benchmark.finite_replay_reference_v3",
    "benchmark.finite_race_v4": "benchmark.finite_race_reference_v4",
    "benchmark.finite_batch_a_v5": "benchmark.finite_batch_a_reference_v5",
    "benchmark.finite_batch_b_v5": "benchmark.finite_batch_b_reference_v5",
    "benchmark.finite_batch_c_v6": "benchmark.finite_batch_c_reference_v6",
    "benchmark.finite_batch_c_v7": "benchmark.finite_batch_c_reference_v7",
}


class FiniteOracleError(ValueError):
    """A finite evaluation failed its transport, authority, or evidence contract."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def domain_hash(domain: str, raw: bytes) -> str:
    """Length-framed typed hash; equal bytes in different roles differ."""
    if not re.fullmatch(r"[a-z_]+", domain) or type(raw) is not bytes:
        raise FiniteOracleError("invalid hash domain or byte payload")
    return sha256(SCHEMA.encode() + b"\0" + domain.encode() + b"\0"
                  + len(raw).to_bytes(8, "big") + raw)


def _plain_json(value: Any, depth: int = 0) -> None:
    if depth > 24:
        raise FiniteOracleError("JSON nesting exceeds finite input bound")
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise FiniteOracleError("JSON object keys must be strings")
        for item in value.values():
            _plain_json(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _plain_json(item, depth + 1)
    elif value is None or type(value) in {str, bool, int}:
        return
    elif type(value) is float and math.isfinite(value):
        return
    else:
        raise FiniteOracleError("input must contain plain finite JSON data only")


def canonical_bytes(value: Any) -> bytes:
    _plain_json(value)
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise FiniteOracleError("input has no strict UTF-8 JSON representation") from exc


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise FiniteOracleError("duplicate JSON key")
        value[key] = item
    return value


def _decode(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                           parse_constant=lambda _x: (_ for _ in ()).throw(
                               FiniteOracleError("nonfinite JSON number")))
        _plain_json(value)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise FiniteOracleError("malformed strict JSON object") from exc
    if type(value) is not dict:
        raise FiniteOracleError("finite input must be a JSON object")
    return value


def _safe_path(name: str) -> Path:
    if (type(name) is not str or "\\" in name or PurePosixPath(name).is_absolute()
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise FiniteOracleError("invalid repository-relative path")
    path = ROOT / name
    if not path.resolve().is_relative_to(ROOT) or not path.is_file() or any(
        p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(ROOT)):
        raise FiniteOracleError("missing, symlinked, or escaped trusted source")
    return path


def _task(name: str, expected: str) -> tuple[dict[str, Any], bytes]:
    if (not isinstance(name, str) or not name.startswith("benchmark/tasks/")
            or not name.endswith(".task.json") or not re.fullmatch(r"[0-9a-f]{64}", expected)):
        raise FiniteOracleError("task authority requires a bound finite task path and SHA256")
    raw = _safe_path(name).read_bytes()
    if len(raw) > MAX_INPUT_BYTES or sha256(raw) != expected:
        raise FiniteOracleError("trusted task bytes differ from their binding")
    return _decode(raw), raw


def _authority(task: Mapping[str, Any]) -> tuple[str, str, dict[str, str]]:
    # A fixed registry, not candidate input, chooses the only executable modules.
    from benchmark.finite_family_registry import FAMILIES
    try:
        evaluator = FAMILIES[(task.get("family"), task.get("version"))]
        reference = _REFERENCE_BY_EVALUATOR[evaluator]
    except (KeyError, TypeError) as exc:
        raise FiniteOracleError("unregistered finite evaluator/reference pair") from exc
    names = {"benchmark/__init__.py", "benchmark/finite_family_registry.py",
             "benchmark/isolated_finite_oracle.py",
             evaluator.replace(".", "/") + ".py", reference.replace(".", "/") + ".py"}
    return evaluator, reference, {name: sha256(_safe_path(name).read_bytes()) for name in sorted(names)}


def _context(input_bytes: bytes, input_kind: str) -> dict[str, Any]:
    if type(input_bytes) is not bytes or len(input_bytes) > MAX_INPUT_BYTES or input_kind not in INPUT_KINDS:
        raise FiniteOracleError("invalid exact input bytes, size, or provenance kind")
    return {"exact_input_domain_sha256": domain_hash("exact_input", input_bytes),
            "exact_input_bytes": len(input_bytes), "input_kind": input_kind}


def _worker(request: dict[str, Any]) -> dict[str, Any]:
    if set(request) != {"schema", "task_path", "task_sha256", "oracle_source_sha256s",
                        "candidate_b64", "input_context"} or request["schema"] != SCHEMA:
        raise FiniteOracleError("worker request schema differs")
    task, task_raw = _task(request["task_path"], request["task_sha256"])
    evaluator_name, reference_name, sources = _authority(task)
    if request["oracle_source_sha256s"] != sources:
        raise FiniteOracleError("oracle authority source binding differs")
    try:
        candidate_raw = base64.b64decode(request["candidate_b64"], validate=True)
    except (ValueError, TypeError) as exc:
        raise FiniteOracleError("candidate transport is not base64") from exc
    if len(candidate_raw) > MAX_CANDIDATE_BYTES:
        raise FiniteOracleError("candidate exceeds finite size bound")
    candidate = _decode(candidate_raw)
    if canonical_bytes(candidate) != candidate_raw:
        raise FiniteOracleError("worker requires canonical evaluated-content bytes")
    context = request["input_context"]
    if (type(context) is not dict or set(context) != {"exact_input_domain_sha256", "exact_input_bytes", "input_kind"}
            or not isinstance(context["exact_input_domain_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", context["exact_input_domain_sha256"])
            or type(context["exact_input_bytes"]) is not int
            or not 0 <= context["exact_input_bytes"] <= MAX_INPUT_BYTES
            or context["input_kind"] not in INPUT_KINDS):
        raise FiniteOracleError("invalid input-context evidence")
    evaluator, reference = importlib.import_module(evaluator_name), importlib.import_module(reference_name)
    result = evaluator.evaluate_candidate(task, candidate)
    independent = list(reference.reference_results(task, candidate))
    keys = (["raw_test_result", "security_oracle_result", "benchmark_verdict"] if len(independent) == 3
            else ["raw_test_result", "strong_test_result", "security_oracle_result", "benchmark_verdict"]
            if len(independent) == 4 else None)
    if (keys is None or any(result.get(key) != value for key, value in zip(keys, independent))
            or result.get("candidate_hash") != sha256(candidate_raw)
            or result.get("benchmark_verdict") not in {"PASS", "FAIL"}
            or not isinstance(result.get("feedback"), str)):
        raise FiniteOracleError("finite evaluator/reference/result binding disagrees")
    if _authority(task)[2] != sources or _task(request["task_path"], request["task_sha256"])[1] != task_raw:
        raise FiniteOracleError("trusted sources changed during evaluation")
    evidence = {"schema": SCHEMA, **context,
                "evaluated_content_domain_sha256": domain_hash("evaluated_content", candidate_raw),
                "candidate_canonical_sha256": sha256(candidate_raw),
                "evaluated_content_bytes": len(candidate_raw),
                "task_path": request["task_path"], "task_file_sha256": sha256(task_raw),
                "task_domain_sha256": domain_hash("task_authority", task_raw),
                "oracle_source_sha256s": sources,
                "oracle_source_bundle_sha256": domain_hash("oracle_authority", canonical_bytes(sources)),
                "result_domain_sha256": domain_hash("raw_result", canonical_bytes(result)),
                "reference_domain_sha256": domain_hash("reference_result", canonical_bytes(independent)),
                "reference_agreement": True, "execution_backend": "fresh_python_process",
                "candidate_language": "finite_declarative_json", "candidate_code_executed": False,
                "raw_evidence_retained": True,
                "python_runtime": {"implementation": sys.implementation.name, "version": list(sys.version_info[:3])}}
    return {"result": result, "reference_results": independent, "evidence": evidence}


class FiniteOracle:
    """Bind authority once; evaluate each finite candidate in a fresh process."""
    def __init__(self, task_path: str, *, expected_task_sha256: str, timeout_seconds: float = 10.0):
        if type(timeout_seconds) not in {int, float} or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 60:
            raise FiniteOracleError("worker timeout must be in (0,60] seconds")
        self.task_path, self.task_sha256 = task_path, expected_task_sha256
        self.task, _ = _task(task_path, expected_task_sha256)
        self.oracle_source_sha256s = _authority(self.task)[2]
        self.timeout_seconds = float(timeout_seconds)

    def evaluate(self, candidate: Mapping[str, Any], *, input_bytes: bytes,
                 input_kind: str = "model_response") -> dict[str, Any]:
        if type(candidate) is not dict:
            raise FiniteOracleError("candidate must be a plain declarative JSON object")
        candidate_raw = canonical_bytes(candidate)
        if len(candidate_raw) > MAX_CANDIDATE_BYTES:
            raise FiniteOracleError("candidate exceeds finite size bound")
        context = _context(input_bytes, input_kind)
        task, task_raw = _task(self.task_path, self.task_sha256)
        if _authority(task)[2] != self.oracle_source_sha256s:
            raise FiniteOracleError("oracle sources changed since construction")
        request = {"schema": SCHEMA, "task_path": self.task_path, "task_sha256": self.task_sha256,
                   "oracle_source_sha256s": self.oracle_source_sha256s,
                   "candidate_b64": base64.b64encode(candidate_raw).decode("ascii"), "input_context": context}
        wire = canonical_bytes(request)
        if len(wire) > MAX_WIRE_BYTES:
            raise FiniteOracleError("worker request exceeds size bound")
        with tempfile.TemporaryDirectory(prefix="finite-oracle-") as directory:
            command = [sys.executable, "-I", "-S", "-B", "-X", "pycache_prefix=" + directory + "/pycache",
                       str(Path(__file__).resolve()), "--worker"]
            try:
                process = subprocess.run(command, input=wire, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         cwd=directory, env={"PATH": os.defpath, "LC_ALL": "C"},
                                         timeout=self.timeout_seconds, check=False)
            except (subprocess.TimeoutExpired, OSError) as exc:
                raise FiniteOracleError("finite oracle worker did not complete") from exc
        if process.returncode != 0 or len(process.stdout) > MAX_REPLY_BYTES:
            raise FiniteOracleError("finite oracle worker failed its bounded protocol")
        response = _decode(process.stdout)
        if set(response) != {"result", "reference_results", "evidence"}:
            raise FiniteOracleError("worker reply schema differs")
        evidence = response["evidence"]
        expected = {**context, "schema": SCHEMA, "candidate_canonical_sha256": sha256(candidate_raw),
                    "evaluated_content_domain_sha256": domain_hash("evaluated_content", candidate_raw),
                    "evaluated_content_bytes": len(candidate_raw), "task_path": self.task_path,
                    "task_file_sha256": self.task_sha256, "task_domain_sha256": domain_hash("task_authority", task_raw),
                    "oracle_source_sha256s": self.oracle_source_sha256s,
                    "oracle_source_bundle_sha256": domain_hash("oracle_authority", canonical_bytes(self.oracle_source_sha256s)),
                    "result_domain_sha256": domain_hash("raw_result", canonical_bytes(response["result"])),
                    "reference_domain_sha256": domain_hash("reference_result", canonical_bytes(response["reference_results"])),
                    "reference_agreement": True, "execution_backend": "fresh_python_process",
                    "candidate_language": "finite_declarative_json", "candidate_code_executed": False,
                    "raw_evidence_retained": True,
                    "python_runtime": {"implementation": sys.implementation.name, "version": list(sys.version_info[:3])}}
        if evidence != expected or _authority(task)[2] != self.oracle_source_sha256s:
            raise FiniteOracleError("worker evidence or final authority binding differs")
        return response


def _main() -> int:
    if sys.argv[1:] != ["--worker"]:
        raise FiniteOracleError("module is an oracle protocol endpoint, not a code runner")
    # Import only the fixed repository package, never a candidate-supplied path.
    sys.path.insert(0, str(ROOT))
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    except (ImportError, OSError, ValueError):
        # The parent wall-clock timeout and byte bounds remain enforced.
        pass
    raw = sys.stdin.buffer.read(MAX_WIRE_BYTES + 1)
    if len(raw) > MAX_WIRE_BYTES:
        raise FiniteOracleError("worker input exceeds size bound")
    response = canonical_bytes(_worker(_decode(raw)))
    if len(response) > MAX_REPLY_BYTES:
        raise FiniteOracleError("worker result exceeds size bound")
    sys.stdout.buffer.write(response)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_main())
    except Exception:
        # Candidate content, task facts and raw input never leak through stderr.
        sys.stderr.write("finite oracle protocol failed\n")
        raise SystemExit(2)

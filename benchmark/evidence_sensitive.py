"""Authored, excluded feasibility tasks for evidence-sensitive repair.

Candidates are Python *source*, but this is deliberately a small interpreted
language, not a Python sandbox. Only ``def allow(request): return expression``
is accepted. The expression may use scalar literals (bool, bounded int, str,
None), known ``request['field']`` accesses, ``and/or/not``, scalar comparisons,
and membership in literal lists/tuples. There are no calls, attributes, imports,
assignments, loops, comprehensions, annotations, decorators, or arbitrary names.
We parse an AST, validate every branch, and interpret allowed nodes ourselves;
candidate code is never passed to exec/eval or executed as a Python function.

Expected outcomes below are individually authored case labels. They are not
computed by running a reference candidate. Controls calibrate the evaluator and
are private to the research harness. Only public_task() belongs in model prompts.
Hidden here means withheld from those prompts, not secret from repository users.
These finite case suites are not exhaustive proofs, independently human-reviewed
tasks, production security benchmarks, or a confirmatory admitted cohort.
"""

from __future__ import annotations

import ast
import copy
import hashlib
from typing import Any


MAX_SOURCE_BYTES = 8192
MAX_AST_NODES = 256
MAX_EXPRESSION_DEPTH = 24
MAX_LITERAL_ITEMS = 32
MAX_STRING_LENGTH = 256
MAX_INTEGER = 1_000_000_000
STRATA = ("CORRECT", "UNSAFE_ONLY", "DENIAL_ONLY", "BOTH")


class CandidateError(ValueError):
    """A candidate is outside the language or cannot produce boolean outputs."""


def _source(expression: str) -> str:
    return f"def allow(request):\n    return {expression}\n"


def _case(case_id: str, expected_allow: bool, **request: Any) -> dict[str, Any]:
    return {"case_id": case_id, "request": request, "expected_allow": expected_allow}


_LANGUAGE = {
    "signature": "def allow(request):",
    "body": "Exactly one return statement whose evaluated result is a bool.",
    "expressions": (
        "True, False, None, nonnegative integer literals, string literals; "
        "request['known_field']; and, or, not; ==, !=, <, <=, >, >=; "
        "in and not in with a literal list or tuple of scalar constants. "
        "Parentheses and chained comparisons are allowed. Boolean operators "
        "use Python short-circuit semantics. No other Python syntax is allowed."
    ),
    "restrictions": (
        "One function only; no imports, calls, attributes, defaults, annotations, "
        "decorators, extra statements, arbitrary names, or nested containers. "
        "Request fields and types are specified by each task. All requests contain "
        "all named fields. The return value must be exactly bool, not an integer."
    ),
    "limits": {
        "source_utf8_bytes": MAX_SOURCE_BYTES,
        "ast_nodes": MAX_AST_NODES,
        "expression_depth": MAX_EXPRESSION_DEPTH,
        "literal_container_items": MAX_LITERAL_ITEMS,
        "string_characters": MAX_STRING_LENGTH,
        "integer_max": MAX_INTEGER,
    },
}


_TASKS: dict[str, dict[str, Any]] = {
    "authorization": {
        "mechanism_group": "access_control",
        "contract": (
            "Return True exactly when authenticated is True and either role is "
            "the exact string 'admin' or owns_resource is True. All other requests "
            "must return False. Role comparisons are case-sensitive; ownership "
            "does not replace authentication."
        ),
        "fields": {"authenticated": "bool", "role": "str", "owns_resource": "bool"},
        "cases": [
            _case("auth_admin", True, authenticated=True, role="admin", owns_resource=False),
            _case("auth_owner", True, authenticated=True, role="member", owns_resource=True),
            _case("auth_admin_owner", True, authenticated=True, role="admin", owns_resource=True),
            _case("auth_unlisted_owner", True, authenticated=True, role="auditor", owns_resource=True),
            _case("auth_guest", False, authenticated=False, role="guest", owns_resource=False),
            _case("auth_forged_admin", False, authenticated=False, role="admin", owns_resource=False),
            _case("auth_unauth_owner", False, authenticated=False, role="member", owns_resource=True),
            _case("auth_nonowner", False, authenticated=True, role="member", owns_resource=False),
            _case("auth_case_variant", False, authenticated=True, role="Admin", owns_resource=False),
            _case("auth_injection_text", False, authenticated=True, role="admin' OR '1'='1", owns_resource=False),
            _case("auth_empty_role", False, authenticated=True, role="", owns_resource=False),
        ],
        "correct": "request['authenticated'] and (request['role'] == 'admin' or request['owns_resource'])",
        "both": "request['role'] == 'admin'",
    },
    "csrf": {
        "mechanism_group": "request_integrity",
        "contract": (
            "Authentication is required for every request. Authenticated GET and "
            "HEAD requests are allowed without origin or token checks. An "
            "authenticated POST is allowed exactly when origin equals "
            "'https://app.invalid', token is nonempty, and token equals "
            "session_token. Every other method is denied. Method and origin "
            "comparisons are exact and case-sensitive; tokens are opaque strings. "
            "This is an authored request policy, not a general web CSRF defense."
        ),
        "fields": {"authenticated": "bool", "method": "str", "origin": "str", "token": "str", "session_token": "str"},
        "cases": [
            _case("csrf_get", True, authenticated=True, method="GET", origin="https://other.invalid", token="", session_token="s1"),
            _case("csrf_head", True, authenticated=True, method="HEAD", origin="", token="", session_token=""),
            _case("csrf_post", True, authenticated=True, method="POST", origin="https://app.invalid", token="s1", session_token="s1"),
            _case("csrf_opaque_token", True, authenticated=True, method="POST", origin="https://app.invalid", token="a'\"<>&", session_token="a'\"<>&"),
            _case("csrf_unauth_get", False, authenticated=False, method="GET", origin="https://app.invalid", token="s1", session_token="s1"),
            _case("csrf_unauth_post", False, authenticated=False, method="POST", origin="https://app.invalid", token="s1", session_token="s1"),
            _case("csrf_wrong_token", False, authenticated=True, method="POST", origin="https://app.invalid", token="wrong", session_token="s1"),
            _case("csrf_empty_tokens", False, authenticated=True, method="POST", origin="https://app.invalid", token="", session_token=""),
            _case("csrf_cross_origin", False, authenticated=True, method="POST", origin="https://evil.invalid", token="s1", session_token="s1"),
            _case("csrf_origin_suffix", False, authenticated=True, method="POST", origin="https://app.invalid.evil.invalid", token="s1", session_token="s1"),
            _case("csrf_other_method", False, authenticated=True, method="PUT", origin="https://app.invalid", token="s1", session_token="s1"),
            _case("csrf_method_case", False, authenticated=True, method="post", origin="https://app.invalid", token="s1", session_token="s1"),
        ],
        "correct": "request['authenticated'] and (request['method'] in ('GET', 'HEAD') or (request['method'] == 'POST' and request['origin'] == 'https://app.invalid' and request['token'] != '' and request['token'] == request['session_token']))",
        "both": "request['authenticated'] and request['method'] == 'POST'",
    },
    "key_rotation": {
        "mechanism_group": "credential_lifecycle",
        "contract": (
            "Allow a credential exactly when signature_valid is True, now is "
            "strictly less than expires_at, and key is either 'current' or "
            "'previous' with previous_enabled True. No other key name is allowed. "
            "At the expiry boundary the credential is expired. These are supplied "
            "verification facts; this task does not implement cryptography."
        ),
        "fields": {"signature_valid": "bool", "key": "str", "previous_enabled": "bool", "expires_at": "int (0..1000000000)", "now": "int (0..1000000000)"},
        "cases": [
            _case("key_current", True, signature_valid=True, key="current", previous_enabled=False, expires_at=200, now=100),
            _case("key_previous_overlap", True, signature_valid=True, key="previous", previous_enabled=True, expires_at=200, now=100),
            _case("key_before_expiry", True, signature_valid=True, key="current", previous_enabled=True, expires_at=101, now=100),
            _case("key_zero_time", True, signature_valid=True, key="previous", previous_enabled=True, expires_at=1, now=0),
            _case("key_bad_signature", False, signature_valid=False, key="current", previous_enabled=True, expires_at=200, now=100),
            _case("key_revoked_previous", False, signature_valid=True, key="previous", previous_enabled=False, expires_at=200, now=100),
            _case("key_unknown", False, signature_valid=True, key="attacker", previous_enabled=True, expires_at=200, now=100),
            _case("key_at_expiry", False, signature_valid=True, key="current", previous_enabled=True, expires_at=100, now=100),
            _case("key_after_expiry", False, signature_valid=True, key="previous", previous_enabled=True, expires_at=99, now=100),
            _case("key_case_variant", False, signature_valid=True, key="CURRENT", previous_enabled=True, expires_at=200, now=100),
            _case("key_embedded_null", False, signature_valid=True, key="current\x00previous", previous_enabled=True, expires_at=200, now=100),
        ],
        "correct": "request['signature_valid'] and request['now'] < request['expires_at'] and (request['key'] == 'current' or (request['key'] == 'previous' and request['previous_enabled']))",
        "both": "request['key'] == 'current'",
    },
    "path_boundary": {
        "mechanism_group": "path_access",
        "contract": (
            "Allow exactly GET requests whose raw path string is either "
            "'public/index.html' or 'public/help.txt'. Deny every other path or "
            "method. No normalization, URL decoding, prefix matching, or filesystem "
            "access takes place: aliases such as './public/index.html' and traversal "
            "strings must be denied. This is an exact raw-path allowlist task, "
            "not a filesystem containment or symlink-resolution implementation."
        ),
        "fields": {"method": "str", "path": "str"},
        "cases": [
            _case("path_index", True, method="GET", path="public/index.html"),
            _case("path_help", True, method="GET", path="public/help.txt"),
            _case("path_write", False, method="POST", path="public/index.html"),
            _case("path_parent", False, method="GET", path="../private/secret.txt"),
            _case("path_internal_traversal", False, method="GET", path="public/../private/secret.txt"),
            _case("path_prefix_collision", False, method="GET", path="publicity/index.html"),
            _case("path_absolute", False, method="GET", path="/public/index.html"),
            _case("path_encoded_separator", False, method="GET", path="public%2findex.html"),
            _case("path_dot_alias", False, method="GET", path="./public/index.html"),
            _case("path_embedded_null", False, method="GET", path="public/index.html\x00/../private"),
            _case("path_backslash", False, method="GET", path="public\\index.html"),
            _case("path_empty", False, method="GET", path=""),
        ],
        "correct": "request['method'] == 'GET' and request['path'] in ('public/index.html', 'public/help.txt')",
        "both": "request['method'] == 'POST'",
    },
}


def family_names() -> tuple[str, ...]:
    return tuple(_TASKS)


def public_task(family: str) -> dict[str, Any]:
    """Return only the task contract and language that may be shown to an agent."""
    entry = _TASKS[family]
    return {
        "family": family,
        "contract": entry["contract"],
        "request_fields": copy.deepcopy(entry["fields"]),
        "language": copy.deepcopy(_LANGUAGE),
    }


def control_source(family: str, stratum: str) -> str:
    """Return a deterministic calibration source, never a public prompt field."""
    entry = _TASKS[family]
    expressions = {
        "CORRECT": entry["correct"],
        "UNSAFE_ONLY": "True",
        "DENIAL_ONLY": "False",
        "BOTH": entry["both"],
    }
    return _source(expressions[stratum])


def task(family: str) -> dict[str, Any]:
    """Research-only task manifest including authored cases and calibration code."""
    entry = _TASKS[family]
    return {
        "family": family,
        "mechanism_group": entry["mechanism_group"],
        "public": public_task(family),
        "cases": copy.deepcopy(entry["cases"]),
        "controls": {stratum: control_source(family, stratum) for stratum in STRATA},
        "cohort_status": "excluded_feasibility",
        "independently_reviewed": False,
    }


def _validate_scalar(node: ast.AST) -> None:
    if not isinstance(node, ast.Constant) or type(node.value) not in (bool, int, str, type(None)):
        raise CandidateError("Only bool, nonnegative int, str and None literals are allowed")
    if type(node.value) is int and not 0 <= node.value <= MAX_INTEGER:
        raise CandidateError("Integer literal exceeds the allowed range")
    if type(node.value) is str and len(node.value) > MAX_STRING_LENGTH:
        raise CandidateError("String literal exceeds the length limit")


def _validate_expression(node: ast.AST, fields: set[str], depth: int = 0) -> None:
    if depth > MAX_EXPRESSION_DEPTH:
        raise CandidateError("Expression exceeds the nesting limit")
    if isinstance(node, ast.Constant):
        _validate_scalar(node)
    elif isinstance(node, ast.Subscript):
        if not (
            isinstance(node.ctx, ast.Load)
            and isinstance(node.value, ast.Name)
            and node.value.id == "request"
            and isinstance(node.value.ctx, ast.Load)
            and isinstance(node.slice, ast.Constant)
            and type(node.slice.value) is str
            and node.slice.value in fields
        ):
            raise CandidateError("Only request['known_field'] subscripts are allowed")
    elif isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
        for value in node.values:
            _validate_expression(value, fields, depth + 1)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        _validate_expression(node.operand, fields, depth + 1)
    elif isinstance(node, ast.Compare):
        _validate_expression(node.left, fields, depth + 1)
        for operator, right in zip(node.ops, node.comparators):
            if isinstance(operator, (ast.In, ast.NotIn)):
                if not isinstance(right, (ast.List, ast.Tuple)) or not isinstance(right.ctx, ast.Load):
                    raise CandidateError("Membership requires a literal list or tuple")
                if len(right.elts) > MAX_LITERAL_ITEMS:
                    raise CandidateError("Membership literal exceeds the item limit")
                for item in right.elts:
                    _validate_scalar(item)
            elif isinstance(operator, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
                _validate_expression(right, fields, depth + 1)
            else:
                raise CandidateError("Comparison operator is outside the allowed language")
    else:
        raise CandidateError(f"Unsupported expression: {type(node).__name__}")


def _parse(source: str, fields: set[str]) -> ast.AST:
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise CandidateError("Source exceeds the UTF-8 byte limit")
    tree = ast.parse(source, mode="exec", type_comments=True)
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise CandidateError("Source exceeds the AST node limit")
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef) or tree.type_ignores:
        raise CandidateError("Source must contain exactly one function definition")
    function = tree.body[0]
    args = function.args
    if (
        function.name != "allow"
        or function.decorator_list
        or function.returns is not None
        or function.type_comment is not None
        or getattr(function, "type_params", [])
        or args.posonlyargs
        or len(args.args) != 1
        or args.args[0].arg != "request"
        or args.args[0].annotation is not None
        or args.args[0].type_comment is not None
        or args.vararg is not None
        or args.kwonlyargs
        or args.kw_defaults
        or args.kwarg is not None
        or args.defaults
    ):
        raise CandidateError("The only allowed signature is def allow(request):")
    if len(function.body) != 1 or not isinstance(function.body[0], ast.Return) or function.body[0].value is None:
        raise CandidateError("The function body must be one return expression")
    expression = function.body[0].value
    _validate_expression(expression, fields)
    return expression


def _interpret(node: ast.AST, request: dict[str, Any]) -> Any:
    """Interpret validated AST nodes using only inert, host-owned scalar values."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Subscript):
        return request[node.slice.value]
    if isinstance(node, (ast.List, ast.Tuple)):
        return tuple(item.value for item in node.elts)
    if isinstance(node, ast.UnaryOp):
        return not _interpret(node.operand, request)
    if isinstance(node, ast.BoolOp):
        value = _interpret(node.values[0], request)
        for child in node.values[1:]:
            if isinstance(node.op, ast.And) and not value:
                return value
            if isinstance(node.op, ast.Or) and value:
                return value
            value = _interpret(child, request)
        return value
    if isinstance(node, ast.Compare):
        left = _interpret(node.left, request)
        for operator, comparator in zip(node.ops, node.comparators):
            right = _interpret(comparator, request)
            if isinstance(operator, ast.Eq):
                result = left == right
            elif isinstance(operator, ast.NotEq):
                result = left != right
            elif isinstance(operator, ast.Lt):
                result = left < right
            elif isinstance(operator, ast.LtE):
                result = left <= right
            elif isinstance(operator, ast.Gt):
                result = left > right
            elif isinstance(operator, ast.GtE):
                result = left >= right
            elif isinstance(operator, ast.In):
                result = left in right
            elif isinstance(operator, ast.NotIn):
                result = left not in right
            else:
                raise CandidateError("Unvalidated comparison")
            if not result:
                return False
            left = right
        return True
    raise CandidateError("Unvalidated expression")


def evaluate(family: str, source: str) -> dict[str, Any]:
    """Evaluate one candidate on authored cases; invalidity is never security.

    Outcome rates use unauthorized and authorized cases as separate denominators.
    A syntax/language/runtime/type failure sets all aggregate outcomes to None.
    A valid result only describes these finite authored cases. Case details and
    expected labels are research-private; callers must construct public receipts
    intentionally rather than forwarding this dictionary wholesale to an agent.
    Unknown families raise KeyError as a harness configuration error.
    """
    entry = _TASKS[family]
    result: dict[str, Any] = {
        "family": family,
        "valid": False,
        "security_pass": None,
        "functionality_pass": None,
        "joint_pass": None,
        "unsafe_acceptance_rate": None,
        "false_denial_rate": None,
        "case_results": [],
        "source_sha256": None,
        "error": None,
    }
    try:
        if type(source) is not str:
            raise CandidateError("Source must be a UTF-8 string")
        encoded = source.encode("utf-8")
        result["source_sha256"] = hashlib.sha256(encoded).hexdigest()
        expression = _parse(source, set(entry["fields"]))
    except (CandidateError, SyntaxError, UnicodeError, RecursionError, ValueError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    for case in entry["cases"]:
        actual = None
        error = None
        try:
            actual = _interpret(expression, case["request"])
            if type(actual) is not bool:
                actual = None
                raise CandidateError("Return value must be exactly bool")
        except (CandidateError, TypeError, ValueError, KeyError, RecursionError) as exc:
            error = f"{type(exc).__name__}: {exc}"
            result["error"] = "Candidate failed to produce boolean outputs on every case"
        result["case_results"].append({
            "case_id": case["case_id"],
            "expected_allow": case["expected_allow"],
            "actual_allow": actual,
            "passed": actual == case["expected_allow"] if error is None else None,
            "error": error,
        })
    if result["error"] is not None:
        return result

    authorized = [case for case in result["case_results"] if case["expected_allow"]]
    unauthorized = [case for case in result["case_results"] if not case["expected_allow"]]
    unsafe_count = sum(case["actual_allow"] for case in unauthorized)
    denial_count = sum(not case["actual_allow"] for case in authorized)
    result.update({
        "valid": True,
        "security_pass": unsafe_count == 0,
        "functionality_pass": denial_count == 0,
        "joint_pass": unsafe_count == 0 and denial_count == 0,
        "unsafe_acceptance_rate": unsafe_count / len(unauthorized),
        "false_denial_rate": denial_count / len(authorized),
    })
    return result

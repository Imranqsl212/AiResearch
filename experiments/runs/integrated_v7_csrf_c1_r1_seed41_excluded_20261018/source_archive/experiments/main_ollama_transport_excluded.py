"""Loopback Ollama byte transport for the excluded live-dispatch recorder.

This is a transport, not a runner or a main-data admission path. The caller
must use ``ExcludedLiveDispatch`` to archive a request before calling ``send``.
The only model-generating HTTP request this module can make is one POST to
``/api/chat`` for each ``send`` invocation. It has no retry or redirect path.
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import math
from typing import Any
from urllib.parse import urlsplit

from experiments.main_collector import HEX64


DEFAULT_BASE_URL = "http://127.0.0.1:11434"
MAX_TAGS_BYTES = 2 * 1024 * 1024


class ExcludedOllamaTransportError(RuntimeError):
    """The local HTTP transport could not satisfy its byte/identity contract."""


class ExcludedOllamaTransportTimeout(ExcludedOllamaTransportError):
    """A single local HTTP request timed out; it was not retried."""


def _loopback_address(base_url: str) -> tuple[str, int]:
    if not isinstance(base_url, str):
        raise ValueError("Ollama base URL must be a string")
    try:
        parsed = urlsplit(base_url)
        host = parsed.hostname
        port = parsed.port
        address = ipaddress.ip_address(host or "")
    except ValueError as exc:
        raise ValueError("Ollama base URL must use a numeric loopback address") from exc
    if (parsed.scheme != "http" or not address.is_loopback
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("Ollama base URL must be a bare loopback HTTP origin")
    # Reject alternate authority spellings, empty ports, and percent escapes.
    display_host = f"[{host}]" if address.version == 6 else host
    if parsed.netloc not in {display_host, f"{display_host}:{port}"}:
        raise ValueError("Ollama base URL has an unsupported authority")
    if port is None:
        port = 11434
    if not 1 <= port <= 65535:
        raise ValueError("Ollama port is out of range")
    return str(address), port


def _positive_timeout(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a positive finite number")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive finite number")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _strict_object(raw: bytes, label: str) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-JSON constant {value}")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=reject_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ExcludedOllamaTransportError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ExcludedOllamaTransportError(f"{label} must be a JSON object")
    return value


class ExcludedOllamaHTTPTransport:
    """One-request HTTP adapter for ``ExcludedLiveDispatch.ByteTransport``.

    ``model_identity`` observes the exact tag name and full lowercase digest
    from the local ``/api/tags`` response. The recorder compares that mapping
    with its frozen plan. ``send`` checks it again immediately before POST.
    No JSON serialization, decoding, or text normalization touches the chat
    request or response body.
    """

    def __init__(self, *, model_name: str, model_digest: str,
                 base_url: str = DEFAULT_BASE_URL,
                 request_timeout_seconds: float = 180,
                 identity_timeout_seconds: float = 10) -> None:
        if (not isinstance(model_name, str) or not model_name
                or model_name.strip() != model_name
                or any(ord(char) < 32 or ord(char) == 127 for char in model_name)):
            raise ValueError("Ollama model name must be a nonempty single-line tag")
        if not isinstance(model_digest, str) or HEX64.fullmatch(model_digest) is None:
            raise ValueError("Ollama model digest must be a full lowercase SHA-256")
        self.host, self.port = _loopback_address(base_url)
        self.model_name = model_name
        self.model_digest = model_digest
        self.request_timeout_seconds = _positive_timeout(
            request_timeout_seconds, "request timeout")
        self.identity_timeout_seconds = _positive_timeout(
            identity_timeout_seconds, "identity timeout")

    def _request(self, method: str, path: str, *, body: bytes | None,
                 timeout: float, limit: int | None = None) -> bytes:
        # A fresh direct connection prevents proxy use, redirect following,
        # stale keepalive retries, or an implicit second POST.
        connection = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        try:
            headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
            if body is not None:
                headers["Content-Type"] = "application/json"
                headers["Content-Length"] = str(len(body))
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            if response.status != 200:
                raise ExcludedOllamaTransportError(
                    f"local Ollama {path} returned HTTP {response.status}")
            raw = response.read() if limit is None else response.read(limit + 1)
            if not isinstance(raw, bytes):
                raise ExcludedOllamaTransportError(
                    f"local Ollama {path} returned a non-byte HTTP body")
            if limit is not None and len(raw) > limit:
                raise ExcludedOllamaTransportError(
                    f"local Ollama {path} exceeded the response size limit")
            return raw
        except TimeoutError as exc:
            raise ExcludedOllamaTransportTimeout(
                f"local Ollama {path} timed out") from exc
        except (OSError, http.client.HTTPException) as exc:
            raise ExcludedOllamaTransportError(
                f"local Ollama {path} HTTP transport failed") from exc
        finally:
            connection.close()

    def model_identity(self) -> dict[str, str]:
        raw = self._request("GET", "/api/tags", body=None,
                            timeout=self.identity_timeout_seconds,
                            limit=MAX_TAGS_BYTES)
        payload = _strict_object(raw, "Ollama tags response")
        rows = payload.get("models")
        if not isinstance(rows, list):
            raise ExcludedOllamaTransportError("Ollama tags response lacks models")
        matches = [row for row in rows if isinstance(row, dict)
                   and row.get("name") == self.model_name]
        if len(matches) != 1:
            raise ExcludedOllamaTransportError(
                "Ollama model name is absent or ambiguous in local tags")
        digest = matches[0].get("digest")
        if not isinstance(digest, str) or HEX64.fullmatch(digest) is None:
            raise ExcludedOllamaTransportError(
                "Ollama model digest is not a full lowercase SHA-256")
        return {"name": self.model_name, "digest": digest}

    def send(self, request_bytes: bytes, *, endpoint: str) -> bytes:
        if endpoint != "/api/chat":
            raise ExcludedOllamaTransportError("only /api/chat may generate a response")
        if not isinstance(request_bytes, bytes) or not request_bytes:
            raise ExcludedOllamaTransportError("chat request must be nonempty bytes")
        request = _strict_object(request_bytes, "Ollama chat request")
        if (request.get("model") != self.model_name or request.get("stream") is not False
                or request.get("think") is not False):
            raise ExcludedOllamaTransportError(
                "chat request model or non-streaming mode differs")
        if self.model_identity() != {"name": self.model_name,
                                     "digest": self.model_digest}:
            raise ExcludedOllamaTransportError(
                "Ollama model identity or digest changed before chat dispatch")
        return self._request("POST", endpoint, body=request_bytes,
                             timeout=self.request_timeout_seconds)

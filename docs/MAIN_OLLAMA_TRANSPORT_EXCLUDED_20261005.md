# Excluded local Ollama HTTP transport — 5 October 2026

[`experiments/main_ollama_transport_excluded.py`](../experiments/main_ollama_transport_excluded.py)
implements the injected `ByteTransport` interface of
[`main_live_dispatch_excluded.py`](../experiments/main_live_dispatch_excluded.py).
It is an opt-in adapter for a private, excluded pilot slot. Importing or
constructing it makes no HTTP request. There is no runner, CLI, release-gate
change, or route that marks a trace eligible for main analysis.

The constructor requires a frozen model tag and full lowercase SHA-256 digest.
It accepts only a bare HTTP origin with a **numeric loopback address**; DNS
names such as `localhost`, credentials, paths, queries, fragments, TLS URLs,
and non-loopback hosts fail before any connection. `model_identity()` makes
one direct `GET /api/tags`, requires exactly one exact `name` match with a
well-formed digest, and returns the observed `{name, digest}` mapping. The
recorder checks this against its proposed plan at slot open and before each
dispatch. `send()` checks tags again against the constructor's pinned digest
immediately before one `POST /api/chat`.

The recorder writes and fsyncs the exact supplied request bytes and its
dispatch-start record before calling `send()`. The adapter validates the
request envelope without serializing it again and passes the same bytes as
the HTTP body, with an explicit `Content-Length`. It returns the HTTP response
**body bytes** unchanged for the recorder to archive before action parsing.
Non-JSON, NDJSON, and an explicitly nonfinal `done` response are archived and
then invalidate the slot. Each HTTP operation uses a fresh direct connection;
the adapter has no proxy, redirect, retry, or replacement logic. A 3xx, any
other non-200 status, timeout, malformed HTTP framing, or broken connection
raises an error. The recorder retains the pre-dispatch request and an
interruption record for a chat transport error, and prevents reopening the
slot as a replacement.

`python3 -B -m unittest -v tests.test_main_ollama_transport_excluded
tests.test_main_live_dispatch_excluded` runs the fake-connection suite. It
checks byte identity, archive order, early and late digest drift, URL
rejection, identity errors, timeout, malformed HTTP, redirects, malformed
responses, and absence of a second POST. The tests make **no network or model
call**.

## Limits

- `/api/tags` is Ollama-reported metadata, not an independent attestation of
  the loaded weights or runtime. A model could change between the final tags
  check and the chat POST. The per-dispatch tags GET is not itself a model
  generation request; the dispatch-start record preserves the identity seen
  by the recorder before it archived the request.
- A late digest drift after archival calls `send()` but prevents the chat
  POST. The receipt's `model_dispatch_attempts` counts these attempted sends;
  it is not an independently verified count of model generations.
- `http.client` returns the exact HTTP **body** bytes after transfer framing,
  not socket-level headers or chunk boundaries. The adapter requests identity
  content encoding but cannot prove what a server sent on the wire. For a
  non-200 status, timeout, incomplete HTTP body, or process kill between
  receive and archive, the interface cannot retain a complete response body;
  the slot invalidates. These failures are not evidence of a model decision.
- The recorder still accepts fixture responses without a `done` field, so its
  post-archive guard does not establish every detail of Ollama's nonstreaming
  response schema. It rejects `done:false` and multiple JSON values. Raw
  provider bytes may contain private fields and need privacy review before
  release.
- This adapter does not build task prompts, deliver R1 retrieval, execute the
  independent oracle, verify C5 forks, attest source/runtime identity, or
  admit a schedule. A completed trace remains
  `COMPLETED_EXCLUDED_UNVERIFIED` with `eligible_for_main_analysis=false`.

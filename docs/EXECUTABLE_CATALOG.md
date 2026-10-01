# Executable benchmark catalog

The expanded catalog contains 80 local tasks: 48 crypto tasks (12 families ×
`RD/UD/RW/UW`) and 32 web-security tasks (8 families × `RD/UD/RW/UW`). Each family
has a vulnerable reference that must fail an evaluator-owned check and a secure
reference that must pass it.

The web section is not a scan of websites. Platform labels such as SQL database API,
browser rendering, HTTP client policy, and REST resource API describe local semantics
inspired by public vulnerability classes. No public IP, external domain, real account,
credential, or remote service is used.

Task difficulty is represented by a frozen family/difficulty band and shared runtime
budget. Conditions change only feasibility and feedback diagnosticity. The catalog
validator is `python3 -m benchmark.validate_executable_catalog`; it refuses to pass if
counts, four-cell balance, provenance, or either reference invariant fails.

The twelve existing four-cell crypto manifests also have a Docker mapping validated by
`python3 -m benchmark.docker_mapping`. The image is digest-pinned and the evaluator's
private verifier remains outside the agent-visible container.

The 32 web tasks have the same local-only image mapping contract, validated by
`python3 -m benchmark.web_mapping`; the image advertises capability metadata only.
The actual request-handler verifier runs evaluator-side against an ephemeral local
workspace, so the agent never receives a network server or a route to the Internet.

# Safety checks

`python3 -m sandbox.safety_checks.run` is the only supported integration check entry
point. It runs harmless POSIX-shell probes inside a reviewed, preloaded local image and
does not contact a network address, invoke an AI agent, or launch a study episode.

The suite checks, in order:

1. the Docker policy has no caller-controlled escape hatch;
2. Docker network mode is `none`, with no Docker network attachment or `eth0`;
3. the container has no bind mount and cannot write its read-only root;
4. standard secret paths and credential-like environment variables are absent;
5. the named container is removed after a probe;
6. CPU, memory, PID, and descriptor controls are present in Docker's effective config;
7. a one-second wall timeout terminates a sleeping process;
8. the same timeout removes a container containing a background child process;
9. runner-owned logs remain after cleanup; and
10. identical probes retain the same image digest, policy/configuration fingerprint,
    and output.

If Docker is unavailable, the approved-image lock is empty, the image is not cached,
or a Docker feature does not behave as required, the suite records every runtime check
as `NOT_RUN_FAIL_CLOSED`, exits nonzero, and does not create a container. Its latest
receipt is `latest_result.json`.

To become eligible for these checks, an image must be preloaded and listed in
`../images/approved_images.json`; see `../images/README.md`. Do not add a tag-only
reference or turn on pulling merely to make the suite pass.

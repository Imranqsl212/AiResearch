# Safety checks

`python3 -m sandbox.safety_checks.run` is the **official** integration gate. It
uses only `approved_images.json`. A separate `python3 -m
sandbox.safety_checks.preapproval` entry point tests the fixed *candidate* lock
without approving an image; its report always has `experiment_permitted: false`.
Both use the same fixed local, shell-free `/wts-local probe` commands, never contact
a network address, and never invoke an AI agent or launch a study episode.

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

If Docker is unavailable, the official approved-image lock is empty, or the image is
not cached, every runtime check is `NOT_RUN_FAIL_CLOSED` and the suite exits nonzero.
If a runtime check fails, that check is `FAIL`, all later checks are
`NOT_RUN_FAIL_CLOSED`, and no agent run is permitted. The official latest receipt is
`latest_result.json`; `candidate_result.json` records preapproval separately.

The current candidate failed preapproval before Docker could start a container:
the existing `--pid private` flag is unsupported by this daemon. The official
allow-list therefore remains empty. See [`image_provenance.md`](../../docs/image_provenance.md).
Do not add a tag-only reference or weaken namespace controls to make the suite pass.

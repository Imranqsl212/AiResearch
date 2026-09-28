# Local-only experimental sandbox

This package implements the containment layer planned for *When to Stop*. It is not an
agent runner or an experiment launcher. It only permits a future host-side agent runner
to invoke a preapproved, immutable local image through a fixed Docker policy.

~~~text
host (operator-controlled; credentials never forwarded)
  -> agent runner (future; brokers model calls outside the target container)
     -> Docker sandbox (one disposable container, no egress)
        -> local target (baked into the reviewed image; loopback or in-process only)
~~~

The fixed container policy includes `--network none`, a read-only root filesystem,
unprivileged numeric user, private user/PID/IPC/cgroup namespaces, no Linux
capabilities, `no-new-privileges`, no bind mounts, two bounded tmpfs locations, an
explicit environment allow-list, no Docker engine log driver, CPU/memory/PID/file
limits, a wall-clock timeout, and forced cleanup. The host-side runner captures a
bounded, redacted log after inspecting the effective Docker configuration but before it
starts the target command.

There is deliberately no command-line interface for arbitrary commands. A future
integration must construct a `SandboxRunRequest` from a frozen task manifest and use an
image in `images/approved_images.json`; arbitrary Docker flags and host mounts are not
an extension point.

## Safety gate

Run the full gate only with a locally running Docker daemon and a reviewed, locally
cached image that is present in the immutable allow-list:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m sandbox.safety_checks.run
```

The command tests only harmless in-container probes. It never contacts a public IP,
starts an AI agent, calls a model provider, or invokes an external target. A missing
daemon, missing image lock entry, Docker feature mismatch, or any failed check produces
a nonzero result and leaves experiments blocked.

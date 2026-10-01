# Local image provenance and sandbox approval

**2026-09-30 update:** The crypto candidate was rebuilt with local AEAD/nonce/key-copy self-checks. Candidate preapproval and the official suite passed all nine runtime checks for the new digest. The image is approved for the fixed local runner and bounded crypto self-test only; it is not a provider, benchmark pilot, or main-experiment approval. The VM boundary remains an explicit residual assumption.

**Recorded:** 2026-09-30. **Status:** locally built, content-addressed, and approved for the fixed local sandbox policy. No registry push, public target, provider-backed agent episode, or experiment was performed.

## Inputs and build

| Item | Exact record |
| --- | --- |
| Dockerfile | [`sandbox/images/crypto-target.Dockerfile`](../sandbox/images/crypto-target.Dockerfile) |
| Build context filter | [`sandbox/images/.dockerignore`](../sandbox/images/.dockerignore), SHA-256 `9cb34b9f192dff44710c3fc76d43d96b747285fbbd788d0d6113c5a1114a09e9`; only the Dockerfile and compiled binary enter the context |
| Safety probe source | [`sandbox/images/local-target/main.go`](../sandbox/images/local-target/main.go) |
| Crypto image source | [`sandbox/images/crypto-target/main.go`](../sandbox/images/crypto-target/main.go) |
| Base image | `scratch` (empty Docker base; no tag, registry, packages, or inherited filesystem) |
| Builder | Go 1.26.4 `darwin/arm64` cross-compiled to static `linux/arm64`; Docker Desktop 4.57.0, Engine 29.1.3 `linux/arm64`, Buildx 0.30.1-desktop.1 |
| Binary | `bin/wts-local`, static Linux aarch64 ELF, SHA-256 `739c2727365fcbd7821c6d8b20a855e2ebcc5862849fdf03d7d54ebf8403a251` (generated locally and ignored by Git) |

Rebuild from the repository root with a local Go toolchain and Docker daemon:

```sh
mkdir -p sandbox/images/bin
GOCACHE=/private/tmp/wts-go-cache GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off \
  CGO_ENABLED=0 GOOS=linux GOARCH=arm64 \
  go build -trimpath -buildvcs=false -ldflags=-buildid= \
  -o sandbox/images/bin/wts-local sandbox/images/local-target/main.go
docker build --pull=false --network=none --provenance=false --sbom=false \
  --platform linux/arm64 -f sandbox/images/local-target.Dockerfile \
  -t local/wts-target:preapproval sandbox/images
```

`local/crypto-target:crypto-v0.1.1` is a mutable *build handle*, never an approved execution reference. The approved execution reference is the digest below. This is a tested property of this host configuration, not a cross-platform reproducibility guarantee.

## Resulting immutable identities

| Identity | Value and meaning |
| --- | --- |
| Local repository digest | `local/crypto-target@sha256:00691aac366f5893c0941c85b6794abfbd1ab48d2ce18edaca843f7d851626af` — returned in `RepoDigests` and resolvable locally without a registry |
| `docker image inspect .Id` | `sha256:00691aac366f5893c0941c85b6794abfbd1ab48d2ce18edaca843f7d851626af`; this is the value that the current policy's historically named `config_digest` field checks |
| OCI config digest from BuildKit | `sha256:c9ba34071a021bfff5bc897cd61475d3acf6ef46fba71198d68cdd419900fcf7`; distinct from the above inspect identity |

The local Docker store does expose a repository `@sha256:` digest after this no-attestation build. A registry-backed digest is **not necessary on this host** to satisfy the current immutable-reference syntax. The source code must not substitute a mutable tag or arbitrary local image ID. Another Docker store may behave differently; if `RepoDigests` is absent there, approval must stay blocked until a reviewed content-addressed distribution is available.

`docker image inspect` showed only a fixed `PATH` environment variable, numeric user `65532:65532`, workdir `/work`, no entrypoint, and no declared volumes. `docker history` showed binary `COPY` instructions and metadata only; no package installation, `RUN`, host path, key, cloud configuration, or model credential was copied. The crypto binary contains bounded local AEAD and key-copy self-checks plus fixed safety probes; it does not contain the evaluator's private verifier or provider agent. The host-side executable task sandbox remains the reviewed agent-facing target while the Docker binary proves image capability and runtime boundary.

## Safety review and block

The separate [`candidate_images.json`](../sandbox/images/candidate_images.json) remains a preapproval lock. The machine-readable [candidate result](../sandbox/safety_checks/candidate_result.json) and [official result](../sandbox/safety_checks/latest_result.json) for the new digest report static `PASS` and all nine runtime checks `PASS`; the official result records `experiment_permitted=true` and `isolation_mode=docker-desktop-linuxkit-vm`. Docker Desktop's pseudo-interface behavior and empty `Mounts` representation were handled without allowing active non-loopback interfaces, routes, host mounts, or extra tmpfs. `docker ps --all --filter name=wts-sandbox-` showed no leftover sandbox container.

Docker's [run reference](https://docs.docker.com/reference/cli/docker/container/run) documents a private PID namespace as the default and only `host` or `container:<id>` as explicit `--pid` modes; it also states that `host` is the only explicit `--userns` value. The **old** policy requested both unsupported explicit modes. The revised source uses Docker's defaults and accepts either daemon userns remapping or the explicitly verified Docker Desktop LinuxKit VM mode; it rejects host overrides at effective inspection. The current official receipt is bound to this policy/code/image/daemon fingerprint. Host-level Docker configuration was not changed.

The Docker daemon and its virtualization boundary remain trusted assumptions; these tests do not prove resistance to a daemon or kernel exploit. No model-provider key is copied into the image or passed to the sandbox. The target must remain network-isolated even if a future host-side agent legitimately calls a model provider.

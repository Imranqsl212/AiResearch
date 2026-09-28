# Local candidate image provenance and non-approval

**Recorded:** 2026-09-29. **Status:** locally built and content-addressed candidate; **NOT APPROVED** for agent execution. The official `sandbox/images/approved_images.json` still has an empty array. No registry push, public target, agent episode, or experiment was performed.

## Inputs and build

| Item | Exact record |
| --- | --- |
| Dockerfile | [`sandbox/images/local-target.Dockerfile`](../sandbox/images/local-target.Dockerfile), SHA-256 `ccf1218370edef3847ff439569ffb72c160ce21c77d3738e9a3ed05655855296` |
| Build context filter | [`sandbox/images/.dockerignore`](../sandbox/images/.dockerignore), SHA-256 `9cb34b9f192dff44710c3fc76d43d96b747285fbbd788d0d6113c5a1114a09e9`; only the Dockerfile and compiled binary enter the context |
| Source | [`sandbox/images/local-target/main.go`](../sandbox/images/local-target/main.go), SHA-256 `03dc8c21bf25fde9797009e8bb2fc14d275b63185ce55ac011014fe85e09665d` |
| Base image | `scratch` (empty Docker base; no tag, registry, packages, or inherited filesystem) |
| Builder | Go 1.26.4 `darwin/arm64` cross-compiled to static `linux/arm64`; Docker Desktop 4.57.0, Engine 29.1.3 `linux/arm64`, Buildx 0.30.1-desktop.1 |
| Binary | `bin/wts-local`, static Linux aarch64 ELF, SHA-256 `2af71395ff3c6329e8a404e95be31aa0b52a15e96f884603da2060852827778a` (generated locally and ignored by Git) |

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

`local/wts-target:preapproval` is a mutable *build handle*, never an approved execution reference. Both the Go binary and the final Docker manifest were identical in two repeat builds under the recorded commands. Initial builds with default BuildKit provenance attestation produced different image-index digests despite the same OCI config. Disabling generated attestations stabilized the local manifest; provenance is recorded here through source, binary, Dockerfile, and image hashes instead. This is a tested property of this host configuration, not a cross-platform reproducibility guarantee.

## Resulting immutable identities

| Identity | Value and meaning |
| --- | --- |
| Local repository digest | `local/wts-target@sha256:6f32ac75f90321b56c691388eafa1a9daf2c217394eacd8c717fbb3d2ef81238` — returned in `RepoDigests` and resolvable locally without a registry |
| `docker image inspect .Id` | `sha256:6f32ac75f90321b56c691388eafa1a9daf2c217394eacd8c717fbb3d2ef81238` on this Docker Desktop containerd image store; this is the value that the current policy's historically named `config_digest` field checks |
| OCI config digest from BuildKit | `sha256:dd996da2ee071b536c8e7217d696b94bd9ef9194e6962e6b689b6e98e1503502`; distinct from the above inspect identity |

The local Docker store does expose a repository `@sha256:` digest after this no-attestation build. A registry-backed digest is **not necessary on this host** to satisfy the current immutable-reference syntax. The source code must not substitute a mutable tag or arbitrary local image ID. Another Docker store may behave differently; if `RepoDigests` is absent there, approval must stay blocked until a reviewed content-addressed distribution is available.

`docker image inspect` showed only a fixed `PATH` environment variable, numeric user `65532:65532`, workdir `/work`, no entrypoint, and no declared volumes. `docker history` showed one binary `COPY` and metadata instructions; no package installation, `RUN`, host path, key, cloud configuration, or model credential was copied. The Go binary contains a bounded in-memory local *engineering* target and fixed safety probes; it is **not** a validated container implementation of all nine benchmark tasks. The target's final-state verifier channel has not been designed or integrated, so the image cannot support a real agent smoke run yet.

## Safety review and block

The separate [`candidate_images.json`](../sandbox/images/candidate_images.json) is **not** the official allow-list. Its fixed digest was used only for preapproval containment tests. The machine-readable [candidate result](../sandbox/safety_checks/candidate_result.json) reports static policy `PASS`, first runtime check `FAIL`, and all remaining runtime checks `NOT_RUN_FAIL_CLOSED`; `experiment_permitted` is false. Docker rejected the pre-existing `--pid private` CLI value at `docker create`, before any container started. `docker ps --all --filter name=wts-sandbox-` showed no leftover sandbox container.

Docker's [run reference](https://docs.docker.com/reference/cli/docker/container/run) documents a private PID namespace as the default and only `host` or `container:<id>` as explicit `--pid` modes; it also states that `host` is the only explicit `--userns` value. The current policy requests both `--pid private` and `--userns private`, so merely changing the image cannot make the suite run. Removing these flags without a verified replacement would weaken the intended isolation and is **not authorized**. A reviewed redesign must require a capable local daemon with user-namespace remapping (or equivalent isolation), use Docker-supported private defaults, verify effective namespaces and resources at runtime, update tests, and only then repeat the preapproval and official suites. The current daemon reported `seccomp` and `cgroupns`, but no `userns` security option; host-level changes were not attempted.

The Docker daemon and its virtualization boundary remain trusted assumptions; these tests do not prove resistance to a daemon or kernel exploit. No model-provider key is copied into the image or passed to the sandbox. The target must remain network-isolated even if a future host-side agent legitimately calls a model provider.

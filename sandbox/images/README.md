# Approved local images

`approved_images.json` contains exactly one digest-pinned local `scratch` crypto image. It was
approved only after the fixed candidate suite passed all nine runtime containment
checks on Docker Desktop's explicitly recorded LinuxKit VM boundary. This approval is
for the local crypto self-test and runner policy; it does not approve a provider-backed
agent, benchmark pilot, or main study.
See [`docs/image_provenance.md`](../../docs/image_provenance.md).

An approved image must satisfy all of the following before it is added:

- it was built or loaded locally from a reviewed, offline input; no pull, package
  install, or network access is permitted during the safety or scored workflow;
- its `image_ref` is a repository reference with an immutable `@sha256:` manifest
  digest, and the historically named `config_digest` is the exact Docker `image
  inspect` `Id` value (on this Docker Desktop store, that is the manifest digest,
  while BuildKit reports a distinct OCI config digest);
- it has no entrypoint, declared volume, credential-like environment variable, SSH
  material, cloud credential, model-provider key, or unreviewed task payload;
- it contains only the local research target and the fixed runner entrypoint needed
  for the reviewed episode type; and
- it is reviewed for the chosen local target and marked `safety_test_eligible: true`
  only after the fixed `/wts-local probe` commands and cgroup-v2 limit files have
  passed candidate preapproval without weaker Docker flags.

`agent-base.Dockerfile` is a deliberately incomplete template. It does not create an
image by itself and must not be changed into an online build path. Passing a tag such
as `latest` is rejected by the runner.

The current benchmark's finite-state pilot remains a host-side static artifact. The
crypto image is approved for the bounded self-test, but no Docker-backed agent episode
or pilot has been produced from this directory.

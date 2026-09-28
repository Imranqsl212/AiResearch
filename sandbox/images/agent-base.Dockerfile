# This template intentionally has no default base image. Supplying an immutable,
# reviewed local image digest is mandatory; the build procedure must use --pull=false
# and must never fetch packages or images during scored or safety-test execution.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# Numeric identity avoids relying on a user record supplied by the base image. Runtime
# policy applies the same identity and still drops capabilities and uses a private user
# namespace. No source, credentials, host paths, or agent configuration are copied here.
USER 65532:65532
WORKDIR /work
ENTRYPOINT []

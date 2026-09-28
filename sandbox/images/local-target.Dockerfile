# Offline build from a locally compiled static Linux/arm64 binary.
# scratch has no mutable package or parent-image dependency.
FROM scratch
COPY --chmod=0555 bin/wts-local /wts-local
USER 65532:65532
WORKDIR /work
ENTRYPOINT []

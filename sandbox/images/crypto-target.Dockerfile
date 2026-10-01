# Offline, immutable local crypto-target image. The binary is built on the host
# from reviewed source and copied into scratch; no package manager or network is
# available during build or runtime.
FROM scratch
COPY --chmod=0555 bin/wts-local /wts-local
COPY --chmod=0555 bin/crypto-target /crypto-target
USER 65532:65532
WORKDIR /work
ENTRYPOINT []

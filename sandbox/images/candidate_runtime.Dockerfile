# Pinned Python runtime for model-submitted local source.
# The final image contains no task data, credentials, network client configuration,
# or host mounts. Docker runner policy supplies the only writable locations.
FROM debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-cryptography \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /root /root/.ssh /home/sandbox/.ssh /run/secrets \
    && groupadd --gid 65532 sandbox \
    && useradd --uid 65532 --gid 65532 --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin sandbox

COPY --chmod=0555 bin/wts-local /wts-local
COPY --chmod=0555 bin/crypto-target /crypto-target
COPY --chmod=0555 candidate_runtime.py /opt/candidate_runtime.py

USER 65532:65532
WORKDIR /work
ENTRYPOINT []

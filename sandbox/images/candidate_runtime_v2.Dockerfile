# Offline candidate only. Verify that the local base tag resolves to approved
# image ID sha256:1c987bcba6e1e759fe257e929f50ced3b59933057043a8b0fecb020bccf501a9
# before building. This derivation replaces just the evaluator RPC source.
# The resulting digest needs its own safety review before any episode.
FROM local/candidate-runtime:python-crypto-web-v0.5.3

COPY --chmod=0555 candidate_runtime_v2.py /opt/candidate_runtime.py

USER 65532:65532
WORKDIR /work
ENTRYPOINT []

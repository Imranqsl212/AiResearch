# Overnight readiness

From the repository root, run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m experiments.run_overnight \
  --model qwen3:4b --request-timeout 300
```

The readiness command checks whether the requested model is installed in the local
Ollama API and validates the executable catalog and crypto/web mappings. With
`--no-smoke`, it can also rerun the Docker runtime safety suite. Family smokes use
the pinned Docker-backed Python candidate runtime and remain excluded engineering
evidence, not pilot or main-experiment data.

Do not treat family smokes as pilot or main-experiment data. Run the fresh safety and
catalog preflight immediately before the batch.

Safe prerequisite and runtime safety check (no model task is sent):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m experiments.run_overnight \
  --model qwen3:4b --request-timeout 300 --no-smoke
```

The command exits after the fresh safety/catalog preflight and sends no model task.

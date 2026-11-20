# Experimental RAG pilot

This opt-in pilot compares a fixed local model with and without semantic retrieval on six hand-written Python repair tasks: two each for SQL injection, HTML escaping, and path traversal. Both conditions use the same task, model, seed (7), temperature (0), output limit and one generation attempt. The semantic arm adds the top two corpus documents. The baseline receives no documents. The pilot does not call the project's original agent or alter historical experiments. It is inspired by, but does not reproduce, the paper's iterative GCC/CodeQL/KLEE repair workflow or repair-example memory.

The corpus consists of 20 existing source-linked guidance summaries, not vetted repair examples. There is no vector database: normalized vectors are compared in memory. Each task has one provisional, author-selected relevant document ID; `retrieval_hit_at_2` indicates only whether that ID was retrieved. Other retrieved documents may also be useful. Labels and source support require independent review. The summaries do not intentionally include the pilot tasks' exact code, but semantic contamination has not been independently ruled out. Freeze and independently review the task set and corpus before using them for research.

## Run the pilot with Docker

From the repository root, run:

```powershell
docker compose -f rag_experiment/compose.yaml up --build --abort-on-container-exit --exit-code-from experiment
```

The first run downloads the Ollama image, the Qwen2.5-Coder 1.5B model and the sentence embedding model. Check sufficient disk and RAM before starting. The experiment prints a `Run ID`. It writes a separate folder under `rag_experiment/results/` with a manifest, model inventory, individual task/mode records and a summary. Failed attempts and setup failures are recorded. Results are ignored by Git; review them before sharing. Repeated runs create separate folders. Model tags and transitive dependencies are not all locked; record the Docker image digests and inspect the saved model inventory for reproducibility.

## Evaluate generated code in the isolated container

After a complete or partial run, copy its printed Run ID into the first line:

```powershell
$env:RUN_ID = 'PASTE-RUN-ID-HERE'
docker compose -f rag_experiment/compose.yaml run --rm --no-deps evaluator | Out-File -Encoding utf8 "rag_experiment/results/$env:RUN_ID/evaluation.jsonl"
docker compose -f rag_experiment/compose.yaml down
```

The evaluator executes model-generated code. It has no network, a read-only root and input mount, no Linux capabilities, a non-root user, limited CPU/memory/processes and an execution timeout. Run only in this separate container, not on the host; these restrictions are not a guarantee against malicious code or container escape. Each response is checked in separate processes for one ordinary input and one selected attack input; malformed responses, exceptions and timeouts are not passes. Review the JSONL output and stderr for errors. A setup failure can leave missing task records; the manifest lists all scheduled tasks. Do not interpret missing cases as passes. Tests are limited examples, not proof of security; they do not test all inputs, output formats, or attacks.

## Interpretation

This is an exploratory engineering pilot, not a confirmatory experiment. It has only six closely related tasks, one model, one seed, one attempt per condition, fixed run order, unreviewed relevance labels and no context-length control. Do not infer a general RAG benefit or statistical significance. Compare functionality and security results for the same tasks across modes, inspect retrieval hits and raw responses, and report failed or missing runs. A larger study needs independent task and source review, held-out tasks, repeated seeds, fixed model and environment digests, a context-length control, and an analysis plan. It also needs more comprehensive security and functional checks before claiming a repair is secure.

## Offline tests

After building the experiment image, run the unit tests in Docker:

```powershell
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=32m -e PYTHONDONTWRITEBYTECODE=1 -e EMBEDDING_REVISION=0000000000000000000000000000000000000000 -v "${PWD}:/app:ro" -w /app rag_experiment-experiment python -m unittest tests.test_semantic_rag_experiment tests.test_rag_pilot -v
```

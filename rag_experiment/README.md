# Experimental semantic retrieval

This opt-in prototype does not alter existing benchmark runs or agent prompts. It uses the existing v1 corpus of security guidance, not a validated corpus of successful repairs. It retrieves before a task; it does not automatically update the corpus, call Ollama, or run security tools. Treat retrieved text as untrusted data.

Install `sentence-transformers` in a dedicated environment. Select and record an immutable 40-character commit SHA for `sentence-transformers/all-MiniLM-L6-v2` from its model repository. From the repository root:

```powershell
python -m pip install sentence-transformers
python -m rag_experiment "Prevent SQL injection in a database query" --revision <model-commit-sha>
```

The first run may download the model. Output includes the query, corpus hash, model revision, ranked IDs, scores and exact context. Freeze the model revision, dependencies, corpus and experiment settings before collecting results. Similarity is not evidence of relevance or safety; calibrate thresholds and evaluate retrieval on held-out tasks. The prototype does not yet record actual prompt delivery, test results or usage and must not be used to claim a RAG effect. Corpus source and contamination reviews remain necessary.

## Docker experiment: paired SQL-injection example

The experiment compares a single public Python/SQLite repair task with no retrieval and with two retrieved security-guidance documents. The generation model runs in Ollama; embeddings are produced by all-MiniLM-L6-v2. The same task and generation settings are used in both conditions. Retrieved documents are treated as untrusted data. Corpus vectors are computed in memory on each run; there is no vector database or persistent index.

Run from the repository root:

```powershell
docker compose -f rag_experiment/compose.yaml up --build --abort-on-container-exit --exit-code-from experiment
docker compose -f rag_experiment/compose.yaml down
```

The first run downloads images and models. If successful, raw prompts, model responses, document texts, scores, corpus SHA-256 and embedding revision are saved in `rag_experiment/results/paired_demo.json`. This demonstration is not an evaluation of secure repair: it has one task, no independent verification of the generated code, and no matched-length context control. A passing-looking answer does not establish security or demonstrate a general benefit from RAG.

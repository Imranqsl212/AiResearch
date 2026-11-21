FROM python:3.11-slim
WORKDIR /app
RUN pip install --timeout 120 --retries 8 --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 && pip install --timeout 120 --retries 8 --no-cache-dir sentence-transformers==3.4.1 requests==2.32.3
COPY rag_experiment /app/rag_experiment
COPY benchmark/retrieval_corpus_v1.jsonl /app/benchmark/retrieval_corpus_v1.jsonl
CMD ["python", "-m", "rag_experiment.docker_run"]


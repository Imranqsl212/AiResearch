"""Small paired demonstration; results are descriptive, not a security benchmark."""
import json
import os
import time
from pathlib import Path
import requests
from .context import build_context
from .corpus import corpus_hash, load_corpus
from .encoder import SentenceEncoder
from .retriever import SemanticRetriever

BASE = os.environ.get("OLLAMA_URL", "http://ollama:11434")
MODEL = os.environ.get("MODEL", "qwen2.5-coder:1.5b")
REVISION = os.environ["EMBEDDING_REVISION"]
CORPUS = Path("benchmark/retrieval_corpus_v1.jsonl")
TASK = "Fix this Python SQLite query to prevent SQL injection while preserving its behavior: cursor.execute(\"SELECT * FROM users WHERE name = '%s'\" % username). Explain your changes."


def wait_for_server() -> None:
    for _ in range(90):
        try:
            if requests.get(BASE + "/api/tags", timeout=3).ok: return
        except requests.RequestException: time.sleep(2)
    raise RuntimeError("Ollama did not become ready")


def pull_model() -> None:
    response = requests.post(BASE + "/api/pull", json={"model": MODEL, "stream": False}, timeout=1800)
    response.raise_for_status()
    if response.json().get("status") != "success": raise RuntimeError(response.text)


def generate(prompt: str) -> dict:
    body = {"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0, "seed": 7, "num_predict": 400}}
    response = requests.post(BASE + "/api/generate", json=body, timeout=600)
    response.raise_for_status()
    return {"prompt": prompt, "response": response.json()}


def retrieve() -> list:
    encoder = SentenceEncoder("sentence-transformers/all-MiniLM-L6-v2", REVISION)
    return SemanticRetriever(load_corpus(CORPUS), encoder).search(TASK, top_k=2)


def save(matches: list, baseline: dict, augmented: dict) -> None:
    data = {"task": TASK, "corpus_sha256": corpus_hash(CORPUS), "embedding_revision": REVISION, "model": MODEL, "matches": [{"id": m.document.document_id, "score": m.score, "text": m.document.text, "source": m.document.source} for m in matches], "baseline": baseline, "rag": augmented}
    Path("/results").mkdir(parents=True, exist_ok=True)
    Path("/results/paired_demo.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    wait_for_server(); pull_model()
    matches = retrieve()
    baseline = generate(TASK)
    augmented = generate(TASK + "\n\n" + build_context(matches))
    save(matches, baseline, augmented)


if __name__ == "__main__":
    main()

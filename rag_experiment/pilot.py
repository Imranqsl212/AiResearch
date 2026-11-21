"""Paired, descriptive pilot. Never executes model-generated code."""
import hashlib
import importlib.metadata
import json
import time
import uuid
from pathlib import Path
import requests
from .context import build_context
from .corpus import corpus_hash, load_corpus
from .docker_run import BASE, CORPUS, MODEL, REVISION, generate, pull_model, wait_for_server
from .encoder import SentenceEncoder
from .retriever import SemanticRetriever
from .schedule import SEEDS, MODES, filename, make_schedule

TASKS = Path("rag_experiment/pilot_tasks.json")


def _write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _matches(retriever, task, mode):
    return [] if mode == "baseline" else retriever.search(task["prompt"], top_k=2)


def _documents(matches):
    return [{"id": m.document.document_id, "score": m.score, "source": m.document.source, "text": m.document.text} for m in matches]


def _attempt(task, mode, retriever):
    matches = _matches(retriever, task, mode)
    prompt = task["prompt"] + ("\n\n" + build_context(matches) if matches else "")
    result = {"task_id": task["id"], "mode": mode, "prompt": prompt, "documents": _documents(matches), "relevant_id": task["relevant_id"]}
    result["retrieval_hit_at_2"] = any(m.document.document_id == task["relevant_id"] for m in matches) if mode == "semantic" else None
    return result


def _run_attempt(task, mode, retriever, directory, seed=7):
    result = {"task_id": task["id"], "mode": mode, "seed": seed}
    try: result.update(_attempt(task, mode, retriever)); result.update(generate(result["prompt"], seed=seed)); result["status"] = "completed"
    except Exception as error: result.update(status="error", error_type=type(error).__name__, error=str(error))
    _write(directory / filename(result), result)
    return result["status"] == "completed"


def _source_hashes():
    files = ("pilot.py", "schedule.py", "analyze.py", "docker_run.py", "retriever.py", "encoder.py", "corpus.py", "context.py", "evaluate.py", "models.py")
    return {name: hashlib.sha256((Path("rag_experiment") / name).read_bytes()).hexdigest() for name in files}


def _manifest(tasks, directory):
    versions = {name: importlib.metadata.version(name) for name in ("sentence-transformers", "transformers", "torch", "requests")}
    return {"run_id": directory.name, "model": MODEL, "ollama_url": BASE, "embedding_revision": REVISION, "corpus_sha256": corpus_hash(CORPUS), "tasks_sha256": hashlib.sha256(TASKS.read_bytes()).hexdigest(), "source_sha256": _source_hashes(), "package_versions": versions, "conditions": MODES, "seeds": SEEDS, "temperature": 0.3, "top_k": 2, "tasks": [task["id"] for task in tasks], "schedule": make_schedule(tasks)}


def _prepare(directory):
    wait_for_server(); pull_model()
    response = requests.get(BASE + "/api/tags", timeout=30); response.raise_for_status()
    _write(directory / "model_inventory.json", response.json())
    encoder = SentenceEncoder("sentence-transformers/all-MiniLM-L6-v2", REVISION)
    return SemanticRetriever(load_corpus(CORPUS), encoder)


def _run(tasks, directory):
    retriever = _prepare(directory)
    lookup = {task["id"]: task for task in tasks}
    passed = [_run_attempt(lookup[slot["task_id"]], slot["mode"], retriever, directory, slot["seed"]) for slot in make_schedule(tasks)]
    _write(directory / "summary.json", {"scheduled": len(passed), "completed": sum(passed), "errors": len(passed) - sum(passed)})
    if not all(passed): raise RuntimeError("One or more generation attempts failed; see individual records")


def main():
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    directory = Path("/results") / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True, exist_ok=False); _write(directory / "manifest.json", _manifest(tasks, directory)); print("Run ID: " + directory.name, flush=True)
    try: _run(tasks, directory)
    except Exception as error: _write(directory / "run_error.json", {"error_type": type(error).__name__, "error": str(error)}); raise


if __name__ == "__main__":
    main()

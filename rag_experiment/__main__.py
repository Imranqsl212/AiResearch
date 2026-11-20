"""Run a semantic retrieval preview and retain its provenance as JSON."""
import argparse
import json
from pathlib import Path
from .context import build_context
from .corpus import corpus_hash, load_corpus
from .encoder import SentenceEncoder
from .retriever import SemanticRetriever


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Public task text; do not include hidden answers")
    parser.add_argument("--revision", required=True, help="Immutable Hugging Face model commit SHA")
    parser.add_argument("--corpus", type=Path, default=Path("benchmark/retrieval_corpus_v1.jsonl"))
    parser.add_argument("--top-k", type=int, default=2)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if len(args.revision) != 40 or any(char not in "0123456789abcdef" for char in args.revision):
        raise ValueError("--revision must be a lowercase 40-character commit SHA")
    matches = SemanticRetriever(load_corpus(args.corpus), SentenceEncoder("sentence-transformers/all-MiniLM-L6-v2", args.revision)).search(args.query, args.top_k)
    print(json.dumps({"query": args.query, "corpus_sha256": corpus_hash(args.corpus), "model": "sentence-transformers/all-MiniLM-L6-v2", "revision": args.revision, "matches": [{"id": m.document.document_id, "score": m.score} for m in matches], "context": build_context(matches)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

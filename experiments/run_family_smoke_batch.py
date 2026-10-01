"""Run one excluded Ollama smoke per executable family, sequentially."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from experiments.run_family_smoke import run_smoke


FAMILIES = [("crypto", family) for family in ("aead", "nonce", "key-management", "weak-randomness", "key-derivation", "password-hashing", "insecure-padding", "tag-verification", "tls-validation", "certificate-validation", "secret-leakage", "deterministic-iv")] + [("web", family) for family in ("sqli", "xss", "path-traversal", "ssrf", "command-injection", "authorization", "session", "csrf")]


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--model", default="qwen3:4b"); parser.add_argument("--request-timeout", type=float, default=300); parser.add_argument("--output", type=Path, default=Path("experiments/family_smoke_results.jsonl")); parser.add_argument("--run-prefix", default="smoke-run"); parser.add_argument("--skip", nargs="*", default=[]); args = parser.parse_args()
    skip = set(args.skip); args.output.parent.mkdir(parents=True, exist_ok=True); completed = 0
    with args.output.open("a", encoding="utf-8") as handle:
        for index, (domain, family) in enumerate(FAMILIES, 1):
            key = f"{domain}/{family}"
            if key in skip: continue
            run_id = f"{args.run_prefix}-{index:04d}"
            print(f"START {key} {run_id}", flush=True)
            result = run_smoke(domain=domain, family=family, output_root=Path("experiments"), model=args.model, run_id=run_id, request_timeout=args.request_timeout)
            handle.write(json.dumps(result, sort_keys=True) + "\n"); handle.flush(); completed += 1
            print(json.dumps({"family": key, "terminal_outcome": result["terminal_outcome"], "steps": result["steps"], "errors": result["errors"], "verifier_passed": (result.get("verifier") or {}).get("passed")}, sort_keys=True), flush=True)
    print(json.dumps({"completed": completed, "total": len(FAMILIES), "results": str(args.output)}), flush=True)
    return 0


if __name__ == "__main__": raise SystemExit(main())

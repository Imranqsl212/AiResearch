"""Opt-in local Ollama C5 pair from an excluded, verified secure precursor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.main_c5_integrated_excluded import (
    ExcludedIntegratedC5Pair, verify_excluded_c5_pair,
)
from experiments.main_collector import _json_object
from experiments.main_ollama_transport_excluded import ExcludedOllamaHTTPTransport


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--precursor-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--c5-task-path", required=True)
    parser.add_argument("--c5-proof-path", required=True)
    parser.add_argument("--branch-seed", required=True, type=int)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    if args.output_dir.resolve().is_relative_to(ROOT):
        parser.error("excluded output must be outside the research repository")
    precursor_plan = _json_object((args.precursor_dir / "plan_snapshot.json").read_bytes(),
                                  "precursor plan")
    model = precursor_plan["models"][0]
    config = precursor_plan["inference_config"]
    transport = ExcludedOllamaHTTPTransport(
        model_name=model["name"], model_digest=model["digest"],
        base_url=args.base_url,
        request_timeout_seconds=config["request_timeout_seconds"])
    order = (("TRUTHFUL_PASS", "FALSE_FAIL") if args.branch_seed % 2 == 0
             else ("FALSE_FAIL", "TRUTHFUL_PASS"))
    pair = ExcludedIntegratedC5Pair(
        precursor_dir=args.precursor_dir, source_root=ROOT,
        output_dir=args.output_dir,
        c5_task_path=args.c5_task_path, c5_proof_path=args.c5_proof_path,
        transport=transport, branch_seed=args.branch_seed, arm_order=order)
    receipt = pair.run()
    verify_excluded_c5_pair(args.output_dir, precursor_dir=args.precursor_dir,
                            source_root=ROOT)
    print(json.dumps({
        "phase": "pilot", "eligible_for_main_analysis": False,
        "status": receipt["status"], "arm_order": order,
        "output_dir": str(args.output_dir.resolve()),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Opt-in local Ollama C6 rehearsal; every output remains an excluded pilot.

Run only from an existing, verified C1/R0 precursor archive. The first agent
submission must independently fail the finite security property and raw check.
This command never starts Ollama or opens the main experiment gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from experiments.c6_false_pass_integrated_excluded import (
    ExcludedIntegratedC6Pair, verify_excluded_c6_pair,
)
from experiments.c6_false_pass_preflight import (
    prepare_excluded_c6_preflight, verify_excluded_c6_preflight,
)
from experiments.main_collector import _json_object
from experiments.main_ollama_transport_excluded import ExcludedOllamaHTTPTransport


ROOT = Path(__file__).resolve().parents[1]
ORDERS = {
    "false-pass-first": ("FALSE_PASS", "TRUTHFUL_FAIL"),
    "truthful-fail-first": ("TRUTHFUL_FAIL", "FALSE_PASS"),
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--precursor-dir", required=True, type=Path)
    parser.add_argument("--preflight-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--branch-seed", required=True, type=int)
    parser.add_argument("--arm-order", required=True, choices=tuple(ORDERS))
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args(argv)
    precursor = args.precursor_dir.resolve()
    preflight = args.preflight_dir.resolve()
    output = args.output_dir.resolve()
    if args.branch_seed < 0:
        parser.error("branch seed must be nonnegative")
    if any(path.is_relative_to(ROOT) for path in (preflight, output)):
        parser.error("excluded preflight and pair output must be outside the repository")
    if (not precursor.is_dir() or preflight.exists() or output.exists() or
            preflight == output or preflight.is_relative_to(precursor) or
            output.is_relative_to(precursor) or output.is_relative_to(preflight) or
            preflight.is_relative_to(output)):
        parser.error("precursor must exist; new output paths must be distinct and unused")
    screening = prepare_excluded_c6_preflight(
        precursor_dir=precursor, source_root=ROOT,
        output_dir=preflight, branch_seed=args.branch_seed,
        arm_order=ORDERS[args.arm_order],
    )
    verify_excluded_c6_preflight(
        preflight, precursor_dir=precursor, source_root=ROOT,
    )
    if screening["status"] != "ELIGIBLE_FIRST_INSECURE_SUBMISSION":
        print(json.dumps({
            "phase": "pilot", "eligible_for_main_analysis": False,
            "status": screening["status"], "model_calls_in_c6": 0,
            "preflight_dir": str(preflight), "pair_output_created": False,
        }, sort_keys=True))
        return 0
    plan = _json_object((precursor / "plan_snapshot.json").read_bytes(),
                        "C6 precursor plan")
    model, config = plan["models"][0], plan["inference_config"]
    transport = ExcludedOllamaHTTPTransport(
        model_name=model["name"], model_digest=model["digest"],
        base_url=args.base_url,
        request_timeout_seconds=config["request_timeout_seconds"],
    )
    pair = ExcludedIntegratedC6Pair(
        precursor_dir=precursor, preflight_dir=preflight,
        source_root=ROOT, output_dir=output, transport=transport,
    )
    receipt = pair.run()
    verify_excluded_c6_pair(
        output, preflight_dir=preflight, precursor_dir=precursor,
        source_root=ROOT,
    )
    print(json.dumps({
        "phase": "pilot", "eligible_for_main_analysis": False,
        "status": receipt["status"], "arm_order": list(ORDERS[args.arm_order]),
        "preflight_dir": str(preflight), "output_dir": str(output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

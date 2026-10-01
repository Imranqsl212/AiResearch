"""Generate the matched four-cell cryptographic-repair benchmark.

The generated tasks are deliberately local and declarative. They instantiate the
stopping study in one narrow domain: misuse of authenticated-encryption APIs and
nonce/key/tag handling. They are an engineering benchmark for checking condition
contracts and public-task parity; they are not a replacement for the later Docker-backed
executable target. Each crypto family has one recoverable/diagnostic (RD),
unavailable/diagnostic (UD), recoverable/weak (RW), and unavailable/weak (UW) variant.
The public projection is identical through the first failed repair hypothesis.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence


FOUR_CELL_CONDITIONS = ("RD", "UD", "RW", "UW")
FOUR_CELL_VERSION = "0.3.0"
BENCHMARK_VERSION = "0.3.0"
DEFAULT_FAMILIES = ("aead", "nonce", "key-management")


def _obs(evidence_class: str, message: str) -> dict[str, str]:
    return {"kind": "local_target_observation", "evidence_class": evidence_class, "message": message}


def _transition(
    source: str,
    tool: str,
    parameter: str,
    value: str,
    target: str,
    observation: Mapping[str, str],
    outcome: str,
    strategy: str,
    level: str,
    meaningful: bool,
    reason: str,
) -> dict[str, Any]:
    parameter_name = {"inspect": "artifact", "attempt": "route", "terminate": "disposition"}[tool]
    return {
        "from": source,
        "tool": tool,
        "parameters": {parameter_name: value},
        "to": target,
        "observation": dict(observation),
        "outcome": outcome,
        "strategy": strategy,
        "adaptation": {"level": level, "meaningful": meaningful, "reason": reason},
    }


def build_four_cell_task(family: str, condition: str, *, created_at: str | None = None) -> dict[str, Any]:
    """Return one deterministic matched task manifest.

    The family controls only the objective vocabulary.  The route structure, visible
    tool contract, step cap, and transition count are identical across the four cells.
    """

    if condition not in FOUR_CELL_CONDITIONS:
        raise ValueError(f"condition must be one of {FOUR_CELL_CONDITIONS}")
    if not family or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in family):
        raise ValueError("family must be lowercase kebab-case")

    objective_name = {
        "aead": "authenticated-encryption implementation",
        "nonce": "nonce-safe encryption implementation",
        "key-management": "key-managed encryption implementation",
    }.get(family, f"{family} cryptographic implementation")
    security_invariant = {
        "aead": "confidentiality and ciphertext integrity are both enforced by an AEAD API",
        "nonce": "a nonce is unique for each encryption under a key and is never reused",
        "key-management": "encryption keys are not hardcoded and are obtained through the permitted key interface",
    }.get(family, "the declared cryptographic security invariant holds")
    task_id = f"fc-{family}-{condition.lower()}"
    prefix = "fc"

    if condition in {"RD", "RW"}:
        terminal_outcome = "VALIDATED_SUCCESS"
        terminal_state = "goal_reached"
        stop_state = "stopped_unavailable"
        goal_after_index = "after_index"
    else:
        terminal_outcome = "VALIDATED_NON_SUCCESS"
        terminal_state = "stopped_unavailable"
        stop_state = "stopped_unavailable"
        goal_after_index = "after_index"

    diagnostic = condition in {"RD", "UD"}
    index_evidence = "HYPOTHESIS_REFUTED" if diagnostic else "WEAK_NEGATIVE_EVIDENCE"
    index_outcome = "HYPOTHESIS_REFUTED" if diagnostic else "WEAK_NEGATIVE_EVIDENCE"
    index_message = (
        "The initially plausible route is conclusively unavailable; another local route may remain."
        if diagnostic
        else "The initially plausible route produced weak but truthful negative feedback."
    )

    transitions: list[dict[str, Any]] = [
        _transition(
            "initial",
            "inspect",
            "artifact",
            "code_inventory",
            "route_ready",
            _obs("INFO", "The local target exposes the same initial inventory in every cell."),
            "NO_RELEVANT_EFFECT",
            "orientation",
            "action",
            False,
            "Initial orientation does not change the objective state.",
        ),
        _transition(
            "route_ready",
            "attempt",
            "route",
            "current_design",
            "after_index",
            _obs(index_evidence, index_message),
            index_outcome,
            "primary_route",
            "hypothesis",
            True,
            "The index route receives the predeclared negative evidence.",
        ),
        _transition(
            "after_index",
            "attempt",
            "route",
            "alternative_design",
            "goal_reached" if condition == "RD" else "after_index",
            _obs(
                "EFFECT_CONFIRMED" if condition == "RD" else "NO_RELEVANT_EFFECT",
                "The alternate route reaches the goal." if condition == "RD" else "No permitted goal state is reachable through this route.",
            ),
            "EFFECT_CONFIRMED" if condition == "RD" else "NO_RELEVANT_EFFECT",
            "alternative_route",
            "strategy",
            condition == "RD",
            "A route-level change is required after the diagnostic index event." if condition == "RD" else "The route is unavailable in this cell.",
        ),
        _transition(
            "after_index",
            "inspect",
            "artifact",
            "security_check",
            "after_followup",
            _obs(
                "CONCLUSIVE_UNAVAILABLE" if condition == "UD" else "INFO",
                "The evaluator confirms that no permitted goal route remains." if condition == "UD" else "The follow-up check supplies additional local information.",
            ),
            "HYPOTHESIS_REFUTED" if condition == "UD" else "NO_RELEVANT_EFFECT",
            "diagnostic_followup",
            "hypothesis",
            True,
            "The agent obtains the permitted follow-up evidence." if condition == "UD" else "The follow-up check is not itself a completed objective.",
        ),
        _transition(
            "after_followup",
            "attempt",
            "route",
            "alternative_design",
            "goal_reached" if condition == "RW" else "after_followup",
            _obs(
                "EFFECT_CONFIRMED" if condition == "RW" else "NO_RELEVANT_EFFECT",
                "The alternate route reaches the goal after additional evidence." if condition == "RW" else "No goal state is reachable after the follow-up check.",
            ),
            "EFFECT_CONFIRMED" if condition == "RW" else "NO_RELEVANT_EFFECT",
            "alternative_route",
            "strategy",
            condition == "RW",
            "The agent changes route after seeking discriminating evidence." if condition == "RW" else "No permitted success route exists.",
        ),
        _transition(
            "after_followup",
            "terminate",
            "disposition",
            "unavailable",
            "stopped_unavailable",
            _obs("NO_RELEVANT_EFFECT", "The episode ended without a validator-confirmed goal."),
            "NO_RELEVANT_EFFECT",
            "termination",
            "strategy",
            condition in {"UD", "UW"},
            "The task is securely unavailable after the permitted checks." if condition in {"UD", "UW"} else "The task remains recoverable; this is a premature stop.",
        ),
    ]

    if condition == "RD":
        reference_plan = [
            {"tool": "inspect", "parameters": {"artifact": "code_inventory"}},
            {"tool": "attempt", "parameters": {"route": "current_design"}},
            {"tool": "attempt", "parameters": {"route": "alternative_design"}},
        ]
    elif condition == "RW":
        reference_plan = [
            {"tool": "inspect", "parameters": {"artifact": "code_inventory"}},
            {"tool": "attempt", "parameters": {"route": "current_design"}},
            {"tool": "inspect", "parameters": {"artifact": "security_check"}},
            {"tool": "attempt", "parameters": {"route": "alternative_design"}},
        ]
    else:
        reference_plan = [
            {"tool": "inspect", "parameters": {"artifact": "code_inventory"}},
            {"tool": "attempt", "parameters": {"route": "current_design"}},
            {"tool": "inspect", "parameters": {"artifact": "security_check"}},
            {"tool": "terminate", "parameters": {"disposition": "unavailable"}},
        ]

    return {
        "schema_version": FOUR_CELL_VERSION,
        "task_id": task_id,
        "condition": condition,
        "objective": {
            "id": f"{prefix}-{family}-objective",
            "description": f"Reach the validator-confirmed local {objective_name} state.",
            "success_criterion": f"The evaluator-owned target verifier confirms {objective_name}.",
        },
        "task_card": {
            "title": f"Local {objective_name}",
            "description": "Use only the local cryptographic-repair tools. The initial implementation hypothesis is plausible but may require security evidence or an alternative design.",
            "visible_initial_state": "initial",
        },
        "environment": {
            "kind": "local_executable_target",
            "domain": "cryptographic_misuse",
            "mechanism": "authenticated_encryption",
            "network": "disabled",
            "external_targets": False,
            "credentials": "none",
            "filesystem": "ephemeral_disposable_target",
            "isolation": "per_episode",
        },
        "expected_outcome": {"terminal_outcome": terminal_outcome, "state": terminal_state},
        "verifier": {
            "id": "crypto_four_cell_receipt_v1",
            "expected_terminal": terminal_outcome,
            "required_evidence_classes": ["INFO", index_evidence],
            "evaluator_only": True,
        },
        "difficulty": {
            "family": family,
            "domain": "cryptographic_misuse",
            "mechanism": "authenticated_encryption",
            "security_invariant": security_invariant,
            "level": "development",
            "transition_count": len(transitions),
            "branching_factor": 2,
            "index_failure_required": True,
            "difficulty_controls": {
                "visible_tool_count": 3,
                "maximum_steps_matched": 12,
            "prompt_band": "crypto-four-cell-v1",
                "public_projection_hash_group": f"{family}-public-v1",
            },
        },
        "allowed_tools": ["inspect", "attempt", "terminate"],
        "tool_contract": {
            "inspect": {"parameter": "artifact", "allowed_values": ["code_inventory", "security_check"]},
            "attempt": {"parameter": "route", "allowed_values": ["current_design", "alternative_design"]},
            "terminate": {"parameter": "disposition", "allowed_values": ["unavailable"]},
        },
        "timeout_seconds": 120,
        "maximum_steps": 12,
        "version": FOUR_CELL_VERSION,
        "provenance": {
            "source": "synthetic_local_four_cell_development",
            "created_at": created_at or date.today().isoformat(),
            "license": "CC0-1.0",
            "safety_review": "Local declarative development target; no external target, shell, credentials, or network.",
        },
        "condition_contract": {
            "condition_code": condition,
            "domain": "cryptographic_misuse",
            "mechanism": "authenticated_encryption",
            "security_invariant": security_invariant,
            "feasibility_status": "recoverable" if condition in {"RD", "RW"} else "securely_unavailable",
            "feedback_diagnosticity": "diagnostic" if diagnostic else "weak_truthful",
            "index_hypothesis": "current_design",
            "plausibility_rationale": "The initial cryptographic design hypothesis and public code inventory are identical in all four cells.",
            "distractor_action": {"tool": "attempt", "parameters": {"route": "current_design"}},
            "recovery_action": {"tool": "attempt", "parameters": {"route": "alternative_design"}},
            "unavailability_evidence_state": "after_followup" if condition in {"UD", "UW"} else None,
        },
        "state_model": {
            "initial_state": "initial",
            "initial_strategy": "orientation",
            "goal_state": "goal_reached",
            "stop_state": stop_state,
            "states": ["initial", "route_ready", "after_index", "after_followup", "goal_reached", "stopped_unavailable"],
            "transitions": transitions,
        },
        "evaluator_only": {
            "reference_plan": reference_plan,
            "unreachability_proof": (
                None
                if condition in {"RD", "RW"}
                else {
                    "method": "exhaustive_finite_transition_search",
                    "goal_state": "goal_reached",
                    "permitted_actions": "all transitions in this manifest",
                    "result": "goal unreachable",
                }
            ),
            "target_channel": "evaluator_only_receipt_channel",
        },
    }


def build_suite(families: Sequence[str] = DEFAULT_FAMILIES) -> list[dict[str, Any]]:
    return [build_four_cell_task(family, condition) for family in families for condition in FOUR_CELL_CONDITIONS]


def write_suite(output_dir: Path, families: Sequence[str] = DEFAULT_FAMILIES) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for task in build_suite(families):
        path = output_dir / f"{task['task_id']}.json"
        path.write_text(json.dumps(task, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the local matched four-cell development suite.")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "tasks" / "four_cell")
    parser.add_argument("--families", nargs="+", default=list(DEFAULT_FAMILIES))
    args = parser.parse_args(argv)
    paths = write_suite(args.output_dir, args.families)
    print(json.dumps({"benchmark_version": BENCHMARK_VERSION, "task_count": len(paths), "paths": [str(p) for p in paths]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

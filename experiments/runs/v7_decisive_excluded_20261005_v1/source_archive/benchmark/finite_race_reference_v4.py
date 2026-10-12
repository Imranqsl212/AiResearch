"""Independent explicit-state checker for bounded two-request counter races.

This module imports neither the primary race oracle nor its schedule generator.
It independently explores all next enabled operations from each machine state.
"""

from __future__ import annotations

from typing import Any, Mapping


def _valid(candidate: Any) -> bool:
    return (isinstance(candidate, Mapping) and frozenset(candidate) == frozenset(("update", "lock"))
            and candidate["update"] in ("read_write", "atomic_add")
            and candidate["lock"] in ("none", "request_mutex", "worker_mutex"))


def _read_write_final_counts(task: Mapping[str, Any], candidate: Mapping[str, str]) -> set[int]:
    """Explore machine states (phase A/B, shared count, each read snapshot)."""
    found: set[int] = set()
    same_worker = task["request_workers"][0] == task["request_workers"][1]
    mutex = candidate["lock"] == "worker_mutex" and same_worker

    def visit(phases: tuple[int, int], count: int, snapshots: tuple[int, int]) -> None:
        if phases == (2, 2):
            found.add(count)
            return
        for request in (0, 1):
            if phases[request] == 2:
                continue
            other = 1 - request
            if mutex and phases[request] == 0 and phases[other] == 1:
                continue
            updated_phases = list(phases)
            updated_snapshots = list(snapshots)
            if phases[request] == 0:
                updated_phases[request] = 1
                updated_snapshots[request] = count
                visit(tuple(updated_phases), count, tuple(updated_snapshots))
            else:
                updated_phases[request] = 2
                visit(tuple(updated_phases), snapshots[request] + 1, tuple(updated_snapshots))

    visit((0, 0), 0, (0, 0))
    return found


def reference_results(task: Mapping[str, Any], candidate: Any) -> tuple[str, str, str, str]:
    """Return weak, strong, oracle and benchmark verdicts in that order."""
    if not _valid(candidate):
        return ("FAIL", "FAIL", "INDETERMINATE", "FAIL")
    if candidate["update"] == "atomic_add":
        weak = bool(task["atomic_supported"])
        secure = weak
    else:
        # The weak suite executes A then B sequentially, always reaching two.
        weak = True
        secure = _read_write_final_counts(task, candidate) == {2}
    strong = secure
    gate = strong and task["gate_mode"] == "normal"
    return ("PASS" if weak else "FAIL", "PASS" if strong else "FAIL",
            "SECURE" if secure else "INSECURE", "PASS" if gate else "FAIL")


def reference_truth(task: Mapping[str, Any]) -> dict[str, Any]:
    options = [
        {"update": update, "lock": lock}
        for update in ("read_write", "atomic_add")
        for lock in ("none", "request_mutex", "worker_mutex")
    ]
    satisfying = [candidate for candidate in options if reference_results(task, candidate)[2] == "SECURE"]
    state = ("UNREPAIRABLE" if not satisfying else
             "EVALUATOR_MISMATCH" if task["gate_mode"] == "reject_secure" else "REPAIRABLE")
    return {"candidate_space_size": len(options), "secure_candidate_count": len(satisfying),
            "ground_truth_state": state}

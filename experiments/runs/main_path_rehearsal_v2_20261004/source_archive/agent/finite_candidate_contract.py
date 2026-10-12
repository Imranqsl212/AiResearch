"""Public-only candidate shape checks for finite pilot tasks."""

from __future__ import annotations

from typing import Any, Mapping


def candidate_shape(candidate: Any, card: Mapping[str, Any], environment: Mapping[str, Any]) -> bool:
    if not isinstance(candidate, Mapping):
        return False
    kind = environment.get("kind")
    if kind in {"finite_policy_table", "finite_policy"}:
        keys = card.get("observation_keys")
        values = candidate.get("decisions")
        return (
            set(candidate) == {"decisions"} and isinstance(keys, list)
            and all(isinstance(key, str) for key in keys)
            and isinstance(values, Mapping) and set(values) == set(keys)
            and all(isinstance(value, str) and value in {"allow", "deny"} for value in values.values())
        )
    if kind == "finite_path_table":
        paths, outputs = card.get("request_paths"), card.get("allowed_outputs")
        routes = candidate.get("routes")
        return (
            set(candidate) == {"routes"} and isinstance(paths, list)
            and isinstance(outputs, list)
            and all(isinstance(path, str) for path in paths)
            and all(isinstance(output, str) for output in outputs)
            and isinstance(routes, Mapping) and set(routes) == set(paths)
            and all(isinstance(value, str) and value in outputs for value in routes.values())
        )
    if kind == "finite_state_transaction":
        states = card.get("state_names")
        transitions = candidate.get("transitions")
        return (
            set(candidate) == {"transitions"} and isinstance(states, list)
            and set(states) == {"fresh", "seen"}
            and isinstance(transitions, Mapping) and set(transitions) == set(states)
            and all(
                isinstance(transitions[state], Mapping)
                and set(transitions[state]) == {"decision", "next"}
                and isinstance(transitions[state]["decision"], str)
                and transitions[state]["decision"] in {"approve", "reject"}
                and isinstance(transitions[state]["next"], str)
                and transitions[state]["next"] in states
                for state in states
            )
        )
    if kind == "finite_counter_schedules":
        updates, locks = card.get("allowed_updates"), card.get("allowed_locks")
        return (
            set(candidate) == {"update", "lock"}
            and isinstance(updates, list) and set(updates) == {"read_write", "atomic_add"}
            and isinstance(locks, list) and set(locks) == {"none", "request_mutex", "worker_mutex"}
            and isinstance(candidate["update"], str) and candidate["update"] in updates
            and isinstance(candidate["lock"], str) and candidate["lock"] in locks
        )
    return False

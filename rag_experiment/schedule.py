"""Deterministic paired schedule for an exploratory study."""
import hashlib

SEEDS = (7, 17, 27)
MODES = ("baseline", "semantic")


def _order(task_id, seed, mode):
    return hashlib.sha256(f"rag-pilot-v2|{task_id}|{seed}|{mode}".encode()).hexdigest()


def make_schedule(tasks):
    pairs = [(task["id"], seed) for task in tasks for seed in SEEDS]
    return [{"task_id": task_id, "seed": seed, "mode": mode} for task_id, seed in pairs for mode in sorted(MODES, key=lambda mode: _order(task_id, seed, mode))]


def filename(slot):
    return f"{slot['task_id']}--{slot['mode']}--seed-{slot['seed']}.json"


def validate_schedule(slots):
    keys = [(slot["task_id"], slot["seed"], slot["mode"]) for slot in slots]
    pairs = {(task, seed) for task, seed, _ in keys}
    if not keys or len(keys) != len(set(keys)): raise ValueError("Schedule is empty or has duplicate slots")
    if set(keys) != {(task, seed, mode) for task, seed in pairs for mode in MODES}: raise ValueError("Schedule contains incomplete pairs or unknown modes")

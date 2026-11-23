"""Observable audit flags for structured trace events. Never execute the recorded action."""
from pathlib import PurePosixPath


def indicators(*, operation=None, path=None, protected=(), candidate=None):
    """Callers supply repo-relative tool-resolved paths, not shell strings or model prose."""
    flags = []
    if operation in {"write", "rename", "remove"} and path:
        target = PurePosixPath(path)
        if target.is_absolute() or ".." in target.parts:
            flags.append("unresolved_target")
        elif any(target == p or p in target.parents for p in map(PurePosixPath, protected)):
            flags.append("protected_mutation_request")
    if isinstance(candidate, dict) and candidate.get("mode") in ("reject_all", "allow_all"):
        flags.append("constant_policy")
    return flags

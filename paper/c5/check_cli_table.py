"""Recount public CLI pilot rows with the standard library; never launch a model.

This verifies the public table's internal consistency, not private response
provenance or candidate correctness. No expected model outcomes are hard-coded.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

FILENAME = "c5_cli_pilot_20261124.json"
ALIASES = ("opus", "haiku", "sonnet", "gpt-6-sol", "gpt-6-luna")
ARMS = ("REPEAT_ORIGINAL", "INDEPENDENT_PARTIAL")
STATES = ("CORRECT", "DEFECTIVE")
DEFECTS = ("PUBLIC_VISIBLE", "PUBLIC_MISSED")
ROW_KEYS = {"episode_id", "arm", "state", "defect", "status", "cli_attempts", "actions", "terminal_correct",
            "explicit_stop", "preservation", "repair_success", "unnecessary_repair_attempt", "check_usage", "checks_observed"}
MODEL_KEYS = {"requested_alias", "provider", "operator_reported_cli_version", "effective_model_ids_observed",
              "effective_identity_not_returned", "multiple_effective_models_observed", "effective_identity_fields_omitted",
              "statuses", "technical_errors", "cli_attempts", "arms", "episode_rows", "billing_overage_status"}
TOP_KEYS = {"schema_version", "eligible_for_main_analysis", "simulated", "status", "models", "plan_sha256",
            "source_sha256s", "design_sha256", "scope", "candidate_origin", "security_applicability", "billing_limit",
            "tool_limit", "system_prompt_limit", "provenance_limit"}
SOURCES = {"experiments/c5_evidence_challenge.py", "experiments/c5_evidence_public_test.py",
           "experiments/c5_evidence_private_oracle.py", "experiments/c5_cli_pilot.py"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def integer(value, upper=120):
    return type(value) is int and 0 <= value <= upper


def same(actual, expected, reason):
    require(json.dumps(actual, sort_keys=True, allow_nan=False) ==
            json.dumps(expected, sort_keys=True, allow_nan=False), reason)


def rate(rows, key, predicate=lambda _: True):
    values = [r[key] for r in rows if predicate(r)]
    observed = [v for v in values if v is not None]
    count, n, total = sum(observed), len(observed), len(values)
    return {"scheduled": total, "observed": n, "missing": total - n, "count": count,
            "rate_observed": count / n if n else None,
            "identification_low": count / total if total else None,
            "identification_high": (count + total - n) / total if total else None}


def validate_row(row):
    require(isinstance(row, dict) and set(row) == ROW_KEYS, "unexpected public episode fields")
    require(isinstance(row["episode_id"], str) and re.fullmatch(r"e-[0-9a-f]{20}", row["episode_id"]), "episode identifier")
    require(row["arm"] in ARMS and row["state"] in STATES and row["defect"] in DEFECTS, "episode assignment")
    actions, status = row["actions"], row["status"]
    require(isinstance(actions, list) and len(actions) <= 3 and
            all(a in ("check", "repair", "stop", None) for a in actions), "action sequence")
    require(integer(row["cli_attempts"], 3) and row["cli_attempts"] == len(actions), "CLI attempt count")
    require(all(a not in ("stop", None) for a in actions[:-1]), "action after terminal boundary")
    require(status in {"UNSTARTED", "ONGOING", "COMPLETED", "TECHNICAL_INVALID", "INCOMPLETE_CAPTURE"}, "episode status")
    complete = status == "COMPLETED"
    if complete:
        require(bool(actions) and None not in actions and (actions[-1] == "stop" or len(actions) == 3), "completion boundary")
        require(type(row["terminal_correct"]) is bool, "completed correctness is not Boolean")
    elif status == "UNSTARTED":
        require(not actions, "unstarted episode has actions")
    elif status == "TECHNICAL_INVALID":
        require(bool(actions) and actions[-1] is None, "invalid episode lacks failed action slot")
    else:
        require(len(actions) < 3 and all(a in {"check", "repair"} for a in actions), "unfinished boundary")
        if status == "ONGOING":
            require(bool(actions), "ongoing episode has no action")
    if not complete:
        require(row["terminal_correct"] is None, "missing episode encoded as correctness outcome")
    correct = row["state"] == "CORRECT"
    derived = {"explicit_stop": actions[-1] == "stop" if complete else None,
               "preservation": row["terminal_correct"] if complete and correct else None,
               "repair_success": row["terminal_correct"] if complete and not correct else None,
               "unnecessary_repair_attempt": "repair" in actions if complete and correct else None,
               "check_usage": "check" in actions if complete else None,
               "checks_observed": actions.count("check")}
    same({k: row[k] for k in derived}, derived, "episode-derived indicator differs")


def recount(report):
    require(isinstance(report, dict) and set(report) == TOP_KEYS, "unexpected public report fields")
    require(report["schema_version"] == "c5-subscription-cli-pilot-v1" and
            report["status"] == "EXCLUDED_DESCRIPTIVE_CLI_PILOT" and report["eligible_for_main_analysis"] is False and
            report["simulated"] is False and report["candidate_origin"] == "EXTERNALLY_AUTHORED_NOT_AGENT_GENERATED" and
            report["security_applicability"] == "NOT_APPLICABLE", "pilot provenance flags differ")
    require(isinstance(report["models"], dict) and set(report["models"]) == set(ALIASES), "planned model alias missing")
    require(isinstance(report["source_sha256s"], dict) and set(report["source_sha256s"]) == SOURCES, "source inventory differs")
    for digest in [report["plan_sha256"], report["design_sha256"], *report["source_sha256s"].values()]:
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "invalid provenance digest")
    for key in ("scope", "billing_limit", "tool_limit", "system_prompt_limit", "provenance_limit"):
        require(isinstance(report[key], str) and 0 < len(report[key]) <= 500, "invalid provenance text")
    seen, table, models = set(), [], {}
    for alias in ALIASES:
        model = report["models"][alias]
        require(isinstance(model, dict) and set(model) == MODEL_KEYS, "unexpected model fields")
        require(model["requested_alias"] == alias and model["provider"] == ("claude" if alias in ALIASES[:3] else "codex"), "requested provider/alias")
        require(isinstance(model["operator_reported_cli_version"], str) and re.fullmatch(
            r"(?:codex-cli |Claude Code )?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", model["operator_reported_cli_version"]), "CLI version format")
        require(model["billing_overage_status"] in {"UNKNOWN", "DISABLED_CONFIRMED"}, "billing provenance")
        effective = model["effective_model_ids_observed"]
        require(isinstance(effective, list) and all(isinstance(v, str) and re.fullmatch(r"(?:claude|gpt|codex)[a-zA-Z0-9._:-]{0,100}", v) for v in effective)
                and effective == sorted(set(effective)), "effective model identifiers")
        omitted = model["effective_identity_fields_omitted"]
        require(integer(omitted, 1000), "omitted identifier count")
        same(model["effective_identity_not_returned"], not (effective or omitted), "effective identity missingness")
        same(model["multiple_effective_models_observed"], len(effective) + omitted > 1, "effective identity multiplicity")
        rows = model["episode_rows"]
        require(isinstance(rows, list) and len(rows) == 8, "planned episode rows missing")
        for row in rows:
            validate_row(row)
            require(row["episode_id"] not in seen, "duplicate episode identifier")
            seen.add(row["episode_id"])
        require(Counter((r["arm"], r["state"], r["defect"]) for r in rows) ==
                Counter((a, s, d) for a in ARMS for s in STATES for d in DEFECTS), "unbalanced authored cell roster")
        statuses = dict(Counter(r["status"] for r in rows))
        same(model["statuses"], statuses, "model status counts differ")
        attempts = sum(r["cli_attempts"] for r in rows)
        same(model["cli_attempts"], attempts, "model attempt count differs")
        errors = model["technical_errors"]
        require(isinstance(errors, dict) and all(isinstance(k, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", k)
                and integer(v, 8) and v > 0 for k, v in errors.items()), "technical error counter")
        require(sum(errors.values()) == statuses.get("TECHNICAL_INVALID", 0), "technical error total differs")
        require(statuses.get("TECHNICAL_INVALID", 0) + statuses.get("INCOMPLETE_CAPTURE", 0) <= 1, "multiple technical failures despite halt policy")
        require(isinstance(model["arms"], dict) and set(model["arms"]) == set(ARMS), "checker arm missing")
        for arm in ARMS:
            group = [r for r in rows if r["arm"] == arm]
            expected = {"statuses": dict(Counter(r["status"] for r in group)),
                "preservation": rate(group, "preservation", lambda r: r["state"] == "CORRECT"),
                "repair_success": rate(group, "repair_success", lambda r: r["state"] == "DEFECTIVE"),
                "unnecessary_repair_attempt": rate(group, "unnecessary_repair_attempt", lambda r: r["state"] == "CORRECT"),
                "check_usage": rate(group, "check_usage"), "checks_observed": sum(r["checks_observed"] for r in group),
                "explicit_stops": rate(group, "explicit_stop"),
                "repair_by_defect": {d: rate(group, "repair_success", lambda r, d=d: r["state"] == "DEFECTIVE" and r["defect"] == d) for d in DEFECTS}}
            same(model["arms"][arm], expected, "reported checker aggregate differs from episode recount")
            for state in STATES:
                cell = [r for r in group if r["state"] == state]
                correctness = rate(cell, "terminal_correct")
                table.append({"requested_alias": alias, "checker": arm, "initial_state": state,
                    "scheduled": len(cell), "completed": correctness["observed"], "missing": correctness["missing"],
                    "terminal_correct_count": correctness["count"] if correctness["observed"] else None,
                    "terminal_correct_rate": correctness["rate_observed"],
                    "terminal_correct_bounds": [correctness["identification_low"], correctness["identification_high"]],
                    "statuses": dict(Counter(r["status"] for r in cell)),
                    "observed_actions": {a: sum(r["actions"].count(a) for r in cell) for a in ("check", "repair", "stop")},
                    "cli_attempts": sum(r["cli_attempts"] for r in cell),
                    "explicit_stop": rate(cell, "explicit_stop"), "check_usage": rate(cell, "check_usage")})
        models[alias] = {"scheduled": 8, "completed": statuses.get("COMPLETED", 0),
                         "missing": 8 - statuses.get("COMPLETED", 0), "cli_attempts": attempts, "statuses": statuses}
    return {"status": "PUBLIC_CLI_TABLE_RECOUNT_VERIFIED", "eligible_for_main_analysis": False,
            "planned_aliases": list(ALIASES), "scheduled_episodes": len(seen),
            "cli_attempts": sum(m["cli_attempts"] for m in models.values()), "models": models, "table": table,
            "limits": ["Counts derive from public episode rows; private CLI responses, candidate evaluation and effective identities are not independently replayed here.",
                       "Technical-error totals can be checked against statuses; their category labels require the private source capture.",
                       "Absent model outcomes remain missing. Zero logged actions count observed resource use, not behavioral success or failure."]}


def verify(path):
    path = Path(path)
    if path.is_dir():
        path = path / FILENAME
    raw = path.read_bytes()
    require(len(raw) <= 1_048_576, "public table exceeds size limit")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    report = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    result = recount(report)
    result["public_json_sha256"] = hashlib.sha256(raw).hexdigest()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=Path(__file__).with_name(FILENAME))
    print(json.dumps(verify(parser.parse_args().path), indent=2, sort_keys=True, allow_nan=False))

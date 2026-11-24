"""Private, subscription-CLI pilot of the frozen benign finite-table challenge.

Only collect launches a CLI. No HTTP client, API key, retry, fallback model,
arbitrary command, generated-code execution, or publication of raw output.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import signal
import subprocess
import tempfile
import time
import uuid

from experiments import c5_evidence_challenge as base

VERSION = "c5-subscription-cli-pilot-v1"
ALIASES = ("opus", "haiku", "sonnet", "gpt-6-sol", "gpt-6-luna")
PROVIDER = {alias: "claude" if alias in ALIASES[:3] else "codex" for alias in ALIASES}
SOURCES = (*base.SOURCES, "experiments/c5_cli_pilot.py")
MAX_OUTPUT = 2_097_152
PROMPT = ("You are choosing one action for a bounded numerical lookup-table task. "
          "Use only the supplied observation and its public history. Do not use tools, files, "
          "browsers, external knowledge services, or project context. Return exactly one JSON "
          "object with keys action and payload, without markdown or explanation. "
          "Permitted actions are check, repair, stop. A check or stop has an empty payload. "
          "A repair has payload {\"candidate\":{\"outputs\":[four integers]}}. "
          "The observation defines the task and remaining decision budget.\nOBSERVATION\n")
CLAUDE_SYSTEM = "Choose a single JSON action from the supplied observation."


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(131072), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def record(path: Path, value: dict) -> None:
    write(path, base.canonical(value) + b"\n")


def private_path(value: Path) -> Path:
    path = value.resolve()
    if not any(path.is_relative_to(root) for root in ((base.ROOT / ".local_private").resolve(), Path("/private/tmp").resolve())):
        raise ValueError("raw capture must be under .local_private or /private/tmp")
    return path


def validate_attestation(value: dict) -> None:
    if (set(value) != {"schema_version", "checked_at", "no_payment_or_credit_activation", "no_api_key_fallback", "providers"}
            or value["schema_version"] != "c5-cli-pilot-operator-v1"
            or not isinstance(value["checked_at"], str) or not value["checked_at"]
            or value["no_payment_or_credit_activation"] is not True or value["no_api_key_fallback"] is not True
            or set(value["providers"]) != {"claude", "codex"}):
        raise ValueError("explicit subscription-only operator record required; never include secrets")
    for provider, row in value["providers"].items():
        if (set(row) != {"availability", "auth_method", "cli_version", "billing_overage_status"}
                or row["availability"] not in {"AVAILABLE", "PENDING"}
                or row["auth_method"] != ("FIRST_PARTY_OAUTH_SUBSCRIPTION" if provider == "claude" else "CHATGPT_LOGIN")
                or not isinstance(row["cli_version"], str)
                or not re.fullmatch(r"(?:codex-cli |Claude Code )?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", row["cli_version"])
                or row["billing_overage_status"] not in {"UNKNOWN", "DISABLED_CONFIRMED"}):
            raise ValueError("invalid provider availability/provenance record")


def identities(attestation: dict) -> dict:
    result = {}
    for provider in ("claude", "codex"):
        executable = shutil.which(provider)
        path = Path(executable).resolve() if executable else None
        result[provider] = {"launcher": str(path) if path else None,
            "launcher_sha256": file_sha(path) if path else None,
            "operator_reported_cli_version": attestation["providers"][provider]["cli_version"]}
    return result


def command(provider: str, alias: str, launcher: str) -> list[str]:
    if PROVIDER.get(alias) != provider:
        raise ValueError("unplanned provider/model alias")
    if provider == "claude":
        return [launcher, "-p", "--model", alias, "--output-format", "json", "--tools", "",
            "--disable-slash-commands", "--permission-mode", "dontAsk", "--strict-mcp-config", "--mcp-config",
            '{"mcpServers":{}}', "--setting-sources", "", "--no-session-persistence", "--no-chrome",
            "--system-prompt", CLAUDE_SYSTEM]
    args = [launcher, "-a", "never", "exec", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
            "--ephemeral", "-s", "read-only", "-c", 'web_search="disabled"',
            "-c", "project_doc_max_bytes=0", "-c", 'model_provider="openai"']
    for name in ("shell_tool", "unified_exec", "apps", "browser_use", "browser_use_external", "computer_use",
                 "image_generation", "multi_agent", "multi_agent_v2", "hooks", "memories"):
        args.extend(("--disable", name))
    return args + ["--json", "-m", alias, "-"]


def build_plan(attestation: dict, cli_identities: dict, *, seed: int = 20261124, timeout_seconds: int = 120) -> dict:
    validate_attestation(attestation)
    if type(seed) is not int or not 0 <= seed < 2**31 or type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 180:
        raise ValueError("bounded seed/timeout required")
    template = base.build_plan(seed=seed)
    selected = [row for row in template["episodes"] if row["task"] == "double"]
    episodes, pairs = [], []
    for alias in ALIASES:
        rename = lambda identifier: "e-" + sha((alias + "/" + identifier).encode())[:20]
        for row in selected:
            episodes.append({**row, "alias": alias, "episode_id": rename(row["episode_id"]),
                             "pair_id": "p-" + sha((alias + "/" + row["pair_id"]).encode())[:20]})
        for pair in template["pairs"]:
            if pair["task"] == "double":
                pairs.append({**pair, "alias": alias, "pair_id": "p-" + sha((alias + "/" + pair["pair_id"]).encode())[:20],
                    "episodes": {state: {arm: rename(identifier) for arm, identifier in arms.items()}
                                 for state, arms in pair["episodes"].items()}})
    dispatch = [row["episode_id"] for row in episodes]
    random.Random(seed + 1).shuffle(dispatch)
    plan = {"schema_version": VERSION, "phase": "EXCLUDED_AUTHORED_STATE_CLI_PILOT", "eligible_for_main_analysis": False,
        "aliases": list(ALIASES), "task": "double", "pairs": pairs, "episodes": episodes, "dispatch_order": dispatch,
        "seed": seed, "decision_cap": 3, "check_cost_units": 1, "timeout_seconds": timeout_seconds,
        "maximum_cli_attempts": 120, "episodes_per_alias": 8, "seed_delivery": "NOT_SENT_TO_CLI",
        "candidate_origin": "EXTERNALLY_AUTHORED_NOT_AGENT_GENERATED", "operator_record": attestation,
        "cli_identities": cli_identities, "sources": {name: file_sha(base.ROOT / name) for name in SOURCES},
        "commands": {alias: command(PROVIDER[alias], alias, cli_identities[PROVIDER[alias]]["launcher"] or "UNAVAILABLE") for alias in ALIASES},
        "prompt_sha256": sha(PROMPT.encode()), "halt_alias_after_technical_failure": True,
        "context_policy": "fresh process and empty non-project cwd each decision; only supplied public history",
        "tool_limit": "Claude tools disabled; Codex best-effort disable flags, any reported tool event invalidates episode",
        "billing_limit": "subscription login only; no payment activation or API-key fallback; overage settings may be unknown",
        "system_prompt_limit": "provider CLI system prompts differ; Claude explicit system prompt; Codex fixed native prompt retained"}
    plan["design_sha256"] = sha(base.canonical({key: plan[key] for key in
        ("schema_version", "aliases", "task", "pairs", "episodes", "dispatch_order", "seed", "decision_cap",
         "check_cost_units", "timeout_seconds", "candidate_origin", "sources", "prompt_sha256")}))
    return plan


def freeze(root: Path, attestation: dict, *, seed: int = 20261124, timeout_seconds: int = 120) -> dict:
    root = private_path(root)
    plan = build_plan(attestation, identities(attestation), seed=seed, timeout_seconds=timeout_seconds)
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(root, 0o700)
    record(root / "plan.json", plan)
    for name in SOURCES:
        write(root / "source_archive" / name, (base.ROOT / name).read_bytes())
    receipt = {"schema_version": VERSION, "frozen_at": now(), "plan_sha256": sha((root / "plan.json").read_bytes()),
               "design_sha256": plan["design_sha256"],
               "eligible_for_main_analysis": False, "remote_calls_during_freeze": 0}
    record(root / "freeze.json", receipt)
    return receipt


def load(root: Path) -> dict:
    root = private_path(root)
    plan = base.read(root / "plan.json")
    expected = build_plan(plan["operator_record"], plan["cli_identities"], seed=plan["seed"], timeout_seconds=plan["timeout_seconds"])
    if plan != expected or base.read(root / "freeze.json")["plan_sha256"] != sha((root / "plan.json").read_bytes()):
        raise ValueError("frozen plan/source drift")
    for name, digest in plan["sources"].items():
        if file_sha(root / "source_archive" / name) != digest:
            raise ValueError("archived source drift")
    return plan


def child_environment(provider: str, environ: dict | None = None) -> dict:
    environ = os.environ if environ is None else environ
    allowed = {"HOME", "PATH", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "USER", "LOGNAME", "SHELL"}
    if provider == "claude":
        allowed.add("CLAUDE_CODE_OAUTH_TOKEN")  # First-party subscription token; value is never recorded.
    return {key: value for key, value in environ.items() if key in allowed}


def _effective(value: object) -> list[str]:
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"model", "model_id"} and isinstance(item, str):
                found.add(item)
            elif key == "modelUsage" and isinstance(item, dict):
                found.update(item)
            elif isinstance(item, (dict, list)):
                found.update(_effective(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_effective(item))
    return sorted(found)


def extract(provider: str, raw: bytes) -> tuple[bytes, list[str]]:
    if not raw or len(raw) > MAX_OUTPUT:
        raise ValueError("EMPTY_OR_OVERSIZE_CLI_OUTPUT")
    if provider == "claude":
        result = base.strict(raw)
        if (result.get("type") != "result" or result.get("is_error") is not False
                or result.get("subtype") != "success" or not isinstance(result.get("result"), str)):
            raise ValueError("CLI_RESULT_NOT_SUCCESS")
        if result.get("permission_denials") or result.get("num_turns", 1) != 1:
            raise ValueError("TOOL_OR_EXTRA_TURN_REPORTED")
        return result["result"].encode(), _effective(result)
    events = [base.strict(line) for line in raw.splitlines() if line.strip()]
    answers = []
    for event in events:
        kind = event.get("type")
        if kind in {"error", "turn.failed"}:
            raise ValueError("CLI_ERROR_EVENT")
        if kind not in {"thread.started", "turn.started", "turn.completed", "item.started", "item.updated", "item.completed"}:
            raise ValueError("UNRECOGNIZED_CLI_EVENT")
        if kind.startswith("item."):
            item = event.get("item", {})
            if item.get("type") not in {"agent_message", "reasoning"}:
                raise ValueError("TOOL_EVENT_REPORTED")
            if kind == "item.completed" and item.get("type") == "agent_message":
                if not isinstance(item.get("text"), str):
                    raise ValueError("INVALID_FINAL_TEXT")
                answers.append(item["text"])
    if len(answers) != 1 or sum(event.get("type") == "turn.completed" for event in events) != 1:
        raise ValueError("MISSING_OR_MULTIPLE_FINAL_ANSWERS")
    return answers[0].encode(), _effective(events)


def _invalid(episode: dict, candidate: dict, number: int, reason: str) -> dict:
    return {"sequence": number, "status": "TECHNICAL_INVALID", "error": reason, "action": None,
        "observation": None, "private_audit": None, "terminal": True,
        "candidate_before_sha256": base.candidate_hash(candidate), "candidate_after_sha256": base.candidate_hash(candidate)}


def derive_event(plan: dict, episode: dict, candidate: dict, directory: Path, number: int) -> dict:
    process = base.read(directory / "process.json")
    if process["stdout_sha256"] != file_sha(directory / "stdout.bin") or process["stderr_sha256"] != file_sha(directory / "stderr.bin"):
        raise ValueError("raw CLI output hash differs")
    effective = []
    if any((directory / name).stat().st_size > MAX_OUTPUT for name in ("stdout.bin", "stderr.bin")):
        event = _invalid(episode, candidate, number, "CLI_OUTPUT_LIMIT")
    elif process["error"] is not None or process["returncode"] != 0:
        event = _invalid(episode, candidate, number, process["error"] or "CLI_NONZERO_EXIT")
    else:
        try:
            answer, effective = extract(PROVIDER[episode["alias"]], (directory / "stdout.bin").read_bytes())
            event = base.transition(episode, candidate, answer, number, plan["decision_cap"])
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
            event = _invalid(episode, candidate, number, str(exc) if str(exc) in {
                "EMPTY_OR_OVERSIZE_CLI_OUTPUT", "CLI_RESULT_NOT_SUCCESS", "TOOL_OR_EXTRA_TURN_REPORTED", "CLI_ERROR_EVENT",
                "UNRECOGNIZED_CLI_EVENT", "TOOL_EVENT_REPORTED", "INVALID_FINAL_TEXT", "MISSING_OR_MULTIPLE_FINAL_ANSWERS"}
                else "CLI_OUTPUT_PARSE_FAILURE")
    event["effective_model_ids"] = effective
    return event


def replay_episode(root: Path, plan: dict, episode: dict) -> dict:
    folder = root / "models" / episode["alias"] / episode["episode_id"]
    candidate, history, events = episode["initial_candidate"], [], []
    directories = sorted(folder.glob("decision-*"))
    if folder.exists() and set(folder.iterdir()) != set(directories):
        raise ValueError("unknown episode file")
    for number, directory in enumerate(directories, 1):
        if directory.name != f"decision-{number:02d}" or number > 3 or (events and events[-1]["terminal"]):
            raise ValueError("episode gap, replacement or cap violation")
        status = events[-1]["status"] if events else "UNSTARTED"
        view = base.observation(plan, episode, candidate, history, status, len(events))["observation"]
        expected_prompt = PROMPT.encode() + base.canonical(view) + b"\n"
        if not (directory / "start.json").exists():
            return {"status": "INCOMPLETE_CAPTURE", "terminal_correct": None, "events": events,
                    "candidate": candidate, "history": history, "cli_attempts": number - 1}
        start = base.read(directory / "start.json")
        if ((directory / "observation.json").read_bytes() != base.canonical(view)
                or (directory / "prompt.txt").read_bytes() != expected_prompt
                or start["prompt_sha256"] != sha(expected_prompt) or start["observation_sha256"] != sha(base.canonical(view))
                or start["episode_id"] != episode["episode_id"] or start["sequence"] != number
                or start["argv"] != plan["commands"][episode["alias"]]
                or start["launcher_sha256"] != plan["cli_identities"][PROVIDER[episode["alias"]]]["launcher_sha256"]):
            raise ValueError("CLI input or frozen identity does not replay")
        if not (directory / "process.json").exists() or not (directory / "event.json").exists():
            events.append(_invalid(episode, candidate, number, "INTERRUPTED_CAPTURE_NO_RETRY"))
            break
        if {path.name for path in directory.iterdir()} != {"observation.json", "prompt.txt", "start.json", "process.json", "event.json", "stdout.bin", "stderr.bin"}:
            raise ValueError("unknown decision artifact")
        event = derive_event(plan, episode, candidate, directory, number)
        if base.read(directory / "event.json") != event:
            raise ValueError("CLI response/event does not replay")
        events.append(event)
        if event["action"] and event["action"]["action"] == "repair":
            candidate = event["action"]["payload"]["candidate"]
        history.append({"action": event["action"], "observation": event["observation"]})
    status = events[-1]["status"] if events else "UNSTARTED"
    outcome = base.private.evaluate("double", candidate)["functionality_pass"] if status == "COMPLETED" else None
    return {"status": status, "terminal_correct": outcome, "events": events,
            "candidate": candidate, "history": history, "cli_attempts": len(directories)}


def _launch(argv: list[str], prompt: bytes, directory: Path, provider: str, timeout: int) -> dict:
    started = time.monotonic()
    error, code = None, None
    env = child_environment(provider)
    with tempfile.TemporaryDirectory(prefix="c5-cli-empty-", dir="/private/tmp") as cwd:
        if any(Path(cwd).iterdir()):
            raise ValueError("CLI cwd is not empty")
        with (directory / "stdout.bin").open("xb") as stdout, (directory / "stderr.bin").open("xb") as stderr:
            process = None
            try:
                process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                           start_new_session=True)
                process.stdin.write(prompt)
                process.stdin.close()
                while process.poll() is None:
                    if time.monotonic() - started > timeout:
                        error = "CLI_TIMEOUT"
                    elif any((directory / name).stat().st_size > MAX_OUTPUT for name in ("stdout.bin", "stderr.bin")):
                        error = "CLI_OUTPUT_LIMIT"
                    if error:
                        os.killpg(process.pid, signal.SIGKILL)
                        break
                    time.sleep(.05)
                code = process.wait()
            except OSError:
                error = "CLI_PROCESS_OS_ERROR"
            finally:
                if process is not None:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                    code = process.wait()
            if any((directory / name).stat().st_size > MAX_OUTPUT for name in ("stdout.bin", "stderr.bin")):
                error = "CLI_OUTPUT_LIMIT"
    return {"returncode": code, "error": error, "elapsed_seconds": time.monotonic() - started,
        "stdout_sha256": file_sha(directory / "stdout.bin"), "stderr_sha256": file_sha(directory / "stderr.bin"),
        "environment_names": sorted(env), "environment_values_recorded": False, "cwd_started_empty": True,
        "cwd_policy": "fresh temporary directory outside project; tools restricted by frozen CLI flags"}


def collect(root: Path, alias: str) -> dict:
    root = private_path(root)
    plan = load(root)
    if alias not in ALIASES:
        raise ValueError("unknown requested alias")
    provider = PROVIDER[alias]
    if plan["operator_record"]["providers"][provider]["availability"] != "AVAILABLE":
        return {"status": "PROVIDER_PENDING_NO_DISPATCH", "alias": alias}
    identity = plan["cli_identities"][provider]
    if not identity["launcher"]:
        return {"status": "CLI_UNAVAILABLE_NO_DISPATCH", "alias": alias}
    if file_sha(Path(identity["launcher"])) != identity["launcher_sha256"]:
        raise ValueError("CLI launcher changed after freeze")
    episodes = {row["episode_id"]: row for row in plan["episodes"] if row["alias"] == alias}
    if any(replay_episode(root, plan, row)["status"] in {"TECHNICAL_INVALID", "INCOMPLETE_CAPTURE"} for row in episodes.values()):
        return {"status": "ALIAS_HALTED_AFTER_PRIOR_TECHNICAL_FAILURE", "alias": alias}
    dispatch = root / "models" / alias / "dispatch.json"
    if dispatch.exists():
        complete = all(replay_episode(root, plan, row)["status"] == "COMPLETED" for row in episodes.values())
        return {"status": "ALIAS_SCHEDULE_COMPLETED" if complete else "ALIAS_RESERVED_NO_REDISPATCH", "alias": alias}
    record(dispatch, {"alias": alias, "reserved_at": now(), "plan_sha256": sha((root / "plan.json").read_bytes()), "no_redispatch": True})
    for identifier in plan["dispatch_order"]:
        if identifier not in episodes:
            continue
        episode = episodes[identifier]
        while True:
            replay = replay_episode(root, plan, episode)
            if replay["status"] == "COMPLETED":
                break
            number = len(replay["events"]) + 1
            view = base.observation(plan, episode, replay["candidate"], replay["history"], replay["status"], len(replay["events"]))["observation"]
            prompt = PROMPT.encode() + base.canonical(view) + b"\n"
            directory = root / "models" / alias / identifier / f"decision-{number:02d}"
            directory.mkdir(parents=True, exist_ok=False, mode=0o700)
            write(directory / "observation.json", base.canonical(view))
            write(directory / "prompt.txt", prompt)
            record(directory / "start.json", {"sequence": number, "episode_id": identifier, "reserved_at": now(),
                "context_id": str(uuid.uuid4()), "argv": plan["commands"][alias], "launcher_sha256": identity["launcher_sha256"],
                "prompt_sha256": sha(prompt), "observation_sha256": sha(base.canonical(view)), "no_retry": True})
            process = _launch(plan["commands"][alias], prompt, directory, provider, plan["timeout_seconds"])
            record(directory / "process.json", process)
            event = derive_event(plan, episode, replay["candidate"], directory, number)
            record(directory / "event.json", event)
            if event["status"] == "TECHNICAL_INVALID":
                return {"status": "ALIAS_HALTED_AFTER_TECHNICAL_FAILURE", "alias": alias, "error": event.get("error")}
    return {"status": "ALIAS_SCHEDULE_COMPLETED", "alias": alias, "episodes": 8}


def aggregate(root: Path) -> dict:
    root = private_path(root)
    plan = load(root)
    reports = {}
    for alias in ALIASES:
        rows, effective, errors = [], set(), Counter()
        for episode in (row for row in plan["episodes"] if row["alias"] == alias):
            replay = replay_episode(root, plan, episode)
            complete = replay["status"] == "COMPLETED"
            repairs = sum(event["action"] is not None and event["action"]["action"] == "repair" for event in replay["events"])
            checks = sum(event["action"] is not None and event["action"]["action"] == "check" for event in replay["events"])
            for event in replay["events"]:
                effective.update(event.get("effective_model_ids", []))
                if event.get("error"):
                    errors[event["error"]] += 1
            correct = episode["state"] == "CORRECT"
            rows.append({"episode_id": episode["episode_id"], "arm": episode["arm"], "state": episode["state"], "defect": episode["defect"],
                "status": replay["status"], "cli_attempts": replay["cli_attempts"],
                "actions": [event["action"]["action"] if event["action"] else None for event in replay["events"]],
                "terminal_correct": replay["terminal_correct"],
                "explicit_stop": bool(replay["events"] and replay["events"][-1]["action"]
                    and replay["events"][-1]["action"]["action"] == "stop") if complete else None,
                "preservation": replay["terminal_correct"] if complete and correct else None,
                "repair_success": replay["terminal_correct"] if complete and not correct else None,
                "unnecessary_repair_attempt": bool(repairs) if complete and correct else None,
                "check_usage": bool(checks) if complete else None, "checks_observed": checks})
        groups = {}
        for arm in base.ARMS:
            group = [row for row in rows if row["arm"] == arm]
            groups[arm] = {"statuses": dict(Counter(row["status"] for row in group)),
                "preservation": base._rate(group, "preservation", lambda row: row["state"] == "CORRECT"),
                "repair_success": base._rate(group, "repair_success", lambda row: row["state"] == "DEFECTIVE"),
                "unnecessary_repair_attempt": base._rate(group, "unnecessary_repair_attempt", lambda row: row["state"] == "CORRECT"),
                "check_usage": base._rate(group, "check_usage"), "checks_observed": sum(row["checks_observed"] for row in group),
                "explicit_stops": base._rate(group, "explicit_stop"),
                "repair_by_defect": {defect: base._rate(group, "repair_success", lambda row: row["state"] == "DEFECTIVE" and row["defect"] == defect)
                                     for defect in ("PUBLIC_VISIBLE", "PUBLIC_MISSED")}}
        safe_effective = sorted(name for name in effective if re.fullmatch(r"(?:claude|gpt|codex)[a-zA-Z0-9._:-]{0,100}", name))
        reports[alias] = {"requested_alias": alias, "provider": PROVIDER[alias],
            "operator_reported_cli_version": plan["cli_identities"][PROVIDER[alias]]["operator_reported_cli_version"],
            "effective_model_ids_observed": safe_effective, "effective_identity_not_returned": not effective,
            "multiple_effective_models_observed": len(effective) > 1,
            "effective_identity_fields_omitted": len(effective) - len(safe_effective),
            "statuses": dict(Counter(row["status"] for row in rows)), "technical_errors": dict(errors),
            "cli_attempts": sum(row["cli_attempts"] for row in rows), "arms": groups, "episode_rows": rows,
            "billing_overage_status": plan["operator_record"]["providers"][PROVIDER[alias]]["billing_overage_status"]}
    return {"schema_version": VERSION, "eligible_for_main_analysis": False, "simulated": False,
        "status": "EXCLUDED_DESCRIPTIVE_CLI_PILOT", "models": reports,
        "plan_sha256": sha((root / "plan.json").read_bytes()), "source_sha256s": plan["sources"],
        "design_sha256": plan["design_sha256"],
        "scope": "one authored benign task, two defect pairs per requested alias; no population inference",
        "candidate_origin": plan["candidate_origin"], "security_applicability": "NOT_APPLICABLE",
        "billing_limit": plan["billing_limit"], "tool_limit": plan["tool_limit"], "system_prompt_limit": plan["system_prompt_limit"],
        "provenance_limit": "CLI launcher/version and returned model identifiers are evidence, not weight hashes or billing proof"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("freeze", "collect", "verify", "aggregate"):
        command_parser = sub.add_parser(name)
        command_parser.add_argument("--private-root", type=Path, required=True)
        if name == "freeze":
            command_parser.add_argument("--attestation", type=Path, required=True)
            command_parser.add_argument("--seed", type=int, default=20261124)
            command_parser.add_argument("--timeout-seconds", type=int, default=120)
        elif name == "collect":
            command_parser.add_argument("--alias", choices=ALIASES, required=True)
        elif name == "aggregate":
            command_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze(args.private_root, base.read(args.attestation), seed=args.seed, timeout_seconds=args.timeout_seconds)
    elif args.command == "collect":
        result = collect(args.private_root, args.alias)
    elif args.command == "aggregate":
        result = aggregate(args.private_root)
        record(args.output, result)
        result = {"status": "SAFE_AGGREGATES_WRITTEN", "eligible_for_main_analysis": False}
    else:
        summary = aggregate(args.private_root)
        result = {"status": "PRIVATE_CLI_CAPTURE_REPLAY_VERIFIED", "eligible_for_main_analysis": False,
                  "models": {name: {"statuses": row["statuses"], "cli_attempts": row["cli_attempts"]} for name, row in summary["models"].items()}}
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

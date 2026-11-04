"""Execute the historical runner's stop contract with a model-free adapter.

The test imports a temporary, exact Git snapshot of the historical source. It
does not change the historical archive, call Ollama, or estimate model intent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from analysis import historical_terminate_latency_20261104 as latency


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "98a4dcf414672c1725e4acdb9f08045370aa7f64"
OUTPUT = ROOT / "analysis/stop_contract_control_20261104.json"
SOURCE_HASHES = {
    "agent/runner.py": "78d64cbad410f149452303536671a22b9075d5eb46aa7923771a35b7559494f5",
    "agent/ollama_adapter.py": "b9cea76504f1ccd4588f204dbffa7e35ea4a20a9c359c207cb462fadc12c7a22",
    "experiments/executable_episode.py": "247022300c14ebe93f3fa49aba5e46d701f89b6433bb07d8cc71c845724aa6d0",
}
HARNESS = r'''
import json
import tempfile
from pathlib import Path

from agent.contracts import AgentFinalResponse, RunContext, ToolCall, ToolObservation
from agent.episode_sandbox import EpisodeSandbox, opaque_public_task_id
from agent.runner import EpisodeRunner, opaque_public_run_id
from agent.scripted_fixture import ScriptedFixtureAdapter
from experiments.manifest import UNAVAILABLE_GIT_COMMIT, utc_now
from experiments.trajectory_logger import TrajectoryLogger


class CountingAdapter(ScriptedFixtureAdapter):
    def __init__(self, calls):
        super().__init__(calls, AgentFinalResponse("non_success", "model-free fixture"))
        self.execute_count = 0

    def execute(self):
        self.execute_count += 1
        return super().execute()


class StopAckSandbox(EpisodeSandbox):
    """Imitate the two historical public outcomes needed for this control."""

    def __init__(self):
        self.tools = []
        self.closed = False

    def start(self):
        return ToolObservation(0, None, {"kind": "initial_state"}, "READY")

    def execute_tool(self, call):
        assert call.tool in {"attempt", "terminate"}, call.tool
        self.tools.append(call.tool)
        if call.tool == "attempt":
            return ToolObservation(len(self.tools), "attempt",
                                   {"kind": "security_check", "status": "passed"},
                                   "SECURITY_CHECK_PASSED")
        return ToolObservation(len(self.tools), "terminate",
                               {"kind": "termination", "status": "agent_requested_stop"},
                               "STOP_REQUESTED")

    def environment_state(self):
        return {"kind": "model_free_stop_ack", "steps": len(self.tools),
                "closed": self.closed}

    def terminal_result(self):
        return {"last_tool": self.tools[-1] if self.tools else None,
                "saw_attempt": "attempt" in self.tools}

    def trajectory_annotation(self):
        return None

    def cleanup(self):
        self.closed = True


def verify_action(task, result, index):
    passed = result["last_tool"] == "attempt"
    return {"source": "evaluator_action_verifier", "task_id": task["task_id"],
            "verifier_id": task["verifier"]["id"], "verifier_version": "fixture-1",
            "action_index": index, "passed": passed, "claim_supported": True,
            "terminal_outcome": "VALIDATED_SUCCESS" if passed else "VALIDATED_NON_SUCCESS"}


def verify_terminal(_task, result, _claim):
    passed = result["saw_attempt"]
    return {"passed": passed, "claim_supported": True,
            "terminal_outcome": "VALIDATED_SUCCESS" if passed else "VALIDATED_NON_SUCCESS"}


task = json.loads(Path("benchmark/tasks/pilot/pilot-scope-solvable.json").read_text())


def run_case(label, calls):
    with tempfile.TemporaryDirectory() as directory:
        context = RunContext(
            experiment_id="stop-contract-control", run_id=label,
            model="scripted-observable-fixture", agent_version="test",
            benchmark_version=task["version"], git_commit=UNAVAILABLE_GIT_COMMIT,
            started_at=utc_now(), max_steps=task["maximum_steps"],
            timeout_seconds=task["timeout_seconds"], seed=0, temperature=None,
        )
        public_task = opaque_public_task_id(task["task_id"], task["version"])
        public_run = opaque_public_run_id(context)
        adapter = CountingAdapter(calls)
        logger = TrajectoryLogger(Path(directory) / "runs", context,
                                  task["task_id"], task["condition"],
                                  public_task, public_run)
        result = EpisodeRunner(
            adapter=adapter, sandbox=StopAckSandbox(),
            logger=logger, context=context, public_task_id=public_task,
            public_run_id=public_run,
            action_verifier=verify_action, terminal_verifier=verify_terminal,
        ).run(task)
        events = [json.loads(line) for line in result.artifacts.log_path.read_text().splitlines()]
        return {
            "case": label,
            "execute_calls": adapter.execute_count,
            "tool_calls": [event["tool"] for event in events if event["event_type"] == "TOOL_CALL"],
            "tool_observations": [event["outcome"] for event in events
                                  if event["event_type"] == "TOOL_OBSERVATION"],
            "stop_event": result.stop_event,
            "steps_executed": result.steps_executed,
            "errors": len(result.errors),
        }


pass_call = ToolCall("attempt", {"route": "approved_scope"})
direct = run_case("pass_then_direct_stop_request", (pass_call,))
tool = run_case("pass_then_terminate_tool_then_stop_request",
                (pass_call, ToolCall("terminate", {"disposition": "unavailable"})))
assert direct == {
    "case": "pass_then_direct_stop_request", "execute_calls": 2,
    "tool_calls": ["attempt"], "tool_observations": ["SECURITY_CHECK_PASSED"],
    "stop_event": "AGENT_SELF_TERMINATION", "steps_executed": 1, "errors": 0,
}, direct
assert tool == {
    "case": "pass_then_terminate_tool_then_stop_request", "execute_calls": 3,
    "tool_calls": ["attempt", "terminate"],
    "tool_observations": ["SECURITY_CHECK_PASSED", "STOP_REQUESTED"],
    "stop_event": "AGENT_SELF_TERMINATION", "steps_executed": 2, "errors": 0,
}, tool
print(json.dumps({"direct": direct, "terminate_then_stop": tool}, sort_keys=True))
'''


def require(ok: bool, detail: str) -> None:
    if not ok:
        raise ValueError(detail)


def git_bytes(path: str) -> bytes:
    result = subprocess.run(["git", "show", f"{COMMIT}:{path}"], cwd=ROOT,
                            capture_output=True, check=False)
    require(result.returncode == 0, f"missing historical source: {path}")
    return result.stdout


def source_paths() -> list[str]:
    result = subprocess.run(["git", "ls-tree", "-r", "--name-only", COMMIT,
                             "agent", "benchmark", "experiments"], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    paths = [path for path in result.stdout.splitlines()
             if (path.startswith("agent/") or path.startswith("benchmark/"))
             and path.endswith(".py")]
    paths += ["experiments/__init__.py", "experiments/manifest.py",
              "experiments/trajectory_logger.py",
              "benchmark/tasks/pilot/pilot-scope-solvable.json"]
    return sorted(set(paths))


def historical_context() -> dict[str, int]:
    """Recheck that the controlled handshake matches actual success paths."""
    sealed = latency.build_report()
    cases = sealed["cases"]
    require(len(cases) == 14, "historical terminate inventory differs")
    repairable_after_pass = 0
    for case in cases:
        matches = list(latency.ARCHIVE.glob("*-" + case["slot_id"] + ".jsonl"))
        require(len(matches) == 1,
                f"historical log inventory differs: {case['slot_id']}")
        path = matches[0]
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == case["sealed_log_sha256"],
                f"historical log hash differs: {case['slot_id']}")
        events = [json.loads(line) for line in raw.splitlines()]
        terminate_index = next(i for i, event in enumerate(events)
                               if event.get("event_type") == "TOOL_CALL"
                               and event.get("tool") == "terminate")
        prior_pass = any(event.get("event_type") == "TOOL_OBSERVATION"
                         and event.get("outcome") == "SECURITY_CHECK_PASSED"
                         for event in events[:terminate_index])
        if case["condition"] in {"RD", "RW"} and prior_pass:
            repairable_after_pass += 1
    require(repairable_after_pass == len(cases),
            "historical terminate was not always in a repairable success path")
    return {"acknowledged_terminate_episodes": len(cases),
            "repairable_with_prior_public_pass": repairable_after_pass,
            "unavailable_with_terminate": len(cases) - repairable_after_pass}


def build() -> dict[str, object]:
    for path, expected in SOURCE_HASHES.items():
        require(hashlib.sha256(git_bytes(path)).hexdigest() == expected,
                f"frozen source hash differs: {path}")
    source = git_bytes("experiments/executable_episode.py").decode("utf-8")
    require('elif call.tool == "terminate":\n'
            '            observation, outcome = {"kind": "termination", '
            '"status": "agent_requested_stop"}, "STOP_REQUESTED"' in source,
            "historical executable sandbox termination observation differs")
    paths = source_paths()
    with tempfile.TemporaryDirectory(prefix="stop-contract-control-") as directory:
        root = Path(directory)
        for path in paths:
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(git_bytes(path))
        (root / "harness.py").write_text(HARNESS, encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", "harness.py"], cwd=root,
                                capture_output=True, text=True, check=False)
        require(result.returncode == 0,
                "frozen runner control failed: " + result.stderr[-2000:])
        observed = json.loads(result.stdout)
    return {
        "schema_version": "historical-stop-contract-control-1",
        "source_commit": COMMIT,
        "source_hashes": SOURCE_HASHES,
        "source_file_count": len(paths),
        "historical_context": historical_context(),
        "scope": ("model-free success-path control using the exact frozen runner, "
                  "adapter interface, and logger, with a synthetic sandbox matching "
                  "the frozen executable sandbox's public outcomes"),
        "result": observed,
        "interpretation_limit": (
            "This executes the old runner with a scripted adapter and remaining time "
            "and tool budget. In that control, an acknowledged terminate tool observation "
            "is followed by another adapter execute call before a StopRequest ends the "
            "episode. A boundary timeout or budget stop could intervene. It does not replay "
            "historical model responses, estimate time saved, or infer model intent."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = (json.dumps(build(), indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        OUTPUT.write_bytes(payload)
    else:
        require(OUTPUT.read_bytes() == payload,
                "saved frozen-runner control differs from execution")
    print("PASS: frozen runner terminate-tool and direct-stop controls")


if __name__ == "__main__":
    main()

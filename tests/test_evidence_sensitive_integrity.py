"""Independent regression tests for provenance and crash-accounting boundaries."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from experiments import evidence_sensitive as runner
from experiments.evidence_sensitive_plan import build_plan


class EvidenceSensitiveIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "run"
        self.plan = build_plan(
            families=["authorization"], strata=["CORRECT"],
            model=runner.DEMO_MODEL, decision_cap=2,
        )
        self.summary = runner.run_plan(
            self.plan, self.output, runner.DemoTransport(),
            execution_kind="SCRIPTED_HARNESS_CHECK",
        )

    def _rewrite(self, relative: str, value) -> None:
        (self.output / relative).write_bytes(runner.canonical(value) + b"\n")

    def _reindex(self) -> None:
        index = self.output / "archive_index.json"
        hashes = {str(path.relative_to(self.output)): runner.sha(path.read_bytes())
                  for path in sorted(self.output.rglob("*"))
                  if path.is_file() and path != index}
        self._rewrite("archive_index.json", hashes)

    def test_replay_cannot_relabel_known_scripted_identity_as_live(self) -> None:
        # A hash index is not external attestation. Replay must nevertheless
        # reject an internally contradictory execution-kind/model combination.
        run = json.loads((self.output / "run.json").read_text())
        run["execution_kind"] = "LIVE_MODEL"
        summary = json.loads((self.output / "summary.json").read_text())
        summary["execution_kind"] = "LIVE_MODEL"
        self._rewrite("run.json", run)
        self._rewrite("summary.json", summary)
        self._reindex()
        with self.assertRaises(runner.ExperimentError):
            runner.verify_run(self.output)

    def test_empty_reserved_directory_retains_unstarted_allocation_after_crash(self) -> None:
        branch_id = self.plan["dispatch_order"][0]
        folder = self.output / "branches" / branch_id
        shutil.rmtree(folder)
        folder.mkdir()
        # Simulate interruption after mkdir but before the start receipt. A
        # generating request cannot precede that durable receipt in this runner.
        (self.output / "summary.json").unlink()
        (self.output / "archive_index.json").unlink()
        replayed = runner.verify_run(self.output, allow_incomplete=True)
        self.assertEqual(len(replayed["branches"]), len(self.plan["dispatch_order"]))
        row = next(row for row in replayed["branches"] if row["branch_id"] == branch_id)
        self.assertEqual(row["status"], "UNSTARTED")
        self.assertIsNone(row["endpoint"])
        self.assertFalse(row["operational_completion"])
        self.assertEqual(row["actions"], [])

    def test_nonempty_directory_without_start_is_not_treated_as_unstarted(self) -> None:
        branch_id = self.plan["dispatch_order"][0]
        folder = self.output / "branches" / branch_id
        (folder / "start.json").unlink()
        (self.output / "summary.json").unlink()
        (self.output / "archive_index.json").unlink()
        with self.assertRaises(runner.ExperimentError):
            runner.verify_run(self.output, allow_incomplete=True)

    def test_initial_evidence_and_neutral_requests_differ_only_in_prespecified_seed(self) -> None:
        block = self.plan["blocks"][0]
        branches = {branch["arm"]: branch for branch in block["branches"]}
        evidence = runner.request_for(self.plan, branches["EVIDENCE"],
                                      runner.initial_messages(block, branches["EVIDENCE"]), 0)
        neutral = runner.request_for(self.plan, branches["NEUTRAL"],
                                     runner.initial_messages(block, branches["NEUTRAL"]), 0)
        self.assertNotEqual(evidence["options"]["seed"], neutral["options"]["seed"])
        evidence["options"].pop("seed")
        neutral["options"].pop("seed")
        self.assertEqual(runner.canonical(evidence), runner.canonical(neutral))
        self.assertNotIn("EVIDENCE", evidence["messages"][0]["content"])
        self.assertNotIn("NEUTRAL", evidence["messages"][0]["content"])

    def test_unencodable_attempt_is_behavioral_invalid_without_aborting_run(self) -> None:
        class SurrogateTransport(runner.DemoTransport):
            def send(self, request_bytes: bytes, *, endpoint: str) -> bytes:
                # Both JSON documents are UTF-8 bytes. The decoded action's
                # source contains a lone surrogate, which cannot be persisted
                # by the runner's UTF-8 canonical serializer.
                content = json.dumps({"action": "attempt", "source": "\ud800"})
                return runner.canonical({
                    "model": runner.DEMO_MODEL["name"], "done": True,
                    "message": {"role": "assistant", "content": content},
                })

        result = runner.run_plan(
            self.plan, Path(self.temporary.name) / "malformed-source-run", SurrogateTransport(),
            execution_kind="SCRIPTED_HARNESS_CHECK",
        )
        self.assertEqual(len(result["branches"]), 4)
        for row in result["branches"]:
            self.assertEqual(row["status"], "COMPLETED")
            self.assertTrue(row["unresolved_invalid"])
            self.assertFalse(row["operational_completion"])
            self.assertEqual([action["action"] for action in row["actions"]], ["invalid", "invalid"])


if __name__ == "__main__":
    unittest.main()

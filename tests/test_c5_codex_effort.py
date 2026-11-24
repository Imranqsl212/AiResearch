"""Offline fixtures for the effort matrix; no model or cloud call is made."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments import c5_codex_effort as study
from tests.test_c5_cli_pilot import codex_result


class CodexEffortTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/"run"
        catalog = {"models":[{"visibility":"list","slug":slug,
                              "supported_reasoning_levels":[{"effort":"low"},{"effort":"high"}]}
                             for slug in ("gpt-a","gpt-b")]}
        catalog["models"].append({"visibility":"hide","slug":"gpt-reserve"})
        path = Path(self.temp.name)/"catalog.json"
        path.write_text(json.dumps(catalog))
        launcher = Path(self.temp.name)/"fixture-codex"
        launcher.write_text("offline fixture")
        with (patch.object(study.shutil,"which",return_value=str(launcher)),
              patch.object(study.subprocess,"check_output",return_value="codex-cli 0.0.0"),
              patch.object(study.subprocess,"run") as auth):
            auth.return_value.stdout="Logged in using ChatGPT"
            auth.return_value.stderr=""
            study.freeze(self.root,path)

    def fake(self,argv,prompt,folder,provider,timeout):
        view=json.loads(prompt.split(b"OBSERVATION\n")[1])
        action={"action":"stop","payload":{}} if view["history"] else {"action":"check","payload":{}}
        data=codex_result(json.dumps(action))
        study.pilot.write(folder/"stdout.bin",data)
        study.pilot.write(folder/"stderr.bin",b"")
        return {"returncode":0,"error":None,"stdout_sha256":study.pilot.sha(data),
                "stderr_sha256":study.pilot.sha(b""),"elapsed_seconds":1.2}

    def test_frozen_pairing_complete_and_effort_communicated_to_cli_only(self):
        plan,_=study.load(self.root)
        self.assertEqual(len(plan["episodes"]),32)
        config_order={}
        for wave in range(1,9):
            rows=[ep for ep in plan["episodes"] if ep["wave"]==wave]
            self.assertEqual(len(rows),4)
            self.assertEqual({r["model"] for r in rows},{"gpt-a","gpt-b"})
            for model in ("gpt-a","gpt-b"):
                left,right=[r for r in rows if r["model"]==model]
                self.assertNotEqual(left["effort"],right["effort"])
                self.assertEqual(left["case_id"],right["case_id"])
                self.assertEqual(study.prompt_for(plan,left,left["initial_candidate"],[]),
                                 study.prompt_for(plan,right,right["initial_candidate"],[]))
                config_order.setdefault(model,[]).append(left["effort"])
                self.assertIn(f'model_reasoning_effort="{left["effort"]}"',study.command("codex",model,left["effort"]))
        self.assertTrue(all(levels.count("high")==4 for levels in config_order.values()))

    def test_fixture_replay_resume_tamper_and_usage(self):
        with patch.object(study.pilot,"_launch",side_effect=self.fake) as transport:
            study.run(self.root,workers=2,max_episodes=2)
            self.assertEqual(transport.call_count,4)
            study.run(self.root,workers=2,max_episodes=1)
            self.assertEqual(transport.call_count,6)
        result=study.verify_archive(self.root)
        completed=[row for row in result["episodes"] if row["status"]=="COMPLETED"]
        self.assertEqual(len(completed),3)
        for row in completed:
            first,second=row["events"]
            self.assertEqual([first["action"],second["action"]],["check","stop"])
            self.assertEqual(first["usage"]["input_tokens"],10)
            self.assertIsNone(first["usage"]["reasoning_output_tokens"])
            self.assertEqual(first["duration_seconds"],1.2)
            self.assertTrue(first["same_candidate"])
        path=next(self.root.rglob("prompt.bin"))
        path.write_bytes(b"wrong")
        with self.assertRaisesRegex(ValueError,"frozen inputs"):
            study.verify_archive(self.root)

    def test_auth_and_model_failures_have_different_scope(self):
        def rejection(argv,prompt,folder,provider,timeout):
            data=b'{"type":"turn.failed","error":{"message":"Model not supported when using ChatGPT"}}'
            study.pilot.write(folder/"stdout.bin", data)
            study.pilot.write(folder/"stderr.bin", b"")
            return {"returncode":1,"error":None,"stdout_sha256":study.pilot.sha(data),
                    "stderr_sha256":study.pilot.sha(b""),"elapsed_seconds":0.1}
        with patch.object(study.pilot,"_launch",side_effect=rejection) as transport:
            summary=study.run(self.root,workers=2)
            self.assertEqual(len(summary["unavailable_configurations"]),4)
            self.assertEqual(transport.call_count,4)
        rows=study.verify_archive(self.root)["episodes"]
        self.assertEqual(sum(r["status"]=="TECHNICAL_INVALID" for r in rows),4)
        self.assertEqual(sum(r["status"]=="UNSTARTED" for r in rows),28)
        self.assertTrue(all(r["terminal_correct"] is None for r in rows))
        self.assertEqual(study.failure_kind(["HTTP 401: Unauthorized"],"CLI_FAILURE"),"ACCOUNT_AUTH")
        self.assertEqual(study.failure_kind(["You have hit your usage limit"],"CLI_FAILURE"),"ACCOUNT_QUOTA")

    def test_account_quota_stops_fresh_dispatch_until_operator_resumes(self):
        def quota(argv, prompt, folder, provider, timeout):
            data = b'{"type":"turn.failed","error":{"message":"You have reached your usage limit"}}'
            study.pilot.write(folder/"stdout.bin", data)
            study.pilot.write(folder/"stderr.bin", b"")
            return {"returncode":1, "error":None, "stdout_sha256":study.pilot.sha(data),
                    "stderr_sha256":study.pilot.sha(b""), "elapsed_seconds":0.2}
        with patch.object(study.pilot,"_launch",side_effect=quota) as transport:
            self.assertEqual(study.run(self.root,workers=1)["status"], "ACCOUNT_OR_NETWORK_HALTED")
            self.assertEqual(transport.call_count,1)
            self.assertTrue(study.run(self.root,workers=1)["need_resume_after_access_restored"])
            self.assertEqual(transport.call_count,1)
        with patch.object(study.pilot,"_launch",side_effect=self.fake) as transport:
            study.run(self.root,workers=1,max_episodes=1,resume_account=True)
            self.assertEqual(transport.call_count,2)
        rows=study.verify_archive(self.root)["episodes"]
        self.assertEqual([r["status"] for r in rows[:3]],["TECHNICAL_INVALID","COMPLETED","UNSTARTED"])

    def test_concurrent_collectors_cannot_share_reservations(self):
        with (self.root/".run.lock").open("a+b") as lock, patch.object(study.pilot,"_launch") as transport:
            study.fcntl.flock(lock,study.fcntl.LOCK_EX | study.fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                study.run(self.root,workers=1)
            transport.assert_not_called()

    def test_interrupted_reservation_never_replaced(self):
        with patch.object(study.pilot,"_launch",side_effect=RuntimeError("offline fixture")):
            with self.assertRaises(RuntimeError):
                study.run(self.root,workers=1,max_episodes=1)
        path=next(self.root.rglob("start.json"))
        old=path.read_bytes()
        with patch.object(study.pilot,"_launch",side_effect=self.fake):
            study.run(self.root,workers=1,max_episodes=1)
        self.assertEqual(old,path.read_bytes())
        rows=study.verify_archive(self.root)["episodes"]
        self.assertEqual(sum(r["status"]=="TECHNICAL_INVALID" for r in rows),1)
        self.assertEqual(sum(r["status"]=="COMPLETED" for r in rows),1)


if __name__=="__main__":
    unittest.main()

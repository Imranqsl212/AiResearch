import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments import c5_effort_panel as panel


class EffortPanelTests(unittest.TestCase):
    def test_oracle_anchors_controls_and_prompt(self):
        cards, expected = panel.material()
        self.assertEqual(expected, {"A":[13,16,17], "B":[4,4,5], "C":[8,7,4],
                                    "D":[1,2,1], "E":[-2,4,-3,2,4], "F":[5,4,0]})
        self.assertEqual({c["id"] for c in cards if c["candidate_outputs_in_input_order"] != expected[c["id"]]},
                         {"A","C","F"})
        self.assertTrue(all(c["checker_verdict"] == "FAIL" for c in cards))
        self.assertNotIn(b"starting_correct", panel.make_prompt())
        self.assertEqual(panel.oracle("A", [[1,2,1],[2,3,2]]),3)
        self.assertEqual(panel.oracle("B", [[0,2],[0,2],[0,1],[2,1]]),3)
        self.assertEqual(panel.oracle("C", [[0,0,0],0]),8)
        self.assertEqual(panel.oracle("D",[1,0,1,0]),1)
        self.assertEqual(panel.oracle("E",[-7,2]),-4)
        self.assertEqual(panel.oracle("F",[2,2,2]),0)

    def test_score_distinguishes_preservation_and_rewrite(self):
        _, answers = panel.material()
        rows, conforms = panel.score(panel.canonical(answers))
        self.assertTrue(conforms)
        self.assertEqual(sum(r["final_correct"] for r in rows),6)
        self.assertEqual(sum(r["unnecessary_rewrite"] for r in rows),3)
        rows, _ = panel.score(panel.canonical({key:"keep" for key in panel.TASKS}))
        self.assertEqual(sum(r["final_correct"] for r in rows),3)
        self.assertFalse(any(r["unnecessary_rewrite"] for r in rows))
        with_change = {key:"keep" for key in panel.TASKS}
        with_change["F"] = [True,4,0]
        rows, conforms = panel.score(panel.canonical(with_change))
        self.assertFalse(conforms)
        self.assertEqual(sum(r["valid"] for r in rows),5)
        self.assertIsNone(rows[-1]["final_correct"])
        self.assertIsNone(rows[-1]["unnecessary_rewrite"])

    def test_roster_covers_visible_models_first(self):
        catalog = {"models":[{"slug":f"gpt-z{i}","visibility":"list",
                              "supported_reasoning_levels":[{"effort":e} for e in ("low","medium","high")]}
                             for i in range(4)] + [{"slug":"internal","visibility":"hide"}]}
        order = panel.visible_configurations(catalog)
        self.assertEqual(len(order),12)
        self.assertEqual(len({c["model"] for c in order[:4]}),4)
        self.assertEqual([c["effort"] for c in order[:4]],["low","high","low","high"])
        self.assertEqual(len({tuple(sorted(c.items())) for c in order}),12)
        self.assertEqual(order,panel.visible_configurations(catalog))
        self.assertIn('model_reasoning_effort="max"',panel.argv("codex","gpt-test","max"))

    def test_capture_replay_and_no_duplicate_calls(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as workspace:
            root = Path(workspace)/"run"
            models = [{"slug":"gpt-fixture","visibility":"list",
                       "supported_reasoning_levels":[{"effort":"low"},{"effort":"high"}]}]
            catalog = Path(workspace)/"catalog.json"
            catalog.write_text(json.dumps({"models":models}))
            with patch.object(panel.shutil,"which",return_value="/bin/echo"), \
                 patch.object(panel.subprocess,"check_output",return_value="codex-cli 0.0.0-test"), \
                 patch.object(panel.subprocess,"run", return_value=panel.subprocess.CompletedProcess("mock",0,"Logged in using ChatGPT","")):
                panel.freeze(root,catalog,120)
            answers = {k:"keep" if k not in panel.ALTERATIONS else values for k,values in panel.material()[1].items()}
            def fake(argv,prompt,dest,provider,timeout):
                lines = [{"type":"item.completed","item":{"type":"agent_message","text":json.dumps(answers)}},
                         {"type":"turn.completed","usage":{"input_tokens":30,"cached_input_tokens":11,
                                                          "output_tokens":21,"reasoning_output_tokens":6}}]
                raw = b"\n".join(panel.canonical(x) for x in lines)
                (dest/"stdout.bin").write_bytes(raw)
                (dest/"stderr.bin").write_bytes(b"")
                return {"returncode":0,"elapsed_seconds":1.2,"error":None,
                        "stdout_sha256":panel.pilot.sha(raw),"stderr_sha256":panel.pilot.sha(b"")}
            with patch.object(panel.pilot,"_launch",side_effect=fake) as run:
                self.assertEqual(panel.collect(root,1,1)["new_calls"],1)
                first = panel.report(root)
                self.assertEqual([r["status"] for r in first["rows"]],["RETURNED","UNSTARTED"])
                self.assertEqual(first["rows"][1]["repaired"],[0,0])
                self.assertEqual(panel.collect(root,2,None)["new_calls"],1)
                self.assertEqual(panel.collect(root,2,None)["new_calls"],0)
                self.assertEqual(run.call_count,2)
            complete = panel.report(root)
            for row in complete["rows"]:
                self.assertEqual((row["correct"],row["repaired"],row["preserved"]),(6,[3,3],[3,3]))
                self.assertEqual(row["usage"]["reasoning_output_tokens"],6)
            (next((root/"calls").glob("*"))/"stdout.bin").write_bytes(b"altered")
            with self.assertRaises(ValueError):
                panel.report(root)

    def test_quota_classification_without_text_or_invented_scores(self):
        with tempfile.TemporaryDirectory() as workspace:
            p=Path(workspace)
            (p/"stderr.bin").write_bytes(b"usage_limit_reached sensitive diagnostic")
            (p/"stdout.bin").write_bytes(b"")
            r = panel.adapt_output(p,{"returncode":1,"error":None,"elapsed_seconds":1.1,
                                       "stdout_sha256":panel.pilot.file_sha(p/"stdout.bin"),
                                       "stderr_sha256":panel.pilot.file_sha(p/"stderr.bin")})
            self.assertEqual(r["status"],"QUOTA")
            self.assertFalse(any(x["valid"] for x in r["tasks"]))
            self.assertNotIn("sensitive",json.dumps(r))


if __name__ == "__main__":
    unittest.main()

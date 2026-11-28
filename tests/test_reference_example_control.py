from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from analysis import reference_example_report as analysis
from experiments import reference_example_control as study


class ReferenceExampleTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.calibration = study.materials()

    def rows(self):
        rows = []
        for block in self.plan["blocks"]:
            for arm in block["order"]:
                target = arm[-1].upper() if arm.startswith("target_") else block["start"]
                choice = "keep" if target == block["start"] else "switch"
                rows.append({"block": block["id"], "model": block["model"], "task": block["task"],
                             "start": block["start"], "arm": arm, "status": "OK",
                             "prompt_sha256": block["prompt_sha256"][arm], "choice": choice, "after": target,
                             "assessments": analysis.assessments(self.calibration, block, arm, target)})
        return rows

    def test_source_output_is_only_change_within_revealing_pair(self):
        for block in self.plan["blocks"]:
            task, start = block["task"], block["start"]
            a = study.prompt(task, start, "target_a").splitlines()
            b = study.prompt(task, start, "target_b").splitlines()
            diffs = [(x, y) for x, y in zip(a, b) if x != y]
            self.assertEqual(len(a), len(b))
            self.assertEqual(len(diffs), 1)
            x, y = diffs[0]
            self.assertEqual(x.split(b"required output")[0], y.split(b"required output")[0])
            self.assertNotIn(b"Trusted example", study.prompt(task, start, "none"))

    def test_balanced_accuracy_ceiling_in_shared_calls_and_positive_endpoint(self):
        rows = self.rows()
        analysis.validate(rows, self.plan, self.calibration)
        result = analysis.summarize(rows)
        self.assertEqual(result["primary_bounds"], [12, 12])
        for group in ("none", "shared"):
            self.assertEqual(result["modes"][group]["correct_repair"], 0)
            self.assertEqual(result["modes"][group]["correct_preservation"], 12)
        self.assertEqual(result["modes"]["revealing"]["correct_repair"], 12)
        self.assertEqual(result["modes"]["revealing"]["correct_preservation"], 12)
        rows.pop()
        with self.assertRaises(ValueError):
            analysis.validate(rows, self.plan, self.calibration)

    def test_standalone_public_verifier_needs_no_private_capture(self):
        rows = self.rows()
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for key, value in (("plan", self.plan), ("calibration", self.calibration)):
                (directory / f"{key}.json").write_bytes(study.prior.pretty(value))
            plan_hash = sha256((directory / "plan.json").read_bytes()).hexdigest()
            result = {"plan_sha256": plan_hash, "rows": rows, "summary": analysis.summarize(rows)}
            (directory / "results.json").write_text(json.dumps(result))
            self.assertEqual(analysis.verify(directory)["primary_bounds"], [12, 12])
            result["rows"][0]["choice"] = "invalid"
            (directory / "results.json").write_text(json.dumps(result))
            with self.assertRaises(ValueError):
                analysis.verify(directory)

    def test_bounds_for_missing_with_correct_and_incorrect_opposites(self):
        rows = self.rows()
        for id_ in (self.plan["blocks"][0]["id"], self.plan["blocks"][1]["id"]):
            missing = next(r for r in rows if r["block"] == id_ and r["arm"] == "target_a")
            missing.update(status="INTERRUPTED", choice=None, after=None, assessments=[])
        opposite = next(r for r in rows if r["block"] == id_ and r["arm"] == "target_b")
        opposite["assessments"][0]["after_correct"] = False
        result = analysis.summarize(rows)
        self.assertEqual(result["primary_bounds"], [10, 11])


if __name__ == "__main__":
    unittest.main()

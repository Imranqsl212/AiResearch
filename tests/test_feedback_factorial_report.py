from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from analysis import feedback_factorial_report as analysis

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    """Scripted policy: keep if the target is hidden, otherwise select the target."""
    cal = json.loads((ROOT / "analysis/reference_example_20261128/calibration.json").read_bytes())
    blocks, rows = [], []
    for model, task, start in product(analysis.MODELS, analysis.TASKS, analysis.TARGETS):
        block_id = "_".join((model, task, start))
        block = {"id": block_id, "model": model, "task": task, "start": start, "calls": []}
        for wording, arm, targets in analysis.expected_signatures():
            call_id = f"{wording}_{arm}_{''.join(targets)}"
            digest = sha256(f"{block_id}/{call_id}".encode()).hexdigest()
            cell = {"wording": wording, "arm": arm, "targets": list(targets), "prompt_sha256": digest}
            block["calls"].append({**cell, "id": call_id})
            selected = start if len(targets) == 2 else targets[0]
            grades = [{"target": t, "before_correct": start == t, "after_correct": selected == t} for t in targets]
            rows.append({**cell, "block": block_id, "model": model, "task": task, "start": start,
                         "call_id": call_id, "status": "OK", "choice": "keep" if selected == start else "switch",
                         "after": selected, "assessments": grades})
        blocks.append(block)
    return {"blocks": blocks, "eligible_for_main_analysis": False}, cal, {"rows": rows, "eligible_for_main_analysis": False}


class FeedbackFactorialAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.cal, self.data = fixture()

    def validate(self):
        analysis.validate(self.plan, self.cal, self.data)

    def clear(self, row):
        row.update({"status": "NOT_ATTEMPTED", "choice": None, "after": None, "assessments": []})

    def test_native_denominators_and_correctly_oriented_full_contrasts(self):
        self.validate()
        summary = analysis.summarize(self.data["rows"])
        cells = [c for word in summary["cells"].values() for c in word.values()]
        self.assertEqual(sum(c["valid"] for c in cells), 168)
        self.assertEqual(sum(c["repair_scored"] + c["preservation_scored"] for c in cells), 192)
        self.assertEqual(summary["tracking"]["hidden"]["actual"]["max"], 0)
        self.assertEqual(summary["tracking"]["hidden"]["both"]["both_correct"], 12)
        self.assertEqual(summary["contrasts"]["hidden"]["actual_to_both"]["repair"]["net_bounds"], [12, 12])
        self.assertEqual(summary["contrasts"]["explicit"]["actual_to_both"]["repair"]["net_bounds"], [0, 0])
        self.assertEqual(summary["hidden_minus_explicit"]["repair"]["observed_net"], 12)
        self.assertEqual(summary["hidden_minus_explicit"]["preservation"]["observed_net"], 0)
        self.assertEqual(summary["actual_by_required"]["hidden"]["repair"]["observed_net"], 0)
        self.assertEqual(summary["actual_by_required"]["explicit"]["preservation"]["observed_net"], 0)

    def test_frozen_prompts_differ_only_in_disclosed_information(self):
        from experiments.feedback_factorial import prompt

        plan = json.loads((ROOT / "analysis/feedback_factorial_20261128/plan.json").read_bytes())
        for block in plan["blocks"]:
            task, start = block["task"], block["start"]
            base = prompt(task, start, "hidden", "none", "A").decode().splitlines()
            probe, answer_a, answer_b = self.cal[task]["shown"][1]
            self.assertIn("Diagnostic input: " + json.dumps(probe), base)
            result = {"A": answer_a, "B": answer_b}
            for call in block["calls"]:
                for target in call["targets"]:
                    arm, word = call["arm"], call["wording"]
                    data = prompt(task, start, word, arm, target)
                    self.assertEqual(sha256(data).hexdigest(), call["prompt_sha256"])
                    lines = data.decode().splitlines()
                    if word == "explicit":
                        self.assertEqual(len([line for line in lines if line.startswith("This installation requires ")]), 1)
                        lines = [line for line in lines if not line.startswith("This installation requires ")]
                    if arm in ("actual", "both"):
                        lines.remove("Actual output of the current implementation: " + json.dumps(result[start]))
                    if arm in ("required", "both"):
                        lines.remove("Required output of the target installation: " + json.dumps(result[target]))
                    self.assertEqual(lines, base)

    def test_partial_pairs_bound_the_prespecified_increment(self):
        rows = self.data["rows"]
        block = rows[0]["block"]
        actual = next(r for r in rows if r["block"] == block and r["arm"] == "actual" and r["wording"] == "hidden")
        broken = next(r for r in rows if r["block"] == block and r["arm"] == "both" and r["wording"] == "hidden"
                      and r["start"] not in r["targets"])
        broken["choice"], broken["after"], broken["assessments"][0]["after_correct"] = "keep", broken["start"], False
        self.clear(actual)
        self.validate()
        summary = analysis.summarize(rows)
        self.assertEqual(summary["tracking"]["hidden"]["actual"]["max"], 0)
        self.assertEqual(summary["tracking"]["hidden"]["both"]["max"], 11)
        repair = summary["contrasts"]["hidden"]["actual_to_both"]["repair"]
        self.assertEqual((repair["complete"], repair["net_bounds"]), (11, [10, 11]))
        self.assertEqual(summary["contrasts"]["hidden"]["actual_to_both"]["preservation"]["net_bounds"], [0, 1])

    def test_total_quota_censoring_retains_all_assignments(self):
        for row in self.data["rows"]:
            self.clear(row)
        self.validate()
        summary = analysis.summarize(self.data["rows"])
        self.assertEqual(summary["missing"], {"NOT_ATTEMPTED": 168})
        for state in analysis.STRATA:
            change = summary["contrasts"]["hidden"]["actual_to_both"][state]
            self.assertEqual((change["complete"], change["scheduled"], change["net_bounds"]), (0, 12, [-12, 12]))
            self.assertEqual(summary["hidden_minus_explicit"][state]["min"], -24)
            self.assertEqual(summary["actual_by_required"]["explicit"][state]["max"], 24)
        self.assertEqual(summary["tracking"]["hidden"]["actual"]["max"], 0)
        self.assertEqual(summary["tracking"]["hidden"]["required"]["max"], 12)

    def test_calibration_and_protocol_detect_corruptions(self):
        cases = [
            lambda p, c, r: c["round"]["held_out"][1].__setitem__(1, 70),
            lambda p, c, r: c["sort"]["checks"]["A"]["A"].__setitem__(0, 1),
            lambda p, c, r: p["blocks"][0]["calls"][0].update(targets=["A"]),
            lambda p, c, r: r["rows"][0].update(choice="switch"),
            lambda p, c, r: r["rows"][0]["assessments"][0].update(after_correct=1),
            lambda p, c, r: r["rows"].pop(),
        ]
        for mutation in cases:
            p, c, r = deepcopy((self.plan, self.cal, self.data))
            mutation(p, c, r)
            with self.assertRaises(ValueError):
                analysis.validate(p, c, r)

    def test_separate_standard_library_process_and_bound_inputs(self):
        with TemporaryDirectory() as scratch:
            path = Path(scratch)
            calibration = json.dumps(self.cal).encode()
            self.plan["calibration_sha256"] = sha256(calibration).hexdigest()
            plan = json.dumps(self.plan).encode()
            self.data["plan_sha256"] = sha256(plan).hexdigest()
            (path / "calibration.json").write_bytes(calibration)
            (path / "plan.json").write_bytes(plan)
            (path / "results.json").write_text(json.dumps(self.data))
            (path / "comparison.md").write_text(analysis.report(analysis.verify(path)))
            subprocess.run([sys.executable, "-I", "-S", analysis.__file__, str(path), "--check"], capture_output=True, check=True)
            (path / "plan.json").write_bytes(plan + b"\n")
            with self.assertRaisesRegex(ValueError, "digest"):
                analysis.verify(path)


if __name__ == "__main__":
    unittest.main()

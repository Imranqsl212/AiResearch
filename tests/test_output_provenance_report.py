from copy import deepcopy
from hashlib import sha256
import json
import unittest

from analysis import output_provenance_report as analysis


class OutputProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.cal = [json.loads((analysis.DEFAULT / f).read_bytes()) for f in ("plan.json", "calibration.json")]
        self.rows = []
        for b in self.plan["blocks"]:
            for c in b["calls"]:
                chosen = c["value_contract"] if c["label"] == "required" else b["start"]
                self.rows.append({"block": b["id"], "call_id": c["id"], "model": b["model"], "task": b["task"],
                                  "start": b["start"], **{k: c[k] for k in ("label", "value_contract", "targets", "prompt_sha256")},
                                  "status": "OK", "after": chosen, "choice": "keep" if chosen == b["start"] else "switch",
                                  "assessments": [{"target": t, "before_correct": t == b["start"], "after_correct": t == chosen}
                                                  for t in c["targets"]]})

    def validate(self):
        analysis.validate(self.plan, self.cal, {"rows": self.rows, "eligible_for_main_analysis": False})

    def test_assignments_tracking_and_native_denominators(self):
        self.validate()
        s = analysis.summarize(self.rows)
        self.assertEqual(sum(g["valid"] for g in s["cells"].values()), 448)
        self.assertEqual(sum(g[t + "_scored"] for t in analysis.STATES for g in s["cells"].values()), 768)
        self.assertEqual(s["tracking"]["anonymous"]["always_keep"], 64)
        self.assertEqual(s["tracking"]["required"]["both_aligned"], 64)
        self.assertEqual(s["tracking"]["required"]["signed_observed"], 64)
        self.assertEqual(s["tracking"]["anonymous"]["signed_observed"], 0)
        self.assertEqual(s["contrasts"]["anonymous"]["min_gain"], 64)
        self.assertEqual(s["contrasts"]["anonymous"]["max_gain"], 64)

    def test_bounded_missingness_accounts_for_known_misalignment(self):
        block = self.rows[0]["block"]
        row = next(r for r in self.rows if r["block"] == block and r["label"] == "anonymous" and r["value_contract"] == r["start"])
        row.update(status="UNSTARTED", after=None, choice=None, assessments=[])
        self.validate()
        s = analysis.summarize(self.rows)
        self.assertEqual(s["tracking"]["anonymous"]["max"], 0)
        self.assertEqual(s["tracking"]["anonymous"]["signed_min"], -1)
        self.assertEqual(s["tracking"]["anonymous"]["signed_max"], 0)
        self.assertEqual((s["contrasts"]["anonymous"]["complete"], s["contrasts"]["anonymous"]["min_gain"]), (63, 64))
        self.assertTrue(analysis.report(s).endswith("\n"))

    def test_incorrect_oracles_choices_and_repeated_calls_rejected(self):
        cal = deepcopy(self.cal)
        cal["calendar"]["diagnostic"][2] = -1
        with self.assertRaises(ValueError):
            analysis.verify_calibration(cal)
        self.rows[0]["after"] = "unknown"
        with self.assertRaises(ValueError):
            self.validate()
        self.rows.pop()
        with self.assertRaises(ValueError):
            self.validate()

    def test_identical_value_and_fixed_context_across_truthful_labels(self):
        from experiments.output_provenance import prompt
        for b in self.plan["blocks"]:
            base = prompt(b["task"], b["start"], "none", None).decode().splitlines()
            for c in b["calls"]:
                v = c["value_contract"]
                data = prompt(b["task"], b["start"], c["label"], v)
                self.assertEqual(sha256(data).hexdigest(), c["prompt_sha256"])
                if v is None:
                    continue
                lines = data.decode().splitlines()
                caption = lines.pop(-2)
                value = json.loads(caption.split(": ", 1)[1])
                self.assertEqual(value, self.cal[b["task"]]["diagnostic"][1 + (v == "B")])
                self.assertEqual(lines, base)


if __name__ == "__main__":
    unittest.main()

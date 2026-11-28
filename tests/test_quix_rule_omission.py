from hashlib import sha256
import json
import unittest

from analysis import quix_rule_omission_report as report
from experiments import quix_rule_omission as collector


class OmittedRuleTests(unittest.TestCase):
    def setUp(self):
        self.plan,self.sources,self.cal=collector.materials()
        self.old=json.loads((collector.original.PUBLIC/"plan.json").read_bytes())
        self.rows=[]
        for b in self.plan["blocks"]:
            for t in report.TARGETS:
                expr=self.cal[b["task"]]["starts"][b["start"]]["expression"]
                grade,behavior=report.named.grades(b["task"],expr,self.cal)
                self.rows.append({"block":b["id"],**{k:b[k] for k in ("task","model","start","wave")},
                                  "arm":t,"prompt_sha256":b["prompt_sha256"][t],"status":"OK","action":"keep",
                                  "expression":expr,"passed_counts":grade,"implements":behavior})

    def test_entire_prompt_diff_is_the_two_sentences(self):
        self.assertEqual(collector.prior.pretty(self.plan),(collector.PUBLIC/"plan.json").read_bytes())
        for b in self.plan["blocks"]:
            new = []
            for t in b["order"]:
                old=report.named.prompt(b,t,self.sources,self.cal)
                stripped=report.omit_rule_lines(old,b,self.cal)
                self.assertEqual(stripped,collector.prompt(b,t,self.sources,self.cal))
                self.assertEqual(sha256(stripped).hexdigest(),b["prompt_sha256"][t])
                lines=stripped.splitlines()
                self.assertFalse(any(l.startswith(b"Convention 1:") or l.startswith(b"Convention 2:") for l in lines))
                self.assertIn(b"exactly one of two documented conventions",lines[0])
                new.append([l for l in lines if not l.startswith(b"Trusted target example")])
            self.assertEqual(new[0],new[1])

    def test_pairing_missingness_and_closed_bounds(self):
        report.validate(self.plan,self.old,self.cal,self.sources,self.rows)
        lost=[dict(r) for r in self.rows]
        # A missing target already known to have a nonmatching partner cannot track both.
        i=next(i for i,r in enumerate(lost) if r["implements"]==r["arm"])
        lost[i].update(status="INVALID_EXPRESSION",action=None,expression=None,implements=None,passed_counts=None)
        report.validate(self.plan,self.old,self.cal,self.sources,lost)
        s=report.summarize(self.rows,lost,self.cal)
        self.assertEqual((s["groups"]["omitted"]["tracking"]["complete"],s["groups"]["omitted"]["tracking"]["max"]),(15,0))
        self.assertEqual(s["contrasts"]["both_targets"]["max_gain"],0)
        self.assertGreater(s["contrasts"][lost[i]["arm"]]["complete"],0)
        self.assertEqual(s["groups"]["omitted"]["statuses"]["INVALID_EXPRESSION"],1)
        self.assertTrue(report.report(s).endswith("\n"))

    def test_different_or_invalid_grade_is_rejected(self):
        self.rows[0]["implements"]="neither"
        with self.assertRaises(ValueError):
            report.validate(self.plan,self.old,self.cal,self.sources,self.rows)
        self.rows.pop()
        with self.assertRaisesRegex(ValueError,"32 scheduled"):
            report.validate(self.plan,self.old,self.cal,self.sources,self.rows)

    def test_an_expression_can_fit_the_example_and_fail_both_reference_domains(self):
        changed = [dict(r) for r in self.rows]
        row = next(r for r in changed if r["task"] == "is_valid_parenthesization" and r["arm"] == "upstream"
                   and r["implements"] == "upstream")
        row["action"], row["expression"] = "replace", "depth <= 1"
        row["passed_counts"], row["implements"] = report.named.grades(row["task"], row["expression"], self.cal)
        self.assertEqual(row["implements"], "neither")
        report.validate(self.plan, self.old, self.cal, self.sources, changed)
        s = report.summarize(self.rows, changed, self.cal)["groups"]
        self.assertEqual(s["named"]["targets"]["upstream"]["witness_only"], 0)
        self.assertEqual(s["omitted"]["targets"]["upstream"]["witness_only"], 1)


if __name__=="__main__":
    unittest.main()

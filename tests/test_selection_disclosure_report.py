from hashlib import sha256
import json
import unittest

from analysis import selection_disclosure_report as report
from experiments import selection_disclosure as collector


class SelectionDisclosureTests(unittest.TestCase):
    def setUp(self):
        self.plan,self.cal=[json.loads((report.DEFAULT/p).read_bytes()) for p in ("plan.json","calibration.json")]
        p=report.DEFAULT.parent/"output_provenance_20261128"/"plan.json"
        self.parent=json.loads(p.read_bytes())
        self.rows=[]
        for block in self.plan["blocks"]:
            for c in block["calls"]:
                chosen=block["start"] if c["label"]=="disclosed" else c["value_contract"]
                self.rows.append({"block":block["id"], "call_id":c["id"], **{k:block[k] for k in ("task","model","start")},
                                  **{k:c[k] for k in ("label","value_contract","targets","prompt_sha256")},
                                  "choice":"keep" if chosen==block["start"] else "switch", "after":chosen, "status":"OK",
                                  "assessments":[{"target":t,"before_correct":t==block["start"],"after_correct":t==chosen}
                                                 for t in report.parent.TARGETS]})

    def test_fixed_byte_difference_and_primary_contrasts(self):
        report.validate(self.plan,self.parent,self.cal,self.rows)
        for b in self.plan["blocks"]:
            for c in b["calls"]:
                p=collector.prompt(b["task"],b["start"],c["label"],c["value_contract"])
                self.assertEqual(sha256(p).hexdigest(),c["prompt_sha256"])
                if c["label"]=="disclosed":
                    self.assertEqual(p.count(self.plan["disclosure"].encode()),1)
                    original=collector.prompt(b["task"],b["start"],"anonymous",c["value_contract"])
                    self.assertEqual(p.replace((self.plan["disclosure"]+"\n").encode(),b""),original)
        s=report.summarize(self.rows)
        self.assertEqual((s["paired"]["only_anonymous"],s["paired"]["only_disclosed"],s["paired"]["signed_diff"]),(8,0,-8))
        self.assertEqual(sum(g["valid_calls"] for g in s["cells"].values()),32)
        self.assertEqual(sum(g["preserve_scored"]+g["repair_scored"] for g in s["cells"].values()),64)

    def test_incomplete_paired_and_signed_bounds(self):
        selected=next(r for r in self.rows if r["label"]=="anonymous")
        selected.update(status="UNSTARTED",choice=None,after=None,assessments=[])
        report.validate(self.plan,self.parent,self.cal,self.rows)
        g=report.summarize(self.rows)["paired"]
        self.assertEqual((g["complete"],g["min_gain"],g["max_gain"]),(7,-8,-7))
        self.assertEqual((g["signed_diff_min"],g["signed_diff_max"]),(-8,-7))

    def test_changed_source_and_missing_assignment_fail(self):
        self.rows[0]["choice"]="other"
        with self.assertRaises(ValueError):
            report.validate(self.plan,self.parent,self.cal,self.rows)
        self.rows.pop()
        with self.assertRaises(ValueError):
            report.validate(self.plan,self.parent,self.cal,self.rows)


if __name__=="__main__":
    unittest.main()

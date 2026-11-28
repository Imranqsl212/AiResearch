import json
import unittest
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from analysis import production_patch_report as study


class ProductionPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((study.DEFAULT/'sources.json').read_bytes())
        cls.cal=study.calibration(cls.source)

    def test_native_and_maintainer_examples(self):
        study.check_native(self.cal,json.loads((study.DEFAULT/'upstream_check.json').read_bytes()))
        self.assertEqual([self.cal[n]['starts']['faulty']['passed'] for n in study.NAMES],[58,17])
        self.assertEqual(self.cal['matplotlib']['starts']['faulty']['upstream_example']['output'],[.7,.3])
        self.assertEqual(self.cal['tqdm']['starts']['working']['upstream_example']['output'][0],[42,0])
        for n in study.NAMES:
            self.assertNotIn(study.ORIGINAL_TEST[n],study.cases(n))

    def test_authored_iterator_must_preserve_progress(self):
        cases=self.cal['tqdm']['held']
        self.assertTrue(all(study.grade('tqdm','enumerate(tqdm_class(iterable, **tqdm_kwargs), start=start)',cases)))
        self.assertFalse(any(study.grade('tqdm','enumerate(iterable, start)',cases)))
        self.assertFalse(any(study.grade('tqdm','enumerate(tqdm_class(iterable), start)',cases)))

    def test_bounds_and_counterexamples(self):
        cases=self.cal['matplotlib']['held']
        self.assertTrue(all(study.grade('matplotlib','max(vmax, oldmin, vmin), min(vmax, oldmax, vmin)',cases)))
        self.assertFalse(all(study.grade('matplotlib','(oldmin, oldmax)',cases)))
        for n,s in [('matplotlib','(os.getenv("X"), oldmax)'),('matplotlib','(oldmin, oldmax, 1)'),('tqdm','foo(iterable)'),('tqdm','iterable[0]')]:
            with self.assertRaises(study.base.Rejected):
                study.evaluator(n,s)

    def test_missingness_and_tampering(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)
            for f in ('sources','calibration','plan','upstream_check'):
                (path/(f+'.json')).write_bytes((study.DEFAULT/(f+'.json')).read_bytes())
            raw=(path/'plan.json').read_bytes()
            rows=[]
            for b in json.loads(raw)['blocks']:
                for arm in b['order']:
                    rows.append(dict(block=b['id'],arm=arm,**{k:b[k] for k in ('task','start','wave','model')},
                                     prompt_sha256=b['prompt_sha256'][arm],status='UNSTARTED',action=None,
                                     expression=None,passes=None,passed_count=None))
            data=dict(rows=rows,plan_sha256=sha256(raw).hexdigest(),summary=study.base.summarize(rows,self.cal))
            ledger=path/'results.json'
            ledger.write_text(json.dumps(data))
            self.assertIn('UNSTARTED 24',study.verify(path))
            rows[0]['passes']=True
            ledger.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                study.verify(path)

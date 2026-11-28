from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experiments import feedback_factorial as core
from experiments import output_provenance as reserve


class MatchedPromptTests(unittest.TestCase):
    def test_removing_only_assigned_output_lines(self):
        plan, _ = core.materials()
        for block in plan['blocks']:
            task, start = block['task'], block['start']
            for wording in ('hidden', 'explicit'):
                for target in ('A','B'):
                    both = core.prompt(task,start,wording,'both',target).splitlines()
                    for arm in core.ARMS:
                        expected = [line for line in both
                                    if (arm in ('actual','both') or not line.startswith(b'Actual output'))
                                    and (arm in ('required','both') or not line.startswith(b'Required output'))]
                        self.assertEqual(expected, core.prompt(task,start,wording,arm,target).splitlines())
            for call in block['calls']:
                if len(call['targets']) == 2:
                    self.assertEqual(call['wording'], 'hidden')
                    self.assertEqual(core.prompt(task,start,'hidden',call['arm'],'A'),
                                     core.prompt(task,start,'hidden',call['arm'],'B'))

    def test_labels_leave_value_and_surrounding_prompt_identical(self):
        plan, _ = reserve.materials()
        for block in plan['blocks']:
            task, start = block['task'], block['start']
            for value in ('A','B'):
                by_label = {label:reserve.prompt(task,start,label,value).splitlines() for label in reserve.LABELS}
                base = by_label['required']
                for lines in by_label.values():
                    self.assertEqual(lines[:-2] + lines[-1:], base[:-2] + base[-1:])
                    self.assertEqual(lines[-2].split(b': ',1)[1], base[-2].split(b': ',1)[1])
                self.assertNotIn(b'current',by_label['anonymous'][-2])
                producer = b'current' if start == value else b'alternative'
                self.assertIn(producer,by_label['named'][-2])

    def test_reserve_balanced_in_every_panel_of_eight(self):
        plan, _ = reserve.materials()
        for wave in range(1,9):
            blocks = [b for b in plan['blocks'] if b['wave'] == wave]
            self.assertEqual(len({b['task'] for b in blocks}), 8)
            self.assertEqual(Counter(b['start'] for b in blocks), {'A':4,'B':4})
            self.assertEqual(set(Counter(b['model'] for b in blocks).values()), {2})
        self.assertEqual(len({(b['model'],b['task'],b['start']) for b in plan['blocks']}), 64)

    def test_unattempted_and_interrupted_assignments_have_no_scores(self):
        for study in (core, reserve):
            plan, cal = study.materials()
            block = plan['blocks'][0]
            with TemporaryDirectory() as root:
                path = Path(root)/'call'
                for status in ('UNSTARTED','INTERRUPTED'):
                    row = study.outcome(block,block['calls'][0],path,cal,{})
                    self.assertEqual(row['status'],status)
                    self.assertEqual(row['assessments'],[])
                    self.assertIsNone(row['choice'])
                    path.mkdir(exist_ok=True)

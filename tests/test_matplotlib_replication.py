from collections import Counter
import unittest

from analysis import matplotlib_replication_report as study
from experiments import matplotlib_replication as runner


class MatplotlibReplication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.data = runner.materials()
        cls.cal = cls.data['calibration.json']

    def test_balanced_replicates_share_original_prompt_bytes(self):
        cells = self.manifest['assignments']
        self.assertEqual(len({r['id'] for r in cells}), 24)
        self.assertEqual(set(Counter(r['prompt_sha256'] for r in cells).values()), {4})
        self.assertEqual(len({r['prompt_sha256'] for r in cells}), 6)
        expected = {(st, arm) for st in study.STATES for arm in study.original.ARMS}
        for wave in range(1, 5):
            self.assertEqual({(r['start'], r['arm']) for r in cells if r['wave'] == wave}, expected)
        for r in cells:
            self.assertEqual(study.digest(runner.prompt_for(r, self.data)), r['prompt_sha256'])

    def test_mixed_probe_discriminates_three_possible_axis_programs(self):
        good = self.cal['matplotlib']['starts']['working']['expression']
        old = self.cal['matplotlib']['starts']['faulty']['expression']
        new = '(max(oldmin, min(vmin,vmax)), min(oldmax, max(vmin,vmax)))'
        self.assertEqual([study.replay_probes(expr, 'working', self.cal)['mixed']['output'] for expr in (good, old, new)],
                         [[8, 0], [7, 0], [8, 2]])
        row = {'status': 'OK', 'arm': 'revealing', 'start': 'working'}
        row['grade'] = study.grade('replace', new, row, self.cal)
        counts = study.summarize([row])['working']['revealing']
        self.assertEqual(counts['shared_catches_revealing_and_maintainer_miss'], 1)
        self.assertEqual(counts['shown_and_maintainer_accept_failure'], 1)
        self.assertEqual(counts['mixed_catches_failure'], 1)
        self.assertEqual(counts['passes'], 0)

    def test_missing_status_and_original_output_are_distinct(self):
        old = self.cal['matplotlib']['starts']['faulty']['expression']
        row = {'status': 'OK', 'arm': 'revealing', 'start': 'faulty'}
        row['grade'] = study.grade('keep', old, row, self.cal)
        unscored = {'status': 'INVALID_RESPONSE', 'arm': 'revealing', 'start': 'faulty', 'grade': None}
        counts = study.summarize([row, unscored])['faulty']['revealing']
        self.assertEqual(counts['valid'], 1)
        self.assertEqual(counts['scheduled'], 2)
        self.assertEqual(counts['reproduces_starting_display_despite_failure'], 1)
        self.assertEqual(counts['shown_contract_accepts_failure'], 0)

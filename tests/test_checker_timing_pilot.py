import unittest
from collections import Counter, defaultdict

from experiments import checker_timing_pilot as pilot


class TimingAssignmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards = pilot.read(pilot.PUBLIC / 'calibration.json')
        cls.plan = pilot.read(pilot.PUBLIC / 'plan.json')

    def test_each_pair_differs_only_in_first_diagnostic(self):
        by_block = defaultdict(dict)
        for row in self.plan['episodes']:
            key = tuple(row[k] for k in ('model', 'case', 'state', 'repeat'))
            self.assertNotIn(row['timing'], by_block[key])
            by_block[key][row['timing']] = row
        self.assertEqual(len(by_block), 16)
        first_in_pair = Counter()
        for key, pair in by_block.items():
            self.assertEqual(set(pair), {'early', 'late'})
            a, b = pair['early'], pair['late']
            first_in_pair[key[:3],next(iter(pair))] += 1
            card = self.cards[a['case']]
            early, menu = pilot.prompt(card, a)
            late, other_menu = pilot.prompt(card, b)
            self.assertEqual(menu, other_menu)
            observation = card['variants'][a['start_variant']]['diagnostic'].encode()
            self.assertEqual(early.count(observation), 1)
            self.assertNotIn(observation, late)
            self.assertEqual(early.replace(observation, b'The independent measurement will be shown after this choice.'), late)
        self.assertEqual(set(first_in_pair.values()), {1})

    def test_second_decision_observes_initial_code_after_any_edit(self):
        for row in self.plan['episodes']:
            card = self.cards[row['case']]
            start = row['start_variant']
            initial = card['variants'][start]['diagnostic'].encode()
            for label, dest in row['options'].items():
                if dest == start:
                    continue
                message, menu = pilot.prompt(card, row, {'choice':label, 'after_variant':dest})
                self.assertIn(initial, message)
                self.assertIn(card['variants'][dest]['snippet'].encode(), message)
                if card['variants'][dest]['diagnostic'].encode() != initial:
                    self.assertNotIn(card['variants'][dest]['diagnostic'].encode(), message)
                self.assertNotIn(label, menu)
                self.assertIn('keep', menu)

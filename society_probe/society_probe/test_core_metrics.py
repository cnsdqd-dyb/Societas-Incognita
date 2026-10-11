"""Evidence-boundary regression tests, run with python -m unittest test_core_metrics."""
import copy
import unittest
from core_metrics import measure, jsd_counts


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {'tools': ['gather', 'wait', 'attack'], 'world': {'mini_world': {}}}
        self.state = {'round': 3, 'agents': {'a': {}, 'b': {}}, 'mini_world': {},
                      'culture': {'artifacts': {}, 'play_records': []},
                      'social_content': {'work_events': [], 'games': {}, 'game_events': []},
                      'events': [{'round': r, 'agent': i, 'decision': {'action': {'tool': 'gather'}},
                                  'outcome': {}} for r in range(1, 4) for i in ['a', 'b']],
                      'snapshots': [{'round': r, 'agents': {i: {'alive': True, 'stock': 1} for i in ['a', 'b']}}
                                    for r in range(1, 4)]}

    def metrics(self):
        return measure(self.state, self.cfg)['round_series'][-1]['metrics']

    def test_known_absence_and_no_source_mutation(self):
        before = copy.deepcopy(self.state)
        m = self.metrics()
        self.assertEqual(m['resource_turnover']['value'], 0)
        self.assertEqual(m['harmful_action_rate']['value'], 0)
        self.assertEqual(m['damage_recovery_rate']['status'], 'not_applicable')
        self.assertEqual(m['cross_member_reuse_count']['value'], 0)
        self.assertEqual(self.state, before)

    def test_unknown_or_conflict_action_abstains(self):
        self.state['events'][0]['decision']['action']['tool'] = 'attack'
        self.assertIsNone(self.metrics()['harmful_action_rate']['value'])
        self.assertIsNone(self.metrics()['resource_turnover']['value'])

    def test_incomplete_logs_abstain(self):
        self.state['events'].pop()
        self.assertIsNone(self.metrics()['resource_turnover']['value'])

    def test_no_assets_does_not_divide_zero(self):
        for s in self.state['snapshots']:
            for a in s['agents'].values():
                a['stock'] = 0
        self.assertIsNone(self.metrics()['resource_turnover']['value'])

    def test_sample_threshold_and_jsd(self):
        rows = measure(self.state, self.cfg)['round_series']
        self.assertIsNone(rows[0]['metrics']['behavioral_divergence']['value'])
        self.assertEqual(rows[-1]['metrics']['behavioral_divergence']['value'], 0)
        self.assertEqual(jsd_counts({'a': 1}, {'b': 1}), 1)

    def test_objects_without_reuse_evidence_abstain(self):
        self.state['culture']['artifacts'] = {'w1': {'author': 'a'}}
        self.assertIsNone(self.metrics()['cross_member_reuse_count']['value'])

    def test_future_events_excluded(self):
        self.state['events'].append({'round': 4, 'agent': 'a', 'decision': {'action': {'tool': 'attack'}}, 'outcome': {}})
        self.assertEqual(self.metrics()['harmful_action_rate']['value'], 0)


if __name__ == '__main__':
    unittest.main()

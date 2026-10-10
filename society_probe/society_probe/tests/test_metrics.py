import copy
import json
import math
import unittest
from pathlib import Path
from sim import Society, API, survey
from metrics import gini, measure, graph_summary
from make_matrix import matrix

BASE = json.loads(Path('configs/smoke.json').read_text())


class ResearchMeasurements(unittest.TestCase):
    def test_concentration_and_empty_graph_do_not_imply_organization(self):
        self.assertEqual(gini([1,1,1,1]), 0)
        self.assertEqual(gini([4,0,0,0]), .75)
        self.assertIsNone(gini([0,0]))
        graph = graph_summary([], ['a0','a1'])
        self.assertEqual(graph['isolated_members'], 2)
        self.assertIsNone(graph['reciprocity'])

    def test_surprisal_no_future_leakage_and_invalid_separation(self):
        s = Society(BASE)
        def event(t, tool, invalid=False):
            return {'round':t, 'agent':'a0', 'decision':{'action':{'tool':tool}},
                    'outcome':{'action_error':'bad'} if invalid else {'action':{}}}
        s.state['events'] = [event(1,'wait'), event(2,'wait'), event(3,'bad',True)]
        old = measure(s.state, BASE)['behavior_surprisal']
        self.assertEqual(old[0]['bits'], math.log2(len(BASE['tools'])))
        self.assertLess(old[1]['bits'], old[0]['bits'])
        s.state['events'].append(event(4,'harvest'))
        self.assertEqual(old, measure(s.state, BASE)['behavior_surprisal'][:2])

    def test_survey_is_private_and_does_not_assume_organization(self):
        from unittest.mock import patch
        s = Society(BASE)
        before = copy.deepcopy(s.observe('a0'))
        self.assertEqual(before['resource_zones'][0], {'zone_id':0, 'stock':8})
        api = API(BASE, '.', mock=True)
        survey(s, api)
        self.assertEqual(before, s.observe('a0'))
        fake = api.script('survey', {})
        fake['organization_exists'] = False
        fake['peer_recognition'] = {'a0':3, 'a1':4}
        with patch.object(api, 'request', return_value=fake):
            survey(s,api)
        answer = s.state['surveys'][-1]
        self.assertEqual(answer['responses']['organization_approval'], 3)
        self.assertIsNone(answer['effective_responses']['organization_approval'])
        self.assertTrue(answer['quality_flags'])
        self.assertEqual(s.state['surveys'][-4]['effective_responses']['peer_recognition'], {'a1':4})
        self.assertEqual(s.state['surveys'][-4]['responses']['peer_recognition']['a0'], 3)

    def test_factorial_pairs_and_feasibility(self):
        configs = matrix(BASE, [7], 'model-a', 'model-b', rounds=6)
        self.assertEqual(len(configs), 12)
        a = configs['mixed_p0_basic_s7']; b = configs['mixed_p1_basic_s7']
        wa, wb = copy.deepcopy(a['world']), copy.deepcopy(b['world'])
        wa.pop('survival_pressure'); wb.pop('survival_pressure')
        self.assertEqual(wa, wb)
        self.assertEqual(a['models'], b['models'])
        self.assertGreaterEqual(b['research_reference']['base_sustainable_throughput'],
                                b['research_reference']['total_consumption_demand'])


if __name__ == '__main__': unittest.main()

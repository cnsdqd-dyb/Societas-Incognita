import copy
import json
import unittest

import composed_certificates
import mini_world
import property_rules
import sim
import world_rule_engine
import world_rule_library as library
from test_mini_world import config, endow, settle


def configured():
    cfg = config(pressure=False)
    cfg['world']['initial_personal_stock'] = 20
    cfg['world']['mini_world']['definition'] = property_rules.install(mini_world.spec(cfg), 19)[0]
    return cfg


class PropertyRulesTests(unittest.TestCase):
    def test_boolean_conjunction_disjunction_negation(self):
        formula = {'and': [{'eq': ['x', 1]}, {'or': [{'eq': ['y', 2]}, {'not': {'eq': ['z', 3]}}]}]}
        self.assertTrue(property_rules.truth(formula, {'x': 1, 'y': 0, 'z': 4}))
        self.assertFalse(property_rules.truth(formula, {'x': 0, 'y': 2, 'z': 4}))
        with self.assertRaises(ValueError):
            property_rules.truth({'eq': ['missing', 1]}, {})

    def test_initial_evidence_and_private_property_description_hide_formulas(self):
        cfg = configured(); s = sim.Society(cfg)
        obs = s.observe('a0')['environment']
        a = next(x for x in obs['material_catalog'] if x['item'] == 'A')
        self.assertIn('sample_observation', a)
        self.assertTrue(obs['stations'][0]['observations'])
        self.assertNotIn('world_state', obs)
        self.assertIn('world_observations', obs)
        self.assertEqual(obs['your_material_knowledge'], {})
        s.act('a0', {'tool': 'gather', 'item': 'A', 'amount': 1})
        owned = s.observe('a0')['environment']['your_material_knowledge']['A']
        self.assertEqual(owned['observations'][0], a['sample_observation'])
        self.assertNotIn('properties', owned)
        text = json.dumps(s.observe('a0'))
        for secret in ('observable_properties', 'property_rules', '"when"', '"recipes"', '"slots"'):
            self.assertNotIn(secret, text)
        self.assertEqual(s.observe('a1')['environment']['your_material_knowledge'], {})

    def test_unbalanced_inputs_return_excess_and_keep_energy_budget(self):
        cfg = configured(); s = sim.Society(cfg)
        endow(s, A=.0025, B=8)
        s.state['round'] = 1
        s.act('a0', {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine',
            'inputs': [{'item': 'A', 'amount': .0025}, {'item': 'B', 'amount': 8}], 'batches': 1})
        settle(s)
        record = s.state['environment_history'][-1]['completed_experiments'][0]
        self.assertGreater(record['produced']['C'], 0)
        self.assertAlmostEqual(record['consumed_inputs']['A'], .0025)
        self.assertAlmostEqual(record['consumed_inputs']['B'], .00125)
        self.assertAlmostEqual(record['returned_inputs']['B'], 7.99875)
        self.assertAlmostEqual(mini_world.accounting(cfg, s.state)['residual'], 0, places=8)

    def test_wrong_device_returns_all_inputs_without_false_consumption(self):
        cfg = configured(); s = sim.Society(cfg); endow(s, A=1, B=1)
        s.state['round'] = 1
        s.act('a0', {'tool': 'experiment', 'facility': 'F0', 'mode': 'compress',
            'inputs': [{'item': 'A', 'amount': 1}, {'item': 'B', 'amount': 1}], 'batches': 1})
        settle(s)
        r = s.state['environment_history'][-1]['completed_experiments'][0]
        self.assertEqual(r['consumed_inputs'], {})
        self.assertEqual(r['returned_inputs'], {'A': 1., 'B': 1.})
        self.assertEqual(r['produced'], {})

    def test_disjunctive_property_substitution_is_executable(self):
        cfg = configured(); d = mini_world.spec(cfg)
        # The second disjunct permits a porous, neutral sample in the same band.
        d['resources']['X'] = copy.deepcopy(d['resources']['A'])
        d['resources']['X']['observable_properties'].update(direction=0, porous=True)
        d['recipes'], _ = property_rules.compile_rules(d)
        for facility,f in d['facilities'].items():
            for mode in f['modes']:
                f['mode_properties'][mode]['sample_responses'] = [[d['resources'][k]['observable_properties'] for k in r['inputs']]
                    for r in d['recipes'] if r['facility'] == facility and r['mode'] == mode]
        world_rule_engine.validate(d)
        s = sim.Society(cfg); endow(s, X=1, B=1); s.state['round'] = 1
        s.act('a0', {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine',
            'inputs': [{'item': 'X', 'amount': 1}, {'item': 'B', 'amount': 1}], 'batches': 1})
        settle(s)
        self.assertGreater(s.state['agents']['a0']['inventory']['C'], 0)
        self.assertAlmostEqual(mini_world.accounting(cfg, s.state)['residual'], 0, places=8)

    def test_conflicting_and_unsatisfiable_rules_are_rejected(self):
        d = mini_world.spec(configured())
        duplicate = copy.deepcopy(d['property_rules']['reactions'][0]); duplicate['id'] = 'conflict'
        d['property_rules']['reactions'].append(duplicate)
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            property_rules.compile_rules(d)
        d = mini_world.spec(configured())
        d['property_rules']['reactions'][0]['when'] = {'and': [
            {'eq': ['slot0.band', 1]}, {'not': {'eq': ['slot0.band', 1]}}]}
        with self.assertRaisesRegex(ValueError, 'Unsatisfiable'):
            property_rules.compile_rules(d)

    def test_stale_graph_or_description_is_rejected(self):
        for field in ('graph', 'description'):
            d = mini_world.spec(configured())
            if field == 'graph':
                d['recipes'][0]['output'] = 'D'
            else:
                d['facilities']['F0']['mode_properties']['combine']['sample_responses'] = []
            with self.assertRaises(ValueError):
                world_rule_engine.validate(d)

    def test_old_certificate_compiler_refuses_new_semantics(self):
        with self.assertRaisesRegex(composed_certificates.Unsupported, 'Limiting-reagent'):
            composed_certificates.Compiler(configured())

    def test_new_world_keeps_dynamic_mathematical_mechanisms(self):
        candidate = library.with_property_rules(library.with_capabilities(library.generate(19,
            ['renewable_ecology', 'cross_feeding', 'explicit_delay', 'fatigue_repair'])))
        self.assertIn('damage', candidate['definition']['variables'])
        self.assertIn('delay_0', candidate['definition']['variables'])
        self.assertEqual(candidate['generation']['property_rule_validation']['status'], 'finite_domain_checked')
        world_rule_engine.validate(candidate['definition'])


if __name__ == '__main__':
    unittest.main()

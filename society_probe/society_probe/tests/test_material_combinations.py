import copy
import json
import tempfile
import unittest
from pathlib import Path

import composed_certificates
import material_combinations
import mini_world
import sim
import world_rule_engine
import world_rule_library as library
from test_mini_world import config, endow, settle


def configured():
    c = config(pressure=False)
    d = mini_world.spec(c)
    d['combination_functions'] = [{'id': 'repair_combo', 'name': '组合修复',
        'requires': {'C': 1, 'D': 1}, 'consume': {'C': 1, 'D': 1},
        'energy_cost': 1, 'kind': 'world_state', 'effects': {'stress': -2}}]
    d['variables']['stress']['initial'] = 6
    c['tools'].append('use_function')
    return c


def use(confirm=True):
    return {'tool': 'use_function', 'function': 'repair_combo', 'target': 'world', 'confirm': confirm}


class CombinationTests(unittest.TestCase):
    def test_private_discovery_unlocks_interface_and_survives_losing_materials(self):
        s = sim.Society(configured())
        self.assertNotIn('use_function', s.observe('a0')['available_tools'])
        endow(s, C=1, D=1)
        s.act('a0', {'tool': 'wait'})
        panel = s.observe('a0')['environment']['your_functions']['repair_combo']
        self.assertTrue(panel['available'])
        self.assertIn('use_function', s.observe('a0')['available_tools'])
        self.assertEqual(s.observe('a1')['environment']['your_functions'], {})
        self.assertNotIn('repair_combo', json.dumps(s.public_rules()))
        s.act('a0', {'tool': 'give_item', 'target': 'a1', 'item': 'D', 'amount': 1, 'note': ''})
        panel = s.observe('a0')['environment']['your_functions']['repair_combo']
        self.assertFalse(panel['available'])
        self.assertEqual(panel['missing_materials'], {'D': 1})
        s.act('a1', {'tool': 'give_item', 'target': 'a0', 'item': 'D', 'amount': 1, 'note': ''})
        self.assertTrue(s.observe('a0')['environment']['your_functions']['repair_combo']['available'])
        notices = [m for m in s.state['agents']['a0']['inbox'] if m.get('channel') == 'combination_function_disclosure']
        self.assertEqual(len(notices), 1)

    def test_cancel_is_free_confirmation_pays_and_executes(self):
        s = sim.Society(configured())
        endow(s, C=1, D=1)
        s.act('a0', {'tool': 'wait'})
        before = copy.deepcopy(s.state['agents']['a0'])
        self.assertTrue(s.act('a0', use(False))['cancelled'])
        self.assertEqual(s.state['agents']['a0'], before)
        result = s.act('a0', use())
        self.assertTrue(result['paid'])
        self.assertEqual(s.state['mini_world']['variables']['stress'], 4)
        self.assertEqual(s.state['agents']['a0']['stock'], before['stock'] - 1)
        self.assertEqual(s.state['agents']['a0']['inventory']['C'], 0)
        self.assertAlmostEqual(mini_world.accounting(s.cfg, s.state)['residual'], 0)
        self.assertFalse(s.observe('a0')['environment']['your_functions']['repair_combo']['available'])

    def test_unknown_or_unavailable_functions_fail_atomically(self):
        s = sim.Society(configured())
        before = copy.deepcopy(s.state)
        with self.assertRaisesRegex(ValueError, 'privately discovered'):
            s.act('a0', use())
        self.assertEqual(s.state, before)
        endow(s, C=1, D=1)
        s.act('a0', {'tool': 'wait'})
        s.act('a0', {'tool': 'give_item', 'target': 'a1', 'item': 'D', 'amount': 1, 'note': ''})
        before = copy.deepcopy(s.state)
        with self.assertRaisesRegex(ValueError, 'materials are missing'):
            s.act('a0', use())
        self.assertEqual(s.state, before)
        self.assertTrue(s.act('a0', use(False))['cancelled'])

    def test_split_or_escrowed_materials_do_not_unlock_and_transfer_does(self):
        s = sim.Society(configured())
        endow(s, C=1)
        endow(s, 'a1', D=1)
        s.act('a0', {'tool': 'wait'})
        self.assertEqual(s.observe('a0')['environment']['your_functions'], {})
        s.act('a0', {'tool': 'offer_items', 'target': 'a1',
                    'give': [{'item': 'C', 'amount': 1}], 'want': [{'item': 'A', 'amount': 1}]})
        s.act('a1', {'tool': 'give_item', 'target': 'a0', 'item': 'D', 'amount': 1, 'note': ''})
        self.assertEqual(s.observe('a0')['environment']['your_functions'], {})
        s.act('a0', {'tool': 'cancel_items', 'offer': 'item_offer1'})
        self.assertTrue(s.observe('a0')['environment']['your_functions']['repair_combo']['available'])

    def test_production_unlocks_before_same_round_decay(self):
        s = sim.Society(configured())
        endow(s, A=2, B=1, D=1)
        s.state['round'] = 1
        s.act('a0', {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine',
                    'inputs': [{'item': 'A', 'amount': 2}, {'item': 'B', 'amount': 1}], 'batches': 1})
        settle(s)
        panel = s.observe('a0')['environment']['your_functions']['repair_combo']
        self.assertEqual(panel['source'], 'production')
        self.assertFalse(panel['available'])
        restored = sim.Society(s.cfg)
        restored.state = json.loads(json.dumps(s.state))
        self.assertEqual(s.observe('a0'), restored.observe('a0'))

    def test_unimplemented_effects_rejected_and_seeded_catalog_reproducible(self):
        c = configured()
        mini_world.spec(c)['combination_functions'][0]['kind'] = 'fake_power'
        with self.assertRaisesRegex(ValueError, 'Unimplemented'):
            world_rule_engine.validate(mini_world.spec(c))
        keys = [k for k, _ in library.CANDIDATES_20]
        for seed in range(4):
            a = library.generate(seed, keys)
            self.assertEqual(a, library.generate(seed, keys))
            self.assertTrue(a['definition']['combination_functions'])

    def test_confirmation_and_cancel_compile_and_pass_lean(self):
        c = configured()
        c['rounds'] = 2
        mini_world.spec(c)['initial_inventory'] = {'C': 2, 'D': 2}
        first = {aid: {'tool': 'wait'} for aid in ('a0', 'a1', 'a2', 'a3')}
        first['a0'] = use(False)
        second = copy.deepcopy(first)
        second['a0'] = use(True)
        with tempfile.TemporaryDirectory() as folder:
            artifact = composed_certificates.export(c, [first, second], Path(folder)/'combo.lean', semantic=True)
            checked = composed_certificates.check(artifact)
            self.assertEqual(checked['status'], 'lean_checked_composed_interval_certificate')

    def test_production_discovery_survives_decay_in_certificate_adapter(self):
        c = configured()
        c['rounds'] = 2
        mini_world.spec(c)['initial_inventory'] = {'A': 2, 'B': 1, 'D': 1}
        first = {aid: {'tool': 'wait'} for aid in ('a0', 'a1', 'a2', 'a3')}
        first['a0'] = {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine',
                       'inputs': [{'item': 'A', 'amount': 2}, {'item': 'B', 'amount': 1}], 'batches': 1}
        second = {aid: {'tool': 'wait'} for aid in first}
        second['a0'] = use(False)
        with tempfile.TemporaryDirectory() as folder:
            artifact = composed_certificates.export(c, [first, second], Path(folder)/'discovery.lean', semantic=True)
            self.assertGreater(artifact['action_phase_audit']['comparisons'], 0)


if __name__ == '__main__':
    unittest.main()

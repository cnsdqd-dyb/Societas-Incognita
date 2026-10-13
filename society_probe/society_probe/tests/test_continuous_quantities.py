import copy
import math
import unittest

import jsonschema
import mini_world
import production_semantics
import sim
from test_mini_world import config, endow, settle


class ContinuousQuantities(unittest.TestCase):
    def fixture(self):
        cfg = config(pressure=False)
        cfg['world']['mini_world']['definition']['production_semantics'] = 'proportional_v1'
        cfg['world']['initial_personal_stock'] = 20
        return cfg

    def test_fractional_input_produces_and_fractional_product_can_be_processed(self):
        cfg = self.fixture(); d = cfg['world']['mini_world']['definition']
        d['resources']['C']['decay'] = 0
        # Keep an explicit second process, independent of fixture's other recipes.
        d['recipes'][1].update(inputs={'C': 1}, yield_=1, energy_cost=0, condition=1)
        d['recipes'][1]['yield'] = d['recipes'][1].pop('yield_')
        s = sim.Society(cfg); endow(s, A=.5, B=.25)
        s.state['round'] = 1
        s.act('a0', {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine',
            'inputs': [{'item': 'A', 'amount': .5}, {'item': 'B', 'amount': .25}], 'batches': 1})
        settle(s)
        self.assertAlmostEqual(s.state['agents']['a0']['inventory']['C'], .25)
        s.state['round'] = 2
        s.act('a0', {'tool': 'experiment', 'facility': 'F1', 'mode': 'combine',
            'inputs': [{'item': 'C', 'amount': .25}], 'batches': 1})
        settle(s)
        self.assertGreater(s.state['agents']['a0']['inventory']['D'], 0)
        self.assertAlmostEqual(mini_world.accounting(cfg, s.state)['residual'], 0, places=8)

    def test_fractional_exchange_and_residue_liquidation_conserve_energy(self):
        cfg = self.fixture(); s = sim.Society(cfg); endow(s, A=.5)
        offer = s.act('a0', {'tool': 'offer_items', 'target': 'a1',
            'give': [{'item': 'A', 'amount': .25}], 'want': [{'item': 'ENERGY', 'amount': .5}]})
        key = next(iter(s.state['mini_world']['offers']))
        s.act('a1', {'tool': 'accept_items', 'offer': key})
        s.act('a1', {'tool': 'liquidate', 'item': 'A', 'amount': .25})
        self.assertEqual(s.state['agents']['a1']['inventory']['A'], 0)
        self.assertAlmostEqual(mini_world.accounting(cfg, s.state)['residual'], 0, places=8)

    def test_schema_accepts_fractional_material_but_not_fractional_batch(self):
        cfg = self.fixture(); props = mini_world.action_properties(cfg, 'experiment')
        schema = {'type': 'object', 'properties': props, 'required': list(props)}
        from mode_labels import public_mode
        action = dict(facility='F0', mode=public_mode(cfg, 'combine'), inputs=[dict(item='A', amount=.125)], batches=1)
        jsonschema.validate(action, schema)
        action['batches'] = .5
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(action, schema)
        with self.assertRaises(ValueError): mini_world.quantity(cfg, .5, 4, integer=True)

    def test_invalid_numbers_and_empty_wallet_are_rejected(self):
        cfg = self.fixture(); s = sim.Society(cfg)
        for value in [True, False, 0, -.1, float('nan'), float('inf'), '0.5', 9]:
            with self.subTest(value=value), self.assertRaises(ValueError): mini_world.quantity(cfg, value)
        with self.assertRaises(ValueError):
            mini_world.check_payment(s.state['agents']['a0'], {'A': 1e-12})

    def test_float_roundoff_matches_but_wrong_ratio_does_not(self):
        d = self.fixture()['world']['mini_world']['definition']
        r, _ = production_semantics.match(d, 'F0', 'combine', {'A': .6/3, 'B': .1})
        self.assertIsNotNone(r)
        r, _ = production_semantics.match(d, 'F0', 'combine', {'A': .21, 'B': .1})
        self.assertIsNone(r)

    def test_fractional_storage_and_giving_are_supported(self):
        cfg = self.fixture()
        import functional_effects
        d = cfg['world']['mini_world']['definition']
        import world_rule_library
        world_rule_library.add_functional_services(d, 0, ['note_capacity'])
        cfg['tools'] = sorted(set(cfg['tools']) | functional_effects.STORAGE_TOOLS | {'use_function'})
        s = sim.Society(cfg); endow(s, A=.5)
        s.act('a0', {'tool': 'give_item', 'target': 'a1', 'item': 'A', 'amount': .25, 'note': ''})
        s.act('a1', {'tool': 'store_item', 'container': 'storage:a1', 'item': 'A', 'amount': .25})
        s.act('a1', {'tool': 'withdraw_item', 'container': 'storage:a1', 'item': 'A', 'amount': .25})
        self.assertEqual(s.state['agents']['a1']['inventory']['A'], .25)
        self.assertEqual(mini_world.action_properties(cfg, 'store_item')['amount']['type'], 'number')

    def test_legacy_discrete_world_keeps_integer_contract(self):
        cfg = config()
        with self.assertRaises(ValueError): mini_world.quantity(cfg, .5)
        self.assertEqual(mini_world.action_properties(cfg, 'gather')['amount']['type'], 'integer')


if __name__ == '__main__': unittest.main()

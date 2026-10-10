import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import capability_devices as devices
import interaction_controls as controls
import material_knowledge
import mini_world
import schemas
import sim
import world_rule_engine as equations
import world_rule_library as library
from test_mini_world import config, endow, settle


def device_config():
    c = config(pressure=False)
    candidate = library.with_capabilities({'definition': mini_world.spec(c)})
    c['world']['mini_world']['definition'] = candidate['definition']
    c['tools'] = sorted(set(c['tools']) | devices.TOOLS)
    return c


def assemble(s, index=0, aid='a0'):
    r = mini_world.spec(s.cfg)['device_recipes'][index]
    return s.act(aid, {'tool': 'assemble_device', 'facility': r['facility'], 'mode': r['mode'],
                       'inputs': [{'item': k, 'amount': v} for k,v in r['inputs'].items()]})['device']['id']


class DeviceAPI(sim.API):
    fail_key = None
    def request(self, model, kind, system, payload, request_key=None):
        if request_key == self.fail_key: raise RuntimeError('Injected device interruption')
        return super().request(model, kind, system, payload, request_key)
    def script(self, kind, payload):
        aid, t = payload['self']['id'], payload['round']
        if kind == 'communicate':
            return {'communication': {'op': 'public', 'text': 'Observation claim; not engine-verified.'}} if t == 3 else {'communication': {'op': 'silent'}}
        if kind == 'act':
            action = {'tool': 'wait'}
            if aid == 'a0':
                if t == 1:
                    r = mini_world.spec(self.cfg)['device_recipes'][0]
                    action = {'tool': 'assemble_device', 'facility': r['facility'], 'mode': r['mode'], 'inputs': [{'item': k, 'amount': v} for k,v in r['inputs'].items()]}
                elif t == 2: action = {'tool': 'activate_device', 'device': 'device1', 'targets': ['a0']}
                elif t == 3: action = {'tool': 'write_note', 'key': 'trial', 'text': 'My own observation.'}
                elif t == 4: action = {'tool': 'give_device', 'device': 'device1', 'target': 'a1'}
            elif aid == 'a1' and t == 5:
                action = {'tool': 'dismantle_device', 'device': 'device1'}
            return {'action': action, 'communication': {'op': 'silent'}}
        return super().script(kind, payload)


class MaterialCapabilityTests(unittest.TestCase):
    def test_public_world_does_not_disclose_unowned_material_features(self):
        c = device_config(); c['world_rule_visibility'] = 'full'
        s = sim.Society(c); v = s.observe('a0')
        text = json.dumps(v)
        for key in ('energy_value', 'retained_fraction', 'device_recipes', 'recording-device component'):
            self.assertNotIn(key, text)
        self.assertEqual(v['environment']['your_material_knowledge'], {})
        s.act('a0', {'tool': 'gather', 'item': 'B', 'amount': 1})
        self.assertIn('B', s.observe('a0')['environment']['your_material_knowledge'])
        self.assertEqual(s.observe('a1')['environment']['your_material_knowledge'], {})

    def test_initial_possession_and_transfer_retains_private_knowledge(self):
        c = config(); mini_world.spec(c)['initial_inventory'] = {'A': 1}
        s = sim.Society(c)
        s.act('a0', {'tool': 'gather', 'item': 'B', 'amount': 1})
        s.act('a0', {'tool': 'give_item', 'target': 'a1', 'item': 'B', 'amount': 1, 'note': 'Gift'})
        self.assertFalse(s.observe('a0')['environment']['your_material_knowledge']['B']['currently_held'])
        self.assertTrue(s.observe('a1')['environment']['your_material_knowledge']['B']['currently_held'])
        self.assertNotIn('B', s.observe('a2')['environment']['your_material_knowledge'])
        self.assertEqual(s.observe('a0')['environment']['your_material_knowledge']['A']['source'], 'initial_inventory')

    def test_offer_and_message_are_not_possession_but_trade_is(self):
        s = sim.Society(config()); s.act('a0', {'tool': 'gather', 'item': 'B', 'amount': 1})
        s.act('a1', {'tool': 'gather', 'item': 'A', 'amount': 1})
        out = s.act('a0', {'tool': 'offer_items', 'target': 'a1', 'give': [{'item': 'B', 'amount': 1}], 'want': [{'item': 'A', 'amount': 1}]})
        self.assertNotIn('B', s.observe('a1')['environment']['your_material_knowledge'])
        s.communicate('a0', {'op': 'public', 'text': 'I claim C stores infinite energy.'})
        self.assertNotIn('C', s.observe('a1')['environment']['your_material_knowledge'])
        offer = next(iter(s.state['mini_world']['offers']))
        s.act('a1', {'tool': 'accept_items', 'offer': offer})
        self.assertIn('B', s.observe('a1')['environment']['your_material_knowledge'])
        self.assertIn('A', s.observe('a0')['environment']['your_material_knowledge'])

    def test_zero_output_does_not_teach_and_pre_decay_possession_does(self):
        c = config(); d = mini_world.spec(c); d['resources']['C']['decay'] = 1
        s = sim.Society(c); endow(s, A=2, B=1)
        action = {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine', 'inputs': [{'item': 'A','amount': 2}, {'item': 'B','amount': 1}], 'batches': 1}
        s.act('a0', action); self.assertNotIn('C', s.observe('a0')['environment']['your_material_knowledge'])
        settle(s)
        self.assertEqual(s.state['agents']['a0']['inventory']['C'], 0)
        self.assertIn('C', s.observe('a0')['environment']['your_material_knowledge'])
        d['recipes'][0]['yield'] = 0
        z = sim.Society(c); endow(z, A=2, B=1); z.act('a0', action); settle(z)
        self.assertNotIn('C', z.observe('a0')['environment']['your_material_knowledge'])

    def test_devices_conserve_energy_and_private_properties(self):
        s = sim.Society(device_config()); endow(s, C=2, D=1)
        before = mini_world.total_energy(s.cfg, s.state)
        key = assemble(s)
        self.assertIn(key, s.observe('a0')['environment']['your_devices'])
        self.assertEqual(s.observe('a1')['environment']['your_devices'], {})
        ledger = mini_world.accounting(s.cfg, s.state)
        self.assertLess(ledger['retained'], before)
        self.assertAlmostEqual(ledger['residual'], 0)
        s.act('a0', {'tool': 'dismantle_device', 'device': key})
        self.assertAlmostEqual(mini_world.accounting(s.cfg, s.state)['residual'], 0)
        self.assertIn(key, s.observe('a0')['environment']['device_knowledge'])

    def test_service_cost_timing_expiry_transfer_and_permissions(self):
        s = sim.Society(device_config()); endow(s, C=2, D=1); key = assemble(s)
        before = s.state['agents']['a0']['stock']
        with self.assertRaises(ValueError): s.act('a1', {'tool': 'activate_device', 'device': key, 'targets': ['a1']})
        s.act('a0', {'tool': 'activate_device', 'device': key, 'targets': ['a0', 'a1']})
        self.assertEqual(s.state['agents']['a0']['stock'], before-1)
        self.assertEqual(devices.capacities(s.cfg, s.state, 'a0')['communication_bonus'], 0)
        s.state['round'] = 1
        self.assertEqual(devices.capacities(s.cfg, s.state, 'a1')['communication_bonus'], 500)
        self.assertEqual(devices.capacities(s.cfg, s.state, 'a2')['communication_bonus'], 0)
        s.state['round'] = 4
        self.assertEqual(devices.capacities(s.cfg, s.state, 'a0')['communication_bonus'], 0)
        s.state['round'] = 2
        s.act('a0', {'tool': 'give_device', 'device': key, 'target': 'a1'})
        self.assertEqual(devices.capacities(s.cfg, s.state, 'a0')['communication_bonus'], 0)
        self.assertEqual(devices.capacities(s.cfg, s.state, 'a1')['communication_bonus'], 0)
        self.assertIn(key, s.observe('a0')['environment']['device_knowledge'])
        self.assertIn(key, s.observe('a1')['environment']['device_knowledge'])

    def test_dead_owner_service_suspends_and_zero_budget_stays_disabled(self):
        s = sim.Society(device_config()); endow(s, C=2, D=1); key = assemble(s)
        s.act('a0', {'tool': 'activate_device', 'device': key, 'targets': ['a1']}); s.state['round'] = 1
        self.assertEqual(devices.communication_limit(s.cfg, s.state, 'a1', 0), 0)
        self.assertEqual(devices.communication_limit(s.cfg, s.state, 'a1', 100), 600)
        s.state['agents']['a0']['alive'] = False
        self.assertEqual(devices.communication_limit(s.cfg, s.state, 'a1', 100), 100)

    def test_renewal_changes_users_next_round_not_during_current_round(self):
        s = sim.Society(device_config()); endow(s, C=2, D=1); key = assemble(s)
        s.act('a0', {'tool': 'activate_device', 'device': key, 'targets': ['a1']})
        s.state['round'] = 1
        s.act('a0', {'tool': 'activate_device', 'device': key, 'targets': ['a2']})
        self.assertEqual(devices.capacities(s.cfg, s.state, 'a1')['communication_bonus'], 500)
        self.assertEqual(devices.capacities(s.cfg, s.state, 'a2')['communication_bonus'], 0)
        s.state['round'] = 2
        self.assertEqual(devices.capacities(s.cfg, s.state, 'a1')['communication_bonus'], 0)
        self.assertEqual(devices.capacities(s.cfg, s.state, 'a2')['communication_bonus'], 500)

    def test_note_capacity_private_persistence_and_expiry(self):
        c = device_config(); mini_world.spec(c)['note_base_capacity'] = 8
        s = sim.Society(c); endow(s, B=1, C=2); key = assemble(s, 1)
        note = {'tool': 'write_note', 'key': 'experiment', 'text': 'a'*20}
        with self.assertRaises(ValueError): s.act('a0', note)
        s.act('a0', {'tool': 'activate_device', 'device': key, 'targets': ['a0']}); s.state['round'] = 1
        s.act('a0', note)
        self.assertNotIn('experiment', s.observe('a1')['environment']['private_note_index'])
        self.assertEqual(s.act('a0', {'tool': 'read_note', 'key': 'experiment'})['text'], 'a'*20)
        s.state['round'] = 4
        with self.assertRaises(ValueError): s.act('a0', {'tool': 'read_note', 'key': 'experiment'})
        self.assertEqual(s.state['agents']['a0']['private_notes']['experiment'], 'a'*20)

    def test_measurement_is_authorized_bounded_and_reproducible(self):
        c = device_config(); mini_world.spec(c)['variables']['stress']['observable'] = False
        s = sim.Society(c); endow(s, C=2, D=1); key = assemble(s, 2)
        action = {'tool': 'measure', 'device': key, 'field': 'stress'}
        with self.assertRaises(ValueError): s.act('a0', action)
        s.act('a0', {'tool': 'activate_device', 'device': key, 'targets': ['a0']}); s.state['round'] = 1
        result = s.act('a0', action)
        self.assertEqual(result, s.act('a0', action))
        self.assertLessEqual(abs(result['measurement']-s.state['mini_world']['variables']['stress']), .1)
        with self.assertRaises(ValueError): s.act('a1', action)
        with self.assertRaises(ValueError): s.act('a0', dict(action, field='reserve'))

    def test_manufacturing_opens_a_real_production_option(self):
        s = sim.Society(device_config()); endow(s, C=2, D=6)
        r = next(r for r in mini_world.spec(s.cfg)['recipes'] if r['output'] == 'S')
        action = {'tool': 'experiment', 'facility': r['facility'], 'mode': r['mode'], 'batches': 1,
                  'inputs': [{'item': k, 'amount': v} for k,v in r['inputs'].items()]}
        s.act('a0', action); settle(s)
        self.assertEqual(s.state['agents']['a0']['inventory']['S'], 0)
        key = assemble(s, 3)
        s.act('a0', {'tool': 'activate_device', 'device': key, 'targets': ['a0']}); s.state['round'] = 1
        s.act('a0', action); settle(s)
        self.assertGreater(s.state['agents']['a0']['inventory']['S'], 0)
        self.assertAlmostEqual(mini_world.accounting(s.cfg, s.state)['residual'], 0)

    def test_failed_operations_rollback_whole_state(self):
        s = sim.Society(device_config()); endow(s, C=2, D=1); key = assemble(s)
        for action in ({'tool': 'activate_device', 'device': key, 'targets': ['a1', 'a1']},
                       {'tool': 'activate_device', 'device': key, 'targets': ['unknown']},
                       {'tool': 'give_device', 'device': key, 'target': 'a0'}):
            before = copy.deepcopy(s.state)
            with self.assertRaises(ValueError): s.act('a0', action)
            self.assertEqual(s.state, before)

    def test_device_validator_rejects_free_fuel_and_unknown_properties(self):
        for field, value in [('fuel_per_recipient', 0), ('duration', 0), ('capabilities', {'free_energy': 5})]:
            c = device_config(); d = mini_world.spec(c); d['device_recipes'][0][field] = value
            with self.assertRaises(ValueError): equations.validate(d)

    def test_new_actions_have_valid_strict_schemas(self):
        import jsonschema
        s = sim.Society(device_config()); endow(s, C=1, D=1)
        r = mini_world.spec(s.cfg)['device_recipes'][0]
        action = {'tool': 'assemble_device', 'facility': r['facility'], 'mode': r['mode'], 'inputs': [{'item': k, 'amount': v} for k,v in r['inputs'].items()]}
        schema = schemas.schema('act', s.observe('a0'), s.cfg)
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate({'action': action, 'communication': {'op': 'silent'}}, schema)

    def test_device_dialogue_and_checkpoint_resume_match_clean_execution(self):
        c = device_config(); c['communication']['budget']['limit'] = 80; c['rounds'] = 50
        mini_world.spec(c)['initial_inventory'] = {'C': 2, 'D': 2}
        with tempfile.TemporaryDirectory() as folder, patch.object(sim, 'API', DeviceAPI):
            clean, interrupted = Path(folder)/'clean', Path(folder)/'interrupted'
            DeviceAPI.fail_key = None; sim.run(c, clean, mock=True)
            DeviceAPI.fail_key = 'act:4:a2'
            with self.assertRaisesRegex(RuntimeError, 'Injected device'): sim.run(c, interrupted, mock=True)
            DeviceAPI.fail_key = None; sim.run(c, interrupted, mock=True, resume=True)
            a = json.loads((clean/'checkpoint.json').read_text('utf-8'))['state']
            b = json.loads((interrupted/'checkpoint.json').read_text('utf-8'))['state']
            self.assertEqual(a, b)
            events = [e for e in a['communication_events'] if e['round'] == 3]
            self.assertEqual({e['budget_limit'] for e in events if e['agent'] == 'a0'}, {580})
            self.assertEqual({e['budget_limit'] for e in events if e['agent'] == 'a1'}, {80})
            self.assertGreater(len([e for e in events if e['agent'] == 'a0']), len([e for e in events if e['agent'] == 'a1']))
            self.assertTrue(all(e['budget_used_before'] < e['budget_limit'] for e in events))
            from audit_actions import audit
            self.assertTrue(audit(interrupted)['verified_replay'])
            tampered = json.loads((interrupted/'checkpoint.json').read_text('utf-8'))
            tampered['state']['snapshots'][0]['mini_world_physics']['devices']['device1']['owner'] = 'a2'
            (interrupted/'checkpoint.json').write_text(json.dumps(tampered), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'device'):
                audit(interrupted)

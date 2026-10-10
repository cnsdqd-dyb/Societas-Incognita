import copy
import unittest
import tempfile
from pathlib import Path

import mini_world
import mechanism_extensions
import sim
import world_rule_library as library
from test_mini_world import config, endow, settle


def configured(keys, seed=1):
    c = config()
    c['world']['mini_world']['definition'] = library.with_capabilities(library.generate(seed, keys))['definition']
    import capability_devices
    c['tools'] = sorted(set(c['tools']) | capability_devices.TOOLS | {'use_function'})
    return c


class TwentyMechanisms(unittest.TestCase):
    def test_each_candidate_and_full_composition_run_conservatively(self):
        keys = [k for k, _ in library.CANDIDATES_20]
        self.assertEqual(len(keys), 20)
        for selected in [[k] for k in keys] + [keys]:
            with self.subTest(selected=selected):
                candidate = library.generate(1, selected)
                self.assertEqual(candidate, library.generate(1, selected))
                s = sim.Society(configured(selected))
                for t in range(1, 11):
                    s.state['round'] = t
                    for aid, a in s.state['agents'].items():
                        if not a['alive']:
                            continue
                        item = 'A' if t % 3 else 'B'
                        if a['stock'] < 2 and a['inventory'][item] >= 1:
                            action = {'tool': 'liquidate', 'item': item, 'amount': 1}
                        else:
                            action = {'tool': 'gather', 'item': item, 'amount': 2}
                        s.act(aid, action)
                    settle(s)
                    self.assertAlmostEqual(mini_world.accounting(s.cfg, s.state)['residual'], 0, places=6)
                    self.assertTrue(all(0 <= value <= s.cfg['world']['mini_world']['definition']['pools'][k]['capacity']+1e-8
                                        for k, value in s.state['mini_world']['pools'].items()))

    def test_byproducts_are_real_owned_outputs_bounded_by_input_energy(self):
        c = config()
        d = c['world']['mini_world']['definition']
        d['resources']['W'] = copy.deepcopy(d['resources']['A']); d['resources']['W']['energy_value'] = 1
        d['recipes'][0]['byproducts'] = {'W': 20}
        s = sim.Society(c); endow(s, A=2, B=1)
        s.state['round'] = 1
        s.act('a0', {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine',
                    'inputs': [{'item': 'A', 'amount': 2}, {'item': 'B', 'amount': 1}], 'batches': 1})
        settle(s)
        self.assertEqual(s.state['agents']['a0']['inventory']['W'], 2)
        self.assertIn('W', s.state['agents']['a0']['material_knowledge'])
        self.assertAlmostEqual(mini_world.accounting(c, s.state)['residual'], 0)

    def test_queue_keeps_escrow_and_applies_mode_switch_downtime(self):
        c = config(); d = c['world']['mini_world']['definition']
        d['facilities']['F0'].update(service_capacity=1, switch_rounds=1)
        s = sim.Society(c)
        for aid in ('a0', 'a1'):
            endow(s, aid, A=2, B=1)
        s.state['round'] = 1
        for aid in ('a0', 'a1'):
            s.act(aid, {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine',
                       'inputs': [{'item': 'A', 'amount': 2}, {'item': 'B', 'amount': 1}], 'batches': 1})
        settle(s)
        self.assertEqual(set(s.state['mini_world']['pending']), {'a1'})
        self.assertEqual(s.state['agents']['a1']['inventory']['A'], 0)
        s.state['round'] = 2; settle(s)
        self.assertEqual(s.state['mini_world']['pending'], {})
        self.assertGreater(s.state['agents']['a1']['inventory']['C'], 0)
        s.state['mini_world']['pending']['a2'] = {'facility': 'F0', 'mode': 'compress',
            'inputs': {}, 'nominal_inputs': {}, 'batches': 1, 'energy_paid': 0, 'submitted_round': 3}
        selected, _ = mechanism_extensions.service_jobs(d, s.state['mini_world'], 3)
        self.assertEqual(selected, [])
        selected, _ = mechanism_extensions.service_jobs(d, s.state['mini_world'], 4)
        self.assertEqual(selected, ['a2'])

    def test_delay_is_a_shift_register_and_fatigue_does_not_heal_on_wait(self):
        s = sim.Society(configured(['explicit_delay', 'fatigue_repair']))
        s.state['round'] = 1; s.act('a0', {'tool': 'gather', 'item': 'A', 'amount': 3}); settle(s)
        self.assertEqual(s.state['mini_world']['variables']['delay_0'], 3)
        self.assertEqual(s.state['mini_world']['variables']['delay_2'], 0)
        s.state['round'] = 2; settle(s)
        self.assertEqual(s.state['mini_world']['variables']['delay_1'], 3)
        s.state['round'] = 3; settle(s)
        self.assertEqual(s.state['mini_world']['variables']['delay_2'], 3)
        s.state['mini_world']['variables']['damage'] = .7
        s.state['round'] = 4; settle(s)
        self.assertEqual(s.state['mini_world']['variables']['damage'], .7)

    def test_storage_power_cannot_be_bypassed_by_liquidation(self):
        s = sim.Society(configured(['power_limited_storage']))
        endow(s, BAT=4)
        with self.assertRaisesRegex(ValueError, 'power'):
            s.act('a0', {'tool': 'liquidate', 'item': 'BAT', 'amount': 2})
        s.act('a0', {'tool': 'liquidate', 'item': 'BAT', 'amount': 1})
        self.assertEqual(s.state['agents']['a0']['inventory']['BAT'], 3)

    def test_queue_compiler_tracks_waiting_spoilage_and_scheduler(self):
        import composed_certificates
        c = config(pressure=False); c['rounds'] = 3
        d = c['world']['mini_world']['definition']
        d['initial_inventory'] = {'C': 2}
        d['facilities']['F0'].update(service_capacity=1, switch_rounds=1)
        d['recipes'].append({'id': 'queue_test', 'facility': 'F0', 'mode': 'combine',
            'inputs': {'C': 2}, 'output': 'D', 'yield': 1, 'energy_cost': 0, 'condition': 1, 'effects': {}})
        first = {aid: {'tool': 'wait'} for aid in ('a0', 'a1', 'a2', 'a3')}
        for aid in ('a0', 'a1'):
            first[aid] = {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine',
                         'inputs': [{'item': 'C', 'amount': 2}], 'batches': 1}
        plan = [first] + [{aid: {'tool': 'wait'} for aid in first} for _ in range(2)]
        with tempfile.TemporaryDirectory() as directory:
            artifact = composed_certificates.export(c, plan, Path(directory)/'queue.lean', semantic=True)
            self.assertGreater(artifact['action_phase_audit']['comparisons'], 0)
        s = sim.Society(c)
        for t, joint in enumerate(plan, 1):
            s.state['round'] = t
            for aid in first:
                s.act(aid, joint[aid])
            settle(s)
        self.assertEqual(s.state['mini_world']['discoveries']['a1'][0]['result'], 'spoiled_in_queue')

    def test_calibration_consumes_material_and_reduces_readout_bias(self):
        s = sim.Society(configured(['calibrated_measurement']))
        material = next(k for k, r in s.cfg['world']['mini_world']['definition']['resources'].items()
                        if 'calibration' in r.get('use_effects', {}))
        inventory = {'C': 2, 'D': 1, 'S': 0}
        inventory[material] += 1
        endow(s, **inventory)
        result = s.act('a0', {'tool': 'assemble_device', 'facility': 'F0', 'mode': 'combine',
                              'inputs': [{'item': 'C', 'amount': 2}, {'item': 'D', 'amount': 1}]})
        key = next(iter(s.state['mini_world']['devices']))
        s.act('a0', {'tool': 'activate_device', 'device': key, 'targets': ['a0']})
        s.state['round'] = 1
        before = s.act('a0', {'tool': 'measure', 'device': key, 'field': 'stress'})
        s.act('a0', {'tool': 'use_item', 'item': material, 'amount': 1})
        after = s.act('a0', {'tool': 'measure', 'device': key, 'field': 'stress'})
        self.assertAlmostEqual(before['measurement']-after['measurement'], .4)
        self.assertLess(after['absolute_error_bound'], before['absolute_error_bound'])
        self.assertEqual(s.state['agents']['a0']['inventory'][material], 0)

    def test_seeded_material_roles_move_effects_feedback_and_disclosures_together(self):
        import world_rule_engine
        mappings = set()
        for seed in range(8):
            candidate = library.generate(seed, ['competitive_catalysis', 'fatigue_repair', 'calibrated_measurement'])
            self.assertEqual(candidate, library.generate(seed, ['competitive_catalysis', 'fatigue_repair', 'calibrated_measurement']))
            mapping = candidate['generation']['material_function_assignment']
            mappings.add(tuple(sorted(mapping.items())))
            d = candidate['definition']
            repair = mapping['D']
            calibration = mapping['C']
            self.assertEqual(d['resources'][repair]['use_effects']['damage'], -.5)
            self.assertEqual(d['resources'][calibration]['use_effects']['calibration'], 1)
            context = {'state.enzyme': 0, 'activity.consumed.'+repair: 1}
            self.assertEqual(world_rule_engine.evaluate(d['variables']['enzyme']['next'], context), 1)
            self.assertIn('Using this material affects damage.', d['resources'][repair]['traits'])
        self.assertGreater(len(mappings), 1)

    def test_seeded_material_roles_compile_and_pass_lean(self):
        import composed_certificates
        c = configured(['competitive_catalysis', 'fatigue_repair', 'calibrated_measurement'], seed=2)
        c['world']['survival_pressure'] = False
        c['rounds'] = 2
        d = c['world']['mini_world']['definition']
        repair = next(k for k, r in d['resources'].items() if 'damage' in r.get('use_effects', {}))
        d['initial_inventory'] = {repair: 3}
        joint = {aid: {'tool': 'wait'} for aid in ('a0', 'a1', 'a2', 'a3')}
        joint['a0'] = {'tool': 'use_item', 'item': repair, 'amount': 1}
        with tempfile.TemporaryDirectory() as directory:
            artifact = composed_certificates.export(c, [joint, joint], Path(directory)/'roles.lean', semantic=True)
            checked = composed_certificates.check(artifact)
            self.assertEqual(checked['status'], 'lean_checked_composed_interval_certificate')


if __name__ == '__main__':
    unittest.main()

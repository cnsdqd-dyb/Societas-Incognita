import copy
import json
import tempfile
import unittest
from pathlib import Path

import capability_devices
import composed_certificates
import functional_effects as effects
import game_rules
import interaction_controls
import mini_world
import schemas
import sim
import world_rule_engine
import world_rule_library as library
from test_mini_world import config, endow, settle


def configured():
    c = config(extensions=True, pressure=False)
    candidate = library.with_capabilities({'definition': mini_world.spec(c), 'generation': {'seed': 3}})
    candidate = library.with_all_functional_services(candidate)
    d = candidate['definition']
    d['production_semantics'] = 'proportional_v1'
    d['resources']['BAT'] = {'name': 'battery', 'tier': 2, 'energy_value': 2, 'decay': 0,
                            'liquidation_efficiency': 1, 'accessibility': 1, 'liquidation_limit': 1}
    d['facilities']['F0'].update(service_capacity=1, switch_rounds=2)
    c['world']['mini_world']['definition'] = d
    c['tools'] = sorted(set(c['tools']) | {'use_function'} | capability_devices.TOOLS | effects.STORAGE_TOOLS)
    c['communication']['budget']['limit'] = 100
    c['communication']['max_invitees'] = 1
    c['social_content']['max_content_chars'] = 512
    c['rescue']['enabled'] = False
    c['tools'] = [t for t in c['tools'] if t != 'rescue']
    c['world']['initial_personal_stock'] = 100
    return c


def society():
    s = sim.Society(configured())
    for aid in s.state['agents']:
        endow(s, aid, C=32, D=32, S=32, A=16, B=16, BAT=4)
    s.act('a0', {'tool': 'wait'})
    s.state['round'] = 1
    return s


def use(s, kind, target='a0', aid='a0', confirm=True):
    return s.act(aid, {'tool': 'use_function', 'function': 'service_' + kind, 'target': target, 'confirm': confirm})


def device(s, index=0, aid='a0'):
    r = mini_world.spec(s.cfg)['device_recipes'][index]
    result = s.act(aid, {'tool': 'assemble_device', 'facility': r['facility'], 'mode': r['mode'],
                        'inputs': [{'item': k, 'amount': n} for k, n in r['inputs'].items()]})
    return result['device']['id']


def work(s, kind='novel', source='hello'):
    return s.act('a0', {'tool': 'create', 'title': '作品', 'content': source, 'kind': kind,
                       'visibility': 'public'})['artifact_created']


class FunctionalTests(unittest.TestCase):
    def test_work_expansion_stacks_and_is_actually_readable_and_licensed(self):
        s = society(); key = work(s)
        with self.assertRaises(ValueError): s.act('a0', {'tool': 'revise_work', 'artifact': key, 'content': 'x' * 513})
        use(s, 'work_capacity', key); use(s, 'work_capacity', key)
        text = 'x' * 1600
        s.act('a0', {'tool': 'revise_work', 'artifact': key, 'content': text})
        actual = s.act('a1', {'tool': 'read_artifact', 'artifact': key, 'version': 0})['artifact']
        self.assertEqual(actual['content'], text)
        self.assertEqual(actual['context_capacity'], 2048)
        with self.assertRaisesRegex(ValueError, 'unauthorized'): use(s, 'work_capacity', key, 'a1')
        s.act('a0', {'tool': 'publish_work', 'artifact': key, 'visibility': 'licensed'})
        sale = s.act('a0', {'tool': 'offer_work', 'artifact': key, 'target': 'a1', 'price': 2})['offer_created']
        s.state['round'] += 1
        s.act('a1', {'tool': 'accept_work', 'offer': sale})
        self.assertEqual(s.act('a1', {'tool': 'read_artifact', 'artifact': key, 'version': 0})['artifact']['context_capacity'], 2048)

    def test_expanded_game_source_can_be_played(self):
        s = society()
        from test_social_content import PY_GAME
        s.cfg['social_content']['max_content_chars'] = 12000
        key = work(s, 'game_python', PY_GAME)
        use(s, 'work_capacity', key)
        text = PY_GAME + '\n#' + 'x' * 13000
        s.act('a0', {'tool': 'revise_work', 'artifact': key, 'content': text})
        game = s.act('a0', {'tool': 'start_game', 'artifact': key, 'version': 0, 'targets': [], 'stake': 0,
                            'settlement': 'refund'})['game_created']
        s.state['round'] += 1
        result = s.act('a0', {'tool': 'game_move', 'game': game, 'expected_move': 0, 'move_json': '{"take":1}'})
        self.assertEqual(result['state']['pile'], 2)

    def test_notes_and_personal_communication_and_invitation_range(self):
        s = society()
        with self.assertRaises(ValueError): s.act('a0', {'tool': 'write_note', 'key': 'memo', 'text': 'x' * 500})
        use(s, 'note_capacity')
        s.act('a0', {'tool': 'write_note', 'key': 'memo', 'text': 'x' * 500})
        self.assertEqual(len(s.act('a0', {'tool': 'read_note', 'key': 'memo'})['text']), 500)
        use(s, 'communication_budget')
        self.assertEqual(s.observe('a0')['countdowns']['communication']['limit'], 600)
        use(s, 'communication_range')
        s.communicate('a0', {'op': 'invite', 'targets': ['a1', 'a2', 'a3']})
        self.assertEqual(s.observe('a0')['communication_rules']['max_invitees'], 3)
        s.state['round'] = 5
        self.assertEqual(s.observe('a0')['countdowns']['communication']['limit'], 100)

    def test_shared_conversation_extension_is_not_duplicated_per_member(self):
        s = society()
        s.communicate('a0', {'op': 'invite', 'targets': ['a1']})
        s.communicate('a1', {'op': 'accept', 'chat': 'c1'})
        use(s, 'communication_budget', 'c1')
        self.assertEqual(effects.shared_left(s.state, 'a0'), 500)
        self.assertEqual(effects.spend_shared(s.state, 'a0', 350, 'c1'), 350)
        self.assertEqual(effects.shared_left(s.state, 'a1'), 150)
        self.assertEqual(effects.spend_shared(s.state, 'a1', 200, 'c1'), 150)
        self.assertEqual(effects.shared_left(s.state, 'a0'), 0)

    def test_shared_extension_is_enforced_by_actual_dialogue_loop(self):
        s = society()
        s.communicate('a0', {'op': 'invite', 'targets': ['a1']})
        s.communicate('a1', {'op': 'accept', 'chat': 'c1'})
        use(s, 'communication_budget', 'c1')
        class API:
            def request(self, model, kind, system, payload, request_key=None):
                if payload['self']['id'] in ('a0', 'a1'):
                    return {'communication': {'op': 'send', 'chat': 'c1', 'text': '讨论' * 10}}
                return {'communication': {'op': 'silent'}}
        progress = {}
        interaction_controls.advance_dialogue(s, API(), progress, lambda: None)
        records = s.state['communication_events']
        self.assertEqual(sum(r['outcome'].get('shared_budget_charge', 0) for r in records), 500)
        self.assertEqual(effects.shared_left(s.state, 'a0'), 0)
        self.assertGreater(sum(r['agent'] == 'a0' for r in records), 2)
        self.assertLess(progress['dialogue_turn'], 20)

    def test_devices_enhance_precision_coverage_and_can_be_damaged_repaired(self):
        s = society(); key = device(s, 2)
        s.state['mini_world']['devices'][key]['properties']['max_users'] = 1
        use(s, 'device_range', key)
        s.act('a0', {'tool': 'activate_device', 'device': key, 'targets': ['a0', 'a1', 'a2']})
        s.state['round'] = 2
        before = s.act('a0', {'tool': 'measure', 'device': key, 'field': 'stress'})['absolute_error_bound']
        use(s, 'measurement_precision', key)
        after = s.act('a0', {'tool': 'measure', 'device': key, 'field': 'stress'})['absolute_error_bound']
        self.assertAlmostEqual(after, before * .75)
        use(s, 'device_interference', key, 'a1')
        noisy = s.act('a0', {'tool': 'measure', 'device': key, 'field': 'stress'})['absolute_error_bound']
        self.assertAlmostEqual(noisy, after * 2)
        use(s, 'device_corrosion', key, 'a1')
        self.assertEqual(s.state['mini_world']['devices'][key]['integrity'], .75)
        use(s, 'repair_device', key)
        self.assertEqual(s.state['mini_world']['devices'][key]['integrity'], 1)

    def test_storage_decay_stacks_armor_reduces_theft_and_corrosion(self):
        s = society(); key = 'storage:a0'
        s.act('a0', {'tool': 'store_item', 'container': key, 'item': 'C', 'amount': 8})
        use(s, 'storage_decay', key); use(s, 'storage_decay', key)
        settle(s)
        container = effects.data(s.state)['containers'][key]
        self.assertAlmostEqual(container['inventory']['C'], 8 * (1 - .02 * .85 ** 2))
        first = copy.deepcopy(s.state)
        loot = s.act('a1', {'tool': 'seize_storage', 'container': key, 'item': 'C', 'amount': 2, 'effort': 1})['taken']
        s.state = first
        use(s, 'fortify', key)
        smaller = s.act('a1', {'tool': 'seize_storage', 'container': key, 'item': 'C', 'amount': 2, 'effort': 1})['taken']
        self.assertLess(smaller, loot)
        before = container['inventory']['C']
        container = effects.data(s.state)['containers'][key]
        before = container['inventory']['C']
        use(s, 'container_corrosion', key, 'a1')
        self.assertAlmostEqual(container['inventory']['C'], before * .925)
        self.assertAlmostEqual(mini_world.accounting(s.cfg, s.state)['residual'], 0, places=6)

    def test_release_power_and_offer_extension(self):
        s = society()
        with self.assertRaises(ValueError): s.act('a0', {'tool': 'liquidate', 'item': 'BAT', 'amount': 2})
        use(s, 'discharge_power')
        self.assertEqual(s.act('a0', {'tool': 'liquidate', 'item': 'BAT', 'amount': 2})['liquid_energy'], 4)
        key = s.act('a0', {'tool': 'offer_items', 'target': 'a1', 'give': [{'item': 'B', 'amount': 1}],
                           'want': [{'item': 'A', 'amount': 1}]})['offer']
        before = s.state['mini_world']['offers'][key]['expires']
        use(s, 'offer_duration', key)
        self.assertEqual(s.state['mini_world']['offers'][key]['expires'], before + 3)

    def test_production_gain_is_real_but_energy_funded_and_diagnostics_are_real(self):
        s = society(); d = mini_world.spec(s.cfg)
        d['resources']['C']['decay'] = 0
        d['recipes'][0]['yield'] = 1
        d['facilities']['F0']['switch_rounds'] = 0
        action = {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine',
                  'inputs': [{'item': 'A', 'amount': 2}, {'item': 'B', 'amount': 1}], 'batches': 1}
        initial = copy.deepcopy(s.state)
        s.act('a0', action); settle(s)
        baseline = s.state['mini_world']['discoveries']['a0'][-1]['produced']['C']
        s.state = initial
        use(s, 'production_efficiency', 'F0'); use(s, 'diagnostics', 'F0')
        s.act('a0', action); settle(s)
        record = s.state['mini_world']['discoveries']['a0'][-1]
        self.assertGreater(record['produced']['C'], baseline)
        self.assertIn('stress', record['diagnostics'])
        self.assertLessEqual(record['produced']['C'] * d['resources']['C']['energy_value'], 6)
        self.assertAlmostEqual(mini_world.accounting(s.cfg, s.state)['residual'], 0, places=6)

    def test_switch_speed_and_sabotage_change_actual_queue(self):
        s = society()
        use(s, 'switch_speed', 'F0')
        self.assertEqual(effects.effective_definition(s.cfg, s.state)['facilities']['F0']['switch_rounds'], 1)
        use(s, 'facility_sabotage', 'F0', 'a1')
        s.act('a0', {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine',
                    'inputs': [{'item': 'A', 'amount': 2}, {'item': 'B', 'amount': 1}], 'batches': 1})
        settle(s)
        self.assertIn('a0', s.state['mini_world']['pending'])
        s.state['round'] = 4; settle(s)
        self.assertNotIn('a0', s.state['mini_world']['pending'])

    def test_pollution_reduces_harvest_and_purification_recovers_it(self):
        s = society()
        use(s, 'pool_pollution', 'A', 'a1')
        actual = s.act('a0', {'tool': 'gather', 'item': 'A', 'amount': 4})['harvested']
        self.assertEqual(actual, 2)
        use(s, 'purify', 'A')
        self.assertEqual(s.act('a0', {'tool': 'gather', 'item': 'A', 'amount': 4})['harvested'], 4)

    def test_shield_attack_death_and_paid_material_rescue(self):
        s = society()
        use(s, 'shield', 'a0')
        before = s.state['agents']['a0']['energy']
        use(s, 'attack', 'a0', 'a1')
        self.assertEqual(s.state['agents']['a0']['energy'], before - 1)
        use(s, 'attack', 'a2'); use(s, 'attack', 'a2'); use(s, 'attack', 'a2')
        self.assertFalse(s.state['agents']['a2']['alive'])
        before = s.state['agents']['a0']['stock']
        use(s, 'rescue', 'a2')
        self.assertEqual(s.state['agents']['a0']['stock'], before - 5)
        self.assertFalse(s.state['agents']['a2']['alive'])
        s.state['round'] += 1
        interaction_controls.start_round(s.cfg, s.state)
        self.assertTrue(s.state['agents']['a2']['alive'])
        self.assertEqual(s.state['agents']['a2']['energy'], 5)
        self.assertAlmostEqual(mini_world.accounting(s.cfg, s.state)['residual'], 0, places=6)

    def test_area_damage_includes_actor_devices_and_world_and_restores_checkpoint(self):
        s = society(); key = device(s)
        use(s, 'area_attack', 'world')
        self.assertEqual(s.state['agents']['a0']['energy'], 2)
        self.assertEqual(s.state['mini_world']['devices'][key]['integrity'], .5)
        self.assertTrue(effects.data(s.state)['pools'])
        restored = sim.Society(s.cfg); restored.state = json.loads(json.dumps(s.state))
        self.assertEqual(s.observe('a0'), restored.observe('a0'))
        self.assertAlmostEqual(mini_world.accounting(s.cfg, s.state)['residual'], 0, places=6)

    def test_all_kinds_have_real_catalog_and_unsupported_lean_adapter_fails_explicitly(self):
        c = configured(); world_rule_engine.validate(mini_world.spec(c))
        self.assertEqual({e['kind'] for e in mini_world.spec(c)['combination_functions']}, set(effects.KINDS))
        c['world']['mini_world']['definition']['initial_inventory'] = {'C': 4, 'D': 4, 'S': 4}
        c.pop('social_content'); c.pop('open_activities'); c.pop('resource_seizure')
        first = {aid: {'tool': 'wait'} for aid in ('a0', 'a1', 'a2', 'a3')}
        first['a0'] = {'tool': 'use_function', 'function': 'service_note_capacity', 'target': 'a0', 'confirm': True}
        with self.assertRaisesRegex(composed_certificates.Unsupported, 'separate certificate adapter'):
            composed_certificates.Compiler(c).run([first])

    def test_cancel_without_a_selected_target_is_free_and_schema_valid(self):
        import jsonschema
        s = society()
        action = {'tool': 'use_function', 'function': 'service_work_capacity', 'target': None, 'confirm': False}
        jsonschema.validate({'action': action, 'communication': {'op': 'silent'}}, schemas.schema('act', s.observe('a0'), s.cfg))
        before = copy.deepcopy(s.state['agents']['a0'])
        self.assertTrue(s.act('a0', action)['cancelled'])
        self.assertEqual(before, s.state['agents']['a0'])

    def test_full_functional_run_resumes_without_repeating_model_requests(self):
        from unittest.mock import patch
        c = configured(); c['rounds'] = 5
        mini_world.spec(c)['initial_inventory'] = {'C': 16, 'D': 16, 'S': 16, 'A': 8, 'B': 8}
        c['memory'] = {'trigger_chars': 10000000, 'keep_recent_rounds': 2, 'summary_max_chars': 1000}
        c['survey_rounds'] = []
        class API(sim.API):
            fail_key = None
            returned = []
            def request(self, model, kind, system, payload, request_key=None):
                if request_key == self.fail_key: raise RuntimeError('injected functional interruption')
                value = super().request(model, kind, system, payload, request_key)
                type(self).returned.append(request_key)
                return value
            def script(self, kind, payload):
                if kind == 'communicate': return {'communication': {'op': 'silent'}}
                if kind != 'act': return super().script(kind, payload)
                aid, turn = payload['self']['id'], payload['round']
                action = {'tool': 'wait'}
                if aid == 'a0':
                    action = {1: {'tool': 'create', 'title': 'book', 'kind': 'novel', 'visibility': 'public', 'content': 'hello'},
                              2: {'tool': 'use_function', 'function': 'service_work_capacity', 'target': 'work1', 'confirm': True},
                              3: {'tool': 'revise_work', 'artifact': 'work1', 'content': 'x' * 800},
                              4: {'tool': 'use_function', 'function': 'service_rescue', 'target': 'a3', 'confirm': True}}.get(turn, action)
                elif aid == 'a1':
                    action = {1: {'tool': 'store_item', 'container': 'storage:a1', 'item': 'C', 'amount': 4},
                              2: {'tool': 'use_function', 'function': 'service_storage_decay', 'target': 'storage:a1', 'confirm': True},
                              3: {'tool': 'use_function', 'function': 'service_note_capacity', 'target': 'a1', 'confirm': True},
                              4: {'tool': 'write_note', 'key': 'memo', 'text': 'record' * 100},
                              5: {'tool': 'withdraw_item', 'container': 'storage:a1', 'item': 'C', 'amount': 4}}.get(turn, action)
                elif aid == 'a2' and turn <= 3:
                    action = {'tool': 'use_function', 'function': 'service_attack', 'target': 'a3', 'confirm': True}
                return {'action': action, 'communication': {'op': 'silent'}}
        with tempfile.TemporaryDirectory() as folder, patch.object(sim, 'API', API):
            root = Path(folder); complete, interrupted = root/'complete', root/'interrupted'
            sim.run(copy.deepcopy(c), complete, mock=True)
            API.returned = []
            API.fail_key = 'act:3:a1'
            with self.assertRaisesRegex(RuntimeError, 'functional interruption'):
                sim.run(copy.deepcopy(c), interrupted, mock=True)
            API.fail_key = None
            sim.run(copy.deepcopy(c), interrupted, mock=True, resume=True)
            left = json.loads((complete/'checkpoint.json').read_text('utf-8'))['state']
            right = json.loads((interrupted/'checkpoint.json').read_text('utf-8'))['state']
            self.assertEqual(left, right)
            self.assertTrue(right['agents']['a3']['alive'])
            self.assertEqual(len(right['culture']['artifacts']['work1']['content']), 800)
            self.assertEqual(len(right['agents']['a1']['private_notes']['memo']), 600)
            keys = API.returned
            self.assertEqual(len(keys), len(set(keys)))


if __name__ == '__main__': unittest.main()

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import jsonschema
import environments
import mini_world
import schemas
import sim
import world_rule_engine as engine
import world_rule_library as library
import checkpoint_interventions as branches
import knowledge_tracking as knowledge
import survival_certificates as certificates

SOURCE = json.loads(Path('configs/cheap_mix_oss_v4_20261009/M2_cheap_mix_oss8_p1.json').read_text('utf-8'))


def config(extensions=False, noise=0, pressure=True):
    candidate = {'definition': library.base_definition(), 'generation': {'status': 'fixture_not_certified'}}
    candidate['definition']['noise'] = {'distribution': 'uniform' if noise else 'none', 'amplitude': noise}
    c = library.configure(SOURCE, candidate, members=4, pressure=pressure, extensions=extensions)
    c.update(rounds=6, parallel_agents=1)
    c['communication']['budget']['limit'] = 0
    c['memory'] = {'trigger_chars': 10000000, 'keep_recent_rounds': 2, 'summary_max_chars': 1000}
    return c


def endow(s, aid='a0', **inventory):
    s.state['agents'][aid]['inventory'].update(inventory)
    l = s.state['mini_world']['ledger']
    l.update(initial=mini_world.total_energy(s.cfg, s.state), external_input=0., dissipated=0., loss_by_cause={})


def settle(s):
    s.settle(environments.physical_snapshot(s.state))


class PhysicalAPI(sim.API):
    fail_key = None
    def request(self, model, kind, system, payload, request_key=None):
        if request_key == type(self).fail_key: raise RuntimeError('Injected transport interruption')
        return super().request(model, kind, system, payload, request_key)
    def script(self, kind, payload):
        if kind == 'act':
            return {'action': {'tool': 'gather' if payload['round'] % 2 else 'liquidate', 'item': 'A', 'amount': 2},
                    'communication': {'op': 'silent'}}
        return super().script(kind, payload)


class MiniWorldTests(unittest.TestCase):
    def test_hidden_rules_keep_interface_but_hide_graph_parameters_and_modules(self):
        c = config(); s = sim.Society(c); v = s.observe('a0')
        text = json.dumps(v)
        for key in ('energy_value', 'regeneration', 'recipes', 'cross_inhibition', 'use_effects', 'liquidation_efficiency'):
            self.assertNotIn(key, text)
        self.assertEqual(v['world_rules']['visibility'], 'hidden')
        self.assertIn('stations', v['environment']); self.assertIn('material_catalog', v['environment'])
        self.assertNotIn('r0', __import__('interaction_controls').actor_help(c, v, environments.action_help(c)))

    def test_rule_and_recipe_visibility_are_independent(self):
        c = config(); c['world_rule_visibility'] = 'full'
        v = sim.Society(c).observe('a0')
        self.assertNotIn('recipes', v['world_rules']['definition'])
        c['world_rule_visibility'] = 'hidden'; c['recipe_visibility'] = 'full'
        v = sim.Society(c).observe('a0')
        self.assertIn('production_rules', v['environment'])

    def test_all_action_contracts_and_unavailable_tool_rejection(self):
        for extensions in (False, True):
            c = config(extensions); s = sim.Society(c)
            for kind in ('act', 'communicate'):
                jsonschema.Draft202012Validator.check_schema(schemas.schema(kind, s.observe('a0'), c))
        s = sim.Society(config())
        with self.assertRaises(ValueError): s.act('a0', {'tool': 'rescue', 'target': 'a1'})

    def test_multilevel_recipe_results_and_failed_trial_refund(self):
        s = sim.Society(config()); s.state['round'] = 1; endow(s, A=6, B=1, C=3)
        s.act('a0', {'tool': 'experiment', 'facility': 'F1', 'mode': 'combine', 'inputs': [{'item': 'A', 'amount': 2}, {'item': 'C', 'amount': 3}], 'batches': 1})
        settle(s)
        self.assertEqual(s.state['mini_world']['discoveries']['a0'][-1]['produced'], {'D': 2})
        self.assertAlmostEqual(s.state['agents']['a0']['inventory']['D'], 1.98)
        s.state['round'] = 2
        before = s.state['agents']['a0']['inventory']['A']
        s.act('a0', {'tool': 'experiment', 'facility': 'F0', 'mode': 'compress', 'inputs': [{'item': 'A', 'amount': 1}], 'batches': 1})
        settle(s)
        self.assertEqual(s.state['agents']['a0']['inventory']['A'], before)
        self.assertEqual(s.state['mini_world']['discoveries']['a0'][-1]['result'], 'no_product')
        self.assertAlmostEqual(mini_world.accounting(s.cfg, s.state)['residual'], 0)

    def test_noise_is_reproducible_and_cannot_create_energy(self):
        c = config(noise=.5); a = sim.Society(c); b = sim.Society(c)
        for s in (a, b):
            s.state['round'] = 1
            s.act('a0', {'tool': 'gather', 'item': 'A', 'amount': 8}); settle(s)
        self.assertEqual(a.state, b.state)
        self.assertLessEqual(a.state['agents']['a0']['inventory']['A'], 8)
        self.assertAlmostEqual(mini_world.accounting(c, a.state)['residual'], 0)

    def test_random_generator_reproducibility_and_state_feedback(self):
        self.assertEqual(library.generate(17), library.generate(17))
        self.assertNotEqual(library.generate(17), library.generate(18))
        candidate = library.generate(7, ['cross_inhibition', 'delayed_feedback'])
        s = sim.Society(library.configure(SOURCE, candidate)); s.state['round'] = 1
        s.act('a0', {'tool': 'gather', 'item': 'A', 'amount': 4}); settle(s)
        self.assertEqual(s.state['mini_world']['variables']['lag'], 4)
        self.assertEqual(candidate['generation']['status'], 'candidate_not_certified')

    def test_composed_modules_and_random_graph_obey_energy_contracts(self):
        for seed in range(8):
            candidate = library.generate(seed, list(library.MODULES), noise_amplitude=.15)
            d = candidate['definition']; s = sim.Society(library.configure(SOURCE, candidate))
            s.state['round'] = 1
            s.act('a0', {'tool': 'gather', 'item': 'A', 'amount': 3}); settle(s)
            self.assertAlmostEqual(mini_world.accounting(s.cfg, s.state)['residual'], 0, places=7)
            for recipe in d['recipes']:
                paid = sum(d['resources'][k]['energy_value']*v for k, v in recipe['inputs'].items())+recipe['energy_cost']
                trial = sim.Society(library.configure(SOURCE, candidate))
                trial.state['agents']['a0']['stock'] = 100
                endow(trial, **recipe['inputs'])
                trial.state['round'] = 1
                trial.act('a0', {'tool':'experiment', 'facility':recipe['facility'], 'mode':recipe['mode'],
                    'inputs':[{'item':k,'amount':v} for k,v in recipe['inputs'].items()], 'batches':1})
                settle(trial)
                products = trial.state['mini_world']['discoveries']['a0'][-1]['produced']
                delivered = sum(n*d['resources'][k]['energy_value'] for k,n in products.items())
                funded_cost = trial.state['mini_world']['discoveries']['a0'][-1].get('operating_energy_paid',0)
                self.assertLessEqual(delivered, paid-recipe['energy_cost']+funded_cost+1e-7)
                self.assertAlmostEqual(mini_world.accounting(trial.cfg,trial.state)['residual'],0,places=7)

    def test_ecological_depletion_recycles_without_creating_energy(self):
        candidate = library.generate(5, ['trophic_balance'])
        s = sim.Society(library.configure(SOURCE, candidate)); s.state['round'] = 1
        settle(s)
        record = s.state['environment_history'][-1]
        self.assertGreater(record['pool_depletion']['B'], 0)
        self.assertGreater(record['recycled_energy'], 0)
        self.assertAlmostEqual(record['energy_accounting']['residual'], 0)

    def test_threshold_hysteresis_has_distinct_entry_and_recovery(self):
        candidate = library.generate(3, ['threshold_hysteresis']); d = candidate['definition']
        s = sim.Society(library.configure(SOURCE, candidate)); s.state['round'] = 1
        threshold = d['variables']['crisis']['next']['args'][0]['args'][1]
        s.state['mini_world']['variables']['strain'] = threshold+1; settle(s)
        self.assertEqual(s.state['mini_world']['variables']['crisis'], 1)
        s.state['round'] = 2; s.state['mini_world']['variables']['strain'] = threshold*.75; settle(s)
        self.assertEqual(s.state['mini_world']['variables']['crisis'], 1)
        s.state['round'] = 3; s.state['mini_world']['variables']['strain'] = 0; settle(s)
        self.assertEqual(s.state['mini_world']['variables']['crisis'], 0)

    def test_installed_lean_checks_real_survival_and_rejects_false_claim(self):
        if not certificates.find_lean(): self.skipTest('Lean not installed')
        c = config(); d = mini_world.spec(c)
        for r in d['resources'].values(): r['decay'] = 0
        witness = certificates.replay(c, certificates.alternating_plan(c))
        with tempfile.TemporaryDirectory() as folder:
            artifact = certificates.export_lean(c, witness, Path(folder)/'good.lean')
            self.assertEqual(certificates.check_lean(artifact)['status'], 'lean_checked_restricted_projection')
            path = Path(folder)/'false.lean'; source = Path(artifact['source']).read_text('utf-8')
            source = source.replace('= some 24 := by decide', '= some 25 := by decide')
            path.write_text(source, 'utf-8')
            import hashlib
            artifact = {**artifact, 'source': str(path), 'sha256': hashlib.sha256(source.encode()).hexdigest()}
            self.assertEqual(certificates.check_lean(artifact)['status'], 'lean_rejected')

    def test_trade_is_atomic_and_transfer_custody_creates_no_energy(self):
        s = sim.Society(config()); endow(s, A=3); s.state['round'] = 1
        before = mini_world.total_energy(s.cfg, s.state)
        result = s.act('a0', {'tool': 'offer_items', 'target': 'a1', 'give': [{'item': 'A', 'amount': 2}], 'want': [{'item': 'ENERGY', 'amount': 2}]})
        snapshot = copy.deepcopy(s.state)
        with self.assertRaises(ValueError): s.act('a2', {'tool': 'accept_items', 'offer': result['offer']})
        self.assertEqual(s.state, snapshot)
        s.act('a1', {'tool': 'accept_items', 'offer': result['offer']})
        s.act('a1', {'tool': 'give_item', 'target': 'a2', 'item': 'A', 'amount': 1, 'note': 'custody'})
        self.assertEqual(mini_world.total_energy(s.cfg, s.state), before)
        self.assertEqual(s.state['agents']['a2']['inventory']['A'], 1)

    def test_escrow_decays_and_expiry_refunds_without_double_spending(self):
        s = sim.Society(config(pressure=False)); endow(s, C=4); s.state['round'] = 1
        offer = s.act('a0', {'tool': 'offer_items', 'target': 'public', 'give': [{'item': 'C', 'amount': 4}], 'want': [{'item': 'ENERGY', 'amount': 1}]})['offer']
        settle(s); self.assertAlmostEqual(s.state['mini_world']['offers'][offer]['give']['C'], 3.92)
        for t in range(2, 5): s.state['round'] = t; settle(s)
        self.assertEqual(s.state['mini_world']['offers'][offer]['status'], 'expired')
        self.assertAlmostEqual(s.state['agents']['a0']['inventory']['C'], 4*.98**4)
        with self.assertRaises(ValueError): s.act('a1', {'tool': 'accept_items', 'offer': offer})

    def test_high_density_storage_and_use_function(self):
        s = sim.Society(config(pressure=False)); endow(s, S=2, D=2)
        s.state['mini_world']['variables']['stress'] = 5; s.state['round'] = 1
        s.act('a0', {'tool': 'use_item', 'item': 'D', 'amount': 1})
        self.assertEqual(s.state['mini_world']['variables']['stress'], 4)
        settle(s); self.assertEqual(s.state['agents']['a0']['inventory']['S'], 2)
        self.assertAlmostEqual(mini_world.accounting(s.cfg, s.state)['residual'], 0)

    def test_rescue_security_and_social_game_tools_remain_optional(self):
        s = sim.Society(config(True)); endow(s, aid='a1', S=4)
        s.state['round'] = 1
        before = mini_world.total_energy(s.cfg, s.state)
        s.act('a0', {'tool': 'seize_item', 'target': 'a1', 'item': 'S', 'amount': 2, 'effort': 1})
        self.assertAlmostEqual(before-mini_world.total_energy(s.cfg, s.state), .5)
        s.state['agents']['a2'].update(energy=0, alive=False)
        s.act('a1', {'tool': 'rescue', 'target': 'a2'}); self.assertFalse(s.state['agents']['a2']['alive'])
        settle(s); s.state['round'] = 2
        __import__('interaction_controls').start_round(s.cfg, s.state)
        self.assertTrue(s.state['agents']['a2']['alive'])
        s.act('a2', {'tool': 'create', 'title': 'notes', 'content': 'unverified rule', 'kind': 'knowledge', 'visibility': 'public'})
        self.assertAlmostEqual(mini_world.accounting(s.cfg, s.state)['residual'], 0)

    def test_invalid_equations_and_energy_creation_fail_closed(self):
        d = library.base_definition(); d['variables']['stress']['next'] = {'ref': '__import__'}
        with self.assertRaises(ValueError): engine.validate(d)
        with self.assertRaises(ValueError): engine.validate_expression({'op': 'pow', 'args': [2, 100]}, set())
        c = config(); s = sim.Society(c); s.state['round'] = 1
        snapshot = copy.deepcopy(s.state)
        with patch.object(mini_world, 'act', side_effect=lambda cfg, state, aid, action: state['agents'][aid].update(stock=999)):
            with self.assertRaises(ValueError): s.act('a0', {'tool': 'wait'})
        self.assertEqual(s.state, snapshot)

    def test_scoped_claim_verification_does_not_modify_actual_state(self):
        c = config(); s = sim.Society(c); initial = copy.deepcopy(s.state)
        claim = {'type': 'experiment_output', 'source': {'agent': 'a0', 'round': 1, 'event': 'trial'},
                 'action': {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine', 'inputs': [{'item': 'A', 'amount': 2}, {'item': 'B', 'amount': 1}], 'batches': 1},
                 'predicted_output': {'C': 1}}
        checked = knowledge.verify_claim(c, claim, [{'id': 'heldout_1', 'seed': 9}, {'id': 'heldout_2', 'seed': 11}])
        self.assertEqual(checked['status'], 'passed_scoped_tests'); self.assertEqual(s.state, initial)
        claim['predicted_output'] = {'C': 2}
        self.assertEqual(knowledge.verify_claim(c, claim, [{'id': 'bad'}])['status'], 'refuted_in_tests')

    def test_branch_preserves_world_inventory_relationships_and_rejects_tampering(self):
        c = config(); s = sim.Society(c); s.state['round'] = 1; settle(s)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'branch.json'; doc = branches.export_branch(c, s.state, path)
            c['initial_checkpoint_branch'] = {'path': str(path), 'sha256': branches.digest(doc)}
            self.assertEqual(branches.load_branch(c), s.state)
            changed = copy.deepcopy(c); changed['seed'] += 1
            with self.assertRaises(ValueError): branches.load_branch(changed)
            doc['state']['agents']['a0']['stock'] += 1; path.write_text(json.dumps(doc), 'utf-8')
            with self.assertRaises(ValueError): branches.load_branch(c)

    def test_claim_check_preserves_liquid_balance_dependent_world_condition(self):
        c = config()
        mini_world.spec(c)['recipes'][0]['condition'] = library.expr('lt', library.ref('liquid_total'), 100)
        claim = {'type': 'experiment_output', 'source': {'agent': 'a0', 'event': 'trial'},
                 'action': {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine', 'inputs': [{'item': 'A', 'amount': 2}, {'item': 'B', 'amount': 1}], 'batches': 1},
                 'predicted_output': {'C': 1}}
        self.assertEqual(knowledge.verify_claim(c, claim, [{'id': 'liquid_condition'}])['status'], 'passed_scoped_tests')

    def test_knowledge_publication_retains_private_memory_and_resources(self):
        c = config(); s = sim.Society(c)
        claim = {'type': 'experiment_output', 'source': {'agent': 'a0', 'event': 'trial'},
                 'action': {'tool': 'experiment', 'facility': 'F0', 'mode': 'combine', 'inputs': [{'item': 'A', 'amount': 2}, {'item': 'B', 'amount': 1}], 'batches': 1}, 'predicted_output': {'C': 1}}
        verified = knowledge.verify_claim(c, claim, [{'id': 'test'}])
        with tempfile.TemporaryDirectory() as folder:
            doc = branches.export_branch(c, s.state, Path(folder)/'info.json', 'publish_verified_knowledge', [verified])
            self.assertEqual(doc['state']['mini_world'], s.state['mini_world'])
            self.assertEqual(doc['state']['agents']['a0']['memory'], s.state['agents']['a0']['memory'])
            self.assertTrue(doc['state']['agents']['a0']['inbox'])
            self.assertEqual(s.state['agents']['a0']['inbox'], [])

    def test_witness_distinguishes_fixed_noise_from_formal_certificate(self):
        c = config(noise=.2); plan = certificates.alternating_plan(c)
        for joint in plan:
            for action in joint.values():
                if action['tool'] == 'gather': action['amount'] = 3
        checked = certificates.replay(c, plan)
        self.assertEqual(checked['status'], 'replayed_full_survival')
        self.assertEqual(checked['formal_status'], 'not_lean_verified')
        self.assertEqual(checked['noise_scope'], 'fixed_seed_trajectory_only')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError): certificates.export_lean(c, checked, Path(folder)/'bad.lean')

    def test_lean_export_is_restricted_and_absent_lean_is_not_success(self):
        c = config(); d = mini_world.spec(c)
        for r in d['resources'].values(): r['decay'] = 0
        checked = certificates.replay(c, certificates.alternating_plan(c))
        with tempfile.TemporaryDirectory() as folder:
            artifact = certificates.export_lean(c, checked, Path(folder)/'proof.lean')
            self.assertEqual(artifact['status'], 'exported_not_checked')
            with patch.object(certificates, 'find_lean', return_value=None):
                self.assertEqual(certificates.check_lean(artifact)['status'], 'lean_unavailable')

    def test_paid_experiment_rejects_uncertified_world_before_api(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sim, 'API') as api:
            with self.assertRaisesRegex(ValueError, 'checked survival certificate'):
                sim.run(config(), folder, mock=False)
            api.assert_not_called()

    def test_interrupt_resume_matches_uninterrupted_material_trajectory(self):
        c = config()
        with tempfile.TemporaryDirectory() as folder, patch.object(sim, 'API', PhysicalAPI):
            baseline = Path(folder)/'baseline'; interrupted = Path(folder)/'interrupted'
            PhysicalAPI.fail_key = None; sim.run(c, baseline, mock=True)
            PhysicalAPI.fail_key = 'act:2:a1'
            with self.assertRaises(RuntimeError): sim.run(c, interrupted, mock=True)
            PhysicalAPI.fail_key = None; sim.run(c, interrupted, mock=True, resume=True)
            a = json.loads((baseline/'checkpoint.json').read_text('utf-8'))['state']
            b = json.loads((interrupted/'checkpoint.json').read_text('utf-8'))['state']
            self.assertEqual(a, b)
            from audit_actions import audit
            self.assertTrue(audit(interrupted)['verified_replay'])

    def test_branch_continuation_uses_source_round_and_replays(self):
        c = config()
        with tempfile.TemporaryDirectory() as folder, patch.object(sim, 'API', PhysicalAPI):
            PhysicalAPI.fail_key = None
            short = copy.deepcopy(c); short['rounds'] = 2; sim.run(short, Path(folder)/'source', mock=True)
            state = json.loads((Path(folder)/'source/checkpoint.json').read_text('utf-8'))['state']
            path = Path(folder)/'branch.json'; doc = branches.export_branch(c, state, path)
            c['initial_checkpoint_branch'] = {'path': str(path), 'sha256': branches.digest(doc)}
            sim.run(c, Path(folder)/'continued', mock=True)
            from audit_actions import audit
            self.assertTrue(audit(Path(folder)/'continued')['verified_replay'])


if __name__ == '__main__': unittest.main()

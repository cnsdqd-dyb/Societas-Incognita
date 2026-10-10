import copy
import unittest

import capability_feasibility as feasibility
import mini_world
from test_material_capabilities import device_config


class FeasibilityTests(unittest.TestCase):
    def test_from_empty_material_inventory_each_device_has_a_pressure_pair_witness(self):
        for pressure in (False, True):
            for target in ('relay', 'archive', 'sensor', 'workbench'):
                with self.subTest(pressure=pressure, target=target):
                    c = device_config(); c['world']['survival_pressure'] = pressure
                    c['communication']['budget']['limit'] = 1000
                    before = copy.deepcopy(c)
                    report = feasibility.evaluate(c, target)
                    self.assertEqual(report['status'], 'feasible_witness_found', report['reason'])
                    self.assertEqual(report['verification']['score'], 200)
                    self.assertEqual(len(report['plan']), 50)
                    self.assertEqual(report['verification']['formal_status'], 'not_lean_verified')
                    self.assertEqual(report['optimality'], 'not_computed')
                    self.assertEqual(c, before)
                    self.assertTrue(all(all(a['alive'] for a in step['members'].values()) for step in report['trace']))
                    self.assertTrue(all(abs(step['energy_accounting']['residual']) < 1e-7 for step in report['trace']))

    def test_failed_bounded_strategy_is_inconclusive_not_impossibility(self):
        c = device_config(); report = feasibility.evaluate(c, 'workbench', horizon=2)
        self.assertEqual(report['status'], 'inconclusive_strategy_failure')
        self.assertNotIn('verification', report)
        self.assertLessEqual(len(report['plan']), 2)
        c['communication']['budget']['limit'] = 0
        report = feasibility.evaluate(c, 'relay')
        self.assertEqual(report['status'], 'inconclusive_strategy_failure')
        self.assertIn('no increment', report['reason'])

    def test_unreachable_selected_dependency_fails_without_free_endowment(self):
        c = device_config(); mini_world.spec(c)['recipes'] = []
        report = feasibility.evaluate(c, 'sensor')
        self.assertEqual(report['status'], 'inconclusive_strategy_failure')
        self.assertEqual(report['goal'], None)
        self.assertEqual(report['api_cost_usd'], 0)

    def test_replay_rejects_fabricated_or_missing_capability_evidence(self):
        c = device_config(); c['communication']['budget']['limit'] = 1000
        report = feasibility.evaluate(c, 'relay', horizon=20)
        self.assertEqual(report['status'], 'feasible_witness_found')
        for mutate in ('missing', 'inactive', 'fake_base', 'wrong_target'):
            goal = copy.deepcopy(report['goal'])
            if mutate == 'missing': goal['evidence'] = {}
            if mutate == 'inactive': goal['round'] = 1
            if mutate == 'fake_base': goal['evidence']['communication']['base_limit'] = 500
            if mutate == 'wrong_target': goal['recipe'] = 'sensor'
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                feasibility.verify(c, 'relay', report['plan'], goal)

    def test_replay_rejects_deleted_fuel_payment_and_unauthorized_activation(self):
        c = device_config(); report = feasibility.evaluate(c, 'archive', horizon=15)
        self.assertEqual(report['status'], 'feasible_witness_found')
        plan = copy.deepcopy(report['plan'])
        activation = next(j for j in plan if j['a0']['tool'] == 'activate_device')
        activation['a0'] = {'tool': 'wait'}
        with self.assertRaises(ValueError): feasibility.verify(c, 'archive', plan, report['goal'])
        plan = copy.deepcopy(report['plan'])
        activation = next(j for j in plan if j['a0']['tool'] == 'activate_device')
        activation['a0']['targets'] = ['a1']
        with self.assertRaises(ValueError): feasibility.verify(c, 'archive', plan, report['goal'])

    def test_report_is_bound_to_configuration_and_material_order_is_irrelevant(self):
        c = device_config(); report = feasibility.evaluate(c, 'workbench')
        self.assertEqual(feasibility.verify_report(c, report)['score'], 200)
        changed = copy.deepcopy(c); changed['seed'] += 1
        with self.assertRaises(ValueError): feasibility.verify_report(changed, report)
        reordered = copy.deepcopy(report)
        for joint in reordered['plan']:
            for action in joint.values():
                if 'inputs' in action: action['inputs'].reverse()
        self.assertEqual(feasibility.verify_report(c, reordered)['score'], 200)

    def test_joint_action_completeness_and_simulator_execution_order(self):
        import random
        c = device_config(); report = feasibility.evaluate(c, 'archive', horizon=15)
        for step in report['trace']:
            expected = sorted(step['actions']); random.Random(c['seed']+step['round']).shuffle(expected)
            self.assertEqual(step['execution_order'], expected)
        plan = copy.deepcopy(report['plan']); del plan[0]['a2']
        with self.assertRaisesRegex(ValueError, 'one action'):
            feasibility.verify(c, 'archive', plan, report['goal'])


if __name__ == '__main__': unittest.main()

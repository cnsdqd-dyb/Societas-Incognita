import copy
import json
import unittest
from pathlib import Path

from make_core_matrix import configuration
from sim import Society
from state_assessment import rollout, wait_policy, congestion_t10_recovery


class StateAssessmentTests(unittest.TestCase):
    def config(self, family, pressure=True):
        base = json.loads(Path('configs/smoke.json').read_text(encoding='utf-8'))
        return configuration(base, family, 7, pressure, 'information', 100, 8)

    def test_wait_baseline_respects_private_inflow_and_no_pressure(self):
        for family, pressure in [('public_goods', True), ('congestion', False)]:
            cfg = self.config(family, pressure)
            state = Society(cfg).state
            self.assertEqual(rollout(cfg, state, wait_policy, 50)['feasibility'], 'finite_horizon_witness')

    def test_recovery_witness_does_not_mutate_state_or_claim_failed_policy_impossible(self):
        cfg = self.config('congestion')
        state = Society(cfg).state
        state['round'] = 10
        for aid, a in state['agents'].items():
            a.update(stock=0, energy=0, alive=False)
        for aid, stock, energy in [('a0', 0, 3), ('a1', 5, 2), ('a6', 0, 4)]:
            state['agents'][aid].update(stock=stock, energy=energy, alive=True)
        before = copy.deepcopy(state)
        failed = rollout(cfg, state, wait_policy, 50)
        self.assertEqual(failed['feasibility'], 'not_established')
        success = rollout(cfg, state, congestion_t10_recovery, 50)
        self.assertEqual(success['feasibility'], 'finite_horizon_witness')
        self.assertEqual(state, before)
        # Recovery uses no same-round transfer-and-process dependency.
        state['agents'] = dict(reversed(list(state['agents'].items())))
        self.assertEqual(rollout(cfg, state, congestion_t10_recovery, 50)['feasibility'], 'finite_horizon_witness')

    def test_invalid_actions_are_reported_and_not_a_valid_witness(self):
        cfg = self.config('public_goods')
        state = Society(cfg).state
        bad = lambda state, step: {'a0': {'tool': 'transfer', 'target': 'a1', 'amount': 999}}
        result = rollout(cfg, state, bad, 2)
        self.assertTrue(result['all_initial_living_survive'])
        self.assertEqual(result['feasibility'], 'not_established')
        self.assertIn('a0', result['trace'][0]['action_errors'])

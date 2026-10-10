import json
import unittest
from pathlib import Path

from compute_dynamic_benchmarks import compact_initial, policy, certified_rows
from make_core_matrix import configuration
from state_assessment import rollout


class CertifiedBenchmarkTests(unittest.TestCase):
    def config(self, family, pressure=True):
        base = json.loads(Path('configs/smoke.json').read_text(encoding='utf-8'))
        cfg=configuration(base, family, 7, pressure, 'information', 50, 8)
        # These certificates are explicitly for the original four environments,
        # before storage losses and additional destructive actions were introduced.
        cfg.pop('resource_seizure',None)
        cfg['tools']=[t for t in cfg['tools'] if t not in ('seize','defend','secure','withdraw')]
        return cfg

    def test_extended_action_space_cannot_reuse_legacy_certificate(self):
        base=json.loads(Path('configs/smoke.json').read_text('utf-8'))
        cfg=configuration(base,'public_goods',7,True,'information',50,8)
        with self.assertRaisesRegex(ValueError,'extended action space'):
            certified_rows(cfg,[],'extended')

    def snapshots(self, cfg, kind, horizon):
        return [{'round': t['round'], 'agents': t['agents']}
                for t in rollout(cfg, compact_initial(cfg), policy(cfg, kind), horizon)['trace']]

    def test_survival_extremes_attain_certified_global_bounds(self):
        for family, worst, expected in [('commons', 'wait', 0),
                                         ('contest', 'monopoly', 1),
                                         ('congestion', 'delayed_crowding', 0)]:
            cfg = self.config(family)
            rows, _ = certified_rows(cfg, self.snapshots(cfg, worst, 12), 'test')
            self.assertTrue(rows[-1]['worst_alive_exact'])
            self.assertEqual(rows[-1]['worst_alive_lower_bound'], expected)
            self.assertEqual(rows[-1]['optimal_alive_exact'], 8)

    def test_public_goods_wealth_formula_for_every_round_and_pressure_pair(self):
        for pressure in (False, True):
            cfg = self.config('public_goods', pressure)
            w = cfg['world']
            max_policy = lambda s, t: {i: {'tool': 'contribute', 'amount': w['max_contribution']}
                                      for i in s['agents']}
            trace = rollout(cfg, compact_initial(cfg), max_policy, 20)['trace']
            rows, _ = certified_rows(cfg, [{'round': t['round'], 'agents': t['agents']} for t in trace], 'test')
            for row in rows:
                self.assertAlmostEqual(row['stock_range_position'], 1.)
                self.assertEqual(row['worst_alive_lower_bound'], 8)

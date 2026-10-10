import copy
import tempfile
import unittest
from pathlib import Path

import composed_certificates as proof
import production_semantics
import sim
import mini_world
import world_rule_library as library
from test_mini_world import config, endow, settle


def fixture():
    cfg = config(pressure=False)
    cfg['rounds'] = 4
    cfg['world']['initial_personal_stock'] = 20
    d = cfg['world']['mini_world']['definition']
    d['production_semantics'] = 'proportional_v1'
    d['resources']['C']['decay'] = 0
    d['recipes'] = [dict(id='ratio', facility='F0', mode='combine', inputs={'A':8,'B':4},
                         output='C', yield_=2, energy_cost=4, condition=1, effects={})]
    d['recipes'][0]['yield'] = d['recipes'][0].pop('yield_')
    d['initial_inventory'] = {'A':8, 'B':4}
    return cfg


def action(a=2, b=1):
    return dict(tool='experiment', facility='F0', mode='combine',
                inputs=[dict(item='A',amount=a),dict(item='B',amount=b)], batches=1)


class ProportionalProduction(unittest.TestCase):
    def run_plan(self, cfg, plan):
        s = sim.Society(cfg)
        for t, act in enumerate(plan,1):
            s.state['round']=t
            s.act('a0',act)
            settle(s)
        return s

    def test_small_batches_accumulate_without_rounding_away_or_creating_energy(self):
        small=self.run_plan(fixture(),[action() for _ in range(4)])
        big=self.run_plan(fixture(),[action(8,4)]+[{'tool':'wait'} for _ in range(3)])
        for s in (small,big):
            self.assertAlmostEqual(s.state['agents']['a0']['inventory']['C'],2)
            self.assertAlmostEqual(mini_world.accounting(s.cfg,s.state)['residual'],0,places=8)
        self.assertEqual([x['produced']['C'] for x in small.state['mini_world']['discoveries']['a0']],[.5]*4)
        # Trial fees are per action; operation costs and output are proportional.
        self.assertAlmostEqual(big.state['agents']['a0']['stock']-small.state['agents']['a0']['stock'],.3)

    def test_normalizing_preserves_output_and_paid_energy(self):
        cfg=fixture(); normalized=copy.deepcopy(cfg)
        production_semantics.normalize(normalized['world']['mini_world']['definition'])
        self.assertEqual(normalized['world']['mini_world']['definition']['recipes'][0]['inputs'],{'A':2,'B':1})
        a=self.run_plan(cfg,[action()]);b=self.run_plan(normalized,[action()])
        self.assertEqual(a.state['agents']['a0']['inventory'],b.state['agents']['a0']['inventory'])
        self.assertEqual(a.state['agents']['a0']['stock'],b.state['agents']['a0']['stock'])

    def test_fractional_output_obeys_material_decay(self):
        cfg=fixture();cfg['world']['mini_world']['definition']['resources']['C']['decay']=.1
        s=self.run_plan(cfg,[action(),action()])
        self.assertAlmostEqual(s.state['agents']['a0']['inventory']['C'],.855)
        self.assertAlmostEqual(mini_world.accounting(cfg,s.state)['residual'],0,places=8)

    def test_device_minimum_is_explicit_and_failed_trial_refunds_materials(self):
        cfg=fixture();cfg['world']['mini_world']['definition']['facilities']['F0']['min_processing_extent']=1
        s=self.run_plan(cfg,[action()])
        self.assertEqual(s.state['mini_world']['discoveries']['a0'][0]['result'],'below_device_minimum')
        self.assertEqual(s.state['agents']['a0']['inventory']['A'],8)
        self.assertEqual(s.state['agents']['a0']['inventory']['C'],0)
        normalized=copy.deepcopy(cfg)
        production_semantics.normalize(normalized['world']['mini_world']['definition'])
        s2=self.run_plan(normalized,[action()])
        self.assertEqual(s2.state['mini_world']['discoveries']['a0'][0]['result'],'below_device_minimum')
        self.assertEqual(s2.state['agents']['a0']['inventory'],s.state['agents']['a0']['inventory'])

    def test_fractional_production_and_explicit_minimum_have_real_kernel_certificates(self):
        for minimum in (0,1):
            cfg=fixture();cfg['world']['mini_world']['definition']['facilities']['F0']['min_processing_extent']=minimum
            plan=[{a:(action() if a=='a0' else {'tool':'wait'}) for a in ('a0','a1','a2','a3')} for _ in range(4)]
            with tempfile.TemporaryDirectory() as folder:
                artifact=proof.export(cfg,plan,Path(folder)/'ratio.lean',semantic=True)
                result=proof.check(artifact)
                self.assertEqual(result['status'],'lean_checked_composed_interval_certificate',result.get('diagnostics'))

    def test_generated_ratios_are_simple_and_unambiguous(self):
        keys=[key for key,_ in library.CANDIDATES_20]
        for seed in range(5):
            d=library.generate(seed,keys)['definition']
            self.assertEqual(d['production_semantics'],'proportional_v1')
            self.assertTrue(all(n<=3 for r in d['recipes'] for n in r['inputs'].values()))


if __name__=='__main__':
    unittest.main()

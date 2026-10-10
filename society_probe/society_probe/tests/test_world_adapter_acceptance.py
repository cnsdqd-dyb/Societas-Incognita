"""Differential acceptance, not a formal proof of the Python compiler."""
import json
import tempfile
import unittest
from pathlib import Path

import composed_certificates as proof
import sim
import world_rule_library as library
from test_material_capabilities import device_config


class WorldAdapterAcceptance(unittest.TestCase):
    def test_effectless_item_still_requires_possession(self):
        cfg=device_config(); action={'tool':'use_item','item':'A','amount':1}
        with self.assertRaises(ValueError): sim.Society(cfg).act('a0',action)
        with self.assertRaisesRegex(proof.Unsupported,'assets'): proof.Compiler(cfg).act('a0',action)

    def test_all_device_witnesses_match_after_every_action(self):
        with tempfile.TemporaryDirectory() as folder:
            for pressure in (0,1):
                cfg=json.loads(Path(f'configs/capability_fixtures_20261010/capabilities_4agents_p{pressure}_hidden.json').read_text('utf-8'))
                for target in ('relay','archive','sensor','workbench'):
                    with self.subTest(pressure=pressure,target=target):
                        plan=json.loads(Path(f'reports/capability_feasibility_20261010/{target}_p{pressure}.json').read_text('utf-8'))['plan']
                        result=proof.export(cfg,plan,Path(folder)/f'{target}_{pressure}.lean')
                        self.assertGreater(result['action_phase_audit']['comparisons'],result['float_replay_audit']['comparisons'])

    def test_each_module_across_seeds_and_pressure_matches(self):
        source=device_config()
        with tempfile.TemporaryDirectory() as folder:
            for module in library.MODULES:
                for seed in (1,7):
                    for pressure in (False,True):
                        with self.subTest(module=module,seed=seed,pressure=pressure):
                            cfg=library.configure(source,library.generate(seed,[module]),pressure=pressure)
                            plan=[{f'a{i}':{'tool':'gather','item':'A','amount':2} if t%2==0 else
                                {'tool':'liquidate','item':'A','amount':1} for i in range(4)} for t in range(6)]
                            result=proof.export(cfg,plan,Path(folder)/'world.lean')
                            self.assertGreater(result['action_phase_audit']['comparisons'],0)

    def test_intermediate_drift_cannot_hide_behind_equal_round_end_state(self):
        from unittest.mock import patch
        cfg=device_config(); plan=[{f'a{i}':{'tool':'wait'} for i in range(4)}]
        original=proof.Compiler.run
        def drift(compiler,plan):
            original(compiler,plan)
            compiler.action_rows[0]['stock']['a0']=proof.Wire(-1,proof.F(999),proof.F(999))
            return compiler
        with tempfile.TemporaryDirectory() as folder, patch.object(proof.Compiler,'run',drift):
            with self.assertRaisesRegex(proof.Unsupported,'after='):
                proof.export(cfg,plan,Path(folder)/'bad.lean')

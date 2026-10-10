import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import composed_certificates as proof
import survival_certificates as legacy
from test_material_capabilities import device_config


class ComposedCertificates(unittest.TestCase):
    def test_interval_operations_reject_ambiguous_branches_and_zero_divisor(self):
        c=proof.Circuit(); x=c.emit('add',None,None,proof.F(-1),proof.F(1))
        for op in ('floor','truth'):
            with self.assertRaises(proof.Unsupported): c.op(op,x)
        with self.assertRaises(proof.Unsupported): c.op('div',1,x)
        self.assertEqual(c.op('mul',c.const('0.98'),c.const(2)).lo,proof.F('1.96'))

    def test_noise_transcendental_and_unsupported_actions_are_not_silently_dropped(self):
        cfg=device_config(); cfg['world']['mini_world']['definition']['noise']={'distribution':'uniform','amplitude':.2}
        with self.assertRaisesRegex(proof.Unsupported,'Noise'): proof.Compiler(cfg)
        cfg=device_config(); cfg['world']['mini_world']['definition']['external_inflow']={'op':'exp','args':[0]}
        with self.assertRaisesRegex(proof.Unsupported,'exp'): proof.Compiler(cfg)
        cfg=device_config(); compiler=proof.Compiler(cfg)
        joint={aid:{'tool':'wait'} for aid in compiler.ids}; joint['a0']={'tool':'cancel_items','offer':'unknown'}
        with self.assertRaisesRegex(proof.Unsupported,'not covered'): compiler.run([joint])

    def test_death_missing_actions_and_failed_payment_do_not_get_certificates(self):
        cfg=device_config(); cfg['world']['survival_pressure']=True
        plan=[{f'a{i}':{'tool':'wait'} for i in range(4)} for _ in range(10)]
        with self.assertRaisesRegex(proof.Unsupported,'death'): proof.Compiler(cfg).run(plan)
        with self.assertRaisesRegex(proof.Unsupported,'one action'): proof.Compiler(cfg).run([{'a0':{'tool':'wait'}}])
        compiler=proof.Compiler(cfg)
        with self.assertRaisesRegex(proof.Unsupported,'assets'): compiler.act('a0',{'tool':'liquidate','item':'D','amount':1})

    def test_kernel_accepts_correct_constraints_and_rejects_false_arithmetic(self):
        self.assertIsNotNone(legacy.find_lean(),'Actual Lean is required for this test')
        checker=Path('composed_checker.lean').read_text('utf-8')
        valid='''
open Composed
def a : Box := ⟨⟨1,1⟩,⟨1,1⟩⟩
def b : Box := ⟨⟨2,1⟩,⟨2,1⟩⟩
def r : Box := ⟨⟨3,1⟩,⟨3,1⟩⟩
theorem validAddition : check ⟨.add,a,b,r⟩ = true := by decide
'''
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'kernel.lean'; path.write_text(checker+valid,encoding='utf-8')
            artifact={'source':str(path),'sha256':hashlib.sha256((checker+valid).encode()).hexdigest()}
            self.assertEqual(proof.check(artifact)['status'],'lean_checked_composed_interval_certificate')
            wrong=(checker+valid).replace('⟨3,1⟩','⟨4,1⟩'); path.write_text(wrong,encoding='utf-8')
            artifact['sha256']=hashlib.sha256(wrong.encode()).hexdigest()
            self.assertEqual(proof.check(artifact)['status'],'lean_rejected')

    def test_current_fifty_round_device_certificate_is_rechecked_at_admission(self):
        cfg=json.loads(Path('reports/composed_lean_20261010/archive_p1_certified_config.json').read_text('utf-8'))
        self.assertEqual(legacy.validate_admission(cfg)['status'],'lean_checked_composed_interval_certificate')
        changed=copy.deepcopy(cfg); changed['world']['consumption']=2
        with self.assertRaises(ValueError): legacy.validate_admission(changed)

    def test_all_six_mathematical_modules_have_an_actual_lean_checked_example(self):
        cfg=json.loads(Path('reports/composed_lean_20261010/all_six_modules_config.json').read_text('utf-8'))
        record=json.loads(Path('reports/composed_lean_20261010/all_six_modules_check.json').read_text('utf-8'))
        self.assertEqual(len(cfg['experiment']['generation']['modules']),6)
        self.assertEqual(record['horizon'],50)
        self.assertEqual(record['status'],'lean_checked_composed_interval_certificate')
        checked=proof.check(record)
        self.assertEqual(checked['status'],'lean_checked_composed_interval_certificate',checked)

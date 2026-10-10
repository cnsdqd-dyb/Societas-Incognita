import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import composed_certificates as composed
import graph_certificates
import interval_proofs
from test_material_capabilities import device_config


class DependencyCertificates(unittest.TestCase):
    def test_full_world_requirement_cannot_be_satisfied_by_a_graph_certificate(self):
        cfg=device_config(); cfg['require_end_to_end_world_proof']=True
        with self.assertRaisesRegex(ValueError,'End-to-end world proof is not implemented'):
            composed.validate_admission(cfg,{'version':'composed_semantic_survival_v2'})

    def simple(self,path):
        c=composed.Circuit(); c.op('add',2,3)
        pairs={}; lines=[interval_proofs.source(True)]
        for _,_,_,w,_ in c.nodes:
            pairs[w.index]='box'+str(w.index)
            lines.append(f'def box{w.index} : Composed.Box := ⟨{composed.qsource(w.lo)},{composed.qsource(w.hi)}⟩')
        text,meta=graph_certificates.fragment(c,lambda w:pairs[w.index],composed.qsource)
        data='\n'.join(lines)+'\n'+text
        path.write_text(data,encoding='utf-8')
        return {'source':str(path),'sha256':hashlib.sha256(data.encode()).hexdigest(),**meta}

    def test_generic_graph_induction_and_real_dependency_proofs(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact=self.simple(Path(folder)/'good.lean')
            checked=composed.check(artifact)
        self.assertEqual(checked['status'],'lean_checked_composed_interval_certificate',checked)
        self.assertEqual(artifact['graph_nodes'],3)

    def test_wrong_dependency_and_false_operation_are_rejected(self):
        for replacement in ('def actual2 : Q := evalOp .add actual0 actual0',
                            'def actual2 : Q := evalOp .sub actual0 actual1',
                            'def actual2 : Q := evalOp .add actual0 actual999'):
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'bad.lean'; artifact=self.simple(path)
                data=path.read_text('utf-8')
                original='def actual2 : Q := witness2.val'
                self.assertIn(original,data); data=data.replace(original,replacement,1)
                path.write_text(data,encoding='utf-8'); artifact['sha256']=hashlib.sha256(data.encode()).hexdigest()
                checked=composed.check(artifact)
                self.assertEqual(checked['status'],'lean_rejected',checked)

    def test_counterfeit_and_future_wires_cannot_be_exported(self):
        c=composed.Circuit(); a=c.const(2)
        fake=composed.Wire(a.index,a.lo,a.hi)
        c.emit('add',fake,a,composed.F(4),composed.F(4))
        with self.assertRaisesRegex(ValueError,'counterfeit'):
            graph_certificates.fragment(c,lambda w:'irrelevant',composed.qsource)

    def test_two_round_survival_is_linked_to_actual_values_and_bound_at_admission(self):
        cfg=device_config(); cfg['rounds']=2
        plan=[{f'a{i}':{'tool':'wait'} for i in range(4)} for _ in range(2)]
        with tempfile.TemporaryDirectory() as folder:
            artifact=composed.export(cfg,plan,Path(folder)/'world.lean',semantic=True)
            checked=composed.check(artifact)
            self.assertEqual(checked['status'],'lean_checked_composed_interval_certificate',checked)
            self.assertEqual(checked['semantic_live_outputs'],8)
            text=Path(artifact['source']).read_text('utf-8')
            self.assertIn('certified_semantic_survival',text)
            bundle={'version':'composed_semantic_survival_v2','plan':plan,'lean':checked}
            self.assertEqual(composed.validate_admission(cfg,bundle)['status'],'lean_checked_composed_interval_certificate')
            wrong=json.loads(json.dumps(bundle)); wrong['lean']['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'does not match'):
                composed.validate_admission(cfg,wrong)

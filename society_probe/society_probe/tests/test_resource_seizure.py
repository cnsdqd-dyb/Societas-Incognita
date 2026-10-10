import copy
import json
import unittest
from pathlib import Path
import jsonschema
from sim import Society
from resource_seizure import configure
from metrics import measure
from schemas import schema
from audit_actions import well_formed
from make_core_matrix import configuration

BASE=json.loads(Path('configs/smoke.json').read_text('utf-8'))

class ResourceSeizureTests(unittest.TestCase):
    def config(self,family='contest'):
        return configure(configuration(BASE,family,7,False,'information',50,8),'seizure_v1')

    def test_conservation_and_private_notice_in_all_families(self):
        for family in ('commons','public_goods','contest','congestion'):
            s=Society(self.config(family));s.state['round']=1
            before=sum(a['stock'] for a in s.state['agents'].values())
            outcome=s.act('a0',{'tool':'seize','target':'a1','amount':2})
            self.assertEqual(outcome['seized'],2);self.assertEqual(s.state['agents']['a0']['stock'],5.5)
            self.assertEqual(s.state['agents']['a1']['stock'],2)
            self.assertEqual(sum(a['stock'] for a in s.state['agents'].values()),before-.5)
            self.assertEqual(s.observe('a1')['new_messages'][0]['from'],'a0')
            self.assertFalse(s.observe('a2')['new_messages'])

    def test_empty_target_is_valid_paid_failure_and_fractional_stock(self):
        s=Society(self.config());s.state['agents']['a1']['stock']=.3
        self.assertAlmostEqual(s.act('a0',{'tool':'seize','target':'a1','amount':2})['seized'],.3)
        before=s.state['agents']['a0']['stock']
        outcome=s.act('a0',{'tool':'seize','target':'a1','amount':1})
        self.assertFalse(outcome['success']);self.assertEqual(outcome['seized'],0)
        self.assertAlmostEqual(s.state['agents']['a0']['stock'],before-.5)

    def test_invalid_and_unaffordable_actions_do_not_mutate(self):
        s=Society(self.config())
        for action in ({'tool':'seize','target':'a0','amount':1},{'tool':'seize','target':'missing','amount':1},
            {'tool':'seize','target':'a1','amount':3},{'tool':'seize','target':'a1','amount':True}):
            before=copy.deepcopy(s.state)
            with self.assertRaises(ValueError):s.act('a0',action)
            self.assertEqual(s.state,before)
        s.state['agents']['a0']['stock']=0;before=copy.deepcopy(s.state)
        with self.assertRaises(ValueError):s.act('a0',{'tool':'seize','target':'a1','amount':1})
        self.assertEqual(s.state,before)
        s.state['agents']['a0']['stock']=4;s.state['agents']['a1']['alive']=False;before=copy.deepcopy(s.state)
        with self.assertRaises(ValueError):s.act('a0',{'tool':'seize','target':'a1','amount':1})
        self.assertEqual(s.state,before)

    def test_legacy_world_schema_and_audit(self):
        cfg=configure(copy.deepcopy(BASE),'seizure_v1');s=Society(cfg)
        action={'tool':'seize','target':'a1','amount':2}
        self.assertTrue(well_formed(action,cfg))
        jsonschema.validate({'action':action,'communication':{'op':'silent'}},schema('act',s.observe('a0'),cfg))
        self.assertEqual(s.act('a0',action)['seized'],2)
        self.assertFalse(well_formed({**action,'amount':3},cfg))

    def test_successive_seizures_cannot_overdraw_and_metrics_are_separate(self):
        cfg=self.config();s=Society(cfg);s.state['round']=1;s.state['agents']['a1']['stock']=1
        s.act('a0',{'tool':'seize','target':'a1','amount':2})
        s.act('a2',{'tool':'seize','target':'a1','amount':2})
        self.assertEqual(s.state['agents']['a1']['stock'],0)
        s.state['snapshots']=[{'round':1,'agents':copy.deepcopy(s.state['agents'])}]
        row=measure(s.state,cfg)['round_series'][0]
        self.assertEqual(row['seizure_attempts'],2);self.assertEqual(row['seizure_successes'],1)
        self.assertEqual(row['seized_stock'],1);self.assertEqual(row['seizure_cost'],1)
        self.assertEqual(row['seizure_graph']['directed_edges'],[['a0','a1']])
        self.assertFalse(row['transfer_graph']['directed_edges'])

if __name__=='__main__':unittest.main()

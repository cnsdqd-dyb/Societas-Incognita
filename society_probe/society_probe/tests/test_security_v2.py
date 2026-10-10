import copy
import json
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path
import jsonschema
import environments
from sim import Society,run,API
from resource_seizure import configure,local_attack_bounds,conditional_defense_bounds
from schemas import schema
from audit_actions import well_formed,audit

CFG=Path('configs/open_contest_mix_v1_20261009/contest_mixed4_p1_s7.json')

class SecurityV2Tests(unittest.TestCase):
    def society(self):return Society(configure(json.loads(CFG.read_text('utf-8'))))
    def attack(self,s,resource='liquid',target='a1',effort=1):
        return s.act('a0',{'tool':'seize','target':target,'resource':resource,'amount':2,'effort':effort})

    def test_capture_rate_energy_storage_and_defense(self):
        s=self.society();self.assertAlmostEqual(self.attack(s)['seized'],1.)
        s=self.society();s.state['agents']['a1']['energy']=1
        self.assertAlmostEqual(self.attack(s)['seized'],1.25)
        s=self.society();s.state['agents']['a1']['vault']=4
        self.assertAlmostEqual(self.attack(s,'vault')['seized'],.4)
        s=self.society();s.state['agents']['a1']['defense_schedule']={'0':2}
        outcome=self.attack(s)
        self.assertAlmostEqual(outcome['capture_fraction'],.25)
        self.assertAlmostEqual(outcome['seized'],.5)

    def test_defense_is_next_round_and_renewal_preserves_current(self):
        s=self.society();s.state['round']=1;s.act('a1',{'tool':'defend','effort':2})
        self.assertAlmostEqual(self.attack(s)['seized'],1.)
        s.state['round']=2;s.act('a1',{'tool':'defend','effort':1})
        outcome=self.attack(s)
        self.assertAlmostEqual(outcome['capture_fraction'],.25)
        self.assertAlmostEqual(outcome['seized'],.375)
        s.settle(environments.physical_snapshot(s.state))
        self.assertEqual(s.state['agents']['a1']['defense_schedule'],{'3':1})

    def test_storage_conservation_decay_and_fractional_withdrawal(self):
        s=self.society();s.state['round']=1;s.act('a1',{'tool':'secure','amount':2})
        self.assertEqual(s.state['agents']['a1']['stock']+s.state['agents']['a1']['vault'],4)
        s.settle(environments.physical_snapshot(s.state))
        self.assertAlmostEqual(s.state['agents']['a1']['vault'],1.9)
        self.assertAlmostEqual(s.state['environment_history'][-1]['vault_storage_loss'],.1)
        self.assertAlmostEqual(s.act('a1',{'tool':'withdraw','amount':2})['withdrawn'],1.9)
        self.assertEqual(s.state['agents']['a1']['vault'],0)

    def test_vault_cannot_pay_cost_or_maintenance_and_reject_is_atomic(self):
        s=self.society();s.state['agents']['a0'].update(stock=0,vault=4)
        prior=copy.deepcopy(s.state)
        with self.assertRaises(ValueError):self.attack(s)
        self.assertEqual(s.state,prior)
        s.state['mixed']['health'][0]=0;s.settle(environments.physical_snapshot(s.state))
        self.assertEqual(s.state['agents']['a0']['energy'],4)
        self.assertAlmostEqual(s.state['agents']['a0']['vault'],3.8)

    def test_ledger_schema_and_conditional_math(self):
        s=self.society();before=sum(a['stock']+a['vault'] for a in s.state['agents'].values())
        action={'tool':'seize','target':'a1','resource':'liquid','amount':2,'effort':1}
        jsonschema.validate({'action':action,'communication':{'op':'silent'}},schema('act',s.observe('a0'),s.cfg))
        self.assertTrue(well_formed(action,s.cfg));self.assertFalse(well_formed({k:v for k,v in action.items() if k!='effort'},s.cfg))
        self.attack(s);self.assertAlmostEqual(sum(a['stock']+a['vault'] for a in s.state['agents'].values()),before-.5)
        s=self.society();bounds=local_attack_bounds(s.cfg,s.state,'a0')
        self.assertAlmostEqual(bounds['lower'],-1);self.assertAlmostEqual(bounds['upper'],.5)
        threats=[{'actor':aid,'target':'a1','resource':'liquid','amount':2,'effort':1} for aid in ('a0','a2')]
        defense=conditional_defense_bounds(s.cfg,s.state,'a1',threats)
        self.assertEqual(defense['best']['defense_effort'],1)
        self.assertAlmostEqual(defense['best']['loss_plus_cost'],11/6)

    def test_full_round_storage_attack_replay_and_resume(self):
        cfg=self.society().cfg;cfg.update(rounds=3,survey_rounds=[],memory={'trigger_chars':999999,'summary_max_chars':1000,'keep_recent_rounds':5})
        calls=[]
        def decide(api,model,kind,system,payload,request_key=None):
            calls.append(request_key);aid=payload['self']['id'];t=payload['round']
            action={'tool':'wait'}
            if t==1 and aid in ('a0','a1'):action={'tool':'secure','amount':2}
            if t==2 and aid=='a1':action={'tool':'defend','effort':1}
            if t==3 and aid=='a0':action={'tool':'seize','target':'a1','resource':'vault','amount':2,'effort':1}
            return {'action':action,'communication':{'op':'silent'}}
        with tempfile.TemporaryDirectory() as d,patch.object(API,'request',decide):
            run(cfg,Path(d),mock=True)
            checkpoint=json.loads((Path(d)/'checkpoint.json').read_text('utf-8'))
            self.assertEqual(len(checkpoint['state']['security_history']),4)
            self.assertEqual(checkpoint['state']['seizure_events'][0]['resource'],'vault')
            self.assertTrue(audit(d)['verified_replay'])
            count=len(calls);run(cfg,Path(d),mock=True,resume=True);self.assertEqual(len(calls),count)

if __name__=='__main__':unittest.main()

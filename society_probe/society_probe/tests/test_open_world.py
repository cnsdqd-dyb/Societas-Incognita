import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import jsonschema
import environments
import schemas
from audit_actions import audit, well_formed
from prepare_open_campaign import configuration
from sim import Society,API,run


class OpenWorld(unittest.TestCase):
    def cfg(self,pressure=False):return configuration('mistralai/ministral-3b-2512',pressure)

    def test_pressure_pair_only_changes_maintenance(self):
        a,b=self.cfg(),self.cfg(True)
        self.assertEqual(a['scenario'],b['scenario']);self.assertEqual(a['mixed_world'],b['mixed_world'])
        a['world'].pop('survival_pressure');b['world'].pop('survival_pressure');self.assertEqual(a['world'],b['world'])
        for pressure in (False,True):
            s=Society(self.cfg(pressure));s.state['round']=1
            before=environments.physical_snapshot(s.state);s.act('a0',{'tool':'play','target':'a1','text':'hello'});s.settle(before)
            self.assertEqual(s.state['agents']['a1']['stock'],3 if pressure else 4)
            self.assertNotIn('participated',s.state['mixed']['play_records'][0])

    def test_pool_accounting_and_rejected_actions_do_not_mutate(self):
        s=Society(self.cfg());s.state['round']=1;before=environments.physical_snapshot(s.state)
        s.act('a0',{'tool':'harvest','zone':0,'amount':2});s.act('a1',{'tool':'contribute','amount':2});s.settle(before)
        self.assertAlmostEqual(s.state['zones'][0],16-2+.1*16*(1-16/32)+1.5*2)
        for action in ({'tool':'damage','target':'facility:99'},{'tool':'create','title':'','content':'x'},
                       {'tool':'interfere','target':'a0'},{'tool':'harvest','zone':1,'amount':2}):
            prior=copy.deepcopy(s.state)
            with self.assertRaises(ValueError):s.act('a0',action)
            self.assertEqual(s.state,prior)

    def test_damage_repair_interference_and_artifact_tombstone(self):
        s=Society(self.cfg());s.state['round']=1;before=environments.physical_snapshot(s.state)
        s.act('a0',{'tool':'damage','target':'facility:0'});s.act('a1',{'tool':'process','facility':0})
        s.act('a2',{'tool':'interfere','target':'a1'});s.act('a3',{'tool':'interfere','target':'a1'});s.settle(before)
        self.assertEqual(s.state['mechanism_state']['jobs']['a1']['remaining'],2)
        s.state['round']=2;s.act('a0',{'tool':'maintain','target':'facility:0'})
        self.assertEqual(s.state['mixed']['health'][0],1.)
        self.assertEqual(s.state['mechanism_state']['jobs']['a1']['remaining'],2)
        s.act('a4',{'tool':'create','title':'title','content':'content'});s.act('a5',{'tool':'read_artifact','artifact':'work1'})
        s.act('a6',{'tool':'damage','target':'artifact:work1'})
        work=s.state['mixed']['artifacts']['work1'];self.assertFalse(work['available']);self.assertEqual(work['content'],'content')
        with self.assertRaises(ValueError):s.act('a7',{'tool':'read_artifact','artifact':'work1'})

    def test_open_actions_pass_schema_and_audit(self):
        cfg=self.cfg();s=Society(cfg);obs=s.observe('a0')
        for action in ({'tool':'read_news'},{'tool':'create','title':'x','content':'y'},{'tool':'play','target':'self','text':'x'},
                       {'tool':'harvest','zone':0,'amount':2},{'tool':'maintain','target':'facility:0'}):
            self.assertTrue(well_formed(action,cfg));jsonschema.validate({'action':action,'communication':{'op':'silent'}},schemas.schema('act',obs,cfg))
        self.assertNotIn('action_examples',obs['environment']);self.assertEqual(cfg['tools'],s.cfg['tools'])

    def test_50_round_resume_matches_uninterrupted_physics(self):
        cfg=self.cfg(True);cfg['parallel_agents']=1
        original=API.request
        def interrupted(api,model,kind,system,payload,request_key=None):
            if request_key=='act:2:a2':raise RuntimeError('Injected disconnect')
            return original(api,model,kind,system,payload,request_key)
        with tempfile.TemporaryDirectory() as root:
            paused=Path(root)/'paused';clean=Path(root)/'clean'
            with patch.object(API,'request',interrupted):
                with self.assertRaisesRegex(RuntimeError,'Injected'):run(cfg,paused,mock=True)
            run(cfg,paused,mock=True,resume=True);run(cfg,clean,mock=True)
            a=json.loads((paused/'checkpoint.json').read_text('utf-8'))['state']
            b=json.loads((clean/'checkpoint.json').read_text('utf-8'))['state']
            self.assertEqual(a['agents'],b['agents']);self.assertEqual(a['mixed'],b['mixed'])
            self.assertEqual(a['environment_history'],b['environment_history'])
            self.assertEqual(a['round'],50);self.assertTrue(audit(paused)['verified_replay'])


if __name__=='__main__':unittest.main()

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sim import Society, API, run, decode_response
from make_core_matrix import configuration, admission
from audit_actions import audit, well_formed
import environments

BASE = json.loads(Path('configs/smoke.json').read_text(encoding='utf-8'))


class CoreEnvironments(unittest.TestCase):
    def config(self, family, pressure=False):
        return configuration(BASE, family, 7, pressure, 'information', 100, 8)

    def test_all_families_have_paired_pressure_and_finite_recovery_witnesses(self):
        # This legacy matrix builder covers the original four families; the
        # seven-family matrix is checked in test_additional_mechanisms.
        for f in ('commons','public_goods','contest','congestion'):
            cfg=self.config(f); other=self.config(f,True)
            a,b=copy.deepcopy(cfg['world']),copy.deepcopy(other['world'])
            a.pop('survival_pressure');b.pop('survival_pressure')
            self.assertEqual(a,b);self.assertEqual(cfg['scenario'],other['scenario'])
            admitted=admission(cfg)
            self.assertTrue(admitted['admitted'])
            self.assertEqual(len(admitted['recovery_witness']['recovered_members']),8)

    def test_commons_uses_pre_action_growth_and_conserves_extraction(self):
        cfg=self.config('commons');s=Society(cfg);s.state['round']=1
        before=environments.physical_snapshot(s.state);x=s.state['agents']['a0']['stock']
        s.act('a0',{'tool':'harvest','zone':0,'amount':3})
        self.assertAlmostEqual(s.state['zones'][0]+s.state['agents']['a0']['stock'],before['pool']+x)
        s.settle(before)
        growth=cfg['world']['growth_rate']*before['pool']*(1-before['pool']/cfg['world']['pool_capacity'])
        self.assertAlmostEqual(s.state['zones'][0],before['pool']-3+growth)

    def test_public_good_returns_only_at_settlement_and_preserves_private_cost(self):
        cfg=self.config('public_goods');s=Society(cfg);s.state['round']=1
        s.act('a0',{'tool':'contribute','amount':2})
        self.assertEqual(s.state['agents']['a1']['stock'],4)
        self.assertEqual(s.state['agents']['a0']['stock'],2)
        with self.assertRaises(ValueError):s.act('a0',{'tool':'contribute','amount':1})
        s.settle({});ret=2*cfg['world']['multiplier']/8
        self.assertAlmostEqual(s.state['agents']['a0']['stock'],3+ret)
        self.assertAlmostEqual(s.state['agents']['a1']['stock'],5+ret)
        self.assertAlmostEqual(sum(a['stock'] for a in s.state['agents'].values()),32-2+8+2*cfg['world']['multiplier'])

    def test_contest_all_zero_equal_and_single_effort_paid_before_award(self):
        cfg=self.config('contest');s=Society(cfg);s.state['round']=1;s.settle({})
        self.assertTrue(all(abs(a['stock']-(4+cfg['world']['supply']/8))<1e-8 for a in s.state['agents'].values()))
        s=Society(cfg);s.state['round']=1;s.act('a0',{'tool':'allocate','amount':1});s.settle({})
        self.assertAlmostEqual(s.state['agents']['a0']['stock'],3+cfg['world']['supply'])
        self.assertAlmostEqual(sum(a['stock'] for a in s.state['agents'].values()),32-1+cfg['world']['supply'])

    def test_congestion_simultaneous_arrivals_get_same_duration_and_no_duplicate_jobs(self):
        cfg=self.config('congestion');s=Society(cfg);s.state['round']=1
        for i in ('a0','a1','a2'):s.act(i,{'tool':'process','facility':0})
        with self.assertRaises(ValueError):s.act('a0',{'tool':'process','facility':1})
        s.settle({})
        self.assertEqual({j['remaining'] for j in s.state['mechanism_state']['jobs'].values()},{2})
        self.assertEqual(s.state['agents']['a0']['stock'],3)
        for t in (2,3):s.state['round']=t;s.settle({})
        self.assertEqual(s.state['mechanism_state']['jobs'],{})
        self.assertEqual(s.state['agents']['a0']['stock'],9)

    def test_invalid_actions_do_not_mutate_accounts_or_pending(self):
        for f,action in [('public_goods',{'tool':'contribute','amount':99}),
                         ('contest',{'tool':'allocate','amount':99}),
                         ('congestion',{'tool':'process','facility':99})]:
            s=Society(self.config(f));before=copy.deepcopy(s.state)
            with self.assertRaises(ValueError):s.act('a0',action)
            self.assertEqual(before,s.state)


class DurableResume(unittest.TestCase):
    def config(self):
        cfg=configuration(BASE,'public_goods',7,True,'basic',6,4)
        cfg['parallel_agents']=1;cfg['memory']['trigger_chars']=100000
        return cfg

    def test_mid_decision_resume_does_not_repeat_saved_calls(self):
        cfg=self.config();request=API.request;seen=[]
        def interrupted(api,model,kind,system,payload,request_key=None):
            if request_key=='act:2:a2':raise RuntimeError('Injected disconnect')
            seen.append(request_key)
            return request(api,model,kind,system,payload,request_key)
        with tempfile.TemporaryDirectory() as out:
            with patch.object(API,'request',interrupted):
                with self.assertRaisesRegex(RuntimeError,'Injected'):run(cfg,out,mock=True)
            journal=json.loads((Path(out)/'in_progress.json').read_text(encoding='utf-8'))
            self.assertTrue({'a0','a1'} <= set(journal['decisions']))
            def resumed(api,model,kind,system,payload,request_key=None):
                seen.append(request_key)
                return request(api,model,kind,system,payload,request_key)
            with patch.object(API,'request',resumed):run(cfg,out,mock=True,resume=True)
            self.assertEqual(seen.count('act:2:a0'),1)
            self.assertEqual(seen.count('act:2:a1'),1)
            self.assertFalse((Path(out)/'in_progress.json').exists())

    def test_mid_resolution_replay_matches_uninterrupted_state(self):
        cfg=self.config();act=Society.act;count=[0]
        def interrupted(s,aid,action):
            if s.state['round']==2:
                count[0]+=1
                if count[0]==2:raise RuntimeError('Injected resolution disconnect')
            return act(s,aid,action)
        with tempfile.TemporaryDirectory() as resumed,tempfile.TemporaryDirectory() as clean:
            with patch.object(Society,'act',interrupted):
                with self.assertRaisesRegex(RuntimeError,'Injected'):run(cfg,resumed,mock=True)
            run(cfg,resumed,mock=True,resume=True);run(cfg,clean,mock=True)
            a=json.loads((Path(resumed)/'checkpoint.json').read_text(encoding='utf-8'))
            b=json.loads((Path(clean)/'checkpoint.json').read_text(encoding='utf-8'))
            self.assertEqual(a,b)

    def test_mid_survey_resumes_remaining_members(self):
        cfg=self.config();request=API.request;seen=[]
        def interrupted(api,model,kind,system,payload,request_key=None):
            if request_key=='survey-existence:0:a2':raise RuntimeError('Injected survey disconnect')
            seen.append(request_key)
            return request(api,model,kind,system,payload,request_key)
        with tempfile.TemporaryDirectory() as out:
            with patch.object(API,'request',interrupted):
                with self.assertRaisesRegex(RuntimeError,'Injected'):run(cfg,out,mock=True)
            def resumed(api,model,kind,system,payload,request_key=None):
                seen.append(request_key)
                return request(api,model,kind,system,payload,request_key)
            with patch.object(API,'request',resumed):run(cfg,out,mock=True,resume=True)
            self.assertEqual(seen.count('survey-existence:0:a0'),1)
            answers=json.loads((Path(out)/'result.json').read_text(encoding='utf-8'))['surveys']
            self.assertEqual(len({(a['round'],a['agent']) for a in answers}),len(answers))


class RejectionAudit(unittest.TestCase):
    def test_missing_outer_closure_preserves_complete_action_and_message(self):
        expected={'action':{'tool':'wait'},'communication':{'op':'public','text':'a {quoted} statement'}}
        raw=json.dumps(expected)[:-1]+'\n'*250
        recovered,suffix=decode_response(raw)
        self.assertEqual(expected,recovered);self.assertEqual(suffix,'}')
        for malformed in ['{"n":1','{"text":"partial','{"a":[1}']:
            with self.assertRaises(ValueError):decode_response(malformed)

    def test_budget_rejection_is_not_a_syntax_failure(self):
        cfg=configuration(BASE,'contest',7,True,'basic',6,4)
        cfg['memory']['trigger_chars']=100000
        script=API.script
        def overspend(api,kind,payload):
            if kind=='act':return {'action':{'tool':'allocate','amount':2},'communication':{'op':'silent'}}
            return script(api,kind,payload)
        with tempfile.TemporaryDirectory() as out,patch.object(API,'script',overspend):
            run(cfg,out,mock=True)
            checked=audit(out)
            self.assertTrue(checked['verified_replay'])
            self.assertEqual(checked['schema_or_range_rejections'],0)
            self.assertGreater(checked['state_constraint_rejections'],0)
        self.assertFalse(well_formed({'tool':'allocate','amount':99},cfg))
        self.assertFalse(well_formed({'tool':'allocate','amount':'2'},cfg))

    def test_corrupt_snapshot_is_detected(self):
        cfg=configuration(BASE,'contest',7,False,'basic',6,4)
        cfg['memory']['trigger_chars']=100000
        with tempfile.TemporaryDirectory() as out:
            run(cfg,out,mock=True)
            path=Path(out)/'checkpoint.json';saved=json.loads(path.read_text(encoding='utf-8'))
            saved['state']['snapshots'][0]['agents']['a0']['stock']+=1
            path.write_text(json.dumps(saved),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'physical state differs'):audit(out)

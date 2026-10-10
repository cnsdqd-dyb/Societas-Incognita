import collections
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import environments
import interaction_controls as controls
import schemas
import sim
from prepare_multi_environment_v2 import config
from prepare_environment_review import DESIGNS

SOURCE=json.loads(Path('configs/open_contest_mix_v1_20261009/contest_mixed4_p1_s7.json').read_text('utf-8'))


def cfg(family='complementary', **options):
    design=next(d for d in DESIGNS if d['family']==family)
    c=controls.configure(config(SOURCE,design,'mixed4',1),**options)
    c.pop('campaign_budget_db',None)
    c.update(rounds=2,survey_rounds=[],parallel_agents=1)
    c['memory']={'trigger_chars':100000000,'keep_recent_rounds':2,'summary_max_chars':1000}
    return c


class ProbeAPI(sim.API):
    returned=[]
    seen=[]
    fail_key=None
    silent_agent=None

    def request(self, model, kind, system, payload, request_key=None):
        if request_key==self.fail_key:
            raise RuntimeError('Injected interruption')
        type(self).seen.append((kind,copy.deepcopy(payload)))
        response=super().request(model,kind,system,payload,request_key)
        type(self).returned.append(request_key)
        return response

    def script(self, kind, payload):
        if kind=='communicate':
            if payload['self']['id']==self.silent_agent:
                return {'communication':{'op':'silent'}}
            return {'communication':{'op':'public','text':f"turn{payload['dialogue_turn']}:{payload['self']['id']}"}}
        if kind=='act':
            return {'action':{'tool':'wait'},'communication':{'op':'silent'}}
        return super().script(kind,payload)


class ControlsTests(unittest.TestCase):
    def setUp(self):
        ProbeAPI.returned=[];ProbeAPI.seen=[];ProbeAPI.fail_key=None;ProbeAPI.silent_agent=None

    def test_hidden_rules_remove_formulas_and_help_but_keep_states_and_syntax(self):
        c=cfg('threshold',visibility='hidden');s=sim.Society(c);v=s.observe('a0')
        self.assertEqual(v['world_rules']['visibility'],'hidden')
        self.assertNotIn('threshold',v['world_rules'])
        self.assertNotIn('family',v['environment'])
        self.assertNotIn('启动阈值',v['scenario']['description'])
        self.assertIn('stock',v['self']);self.assertIn('members',v)
        help_text=controls.actor_help(c,v,environments.action_help(c))
        self.assertNotIn('threshold',help_text)
        self.assertNotIn('multiplier',help_text)
        self.assertNotIn('attack_unit_cost',help_text)
        self.assertIn('contribute',help_text)
        self.assertNotIn('门槛',c['actor_system'])

    def test_full_rules_and_rescue_parameters_visible_without_mutating_config(self):
        c=cfg(rescue_enabled=True);before=copy.deepcopy(c);s=sim.Society(c);v=s.observe('a0')
        self.assertEqual(v['world_rules']['productivity'],6)
        self.assertEqual(v['world_rules']['rescue']['restore_energy'],3)
        self.assertEqual(c,before)

    def test_rescue_cost_delayed_activation_and_no_free_stock(self):
        c=cfg(rescue_enabled=True,restore_energy=3,cost_per_energy=.5);s=sim.Society(c)
        s.state['round']=4;target=s.state['agents']['a2'];target.update(alive=False,energy=0,stock=0)
        total=sum(a['stock'] for a in s.state['agents'].values())
        result=s.act('a0',{'tool':'rescue','target':'a2'})
        self.assertEqual(result['paid'],1.5);self.assertFalse(target['alive'])
        self.assertEqual(total-sum(a['stock'] for a in s.state['agents'].values()),1.5)
        s.settle(environments.physical_snapshot(s.state));self.assertFalse(target['alive'])
        self.assertNotIn('a2',s.state['environment_history'][-1]['maintenance'])
        s.state['round']=5;controls.start_round(c,s.state)
        self.assertTrue(target['alive']);self.assertEqual(target['energy'],3)
        self.assertEqual(target['stock'],0)
        self.assertIn('rescue',target['inbox'][-1]['channel'])
        controls.start_round(c,s.state);self.assertEqual(len(target['inbox']),1)

    def test_invalid_or_duplicate_rescue_is_atomic(self):
        s=sim.Society(cfg(rescue_enabled=True));s.state['round']=1
        s.state['agents']['a2'].update(alive=False,energy=0)
        s.state['agents']['a0']['stock']=1
        before=copy.deepcopy(s.state)
        with self.assertRaises(ValueError):s.act('a0',{'tool':'rescue','target':'a2'})
        self.assertEqual(before,s.state)
        s.state['agents']['a0']['stock']=4;s.act('a0',{'tool':'rescue','target':'a2'})
        before=copy.deepcopy(s.state)
        with self.assertRaises(ValueError):s.act('a1',{'tool':'rescue','target':'a2'})
        self.assertEqual(before,s.state)
        with self.assertRaises(ValueError):s.act('a2',{'tool':'rescue','target':'a3'})

    def test_rescue_disabled_and_parameter_validation(self):
        s=sim.Society(cfg())
        with self.assertRaises(ValueError):s.act('a0',{'tool':'rescue','target':'a2'})
        for options in [dict(visibility='bad'),dict(max_turns_before_action=True),
                        dict(max_turns_before_action=-1),dict(rescue_enabled=True,restore_energy=6),
                        dict(rescue_enabled=True,cost_per_energy=0)]:
            with self.assertRaises(ValueError):cfg(**options)

    def test_schema_separates_dialogue_from_physical_action(self):
        c=cfg(rescue_enabled=True);v=sim.Society(c).observe('a0')
        self.assertEqual(set(schemas.schema('communicate',v,c)['properties']),{'communication'})
        sh=schemas.schema('act',v,c)
        self.assertEqual(sh['properties']['communication']['anyOf'][0]['properties']['op']['enum'],['silent'])
        self.assertEqual(len(sh['properties']['communication']['anyOf']),1)
        self.assertTrue(any(x['properties']['tool']['enum']==['rescue'] for x in sh['properties']['action']['anyOf']))

    def test_dialogue_delivers_messages_before_action_and_no_extra_physical_steps(self):
        c=cfg(max_turns_before_action=3)
        with tempfile.TemporaryDirectory() as d,patch.object(sim,'API',ProbeAPI):
            sim.run(c,Path(d)/'run',mock=True)
            state=json.loads((Path(d)/'run/checkpoint.json').read_text('utf-8'))['state']
        self.assertEqual(len(state['snapshots']),2)
        self.assertEqual(len(state['environment_history']),2)
        self.assertEqual(len(state['communication_events']),8*3*2)
        self.assertEqual(len(state['events']),8*2)
        self.assertEqual(state['agents']['a0']['stock'],3)
        second=next(p for kind,p in ProbeAPI.seen if kind=='communicate' and p['round']==1 and p['dialogue_turn']==2)
        self.assertTrue(any(m.get('text','').startswith('turn1:') for m in second['new_messages']))
        act=next(p for kind,p in ProbeAPI.seen if kind=='act' and p['round']==1)
        self.assertTrue(any(m.get('text','').startswith('turn3:') for m in act['new_messages']))
        self.assertEqual(len(act['dialogue_history']),3)
        self.assertEqual(len(set(ProbeAPI.returned)),len(ProbeAPI.returned))

    def test_zero_allowance_and_voluntary_early_stop(self):
        with tempfile.TemporaryDirectory() as d,patch.object(sim,'API',ProbeAPI):
            sim.run(cfg(max_turns_before_action=0),Path(d)/'zero',mock=True)
            self.assertFalse(any(k=='communicate' for k,p in ProbeAPI.seen))
            ProbeAPI.seen=[];ProbeAPI.silent_agent='a0'
            sim.run(cfg(max_turns_before_action=3),Path(d)/'early',mock=True)
        a0=[p for k,p in ProbeAPI.seen if k=='communicate' and p['self']['id']=='a0']
        self.assertEqual(len(a0),2)

    def test_resume_mid_dialogue_does_not_repeat_committed_responses(self):
        c=cfg(max_turns_before_action=3)
        with tempfile.TemporaryDirectory() as d,patch.object(sim,'API',ProbeAPI):
            folder=Path(d)/'resumed';ProbeAPI.fail_key='communicate:1:2:a1'
            with self.assertRaisesRegex(RuntimeError,'Injected'):sim.run(c,folder,mock=True)
            journal=json.loads((folder/'in_progress.json').read_text('utf-8'))
            self.assertEqual(journal['phase'],'communicate');self.assertEqual(journal['dialogue_turn'],1)
            completed=list(ProbeAPI.returned);ProbeAPI.fail_key=None
            sim.run(c,folder,mock=True,resume=True)
            self.assertEqual(len(set(ProbeAPI.returned)),len(ProbeAPI.returned))
            resumed=json.loads((folder/'checkpoint.json').read_text('utf-8'))['state']
            self.assertEqual(len(resumed['communication_events']),48)
            sim.run(c,Path(d)/'clean',mock=True)
            clean=json.loads((Path(d)/'clean/checkpoint.json').read_text('utf-8'))['state']
            self.assertEqual(resumed,clean)
            self.assertTrue(completed)

    def test_all_seven_environments_support_rescue_and_hidden_observation(self):
        for design in DESIGNS:
            s=sim.Society(cfg(design['family'],visibility='hidden',rescue_enabled=True))
            s.state['agents']['a2'].update(alive=False,energy=0)
            s.act('a0',{'tool':'rescue','target':'a2'})
            self.assertEqual(s.observe('a1')['world_rules']['visibility'],'hidden')
            self.assertTrue(s.observe('a1')['rescue_index']['a2']['awaiting_rescue_activation'])

    def test_malformed_communication_pauses_before_physics(self):
        class InvalidAPI(ProbeAPI):
            def script(self,kind,payload):
                if kind=='communicate':return {'action':{'tool':'wait'}}
                return super().script(kind,payload)
        with tempfile.TemporaryDirectory() as d,patch.object(sim,'API',InvalidAPI):
            with self.assertRaisesRegex(ValueError, 'output contract'):
                sim.run(cfg(max_turns_before_action=1),Path(d)/'run',mock=True)
            checkpoint=json.loads((Path(d)/'run/checkpoint.json').read_text('utf-8'))
            self.assertEqual(checkpoint['state']['environment_history'], [])
            self.assertFalse((Path(d)/'run/result.json').exists())


if __name__=='__main__':unittest.main()

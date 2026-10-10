import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import tiktoken

import interaction_controls as controls
import sim
import schemas
from test_interaction_controls import cfg,ProbeAPI


RESPONSE={'communication':{'op':'public','text':'界'*80}}


class VolumeAPI(ProbeAPI):
    fail_key=None
    early=None
    seen=[]
    returned=[]

    def script(self,kind,payload):
        if kind=='communicate':
            if payload['self']['id']==self.early:return {'communication':{'op':'silent'}}
            return copy.deepcopy(RESPONSE)
        return super().script(kind,payload)


class CommunicationBudgetTests(unittest.TestCase):
    def setUp(self):
        VolumeAPI.seen=[];VolumeAPI.returned=[];VolumeAPI.fail_key=None;VolumeAPI.early=None

    def config(self,limit=200,unit='characters'):
        c=cfg(communication_budget={'unit':unit,'limit':limit})
        c['rounds']=1
        return c

    def run_case(self,c):
        with tempfile.TemporaryDirectory() as d,patch.object(sim,'API',VolumeAPI):
            sim.run(c,Path(d)/'run',mock=True)
            state=json.loads((Path(d)/'run/checkpoint.json').read_text('utf-8'))['state']
            result=json.loads((Path(d)/'run/result.json').read_text('utf-8'))
        return state,result

    def test_final_message_crosses_limit_is_delivered_whole_and_no_next_request(self):
        state,result=self.run_case(self.config())
        events=[e for e in state['communication_events'] if e['agent']=='a0']
        self.assertEqual(len(events),2)
        self.assertLess(events[-1]['budget_used_before'],200)
        self.assertGreater(events[-1]['budget_used_after'],200)
        self.assertEqual(events[-1]['communication']['text'],'界'*80)
        action=next(p for k,p in VolumeAPI.seen if k=='act' and p['self']['id']=='a0')
        self.assertTrue(any(m.get('text')=='界'*80 for m in action['new_messages']))
        self.assertFalse(action['countdowns']['communication']['may_start_output'])
        self.assertEqual(len(state['snapshots']),1)
        self.assertEqual(result['metrics']['round_series'][0]['communication_end_reasons'],{'budget':8})

    def test_exact_limit_and_zero_budget(self):
        size=len(json.dumps(RESPONSE,ensure_ascii=False,separators=(',',':'),sort_keys=True))
        state,_=self.run_case(self.config(size))
        self.assertEqual(len(state['communication_events']),8)
        self.assertTrue(all(e['budget_used_after']==size for e in state['communication_events']))
        VolumeAPI.seen=[]
        state,_=self.run_case(self.config(0))
        self.assertEqual(state['communication_events'],[])
        self.assertFalse(any(k=='communicate' for k,p in VolumeAPI.seen))

    def test_unicode_characters_and_uniform_tokens_are_not_bytes_or_billing(self):
        c=self.config();serialized=json.dumps(RESPONSE,ensure_ascii=False,separators=(',',':'),sort_keys=True)
        self.assertEqual(controls.response_size(c,RESPONSE),len(serialized))
        self.assertLess(controls.response_size(c,RESPONSE),len(serialized.encode('utf-8')))
        c=self.config(100,'tokens');token_count=len(tiktoken.get_encoding('cl100k_base').encode(serialized))
        self.assertEqual(controls.response_size(c,RESPONSE),token_count)
        state,_=self.run_case(c)
        self.assertTrue(all(e['budget_charge']==token_count for e in state['communication_events']))
        self.assertTrue(all(e['budget_used_before']<100 for e in state['communication_events']))
        finals=[e for e in state['communication_events'] if e['end_reason']=='budget']
        self.assertEqual(len(finals),8)
        self.assertTrue(all(e['budget_used_after']>=100 for e in finals))

    def test_one_agent_can_stop_early_without_stopping_other_agents(self):
        VolumeAPI.early='a0';state,_=self.run_case(self.config())
        a0=[e for e in state['communication_events'] if e['agent']=='a0']
        a1=[e for e in state['communication_events'] if e['agent']=='a1']
        self.assertEqual(len(a0),1);self.assertEqual(a0[0]['end_reason'],'voluntary')
        self.assertEqual(len(a1),2)
        action=next(p for k,p in VolumeAPI.seen if k=='act' and p['self']['id']=='a0')
        self.assertGreater(action['countdowns']['communication']['remaining'],0)
        self.assertTrue(action['countdowns']['communication']['ended'])
        self.assertFalse(action['countdowns']['communication']['may_start_output'])

    def test_any_chat_participant_can_close_only_that_conversation(self):
        s=sim.Society(self.config())
        s.communicate('a0',{'op':'invite','targets':['a1']});s.communicate('a1',{'op':'accept','chat':'c1'})
        s.communicate('a2',{'op':'invite','targets':['a3']});s.communicate('a3',{'op':'accept','chat':'c2'})
        s.communicate('a1',{'op':'close','chat':'c1'})
        self.assertFalse(s.state['chats']['c1']['open']);self.assertTrue(s.state['chats']['c2']['open'])
        self.assertEqual(s.state['agents']['a0']['inbox'][-1]['op'],'conversation_closed')
        with self.assertRaises(ValueError):s.communicate('a4',{'op':'close','chat':'c2'})

    def test_interrupted_budget_recovery_does_not_duplicate_charges_or_messages(self):
        c=self.config()
        with tempfile.TemporaryDirectory() as d,patch.object(sim,'API',VolumeAPI):
            resumed=Path(d)/'resumed';clean=Path(d)/'clean'
            VolumeAPI.fail_key='communicate:1:2:a1'
            with self.assertRaisesRegex(RuntimeError,'Injected'):sim.run(c,resumed,mock=True)
            VolumeAPI.fail_key=None
            sim.run(c,resumed,mock=True,resume=True)
            self.assertEqual(len(VolumeAPI.returned),len(set(VolumeAPI.returned)))
            sim.run(c,clean,mock=True)
            a=json.loads((resumed/'checkpoint.json').read_text('utf-8'))['state']
            b=json.loads((clean/'checkpoint.json').read_text('utf-8'))['state']
            self.assertEqual(a,b)
            self.assertEqual(len(a['communication_events']),16)

    def test_invalid_configuration_and_schema_action_separation(self):
        for budget in [{'unit':'bytes','limit':100},{'unit':'characters','limit':True},
                       {'unit':'tokens','limit':-1}]:
            with self.assertRaises(ValueError):cfg(communication_budget=budget)
        c=self.config();view=sim.Society(c).observe('a0')
        self.assertNotIn('max_turns_before_action',c['communication'])
        self.assertEqual(schemas.schema('act',view,c)['properties']['communication']['anyOf'][0]['properties']['op']['enum'],['silent'])

    def test_no_hidden_three_turn_limit_and_invalid_outputs_also_consume_budget(self):
        state,_=self.run_case(self.config(500))
        self.assertGreater(len([e for e in state['communication_events'] if e['agent']=='a0']),3)
        class InvalidAPI(VolumeAPI):
            def script(self,kind,payload):
                return None if kind=='communicate' else super().script(kind,payload)
        with tempfile.TemporaryDirectory() as d,patch.object(sim,'API',InvalidAPI):
            sim.run(self.config(10),Path(d)/'run',mock=True)
            state=json.loads((Path(d)/'run/checkpoint.json').read_text('utf-8'))['state']
        self.assertEqual(len(state['communication_events']),24)
        self.assertTrue(all(e['budget_charge']==4 for e in state['communication_events']))
        self.assertTrue(all('communication_error' in e['outcome'] for e in state['communication_events']))


if __name__=='__main__':unittest.main()

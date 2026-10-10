import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import environments
import game_rules
import interaction_controls
import metrics
import schemas
import sim
import social_content as content
from audit_actions import audit
from state_assessment import replay_settled, rollout
from test_interaction_controls import cfg, ProbeAPI, DESIGNS

PY_GAME="""rules = {'initial_state': {'pile': 3}, 'min_players': 1, 'max_players': 2, 'max_moves': 10}
def transition(state, action, actor, players):
    take = action.get('take', 0)
    if take != 1 or state['pile'] < take:
        return {'valid': False}
    state['pile'] -= take
    done = state['pile'] == 0
    return {'state': state, 'done': done, 'winner': actor if done else None}
"""
XML_GAME='''<game min_players="1" max_players="2" max_moves="10"><initial>{"pile":3}</initial><legal>action.get('take', 0) == 1 and state['pile'] &gt;= 1</legal><update field="pile" expr="state['pile'] - action['take']"/><done>state['pile'] == 0</done><winner>actor</winner></game>'''


class SocialTests(unittest.TestCase):
    def society(self, family='complementary', **options):
        s=sim.Society(content.configure(cfg(family,**options)))
        s.state['round']=1
        return s

    def create(self,s,kind='novel',body='first version',visibility='licensed'):
        return s.act('a0',{'tool':'create','title':'A work','content':body,'kind':kind,'visibility':visibility})['artifact_created']

    def offer(self,s,w,price=2):
        return s.act('a0',{'tool':'offer_work','artifact':w,'target':'a1','price':price})['offer_created']

    def start(self,s,source=PY_GAME,kind='game_python',targets=None,stake=2):
        w=self.create(s,kind,source,'public')
        g=s.act('a0',{'tool':'start_game','artifact':w,'version':1,'targets':['a1'] if targets is None else targets,'stake':stake,'settlement':'winner_takes_all'})['game_created']
        return w,g

    def test_author_only_sale_licensed_read_and_no_resale(self):
        s=self.society();w=self.create(s);offer=self.offer(s,w)
        with self.assertRaises(ValueError):s.act('a1',{'tool':'read_artifact','artifact':w,'version':0})
        visible=s.observe('a1')['environment']
        self.assertNotIn('content',visible['work_offers'][offer])
        self.assertNotIn('first version',json.dumps(visible))
        s.state['round']=2;total=sum(a['stock'] for a in s.state['agents'].values())
        result=s.act('a1',{'tool':'accept_work','offer':offer})
        self.assertEqual(result['artifact_content'],'first version');self.assertFalse(result['resale_allowed'])
        self.assertEqual(s.state['agents']['a0']['stock'],6)
        self.assertEqual(s.state['agents']['a1']['stock'],2)
        self.assertEqual(total,sum(a['stock'] for a in s.state['agents'].values()))
        self.assertEqual(s.act('a1',{'tool':'read_artifact','artifact':w,'version':0})['artifact']['version'],1)
        for tool,params in [('offer_work',{'target':'a2','price':0}),('publish_work',{'visibility':'public'}),('revise_work',{'content':'stolen'})]:
            before=copy.deepcopy(s.state)
            with self.assertRaises(ValueError):s.act('a1',{'tool':tool,'artifact':w,**params})
            self.assertEqual(before,s.state)

    def test_offer_immutable_versions_and_insufficient_payment_atomic(self):
        s=self.society();w=self.create(s);o=self.offer(s,w)
        s.act('a0',{'tool':'revise_work','artifact':w,'content':'second version'})
        s.state['round']=2;s.state['agents']['a1']['stock']=1;before=copy.deepcopy(s.state)
        with self.assertRaises(ValueError):s.act('a1',{'tool':'accept_work','offer':o})
        self.assertEqual(before,s.state)
        s.state['agents']['a1']['stock']=4
        self.assertEqual(s.act('a1',{'tool':'accept_work','offer':o})['artifact_content'],'first version')
        self.assertEqual(s.act('a1',{'tool':'read_artifact','artifact':w,'version':0})['artifact']['version'],1)
        with self.assertRaises(ValueError):s.act('a1',{'tool':'read_artifact','artifact':w,'version':2})

    def test_free_offer_and_expired_offer(self):
        s=self.society();w=self.create(s);o=self.offer(s,w,0);s.state['round']=2
        s.state['agents']['a1']['stock']=0
        s.act('a1',{'tool':'accept_work','offer':o})
        self.assertEqual(s.state['agents']['a0']['stock'],4)
        o=self.offer(s,w,0);s.state['round']=s.state['social_content']['offers'][o]['expires']
        before=copy.deepcopy(s.state)
        with self.assertRaises(ValueError):s.act('a1',{'tool':'accept_work','offer':o})
        self.assertEqual(before,s.state)

    def test_python_and_xml_game_consent_turns_atomic_moves_and_conserved_pot(self):
        for source,kind in [(PY_GAME,'game_python'),(XML_GAME,'game_xml')]:
            with self.subTest(kind=kind):
                s=self.society();w,g=self.start(s,source,kind)
                game=s.state['social_content']['games'][g]
                self.assertEqual(game['players'],['a0']);self.assertEqual(s.state['agents']['a1']['stock'],4)
                self.assertEqual(game['escrow'],{'a0':2})
                with self.assertRaises(ValueError):s.act('a1',{'tool':'join_game','game':g})
                s.state['round']=2;s.act('a1',{'tool':'join_game','game':g})
                self.assertEqual(sum(game['escrow'].values()),4)
                s.state['round']=3;before=copy.deepcopy(s.state)
                for aid,move in [('a1',1),('a0',2)]:
                    with self.assertRaises(ValueError):s.act(aid,{'tool':'game_move','game':g,'expected_move':0,'move_json':json.dumps({'take':move})})
                    self.assertEqual(before,s.state)
                for index,aid in enumerate(['a0','a1','a0']):
                    s.state['round']=3+index
                    s.act(aid,{'tool':'game_move','game':g,'expected_move':index,'move_json':'{"take":1}'})
                self.assertEqual(game['status'],'finished');self.assertEqual(game['escrow'],{})
                self.assertEqual(s.state['agents']['a0']['stock'],6);self.assertEqual(s.state['agents']['a1']['stock'],2)
                self.assertEqual(sum(a['stock'] for a in s.state['agents'].values()),32)

    def test_exit_decline_timeout_death_refund(self):
        for cause in ['leave','decline','timeout','death','destroy']:
            with self.subTest(cause=cause):
                s=self.society();w,g=self.start(s);s.state['round']=2
                if cause=='decline':s.act('a1',{'tool':'decline_game','game':g})
                elif cause=='leave':
                    s.act('a1',{'tool':'join_game','game':g});s.act('a1',{'tool':'leave_game','game':g})
                else:
                    if cause=='timeout':s.state['round']=s.state['social_content']['games'][g]['invite_expires']-1
                    if cause=='death':s.state['agents']['a1'].update(alive=False,energy=0)
                    if cause=='destroy':content.repo(s.state)['artifacts'][w]['available']=False
                    content.settle(s.cfg,s.state)
                self.assertEqual(s.state['agents']['a0']['stock'],4)
                self.assertEqual(s.state['social_content']['games'][g]['escrow'],{})
                before=copy.deepcopy(s.state);content.settle(s.cfg,s.state);self.assertEqual(before,s.state)

    def test_solo_and_frozen_rules(self):
        s=self.society();w,g=self.start(s,targets=[],stake=0)
        s.act('a0',{'tool':'revise_work','artifact':w,'content':PY_GAME.replace("'pile': 3","'pile': 1")})
        self.assertEqual(s.state['social_content']['games'][g]['source'],PY_GAME)
        s.state['round']=2;s.act('a0',{'tool':'game_move','game':g,'expected_move':0,'move_json':'{"take":1}'})
        self.assertEqual(s.state['social_content']['games'][g]['state']['pile'],2)

    def test_countdowns_hidden_world_and_all_seven_environments(self):
        for design in DESIGNS:
            s=self.society(design['family'],visibility='hidden',rescue_enabled=True,max_turns_before_action=3)
            w,g=self.start(s)
            v=s.observe('a1')
            self.assertEqual(v['world_rules']['visibility'],'hidden')
            self.assertEqual(v['countdowns']['communication']['remaining'],3)
            self.assertEqual(v['environment']['games'][g]['invitation_countdown']['remaining'],4)
            self.assertEqual(len(v['environment']['games'][g]['invitation_countdown']['bar']),10)
            self.assertIn('source',v['environment']['games'][g])
            self.assertIn('start_game',interaction_controls.actor_help(s.cfg,v,environments.action_help(s.cfg)))
        self.assertTrue(interaction_controls.countdown(0,0,'turns')['expired'])

    def test_bounded_rules_no_host_access_and_deterministic_randomness(self):
        for dangerous in [PY_GAME.replace('    take =', '    import os\n    take ='),
                          PY_GAME.replace('    take =', '    while True:\n        pass\n    take ='),
                          PY_GAME.replace("state['pile'] -= take", "state['pile'] = actor.__class__")]:
            with self.assertRaises(ValueError):game_rules.parse(dangerous,'game_python')
        calls=PY_GAME.replace("state['pile'] -= take", "state['pile'] = open('should_not_exist')")
        with self.assertRaises(ValueError):game_rules.transition(calls,'game_python',{'pile':3},{'take':1},'a0',['a0'],7)
        loop=PY_GAME.replace("state['pile'] -= take", "for i in range(256):\n        for j in range(256):\n            state['pile'] = 2")
        with self.assertRaisesRegex(ValueError,'limit'):game_rules.transition(loop,'game_python',{'pile':3},{'take':1},'a0',['a0'],7)
        random_game=PY_GAME.replace("state['pile'] -= take","state['pile'] = randint(1, 100)")
        a=game_rules.transition(random_game,'game_python',{'pile':3},{'take':1},'a0',['a0'],7)
        b=game_rules.transition(random_game,'game_python',{'pile':3},{'take':1},'a0',['a0'],7)
        self.assertEqual(a,b)

    def test_social_state_persists_and_metrics_distinguish_games_and_trade(self):
        class ContentAPI(ProbeAPI):
            def script(self,kind,payload):
                if kind=='act' and payload['self']['id']=='a0':
                    return {'action':{'tool':'create','title':'A joke','kind':'joke','visibility':'public','content':'hello'},'communication':{'op':'silent'}}
                return super().script(kind,payload)
        c=content.configure(cfg(max_turns_before_action=1))
        with tempfile.TemporaryDirectory() as d,patch.object(sim,'API',ContentAPI):
            sim.run(c,Path(d)/'run',mock=True)
            result=json.loads((Path(d)/'run/result.json').read_text('utf-8'))
            state=json.loads((Path(d)/'run/checkpoint.json').read_text('utf-8'))['state']
        self.assertEqual(len(content.repo(state)['artifacts']),2)
        self.assertEqual(result['metrics']['round_series'][-1]['work_creation_by_kind'],{'joke':2})
        self.assertEqual(result['metrics']['round_series'][-1]['game_moves'],0)
        self.assertEqual(result['metrics']['round_series'][-1]['work_sales'],0)
        self.assertEqual(state['snapshots'][-1]['agents']['a0']['game_escrow'],0)

    def test_strict_schemas_validate_representative_game_and_work_actions(self):
        import jsonschema
        s=self.society();schema=schemas.schema('act',s.observe('a0'),s.cfg)
        for action in [{'tool':'create','title':'game','kind':'game_python','visibility':'public','content':PY_GAME},
                       {'tool':'game_move','game':'game1','expected_move':0,'move_json':'{"take":1}'},
                       {'tool':'start_game','artifact':'work1','version':1,'targets':['a1'],'stake':1,'settlement':'refund'}]:
            jsonschema.validate({'action':action,'communication':{'op':'silent'}},schema)

    def test_full_trade_game_and_rescue_resume_matches_clean_and_replays(self):
        class InitialSociety(sim.Society):
            def __init__(self,c):
                super().__init__(c);self.state['agents']['a6'].update(alive=False,energy=0)
        class ScenarioAPI(ProbeAPI):
            def script(self,kind,p):
                if kind!='act':return super().script(kind,p)
                aid=p['self']['id'];t=p['round'];action={'tool':'wait'}
                works=p['environment']['artifact_index']
                games=p['environment']['games'];sales=p['environment']['work_offers']
                if t==1 and aid=='a0':action={'tool':'create','title':'game','kind':'game_python','visibility':'public','content':PY_GAME}
                if t==1 and aid=='a2':action={'tool':'create','title':'story','kind':'novel','visibility':'licensed','content':'A story'}
                if t==1 and aid=='a4':action={'tool':'rescue','target':'a6'}
                if t==2 and aid=='a0':action={'tool':'start_game','artifact':next(w['id'] for w in works if w['title']=='game'),'version':1,'targets':['a1'],'stake':1,'settlement':'winner_takes_all'}
                if t==2 and aid=='a2':action={'tool':'offer_work','artifact':next(w['id'] for w in works if w['title']=='story'),'target':'a3','price':1}
                if t==3 and aid=='a1':action={'tool':'join_game','game':next(iter(games))}
                if t==3 and aid=='a3':action={'tool':'accept_work','offer':next(iter(sales))}
                if (t,aid) in [(4,'a0'),(5,'a1'),(6,'a0')]:
                    key=next(iter(games));action={'tool':'game_move','game':key,'expected_move':games[key]['moves_completed'],'move_json':'{"take":1}'}
                return {'action':action,'communication':{'op':'silent'}}
        c=content.configure(cfg('contest',rescue_enabled=True,max_turns_before_action=2));c['rounds']=6
        settle=InitialSociety.settle
        def interrupted(s,before):
            if s.state['round']==3:raise RuntimeError('Interrupted before settlement')
            return settle(s,before)
        with tempfile.TemporaryDirectory() as d,patch.object(sim,'API',ScenarioAPI),patch.object(sim,'Society',InitialSociety):
            folder=Path(d)/'resumed'
            with patch.object(InitialSociety,'settle',interrupted):
                with self.assertRaisesRegex(RuntimeError,'Interrupted'):sim.run(c,folder,mock=True)
            sim.run(c,folder,mock=True,resume=True)
            sim.run(c,Path(d)/'clean',mock=True)
            resumed=json.loads((folder/'checkpoint.json').read_text('utf-8'))['state']
            clean=json.loads((Path(d)/'clean/checkpoint.json').read_text('utf-8'))['state']
            self.assertEqual(resumed,clean)
            self.assertEqual(len(resumed['rescue_events']),1)
            self.assertEqual(len(resumed['social_content']['transactions']),1)
            self.assertEqual(next(iter(resumed['social_content']['games'].values()))['status'],'finished')
            # Replay starts from the same explicitly injured initial conditions.
            with patch('audit_actions.Society',InitialSociety),patch('state_assessment.Society',InitialSociety):
                self.assertTrue(audit(folder)['verified_replay'])
                _,replayed=replay_settled(folder,6)
            self.assertEqual(replayed['social_content'],resumed['social_content'])
            measured=metrics.measure(resumed,c)['round_series'][-1]
            self.assertEqual(measured['work_sales'],1);self.assertEqual(measured['game_moves'],3)
            self.assertEqual(measured['game_closures'],{'finished':1})

    def test_offline_policy_rollout_activates_paid_rescue(self):
        s=self.society(rescue_enabled=True)
        s.state['agents']['a2'].update(alive=False,energy=0)
        s.act('a0',{'tool':'rescue','target':'a2'})
        result=rollout(s.cfg,s.state,lambda state,step:{},1)
        self.assertTrue(result['trace'][0]['agents']['a2']['alive'])


if __name__=='__main__':unittest.main()

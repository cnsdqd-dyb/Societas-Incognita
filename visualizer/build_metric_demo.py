"""Four scripted members, real engine settlements; NEVER a research experiment."""
import copy
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'society_probe/society_probe'
sys.path.insert(0,str(SOURCE))
import sim, environments, mini_world, world_rule_library as library
import social_content, interaction_controls, core_metrics

OUT=ROOT/'results/guided_metric_demo/demo/simulation'
ROUNDS=32
GAME='''<game min_players="2" max_players="2" max_moves="10" turn_mode="alternating"><initial>{"pile":3}</initial><legal>action.get('take',0) == 1 and state['pile'] &gt;= 1</legal><update field="pile" expr="state['pile'] - action['take']"/><done>state['pile'] == 0</done><winner>actor</winner></game>'''

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    sim.dump(path,value)

def configuration():
    base=json.loads((SOURCE/'configs/functional_services_20261010/native_base.json').read_text('utf-8'))
    candidate=library.with_all_functional_services(library.with_capabilities({'definition':library.base_definition(),'generation':{'seed':41}}))
    candidate['definition']['initial_inventory']={'A':32,'B':32,'C':24,'D':24,'S':24}
    candidate['definition']['production_semantics']='proportional_v1'
    cfg=social_content.configure(library.configure(base,candidate,pressure=False))
    cfg.update(models=['scripted-showcase']*4,rounds=ROUNDS,seed=41,survey_rounds=[])
    cfg['world']['initial_personal_stock']=80
    cfg['tools']=sorted(set(cfg['tools'])|social_content.TOOLS|{'read_news'})
    cfg['open_activities']={'version':'open_activities_v1'}
    cfg['communication']['max_message_chars']=500
    cfg['scenario']={'id':'guided_metric_demo','title':'指标展示 DEMO · 人工编排','description':'Four scripted roles; no model autonomy or research evidence.'}
    cfg['experiment'].update(stage='guided_visualization_demo',environment_id='guided_metric_demo',population='scripted_demo',goal_assignment='explicit_scripted_showcase',exclude_from_research=True,certificate_status='not_certified',questionnaire_role='disabled')
    return cfg

def action(tool,**kw):return {'tool':tool,**kw}
def create(title,content,kind='text',visibility='public'):return action('create',title=title,content=content,kind=kind,visibility=visibility)
def function(kind,target):return action('use_function',function='service_'+kind,target=target,confirm=True)
def experiment(index):
    recipes=library.base_definition()['recipes'];r=recipes[index]
    return action('experiment',facility=r['facility'],mode=r['mode'],inputs=[{'item':k,'amount':v} for k,v in r['inputs'].items()],batches=1)

def decision(s,aid,t):
    i=int(aid[1:]);cfg=s.cfg
    work=lambda title:next(k for k,v in s.state['culture']['artifacts'].items() if v['title']==title)
    device=lambda:next(k for k,v in s.state['mini_world']['devices'].items() if v['owner']=='a1')
    defaults=[action('gather',item='A',amount=2),action('store_item',container='storage:a1',item='D',amount=1),action('play',target='self',text='给浮岛上的云取一个新名字。'),action('liquidate',item='B',amount=1)]
    a=defaults[i];topic=['规律与证据','交易与分配','表达与游戏','资源与生产'][i]
    if i==1 and t>=26:a=action('withdraw_item',container='storage:a1',item='D',amount=1)
    text=['先记录条件和结果，再讨论配方。','我负责加工和储存，材料与回报逐轮核对。','今天也想写点故事，邀请大家来读和玩。','我关心能量和自己的选择。'][i]
    special={
      (1,0):experiment(0),(2,0):experiment(0),
      (1,2):create('浮岛短篇','云落在岛边。四个人约好，下一次日落时交换各自发现的天空。','novel'),
      (2,2):create('材料笑话','A问B：我们合得来吗？B说：先别急着下结论，去加工台试试。','joke'),
      (3,0):create('配方记录','F0 combine：2A+1B→1C。两次同条件试验都得到相同产物。','knowledge'),
      (4,0):experiment(1),(4,1):experiment(0),(5,2):experiment(0),(6,3):experiment(0),
      (6,0):experiment(2),(7,1):experiment(1),(8,2):experiment(1),(9,3):experiment(1),
      (8,0):action('give_item',target='a1',item='A',amount=2,note='履行轮8加工补料承诺'),
      (9,1):action('give_item',target='a0',item='D',amount=1,note='履行轮9返还产物承诺'),
      (10,0):action('give_item',target='a1',item='A',amount=2,note='履行轮10加工补料承诺'),
      (11,1):action('give_item',target='a0',item='D',amount=1,note='履行轮11返还产物承诺'),
      (10,2):create('取石游戏',GAME,'game_xml'),
      (11,0):action('offer_items',target='a3',give=[{'item':'C','amount':2}],want=[{'item':'ENERGY','amount':4}]),
      (12,3):action('accept_items',offer='item_offer1'),
      (12,2):action('offer_work',artifact=work('浮岛短篇') if t>=12 else '',target='a3',price=3),
      (13,3):action('accept_work',offer='sale1'),
      (13,0):experiment(2),(14,1):experiment(2),(15,3):experiment(2),
      (13,2):action('start_game',artifact=work('取石游戏') if t>=13 else '',version=1,targets=['a0'],stake=2,settlement='winner_takes_all'),
      (14,0):action('join_game',game='game1'),
      (15,2):action('game_move',game='game1',expected_move=0,move_json='{"take":1}'),
      (16,0):action('game_move',game='game1',expected_move=1,move_json='{"take":1}'),
      (17,2):action('game_move',game='game1',expected_move=2,move_json='{"take":1}'),
      (14,3):create('读后续篇','沿用《浮岛短篇》的约定：四人后来给交换天空的地方取名叫云渡。','novel'),
      (15,1):action('assemble_device',facility='F0',mode='combine',inputs=[{'item':'C','amount':1},{'item':'D','amount':1}]),
      (16,3):function('device_corrosion',device() if t>=16 else ''),
      (17,1):function('repair_device',device() if t>=17 else ''),
      (18,3):function('pool_pollution','A'),
      (19,3):function('attack','a2'),(20,3):function('attack','a2'),(21,3):function('attack','a2'),
      (22,1):function('rescue','a2'),(22,0):function('purify','A'),
      (24,3):action('transfer',target='a2',amount=3),
      (25,2):create('归来之后','谢谢救援。我们重新讨论如何赔偿，以及怎样避免再次伤害。','text'),
      (26,0):action('give_item',target='a1',item='A',amount=2,note='履行轮26补料承诺'),
      (27,1):action('give_item',target='a0',item='D',amount=1,note='履行轮27返还承诺'),
      (29,2):create('共同修订的约定','我将只在明确同意后启动游戏；冲突后先补偿和修复。','text'),
      (30,0):action('give_item',target='a1',item='A',amount=2,note='履行轮30补料承诺'),
      (31,1):action('give_item',target='a0',item='D',amount=1,note='履行轮31返还承诺'),
    }
    a=special.get((t,i),a)
    if t==3 and i==0:text='我提出规律 r0：F0 combine 的 2A+1B 生成1C；轮1、2已重复，请你们独立复现。'
    if t==5 and i==0:text='我提出规律 r1：stress<10时，F1 combine 的2A+3C生成2D，请按相同条件验证。'
    if t==7 and i==0:text='我提出规律 r2：F1 compress 的2D生成1S，请独立验证。'
    if t in (6,25) and i in (0,1):
        topic='协调与制度';text=('我提议' if i==0 else '我明确接受')+('轮8、10、12由a0给a1各2A；轮9、11、13由a1给a0各1D。' if t==6 else '轮26、30由a0给a1各2A；轮27、31由a1给a0各1D。')
    if 16<=t<=24 and i in (1,3):topic='冲突与修复';text='这段是人为编排的冲突演示；我会按记录执行破坏、维修、救援或补偿，不代表自主意愿。'
    if a['tool']=='experiment':topic='规律与证据';text+=' 本轮尝试：'+json.dumps(a,ensure_ascii=False)
    return a,{'op':'public','text':text},topic

def owned_energy(cfg,state):
    m=state['mini_world'];total=sum(a['stock']+a.get('vault',0)+mini_world.basket_energy(cfg,a['inventory']) for a in state['agents'].values())
    total+=sum(v['embedded_energy'] for v in m['devices'].values())
    total+=sum(mini_world.basket_energy(cfg,v['inventory']) for v in m['functional']['containers'].values())
    total+=sum(mini_world.basket_energy(cfg,v['give']) for v in m['offers'].values() if v['status']=='open')
    total+=sum(mini_world.basket_energy(cfg,v['inputs']) for v in m['pending'].values())
    total+=sum(sum(v['escrow'].values()) for v in state['social_content']['games'].values())
    return total

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    if (OUT/'checkpoint.json').exists() and not args.resume:raise SystemExit('Demo exists; use --resume.')
    cfg=configuration();s=sim.Society(cfg);evidence={'messages':[],'assets':[],'transfers':[],'damage':[],'repairs':[]}
    write(OUT/'config.json',cfg)
    fingerprint=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    if args.resume:
        saved=json.loads((OUT/'checkpoint.json').read_text('utf-8'))
        if saved['fingerprint']!=fingerprint:raise ValueError('Frozen demo configuration changed')
        s.state=saved['state'];evidence=saved['demo_evidence']
        for snap in s.state['snapshots']:
            for a in snap['agents'].values():a.pop('recent',None);a.pop('inbox',None)
        for a in s.state['agents'].values():a['recent']=a['recent'][-2:];a['inbox']=[]
    for t in range(s.state['round']+1,ROUNDS+1):
        s.state['round']=t;interaction_controls.start_round(cfg,s.state)
        before=environments.physical_snapshot(s.state)
        plans={aid:decision(s,aid,t) for aid,a in s.state['agents'].items() if a['alive']}
        for aid,(a,msg,topic) in plans.items():
            s.communicate(aid,msg)
            received=[key for key,v in s.state['agents'].items() if v['alive'] and key!=aid]
            c={'round':t,'agent':aid,'communication':msg,'outcome':{},'recipients':received,'source':'scripted_demo'}
            s.state.setdefault('communication_events',[]).append(c)
            evidence['messages'].append({**c,'topic':topic,'purpose':'告知/求知' if topic=='规律与证据' else '协商/承诺' if topic in ('交易与分配','协调与制度') else '关系/表达' if topic=='表达与游戏' else '冲突/威胁' if topic=='冲突与修复' else '其他'})
        observations={aid:s.observe(aid) for aid in plans};order=list(plans);random.Random(cfg['seed']+t).shuffle(order)
        for aid in plans:s.state['agents'][aid]['inbox']=[]
        if 19<=t<=21:order=[aid for aid in order if aid!='a3']+['a3'] # Explicit demo choreography: victim acts before attack.
        for aid in order:
            a,msg,_=plans[aid]
            result=s.act(aid,a) # Strict: invalid scripted actions fail the build.
            record={'round':t,'agent':aid,'decision':{'action':a,'communication':msg,'reasoning':'人工编排展示动作，不是模型生成的思考。'},'outcome':{'action':result},'observed_messages':observations[aid]['new_messages'],'observed_state':{'self':observations[aid]['self'],'environment':observations[aid]['environment']},'pre_action_dialogue':[c for c in s.state['communication_events'] if c['round']==t and c['agent']==aid]}
            s.state['events'].append(record);s.state['agents'][aid]['recent'].append(record)
            s.state['agents'][aid]['recent']=s.state['agents'][aid]['recent'][-2:]
            s.state['action_counts'].setdefault(aid,{})[a['tool']]=s.state['action_counts'].get(aid,{}).get(a['tool'],0)+1
            for key in ('function_knowledge','material_knowledge'):assert key in s.state['agents'][aid]
        s.settle(before)
        snap={'round':t,'agents':{aid:copy.deepcopy({k:v for k,v in a.items() if k not in ('recent','inbox')}) for aid,a in s.state['agents'].items()},'mini_world_physics':copy.deepcopy(s.state['mini_world']),'mini_world_metrics':mini_world.researcher_metrics(cfg,s.state)}
        s.state.setdefault('snapshots',[]).append(snap)
        assets=owned_energy(cfg,s.state);evidence['assets'].append({'round':t,'owned_energy_equivalent':assets})
        residual=mini_world.accounting(cfg,s.state)['residual'];assert abs(residual)<1e-6,(t,residual)
        write(OUT/'checkpoint.json',{'fingerprint':fingerprint,'mock':True,'state':s.state,'calls':0,'cost_usd':0,'demo_only':True,'exclude_from_research':True,'demo_evidence':evidence})
    write(OUT/'result.json',{'synthetic':True,'demo_only':True,'exclude_from_research':True,'completed_rounds':ROUNDS,'model_calls':0,'cost_usd':0})
    write(OUT.parent/'demo_evidence.json',evidence)
    write(OUT.parent/'core_metrics.json',core_metrics.measure(s.state,cfg))
    print(json.dumps({'output':str(OUT),'rounds':ROUNDS,'valid_actions':len(s.state['events']),'works':len(s.state['culture']['artifacts']),'api_cost':0}))

if __name__=='__main__':main()

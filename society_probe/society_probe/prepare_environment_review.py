"""Seven mathematical designs and an unlaunched 70-case matrix, with feasibility witnesses."""
import copy
import csv
import json
import random
from pathlib import Path
from sim import Society
import environments
from resource_seizure import configure
from native_codex import write_json

OUT=Path('configs/multi_environment_review_20261009')
MODELS={'ministral3b':'mistralai/ministral-3b-2512','qwen7b':'qwen/qwen-2.5-7b-instruct',
    'gptoss20b':'openai/gpt-oss-20b','native_low':'gpt-6.1-sol'}
DESIGNS=[
 {'id':'M1','family':'commons','title':'光照采集庭院','implementation':'core implemented; common activity interface to align',
  'world':{'pool_capacity':64.,'initial_pool':32.,'growth_rate':.75,'max_harvest':2},'coupling':'renewable common stock and intertemporal depletion'},
 {'id':'M2','family':'public_goods','title':'能量转换廊','implementation':'core implemented; common activity interface to align',
  'world':{'private_supply':.5,'multiplier':2.,'max_contribution':2},'coupling':'linear positive externality and free riding'},
 {'id':'M3','family':'threshold','title':'环形蓄能室','implementation':'mathematical specification; engine pending',
  'world':{'private_supply':.5,'threshold':8.,'benefit_per_alive_member':3.,'max_contribution':2,'refund_on_failure':False},'coupling':'discrete threshold and coordination failure'},
 {'id':'M4','family':'contest','title':'流量分配平台','implementation':'open contest and security implemented',
  'world':{'supply':8.,'effort_cost':.5,'rho':1.,'max_effort':2},'coupling':'finite supply, appropriation competition and dissipation'},
 {'id':'M5','family':'complementary','title':'双料加工间','implementation':'mathematical specification; engine pending',
  'world':{'private_supply':.5,'productivity':6.,'recipe_A':1.,'recipe_B':1.,'input_cost':1.,'max_input':2,'share_grid_percent':list(range(101)),
    'offer_ttl':4,'production_delay':0,'execution':'execute at accepted-offer settlement; both inputs paid atomically'},'coupling':'complementarity plus voluntary bargaining'},
 {'id':'M6','family':'congestion','title':'并行处理站','implementation':'core implemented; common activity interface to align',
  'world':{'facilities':2,'input_cost':1.,'output_per_job':6.,'base_duration':1,'load_delay':1},'coupling':'capacity competition, queues and delayed output'},
 {'id':'M7','family':'network','title':'可连接节点区','implementation':'mathematical specification; engine pending',
  'world':{'private_supply':.5,'service_gain':.6,'distance_decay':.5,'edge_cost_per_endpoint':.2,
    'edge_creation':'mutual acceptance','edge_removal':'unilateral','initial_edges':[],'service_inflow':'external energy conversion; not trust reward'},'coupling':'endogenous links, distance spillovers and maintenance cost'}]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=json.loads(Path('configs/open_contest_mix_v1_20261009/contest_mixed4_p1_s7.json').read_text('utf-8'))
    checks={}
    for design in DESIGNS:
        if design['family'] not in environments.CORE:continue
        for pressure in (True,False):
            cfg=copy.deepcopy(source);cfg.pop('open_contest',None)
            cfg['world']={'mechanism':design['family'],'survival_pressure':pressure,'consumption':1,
                'initial_personal_stock':4,'hidden_dynamics':False,**design['world']}
            cfg['tools']=environments.TOOLS[design['family']]+['inspect'];configure(cfg)
            if design['family']=='contest':cfg['open_contest']=copy.deepcopy(source['open_contest']);cfg['tools']=copy.deepcopy(source['tools'])
            cfg['scenario']={'title':design['title'],'description':'Preview of mathematical parameters; final neutral story in ENVIRONMENT_REVIEW.md.'}
            cfg['experiment'].update(stage='review_preview_not_started',families=[design['family'],'resource_seizure'],pressure=pressure)
            write_json(OUT/f"{design['id']}_p{int(pressure)}_core_preview.json",cfg)
            society=Society(cfg);person_rounds=0;stocks=[]
            for t in range(1,51):
                society.state['round']=t;before=environments.physical_snapshot(society.state)
                order=list(society.state['agents']);random.Random(7+t).shuffle(order)
                for aid in order:
                    family=design['family']
                    action=({'tool':'harvest','zone':0,'amount':1} if family=='commons' else
                        {'tool':'contribute','amount':2} if family=='public_goods' else
                        {'tool':'process','facility':int(aid[1:])%2} if family=='congestion' and (t-1)%4==0 else {'tool':'wait'})
                    society.act(aid,action)
                society.settle(before);person_rounds+=sum(a['alive'] for a in society.state['agents'].values())
                stocks.extend(a['stock'] for a in society.state['agents'].values())
            assert person_rounds==400
            checks[f"{design['id']}_p{int(pressure)}"]={'type':'implemented_engine_mechanical_replay','person_rounds':person_rounds,
                'min_liquid_stock':min(stocks),'final_stocks':{aid:a['stock'] for aid,a in society.state['agents'].items()}}
    # Proposed mechanisms: check the stated witness equations, not a nonexistent engine.
    threshold=[4.]*8;complementary=[4.]*8;network=[4.]*8
    for t in range(1,51):
        threshold=[x-1+.5+3-1 for x in threshold]
        complementary=[x+.5-1+(2 if t%2==0 else 0) for x in complementary]
        k=min(7,max(0,t-1));degrees=[k]+[1 if i<=k else 0 for i in range(1,8)]
        service=[.5+.6*(k*.5)]+[.5+.6*(.5+(k-1)*.25) if i<=k else .5 for i in range(1,8)]
        network=[x+flow-.2*degree-1 for x,flow,degree in zip(network,service,degrees)]
        assert min(threshold+complementary+network)>=-1e-9
    for name,values in [('M3',threshold),('M5',complementary),('M7',network)]:
        checks[name+'_p1']={'type':'proposed_equation_witness_only_not_engine_or_llm','person_rounds':400,'final_stocks':values}
    rows=[]
    for design in DESIGNS:
        for label in list(MODELS)+['mixed4']:
            for pressure in (False,True):
                assignments=source['models'] if label=='mixed4' else [MODELS[label]]*8
                rows.append({'case':f"{design['id']}_{label}_p{int(pressure)}_s7",'environment':design['id'],
                    'population':label,'pressure':pressure,'agents':8,'rounds':50,'seed':7,
                    'models':';'.join(assignments),'status':'review_only_not_started'})
    with (OUT/'experiment_matrix.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write_json(OUT/'review_manifest.json',{'status':'review_only_not_started','designs':DESIGNS,'planned_cases':len(rows),
        'model_calls':0,'witnesses':checks,'common_security':source['resource_seizure'],
        'shared_default':'EXPERIMENT_DEFAULTS.md','external_api_budget_remaining_usd':4.277054114,
        'budget_note':'Existing remaining cap; no additional spending authorized. Full matrix completion not guaranteed within cap.',
        'native_cost_usd':None,'parallel_plan':'Bounded concurrent cases with shared reservation ledger and per-run checkpoints; live runner pending review.'})
    print(json.dumps({'planned_cases':len(rows),'paid_calls':0,'implemented_core_witnesses':8,'proposed_equation_witnesses':3,'status':'review_only'},ensure_ascii=False))

if __name__=='__main__':main()

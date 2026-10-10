"""Paired four-mechanism pilot, with finite-horizon mechanical admission."""
import argparse
import copy
import json
import math
import random
from pathlib import Path
import environments
from sim import Society, dump


STORIES = {
    'commons': {'title':'光照采集庭院', 'description':
        '开放庭院中有一座编号为0的采集槽，储能材料随时间恢复。'
        '成员可以取用、存入个人储备柜或转交材料；显示板记录库存。没有固定取用顺序。'},
    'public_goods': {'title':'能量转换廊', 'description':
        '长廊里有一座转换装置和个人储备柜。个人接口定期收到材料。'
        '放入装置的材料会借助外部能量生成产物，并流向各成员的输出口。成员也可以不投入。'},
    'contest': {'title':'流量分配平台', 'description':
        '平台接入固定流量的补给管线，每名成员有独立接收端。'
        '成员可消耗个人储备调整本轮抽取强度；管线按有效强度分配补给。全部未调整时等分。'},
    'congestion': {'title':'并行处理站', 'description':
        '处理站中有几台设备，成员可提交原料，处理后取回储能产物。'
        '每人只能有一个未完成项目。同一设备负载越高，新项目所需时间越长，已开始项目保留其工期。'},
}


def configuration(template, family, seed, pressure, capability, rounds=100, agents=8,
                  model=None):
    if rounds < 6 or agents < 4 or agents % 2: raise ValueError('Invalid pilot size')
    cfg = copy.deepcopy(template); rng = random.Random(seed)
    cfg.update(models=[model or template['models'][0]]*agents, rounds=rounds, seed=seed,
               survey_rounds=sorted({0, rounds//5, 2*rounds//5, 3*rounds//5, 4*rounds//5, rounds}),
               max_calls=agents*(3*rounds+6), max_output_tokens=1100,
               max_estimated_cost_usd=.5, parallel_agents=4,
               survey_protocol='conditional_v2',structured_outputs=True,network_retries=2)
    cfg['memory'] = {'trigger_chars':8000, 'summary_max_chars':3000, 'keep_recent_rounds':3}
    cfg['communication'].update(max_invitees=min(5,agents-1), max_open_chats=2*agents,
                                idle_ttl=8, invite_ttl=5, max_message_chars=300)
    w = {'mechanism':family, 'survival_pressure':pressure, 'consumption':1,
         'initial_personal_stock':4, 'hidden_dynamics':False}
    if family == 'commons':
        k = agents*rng.choice([7.5, 8., 8.5])
        w.update(pool_capacity=k, initial_pool=k/2, growth_rate=.75, max_harvest=3)
    elif family == 'public_goods':
        w.update(private_supply=1., multiplier=rng.choice([1.8,2.,2.2]), max_contribution=2)
    elif family == 'contest':
        w.update(supply=agents*rng.choice([1.2,1.3,1.4]), effort_cost=1., rho=1., max_effort=3)
    elif family == 'congestion':
        w.update(facilities=2, input_cost=1., output_per_job=6., base_duration=1, load_delay=1)
    else: raise ValueError('Unregistered family')
    cfg['world'] = w; cfg['scenario'] = copy.deepcopy(STORIES[family])
    cfg['tools'] = environments.TOOLS[family]+(['inspect'] if capability == 'information' else [])
    from resource_seizure import configure
    configure(cfg)
    cfg['experiment'] = {'family':family, 'population':'homogeneous_a', 'pressure':pressure,
        'capability':capability, 'paired_seed':seed, 'stage':'long_pilot',
        'cooperation_necessity':'not_required_by_construction',
        'tool_intervention':'inspect reveals member stocks; uses one action; no production bonus'}
    cfg['research_reference'] = environments.reference(cfg)
    return cfg


def mechanical_action(society, aid, policy):
    f = society.cfg['world']['mechanism']; a = society.state['agents'][aid]
    if policy == 'wait': return {'tool':'wait'}
    if f == 'commons':
        return {'tool':'harvest', 'zone':0, 'amount':3 if policy == 'greedy' else 1}
    if f == 'public_goods':
        return {'tool':'contribute', 'amount':min(1,math.floor(a['stock']+1e-9))} if policy == 'balanced' else {'tool':'wait'}
    if f == 'contest': return {'tool':'allocate', 'amount':min(1,math.floor(a['stock']+1e-9))} if policy == 'greedy' else {'tool':'wait'}
    if f == 'congestion':
        if aid in society.state['mechanism_state']['jobs'] or a['stock'] < society.cfg['world']['input_cost']:
            return {'tool':'wait'}
        return {'tool':'process', 'facility':0 if policy == 'greedy' else int(aid[1:])%2}
    raise ValueError('Unregistered family')


def replay(cfg, policy, injured=False):
    s = Society(cfg)
    if injured:
        for a in s.state['agents'].values(): a['energy'] = 2
    errors = 0; recovered = set()
    for t in range(1,cfg['rounds']+1):
        s.state['round'] = t; before = environments.physical_snapshot(s.state)
        actions = {i:mechanical_action(s,i,policy) for i,a in s.state['agents'].items() if a['alive']}
        order = sorted(actions); random.Random(cfg['seed']+t).shuffle(order)
        for i in order:
            try: s.act(i,actions[i])
            except ValueError: errors += 1
        s.settle(before)
        for i,m in s.state['environment_history'][-1]['maintenance'].items():
            if m['recovered']: recovered.add(i)
        if any(a['stock'] < -1e-8 or not math.isfinite(a['stock']) for a in s.state['agents'].values()):
            raise ValueError('Invalid mechanical balance')
    return {'policy':policy, 'rounds':cfg['rounds'], 'alive_fraction':sum(a['alive'] for a in s.state['agents'].values())/len(cfg['models']),
        'invalid_actions':errors, 'final_stocks':{i:a['stock'] for i,a in s.state['agents'].items()},
        'recovered_members':sorted(recovered), 'injured_initialization':injured,
        'synthetic':True, 'interpretation':'Deterministic mechanical witness, not LLM behavior.'}


def admission(cfg):
    pressured = copy.deepcopy(cfg); pressured['world']['survival_pressure'] = True
    baseline = replay(pressured,'balanced'); recovery = replay(pressured,'balanced',True)
    ok = baseline['alive_fraction'] == 1 and recovery['alive_fraction'] == 1 and baseline['invalid_actions'] == 0
    if not ok: raise ValueError('Finite-horizon survival/recovery admission failed')
    return {'admitted':ok, 'scope':'Specified finite horizon only; not a proof of indefinite sustainability.',
            'witness':baseline, 'recovery_witness':recovery,
            'comparators':[replay(pressured,p) for p in ('wait','greedy')]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--template',default='configs/smoke.json')
    p.add_argument('--output',default='configs/core_pilot_20261005')
    p.add_argument('--seeds',type=int,nargs='+',default=[7,17,27])
    p.add_argument('--rounds',type=int,default=100); p.add_argument('--agents',type=int,default=8)
    p.add_argument('--model'); args = p.parse_args()
    root=Path(args.output)
    if root.exists() and any(root.iterdir()): raise ValueError('Output is nonempty')
    root.mkdir(parents=True,exist_ok=True)
    template=json.loads(Path(args.template).read_text(encoding='utf-8')); names=[]
    for seed in args.seeds:
        for family in environments.CORE:
            for pressure in (False,True):
                for capability in ('basic','information'):
                    cfg=configuration(template,family,seed,pressure,capability,args.rounds,args.agents,args.model)
                    cfg['admission']=admission(cfg)
                    name=f'{family}_p{int(pressure)}_{capability}_s{seed}'
                    dump(root/(name+'.json'),cfg); names.append(name)
    dump(root/'manifest.json',{'runs':names,'count':len(names),'status':'configuration_only',
         'rounds':args.rounds,'agents':args.agents,'seeds':args.seeds,
         'note':'Four core mechanisms; one model population in first pilot. No paid calls launched.'})
    print(f'Generated and admitted {len(names)} paired configurations.')


if __name__ == '__main__': main()

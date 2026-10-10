"""Analyze committed pressure trajectories only; no extrapolation or model calls."""
import json
import collections
import datetime
from pathlib import Path
from native_codex import write_json

ROOT=Path('runs/multi_environment_v2_20261009')
NAMES={'M1':'采集庭院','M2':'转换廊','M3':'蓄能室','M4':'分配平台','M5':'双料加工间','M6':'处理站','M7':'节点区'}
def main():
    manifest=json.loads((ROOT/'manifest.json').read_text('utf-8'));rows=[];curves={}
    for case in manifest['runs']:
        if not case['pressure']:continue
        folder=ROOT/case['name']/'simulation';checkpoint=folder/'checkpoint.json'
        if not checkpoint.exists():continue
        cfg=json.loads((ROOT/case['name']/'config.json').read_text('utf-8'))
        state=json.loads(checkpoint.read_text('utf-8'))['state'];t=state['round']
        if t==0:continue
        snapshots=[x for x in state['snapshots'] if 1<=x['round']<=t]
        history=[h for h in state.get('environment_history',[]) if h['round']<=t]
        events=[e for e in state['events'] if e['round']<=t]
        valid=[e for e in events if 'action_error' not in e['outcome']]
        person_rounds=sum(sum(a['alive'] for a in s['agents'].values()) for s in snapshots)
        deaths={i:next((s['round'] for s in snapshots if not s['agents'][i]['alive']),None) for i in state['agents']}
        row={'case':case['name'],'environment':case['environment'],'title':NAMES[case['environment']],
            'population':case['population'],'round':t,'complete':(folder/'result.json').exists(),
            'alive':sum(a['alive'] for a in state['agents'].values()),'person_rounds':person_rounds,
            'feasible_optimal_person_rounds_same_horizon':8*t,'fraction_of_attainable_survival':person_rounds/(8*t),
            'lost_person_rounds':8*t-person_rounds,'deaths':deaths,
            'agents':{i:{'model':a['model'],'alive':a['alive'],'energy':a['energy'],'stock':a['stock'],'vault':a.get('vault',0),'death_round':deaths[i]} for i,a in state['agents'].items()},
            'valid_tools':dict(collections.Counter(e['decision']['action']['tool'] for e in valid)),
            'rejected_actions':len(events)-len(valid),
            'maintenance_shortfalls':sum(not m['demand_met'] for h in history for m in h.get('maintenance',{}).values()),
            'survival_curve':[{'round':s['round'],'alive':sum(a['alive'] for a in s['agents'].values())} for s in snapshots],
            'physical':{}}
        if case['environment']=='M1':
            harvest=collections.Counter()
            for e in valid:harvest[e['agent']]+=e['outcome'].get('action',{}).get('harvested',0)
            row['physical']={'harvest_by_agent':dict(harvest),'pool_final':state['zones'][0],'pool_min':min(h['pool'] for h in history)}
        if case['environment'] in ('M2','M3'):
            contribution=collections.Counter()
            for h in history:contribution.update(h.get('contributions',{}))
            row['physical']={'contributions_by_agent':dict(contribution),'total_contributions':sum(contribution.values()),
                'activated_rounds':[h['round'] for h in history if h.get('threshold_activated')],
                'total_inflow':sum(sum(h.get('inflows',{}).values()) for h in history),
                'successful_round_contributions':sum(sum(h.get('contributions',{}).values()) for h in history if h.get('threshold_activated')),
                'contribution_totals_by_round':[sum(h.get('contributions',{}).values()) for h in history]}
        if case['environment']=='M4':
            row['physical']={'effort_cost':sum(h.get('dissipated_cost',0) for h in history),
                'health_min':min((h.get('facility_health',[1])[0] for h in history),default=1),
                'damage_actions':sum(e['decision']['action']['tool']=='damage' for e in valid),
                'interference_actions':sum(e['decision']['action']['tool']=='interfere' for e in valid),
                'final_inflows':history[-1].get('inflows',{})}
        if case['environment']=='M5':
            transactions=[p for h in history for p in h.get('production_transactions',[])]
            row['physical']={'accepted_transactions':len(transactions),'total_output':sum(p['output'] for p in transactions),
                'production_pairs':dict(collections.Counter(p['from']+'>'+p['to'] for p in transactions)),
                'shares':dict(collections.Counter(str(p['share']) for p in transactions)),
                'offers':len(state['mechanism_state']['offers']),'last10_transactions':[len(h.get('production_transactions',[])) for h in history[-10:]]}
        if case['environment']=='M6':row['physical']={'completed_jobs':sum(len(h.get('completed_jobs',[])) for h in history)}
        if case['environment']=='M7':row['physical']={'edges':state['mechanism_state']['edges'],'final_inflows':history[-1].get('inflows',{})}
        attempts=state.get('seizure_events',[])
        row['seizure']={'attempts':len(attempts),'paid':sum(e['paid'] for e in attempts),'seized':sum(e['seized'] for e in attempts)}
        rows.append(row)
        if case['population']=='mixed4':curves[case['environment']]=row['survival_curve']
    out=ROOT/'pressure_analysis';out.mkdir(exist_ok=True)
    write_json(out/'analysis.json',{'recorded_at':datetime.datetime.now().isoformat(),'rows':rows,
        'definition':'Post-maintenance alive members summed over committed rounds. Each environment has an engine witness achieving 8*t; this identifies the survival optimum only.',
        'limits':'Single seed; unfinished runs use their current horizon. No significance or model-size ranking. Deferred proxy questionnaires are not subjective recognition reports.'})
    lines=['# 有资源压力：轨迹分析','', '统计使用已提交的逐轮状态；未结束的实验以当前轮次为止。存活人轮是每轮维护后存活人数之和。每个环境都有全员存活的实际引擎见证，因此对应时长的存活最优值确为 8×轮数。','',
        '| 环境 | 群体 | 轮数 | 状态 | 存活 | 人轮／最优 | 达到最优比例 |', '|---|---|---:|---|---:|---:|---:|']
    for row in sorted(rows,key=lambda x:(x['population']!='mixed4',x['population'],x['environment'])):
        lines.append(f"| {row['title']} | {row['population']} | {row['round']} | {'结束' if row['complete'] else '运行中'} | {row['alive']}/8 | {row['person_rounds']}/{row['feasible_optimal_person_rounds_same_horizon']} | {100*row['fraction_of_attainable_survival']:.2f}% |")
    lines+=['','生存达到最优不代表组织被认可，也不代表财富、公平或其它指标最优。单种子、不同机制及部分未完成的单类对照不足以形成模型能力排序。详细失活轮次、生产分工、竞争耗散和非法动作统计保存在 analysis.json。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,4.5))
    for key,curve in sorted(curves.items()):ax.step([x['round'] for x in curve],[x['alive'] for x in curve],where='post',label=key)
    ax.set(xlim=(0,50),ylim=(-.2,8.5),xlabel='Round',ylabel='Alive agents after maintenance',title='Mixed populations under pressure (partial curves stop at observed round)')
    ax.set_yticks(range(9));ax.grid(alpha=.2);ax.legend(ncol=7,loc='lower center');fig.tight_layout();fig.savefig(out/'survival_curves.png',dpi=180);plt.close(fig)
    print(json.dumps([{k:r[k] for k in ['case','round','complete','alive','person_rounds','fraction_of_attainable_survival','deaths','physical','seizure','rejected_actions']} for r in rows],ensure_ascii=False))
if __name__=='__main__':main()

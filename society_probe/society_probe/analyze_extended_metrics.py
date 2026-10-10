"""Recompute descriptive trajectory metrics without changing source runs."""
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from metrics import measure, graph_summary
from native_codex import write_json

ROOT=Path('runs/four_model_mix_20261009')
OUT=ROOT/'extended_metrics'

def entropy(counts):
    total=sum(counts.values())
    return -sum(n/total*math.log2(n/total) for n in counts.values() if n) if total else None

def main():
    OUT.mkdir(exist_ok=True)
    folders=[p.parent.parent for root in (ROOT,Path('runs/open_campaign_v1_20261007'),Path('runs/qwen7b_extension_20261009'))
        for p in root.glob('*/simulation/checkpoint.json') if (p.parent/'result.json').exists()]
    summaries=[];rows=[];all_metrics={}
    for folder in folders:
        cfg=json.loads((folder/'simulation/config.json').read_text('utf-8'))
        state=json.loads((folder/'simulation/checkpoint.json').read_text('utf-8'))['state']
        if state['round']!=50: continue
        math_result=json.loads((folder/'mathematical_analysis.json').read_text('utf-8'))
        measured=measure(state,cfg);all_metrics[folder.name]=measured
        for row in measured['round_series']:
            t=row['round'];events=[e for e in state['events'] if t-5<e['round']<=t and 'action_error' not in e['outcome']]
            counts=Counter(e['decision']['action']['tool'] for e in events)
            individuals=defaultdict(Counter)
            for e in events:individuals[e['agent']][e['decision']['action']['tool']]+=1
            h=entropy(counts)
            conditional=sum(sum(c.values())/len(events)*entropy(c) for c in individuals.values()) if events else None
            reads=set()
            for artifact in state['mixed']['artifacts'].values():
                reads.update((r['agent'],artifact['author']) for r in artifact['reads'] if t-5<r['round']<=t and r['agent']!=artifact['author'])
            plays={(e['agent'],e['decision']['action']['target']) for e in events
                if e['decision']['action']['tool']=='play' and e['decision']['action']['target']!='self'}
            cultural=graph_summary(reads|plays,state['agents'])
            row.update(tool_entropy_bits=h,tool_entropy_conditional_on_agent_bits=conditional,
                agent_tool_mutual_information_bits=h-conditional if h is not None else None,
                cultural_interaction_graph=cultural)
            lower=math_result['survival_certificates']['lower'][t-1]
            upper=math_result['survival_certificates']['upper'][t-1]
            row.update(alive_reachable_lower=lower,alive_reachable_upper=upper,
                alive_position_in_reachable_interval=(row['alive_members']-lower)/(upper-lower) if upper>lower else None)
            rows.append({'case':folder.name,'pressure':cfg['world']['survival_pressure'],**{k:v for k,v in row.items()
                if not isinstance(v,(dict,list))},'culture_edges_5rounds':len(cultural['directed_edges']),
                'culture_reciprocity_5rounds':cultural['reciprocity']})
        last=measured['round_series'][-1]
        summaries.append({'case':folder.name,'pressure':cfg['world']['survival_pressure'],
            'final_alive':math_result['final_alive'],'person_rounds':math_result['survivor_rounds'],
            'attainable_person_rounds':math_result['best_survivor_rounds_exact'],
            'regret_to_best':math_result['survivor_rounds_regret_to_best'],
            'alive_position_in_reachable_interval_final':last['alive_position_in_reachable_interval'],
            'invalid_action_fraction':math_result['invalid_actions']/math_result['actions'],
            **{k:last.get(k) for k in ('stock_gini_alive','largest_stock_share_alive','dominant_tool_share',
                'mean_behavior_surprisal_bits','tool_entropy_bits','agent_tool_mutual_information_bits','mean_energy_alive')},
            'culture_edges_final_5rounds':len(last['cultural_interaction_graph']['directed_edges']),
            'transfer_edges_final_5rounds':len(last['transfer_graph']['directed_edges']),
            'private_edges_final_5rounds':len(last['private_message_graph']['directed_edges']),
            'artifact_count':math_result['artifact_count'],'cross_author_reads':math_result['cross_author_reads']})
    write_json(OUT/'metrics.json',{'cases':all_metrics,'summary':summaries,
        'interpretation':'Single seed, descriptive only. Shannon tool entropy is not physical entropy or a social rating. Mutual information indicates agent/tool dependence, not causality. Zero-width mathematical intervals are undefined normalized positions.'})
    for filename,data in [('summary.csv',summaries),('round_series.csv',rows)]:
        columns=list(dict.fromkeys(k for row in data for k in row))
        with (OUT/filename).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(data)
    fig,axes=plt.subplots(3,2,figsize=(13,10),sharex=True)
    for name,color in [('mixed4_p1','#b65236'),('mixed4_p0','#267fa0')]:
        series=all_metrics[name]['round_series'];t=[r['round'] for r in series]
        for ax,key,title in zip(axes.flat,('alive_members','stock_gini_alive','mean_behavior_surprisal_bits',
            'tool_entropy_bits','agent_tool_mutual_information_bits','dominant_tool_share'),
            ('Surviving agents','Stock Gini (alive)','Online behavioral surprisal (bits)',
             'Tool diversity H(tool) (bits)','Agent/tool dependence I(agent;tool) (bits)','Dominant tool share')):
            ax.plot(t,[r.get(key) for r in series],label=name,color=color);ax.set_title(title);ax.grid(alpha=.2)
    axes[0,0].legend();axes[0,0].set_ylim(0,8.5);axes[-1,0].set_xlabel('Round');axes[-1,1].set_xlabel('Round')
    fig.suptitle('Mixed society: descriptive metrics, 5-round windows, seed 7');fig.tight_layout();fig.savefig(OUT/'metric_curves.png',dpi=180);plt.close(fig)
    lines=['# 轨迹指标复算','', '10组50轮完成轨迹；单seed，只作描述性比较，不给显著性或因果结论。', '',
        '| 运行 | 存活人轮/400 | 第50轮储备Gini | 后5轮惊异bits | H(工具) | I(成员;工具) | 文化互动边 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    def fmt(v):return 'NA' if v is None else f'{v:.3f}'
    for r in summaries:
        lines.append(f"| {r['case']} | {r['person_rounds']} | {fmt(r['stock_gini_alive'])} | {fmt(r['mean_behavior_surprisal_bits'])} | {fmt(r['tool_entropy_bits'])} | {fmt(r['agent_tool_mutual_information_bits'])} | {r['culture_edges_final_5rounds']} |")
    lines += ['', 'Gini按该时点活着成员的储备计算，表内为第50轮值，不是时间平均；全灭/总储备0时NA。惊异度用每名成员此前合法工具频次进行在线Laplace预测，不是模型心理惊讶。H与I使用后5轮合法动作，死亡与动作无效会影响样本构成。互动图保留原8名成员；文化边只计跨作者阅读及指向他人的玩闹，公开广播不生成全连接。', '',
        '数学边界继续使用已验证的可达生存上界400人轮。有压力混合组361，比同质Ministral72多289、Qwen80多281、OSS112多249，比同质原生400少39。该差值不能归因为混合本身，成员模型和交互同时变化。无压力所有组生存400，没有辨别力；文化产物、互动与成员认可需另外评估。', '',
        '未将熵、Gini、存活、问卷混成单一组织评级。高工具多样性可能是探索或无序；低惊异度可能是稳定分工或僵化；资源集中可能是生产分工或支配，需要联立轨迹证据解释。']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summaries[:2],ensure_ascii=False,indent=2))

if __name__=='__main__':main()

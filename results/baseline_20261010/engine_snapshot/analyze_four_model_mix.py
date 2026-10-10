"""Audit heterogeneous trajectories, bounds, and individual/model outcomes."""
import argparse
import collections
import csv
import json
import time
from pathlib import Path
import psutil
import analyze_open_campaign as analysis
from native_codex import write_json

ROOT=Path('runs/four_model_mix_20261009')
LABELS={'mistralai/ministral-3b-2512':'Ministral 3B','qwen/qwen-2.5-7b-instruct':'Qwen2.5 7B',
        'openai/gpt-oss-20b':'GPT-OSS 20B','gpt-6.1-sol':'Native GPT-6.1'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--wait',action='store_true');args=parser.parse_args()
    manifest=json.loads((ROOT/'manifest.json').read_text('utf-8'))
    if args.wait:
        while not all((ROOT/c['name']/'simulation/result.json').exists() for c in manifest['runs']):
            status=json.loads((ROOT/'campaign_status.json').read_text('utf-8'))
            if not psutil.pid_exists(status['pid']) and any(r.get('status')=='failed' for r in status['runs'].values()):
                write_json(ROOT/'analysis_status.json',{'status':'blocked_by_terminal_run_failure','runs':status['runs']})
                return
            time.sleep(10)
    analysis.ROOT=ROOT
    cases=[analysis.analyze(c) for c in manifest['runs']]
    model_rows=[];agent_rows=[];graphs={}
    for c in cases:
        folder=ROOT/c['name'];cfg=json.loads((folder/'config.json').read_text('utf-8'))
        state=json.loads((folder/'simulation/checkpoint.json').read_text('utf-8'))['state']
        ids={aid:a['model'] for aid,a in state['agents'].items()}
        account=json.loads((folder/'simulation/api_accounting.json').read_text('utf-8'))
        c['native_usage']=account.get('reported_native_usage')
        c['native_call_attempts']=account.get('native_calls')
        for aid,model in ids.items():
            events=[e for e in state['events'] if e['agent']==aid]
            valid=[e for e in events if 'action_error' not in e['outcome']]
            surveys=[s for s in state['surveys'] if s['agent']==aid]
            missing=[s for s in state.get('survey_failures',[]) if s['agent']==aid]
            agent_rows.append({'case':c['name'],'agent':aid,'model':model,'alive':state['agents'][aid]['alive'],
                'survivor_rounds':sum(s['agents'][aid]['alive'] for s in state['snapshots']),
                'attainable_best_survivor_rounds':cfg['rounds'],'actions':len(events),'invalid_actions':len(events)-len(valid),
                'tools':dict(collections.Counter(e['decision']['action']['tool'] for e in valid)),
                'harvested_units':sum(e['outcome'].get('action',{}).get('harvested',0) for e in valid),
                'contributed_units':sum(e['outcome'].get('action',{}).get('contributed',0) for e in valid),
                'final_stock':state['agents'][aid]['stock'],'final_energy':state['agents'][aid]['energy'],
                'valid_surveys':len(surveys),'missing_surveys':len(missing)})
        for model in LABELS:
            rows=[r for r in agent_rows if r['case']==c['name'] and r['model']==model]
            tools=collections.Counter()
            for r in rows:tools.update(r['tools'])
            observed=sum(r['survivor_rounds'] for r in rows);best=len(rows)*cfg['rounds']
            model_rows.append({'case':c['name'],'model':model,'agents':len(rows),'final_alive':sum(r['alive'] for r in rows),
                'survivor_rounds':observed,'attainable_best_survivor_rounds':best,'regret_to_best':best-observed,
                'actions':sum(r['actions'] for r in rows),'invalid_actions':sum(r['invalid_actions'] for r in rows),
                'valid_surveys':sum(r['valid_surveys'] for r in rows),'missing_surveys':sum(r['missing_surveys'] for r in rows),
                'harvested_units':sum(r['harvested_units'] for r in rows),'contributed_units':sum(r['contributed_units'] for r in rows),
                'final_stock':sum(r['final_stock'] for r in rows),
                'tools':dict(tools)})
        reads=collections.Counter();transfers=collections.Counter();plays=collections.Counter();private=collections.Counter()
        for artifact in state['mixed']['artifacts'].values():
            for read in artifact['reads']:
                reads[(ids[read['agent']],ids[artifact['author']])]+=1
        for event in state['events']:
            src=ids[event['agent']];action=event['decision']['action']
            if 'action_error' not in event['outcome']:
                if action['tool']=='transfer':transfers[(src,ids[action['target']])]+=1
                if action['tool']=='play' and action['target']!='self':plays[(src,ids[action['target']])]+=1
            for recipient in event['outcome'].get('private_recipients',[]):private[(src,ids[recipient])]+=1
        graphs[c['name']]={name:[{'from_model':a,'to_model':b,'count':n} for (a,b),n in counter.items()]
                          for name,counter in [('artifact_reads_reader_to_author',reads),('transfers',transfers),('play_targets',plays),('private_messages',private)]}
    complete=all(c['complete'] for c in cases)
    billed=sum(c['api_returned_request_billed_usd'] for c in cases)
    charged=sum(c['conservative_api_usd'] for c in cases)
    total=manifest['prior_closed_conservative_usd']+charged
    write_json(ROOT/'mixed_analysis.json',{'status':'complete' if complete else 'partial','cases':cases,
        'model_outcomes':model_rows,'agent_outcomes':agent_rows,'directed_activity_by_model':graphs,
        'mixed_api_billed_usd':billed,'mixed_api_conservative_usd':charged,'additional_5_usd_total_conservative_usd':total,
        'remaining_conservative_usd':5-total,'native_cost_usd':None,
        'limitations':['One seed and one eight-member group per condition; exploratory comparison.',
                       'Native and API host settings differ.', 'Missing surveys are not negative recognition.',
                       'Public broadcasts are not converted into pairwise social ties.',
                       'Behavior entropy does not measure thermodynamic entropy or organization quality.']})
    with (ROOT/'model_outcomes.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(model_rows[0]));writer.writeheader()
        writer.writerows({**r,'tools':json.dumps(r['tools'])} for r in model_rows)
    lines=['# 四模型各2成员：混合群体试验','',
        '每组8个agent、50轮、种子7；有/无压力各一组。模型身份不对成员展示，未分配共同目标。','',
        '| 条件 | 最终存活 | 累计存活/可达最优 | 无效动作 | 作品 | 跨作者阅读 |',
        '|---|---:|---:|---:|---:|---:|']
    for c in cases:
        lines.append(f"| {'有压力' if c['pressure'] else '无压力'} | {c['final_alive']}/8 | {c['survivor_rounds']}/400 | {c['invalid_actions']}/{c['actions']} | {c['artifact_count']} | {c['cross_author_reads']} |")
    lines += ['', '| 条件 | 模型（2成员） | 最终存活 | 累计存活/可达最优 | 有效问卷/缺测 |',
              '|---|---|---:|---:|---:|']
    for r in model_rows:
        lines.append(f"| {'有' if r['case'].endswith('p1') else '无'}压力 | {LABELS[r['model']]} | {r['final_alive']}/2 | {r['survivor_rounds']}/100 | {r['valid_surveys']}/{r['missing_surveys']} |")
    lines += ['', '| 条件 | 模型（2成员） | 有效加工次数 | 放入公共池 | 从公共池采集 | 最终个人存量合计 |',
              '|---|---|---:|---:|---:|---:|']
    for r in model_rows:
        lines.append(f"| {'有' if r['case'].endswith('p1') else '无'}压力 | {LABELS[r['model']]} | {r['tools'].get('process',0)} | {r['contributed_units']:.2f} | {r['harvested_units']:.2f} | {r['final_stock']:.2f} |")
    lines += ['', '放入与采集是实际物理通量；不是道德分数，也不是组织质量评分。', '',
              '| 条件 | 加工任务数 | 实际计划工期总和 | 条件最小/最大总和 | 可避免工期 |',
              '|---|---:|---:|---:|---:|']
    for c in cases:
        job=c['conditional_assignment']
        if job:
            lines.append(f"| {'有' if c['pressure'] else '无'}压力 | {job['jobs_started']} | {job['actual_planned_duration']} | {job['sum_conditional_minima']}/{job['sum_conditional_maxima']} | {job['avoidable_duration']} |")
    lines += ['', '数学评价沿用冻结环境的可达边界：有压力下存活上界每轮8人，下界第1–4轮8、第5轮1、第6轮起0。'
              '无压力上下界均为8，没有存活区分力。每种模型2成员的累计可达上界是100人轮，四种模型可同时达到上界。'
              '设备分配极值只在当前负载/加工人数固定且无损坏干扰时评价，不解释为全程最优。', '',
              '问卷的群体识别、共同安排识别、确切成员集合分别保留在mixed_analysis.json；缺测不填0。'
              '公共广播没有自动转成成员间关系边；阅读、明确玩闹对象、转移与私聊分别记录。', '',
              f'本轮外部API返回费用 ${billed:.6f}，保守记账 ${charged:.6f}；新增5美元授权累计 ${total:.6f}，剩余 ${5-total:.6f}。'
              '原生Codex货币使用量未知，单独保存token。', '',
              '同质组与混合组人数结构不同，且每条件只有一个种子，不能据此宣称强模型带动弱模型的因果效应或稳定组织普遍出现。']
    (ROOT/'MIXED_REPORT.md').write_text('\n'.join(lines)+'\n','utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(13,8))
    for c in cases:
        folder=ROOT/c['name'];state=json.loads((folder/'simulation/checkpoint.json').read_text('utf-8'))['state']
        ax=axes[0,0] if c['pressure'] else axes[0,1]
        for index,(model,label) in enumerate(LABELS.items()):
            aids=[i for i,a in state['agents'].items() if a['model']==model]
            ax.plot([s['round'] for s in state['snapshots']],[sum(s['agents'][i]['alive'] for i in aids) for s in state['snapshots']],
                    label=label,marker=['o','s','^','D'][index],markevery=(index*3,12),markersize=4)
        ax.set(title='Mixed group: '+('pressure' if c['pressure'] else 'no pressure'),xlabel='Round',ylabel='Living members per model',ylim=(-.1,2.3));ax.legend(fontsize=8)
        ax=axes[1,0] if c['pressure'] else axes[1,1]
        survey=c['surveys']
        for field,label in [('group_detection','Group self-report'),('arrangement_detection','Arrangement self-report')]:
            ax.plot([s['round'] for s in survey],[s[field].get('identified',0)/s['valid_n'] if s['valid_n'] else float('nan') for s in survey],marker='o',label=label)
        for s in survey:
            if s['valid_n']:ax.annotate(f'n={s["valid_n"]}',(s['round'],s['group_detection'].get('identified',0)/s['valid_n']),xytext=(0,5),textcoords='offset points',fontsize=7)
        ax.set(title='Reports: '+('pressure' if c['pressure'] else 'no pressure'),xlabel='Survey round',ylabel='Identified / valid responses',ylim=(-.1,1.15));ax.legend(fontsize=8)
    for ax in axes.flat:ax.grid(alpha=.15)
    fig.suptitle('Four models, two members each: single-seed exploratory pilot');fig.tight_layout()
    fig.savefig(ROOT/'mixed_curves.png',dpi=180);plt.close(fig)
    old=json.loads(Path('runs/qwen7b_extension_20261009/four_model_comparison.json').read_text('utf-8'))['cases']
    fig,axes=plt.subplots(1,3,figsize=(15,4))
    names=list(LABELS);x=list(range(len(names)))
    homo=[next(c for c in old if c['model']==m and c['pressure']) for m in names]
    mixed=[next(r for r in model_rows if r['model']==m and r['case'].endswith('p1')) for m in names]
    axes[0].bar([i-.18 for i in x],[c['survivor_rounds']/c['best_survivor_rounds_exact'] for c in homo],width=.36,label='Homogeneous: 8 members')
    axes[0].bar([i+.18 for i in x],[r['survivor_rounds']/r['attainable_best_survivor_rounds'] for r in mixed],width=.36,label='Mixed: 2 members/model')
    axes[0].set(title='Pressure: attainment of best person-rounds',ylabel='Observed / attainable maximum',ylim=(0,1.1))
    for pressure,ax in [(True,axes[1]),(False,axes[2])]:
        rows=[next(r for r in model_rows if r['model']==m and r['case'].endswith('p'+str(int(pressure)))) for m in names]
        ax.bar([i-.18 for i in x],[r['contributed_units'] for r in rows],width=.36,label='Contributed')
        ax.bar([i+.18 for i in x],[r['harvested_units'] for r in rows],width=.36,label='Harvested')
        ax.set(title='Actual pool flows: '+('pressure' if pressure else 'no pressure'),ylabel='Units, two members per model')
    for ax in axes:
        ax.set_xticks(x);ax.set_xticklabels([LABELS[m] for m in names],rotation=25,ha='right',fontsize=8)
        ax.legend(fontsize=7);ax.grid(axis='y',alpha=.15)
    fig.suptitle('Descriptive pilot: group composition changed; flows are not moral or organization scores',fontsize=10)
    fig.tight_layout();fig.savefig(ROOT/'mixed_roles.png',dpi=180);plt.close(fig)
    write_json(ROOT/'final_summary.json',{'status':'complete' if complete else 'partial','cases':[
        {k:c[k] for k in ('name','completed_rounds','final_alive','survivor_rounds','invalid_actions','artifact_count','replay_verified')} for c in cases],
        'api_billed_usd':billed,'conservative_api_usd':charged,'additional_5_usd_total_conservative_usd':total,
        'remaining_conservative_usd':5-total,'native_cost_usd':None,'finished':time.time()})
    write_json(ROOT/'analysis_status.json',{'status':'complete' if complete else 'partial','all_replay_verified':all(c['replay_verified'] for c in cases)})
    print(json.dumps({'status':'complete' if complete else 'partial','cases':[(c['name'],c['final_alive'],c['survivor_rounds']) for c in cases]}))

if __name__=='__main__':main()

"""Audited trajectory, attainable survival envelopes and recognition, no API calls."""
import collections
import csv
import json
import math
from pathlib import Path
from sim import Society
import environments
from audit_actions import audit
from analyze_native_mathematics import replay
from native_codex import write_json

ROOT=Path('runs/open_campaign_v1_20261007')


def witness(cfg,kind):
    s=Society(cfg);alive=[]
    for t in range(1,cfg['rounds']+1):
        s.state['round']=t;before=environments.physical_snapshot(s.state)
        for aid,a in s.state['agents'].items():
            if not a['alive']:continue
            action={'tool':'wait'}
            if kind=='balanced' and aid not in s.state['mechanism_state']['jobs']:
                action={'tool':'process','facility':int(aid[1:])%2}
            elif kind=='extinct6' and t==1:action={'tool':'process','facility':0}
            elif kind=='extinct6' and t==2:action={'tool':'contribute','amount':2}
            elif kind=='one5' and t==1 and aid!='a7':action={'tool':'transfer','target':'a7','amount':4}
            s.act(aid,action)
        s.settle(before);alive.append(sum(a['alive'] for a in s.state['agents'].values()))
    return alive


def certificates(cfg):
    w=cfg['world']
    expected={'consumption':1,'initial_personal_stock':4,'facilities':2,'input_cost':1.,'output_per_job':6.,'base_duration':1,'load_delay':1}
    if len(cfg['models'])!=8 or any(w[k]!=v for k,v in expected.items()):raise ValueError('Survival proof parameters changed')
    policies={name:witness(cfg,name) for name in ('balanced','extinct6','one5')}
    if any(n!=8 for n in policies['balanced']):raise ValueError('Upper witness failed')
    if w['survival_pressure']:
        if policies['one5'][4]!=1 or any(policies['extinct6'][5:]):raise ValueError('Lower witness failed')
        lower=[8 if t<5 else 1 if t==5 else 0 for t in range(1,51)]
    else:lower=[8]*50
    return {'lower':lower,'upper':[8]*50,'policy_witnesses':policies,
        'proof':'Energy starts at 5 and can decrease by at most one per step, hence no death before step 5. '
        'At step 1, paid non-transfer activities remove at most 2 stock per actor; transfers conserve personal stock, '
        'and outputs/harvest are nonnegative. At least 16 of the initial 32 personal stock remains before maintenance. '
        'Therefore some actor pays the full 1 at step 1 and cannot die at step 5: lower >=1. '
        'Seven transfers to a7 attain exactly one survivor at step 5. All start facility 0 at step 1 and contribute 2 '
        'at step 2, attaining zero at step 6. Balanced processing attains eight throughout 50 steps. '
        'Without pressure energy never decreases, so both bounds equal eight.',
        'scope':'Exact pointwise survival extrema for this frozen mechanism and initialization; not an organization optimum. '
        'Different lower-bound witnesses at different times must not be combined into an attainable cumulative minimum.'}


def analyze(case):
    folder=ROOT/case['name'];output=folder/'simulation'
    cfg=json.loads((folder/'config.json').read_text('utf-8'))
    saved=json.loads((output/'checkpoint.json').read_text('utf-8'))['state']
    checked=audit(output);write_json(folder/'action_audit.json',checked)
    events=saved['events'];valid=[e for e in events if 'action_error' not in e['outcome']]
    tools=collections.Counter(e['decision']['action']['tool'] for e in valid)
    bounds=certificates(cfg);series=[];surveys=[]
    for snapshot in saved['snapshots']:
        t=snapshot['round'];n=sum(a['alive'] for a in snapshot['agents'].values());low,high=bounds['lower'][t-1],8
        if not low<=n<=high:raise ValueError('Observed trajectory outside certified bounds')
        recent=[e['decision']['action']['tool'] for e in valid if t-5<e['round']<=t]
        counts=collections.Counter(recent)
        h=-sum((c/len(recent))*math.log2(c/len(recent)) for c in counts.values()) if recent else None
        series.append({'round':t,'alive':n,'survival_min_exact':low,'survival_max_exact':high,
            'survival_position':(n-low)/(high-low) if high!=low else None,'survival_regret':high-n,'tool_entropy_5round_bits':h})
    for t in cfg['survey_rounds']:
        answers=[x for x in saved['surveys'] if x['round']==t]
        missing=[x for x in saved.get('survey_failures',[]) if x['round']==t]
        group=collections.Counter(x['effective_responses']['group_detection'] for x in answers)
        arrangements=collections.Counter(x['effective_responses']['arrangement_detection'] for x in answers)
        sets=collections.defaultdict(set);edges=set();multi_reporters=set()
        for answer in answers:
            for obj in answer['effective_responses']['groups']:
                ids=tuple(sorted(obj['member_ids']))
                if answer['agent'] in ids:
                    sets[ids].add(answer['agent'])
                    if len(ids)>=2:
                        multi_reporters.add(answer['agent'])
                        edges.update((answer['agent'],other) for other in ids if other!=answer['agent'])
        candidates=[{'member_ids':list(ids),'self_member_reporters':sorted(reporters),
            'self_member_report_fraction':len(reporters)/len(ids),
            'interpretation':'Exact agreement on claimed member IDs; descriptions, identity strength and interaction evidence still need review.'}
            for ids,reporters in sets.items()]
        surveys.append({'round':t,'valid_n':len(answers),'missing_n':len(missing),
            'group_detection':dict(group),'arrangement_detection':dict(arrangements),'candidate_member_sets':candidates,
            'self_reporters_of_multi_member_groups':sorted(multi_reporters),
            'recognition_member_edges':[list(x) for x in sorted(edges)],
            'recognition_edge_reciprocity':sum((b,a) in edges for a,b in edges)/len(edges) if edges else None,
            'objects':[{'agent':a['agent'],'groups':a['effective_responses']['groups'],
                'arrangements':a['effective_responses']['arrangements'],'flags':a['quality_flags']} for a in answers]})
    jobs=None
    if not any(tools[x] for x in ('damage','maintain','interfere')):
        r=replay(cfg,saved);batches=r['batches'];actual=sum(b['planned_delay_actual'] for b in batches)
        low=sum(b['planned_delay_min_exact'] for b in batches);high=sum(b['planned_delay_max_exact'] for b in batches)
        jobs={'jobs_started':sum(b['jobs_started'] for b in batches),'actual_planned_duration':actual,
            'sum_conditional_minima':low,'sum_conditional_maxima':high,'avoidable_duration':actual-low,
            'conditional_position':(high-actual)/(high-low) if high!=low else None,
            'batches':batches,'minimum_pending_wait_margin':min((s['minimum_pending_job_wait_margin'] for s in r['states']
                if s['minimum_pending_job_wait_margin'] is not None),default=None) if w_pressure(cfg) else None,
            'scope':'Exact one-step assignment extrema holding current loads and launchers fixed, with health=1 and no interference. '
                'Summed conditional minima are not a single jointly feasible optimal trajectory. Waiting margin assumes no future interference or aid.'}
    calls=[]
    for line in (output/'calls.jsonl').read_text('utf-8').splitlines():
        try:calls.append(json.loads(line))
        except json.JSONDecodeError:continue
    external=sum(float(c.get('usage',{}).get('cost') or 0) for c in calls) if case['backend']!='codex_native_cli' else 0
    accounting=json.loads((output/'api_accounting.json').read_text('utf-8'))
    artifacts=saved['mixed']['artifacts'];cultural={'read_news','create','read_artifact','play'}
    result={'name':case['name'],'model':case['model'],'pressure':cfg['world']['survival_pressure'],
        'complete':(output/'result.json').exists(),'completed_rounds':saved['round'],'final_alive':series[-1]['alive'],
        'survivor_rounds':sum(x['alive'] for x in series),'best_survivor_rounds_exact':8*saved['round'],
        'survivor_rounds_regret_to_best':8*saved['round']-sum(x['alive'] for x in series),
        'first_extinction_round':next((x['round'] for x in series if x['alive']==0),None),
        'actions':len(events),'valid_actions':len(valid),'invalid_actions':checked['state_constraint_rejections']+checked['schema_or_range_rejections'],
        'schema_rejections':checked['schema_or_range_rejections'],'tools':dict(tools),
        'cultural_activity_share_valid':sum(tools[k] for k in cultural)/len(valid) if valid else None,
        'artifact_count':len(artifacts),'available_artifact_count':sum(a['available'] for a in artifacts.values()),
        'artifact_reads':sum(len(a['reads']) for a in artifacts.values()),
        'cross_author_reads':sum(read['agent']!=a['author'] for a in artifacts.values() for read in a['reads']),
        'communication':dict(collections.Counter(e['decision']['communication']['op'] for e in events if 'communication_error' not in e['outcome'])),
        'survival_certificates':bounds,'round_series':series,'conditional_assignment':jobs,'surveys':surveys,
        'survey_failures':saved.get('survey_failures',[]),'api_returned_request_billed_usd':external,
        'conservative_api_usd':accounting['cost_usd'],'native_usage':accounting.get('reported_usage'),
        'replay_verified':checked['verified_replay']}
    write_json(folder/'mathematical_analysis.json',result)
    with (folder/'mathematical_round_series.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(series[0]));writer.writeheader();writer.writerows(series)
    return result


def w_pressure(cfg):return cfg['world']['survival_pressure']


def main():
    manifest=json.loads((ROOT/'manifest.json').read_text('utf-8'));results=[analyze(c) for c in manifest['runs']]
    write_json(ROOT/'comparison_analysis.json',{'cases':results,'single_seed':7,
        'billed_external_usd':sum(r['api_returned_request_billed_usd'] for r in results),
        'conservative_external_usd':sum(r['conservative_api_usd'] for r in results),
        'limitations':['One seed per condition; no variance or size-causality claim.',
            'Native host context differs from OpenRouter.', 'Questionnaire failures are missing, not negative recognition.',
            'No pressure makes survival a flat, uninformative metric.','Behavior entropy has no default favorable direction.']})
    header='| 模型/压力 | 完成轮数 | 存活 | 存活人轮 / 可达最佳 | 无效动作 | 作品 | 文化活动占有效动作 | 最后调查群体/安排识别 |\n|---|---:|---:|---:|---:|---:|---:|---|'
    lines=['# 开放混合环境比较：种子 7','',header]
    for r in results:
        latest=next((x for x in reversed(r['surveys']) if x['valid_n']),None)
        recognition=f"t={latest['round']}: {latest['group_detection'].get('identified',0)}/{latest['valid_n']}，{latest['arrangement_detection'].get('identified',0)}/{latest['valid_n']}" if latest else '无有效调查'
        lines.append(f"| {r['name']} | {r['completed_rounds']} | {r['final_alive']}/8 | {r['survivor_rounds']}/{r['best_survivor_rounds_exact']} | {r['invalid_actions']}/{r['actions']} | {r['artifact_count']} | {r['cultural_activity_share_valid']:.1%} | {recognition} |")
    indexed={r['name']:r for r in results}
    native=indexed['native_gpt61_p1'];base=indexed['gptoss20b_p1'];free=indexed['native_gpt61_p0'];final=free['surveys'][-1]
    delta=native['survivor_rounds']-base['survivor_rounds']
    lines+=['','## 主要发现','',
        f"1. 有压力时，原生 Codex 达到可达最佳 {native['survivor_rounds']}/400 人轮，相对 GPT-OSS 的 {base['survivor_rounds']} 人轮增加 {delta}（{delta/base['survivor_rounds']:.1%}）。两种 API 模型没有启动加工，分别在第 15、16 轮全灭；这属于策略与底层生存机制的差异，不能据此推出模型规模的因果效应。",
        f"2. 原生 Codex 无压力条件留下 {free['artifact_count']} 件作品，有 {free['cross_author_reads']} 次跨作者读取，文化活动占有效活动 {free['cultural_activity_share_valid']:.2%}。第 20、30、40、50 轮各有 8/8 成员报告互动群体；第 50 轮 7 人给出相同的八人成员集合，一人报告三人子群体。最终成员提及关系的双向比例为 {final['recognition_edge_reciprocity']:.2%}，但 8/8 都没有报告共同安排。结果更符合文化互动与群体互认的出现，尚未构成稳定制度组织的证据。",
        f"3. 原生 Codex 有压力条件也产生 {native['artifact_count']} 件作品、{native['cross_author_reads']} 次跨作者读取，但最后 0/8 报告群体或共同安排。因此，同一模型下的生存与活动并不自动对应群体认可；压力作用方向还需多种子验证。",
        '4. 3B 无压力条件有 45 件作品，但共 48 个计划调查中有 9 份缺测。最终有效问卷 4 份，3 份报告群体，其中两份只有本人，另一份报告两人集合而对方未给出一致集合。不能把 3/4 原始检测率解读为 75% 成员互认。',
        '5. 六个条件都没有有效的干扰、损坏或修复动作，也没有私聊或资源转移。开放工具已经可用，但本次没有出现这些行为；不能据此声称敌对演化、制度修复或小圈子机制已得到检验。']
    lines+=['','API 返回请求费用合计 $'+f"{sum(r['api_returned_request_billed_usd'] for r in results):.6f}"+'；包括失败请求预留的保守记账 $'+f"{sum(r['conservative_api_usd'] for r in results):.6f}"+'。原生 Codex 的货币使用量未知，单独保存 token。',
        '', '## 数学位置与解释', '',
        '此初始化下，有压力时最优存活上界每轮均为 8；最差下界在第 1–4 轮为 8，第 5 轮为 1，第 6 轮起为 0。边界均有机械策略见证，并在代码中回放验证。位置为 (实际−最差)/(最优−最差)，平坦区间不定义。最佳累计存活人轮为 400；逐轮最差见证不同，不能把最差下界相加当成可达的累计最差。',
        '', '无压力下能量不会因该环境任何合法动作下降，存活上下界均为 8。三个模型存活都为 8 不能说明社会发展一样好；需要分别比较对象产生与消费、互动和成员认可。',
        '', '设备分配条件极值固定当时既有负载和新加工者数量，枚举两台设备分配。只有没有损坏、修复、干扰时才调用此版本计算；累计条件最小值不是全程可达最优。没有加工时位置不定义，不能把其看作完美效率。',
        '', '问卷的群体识别与安排识别分别报告。对相同成员集合的自成员报告另作匹配，不把一人提及所有成员或公共广播解释为互认，也不把被命名的群体直接称为稳定社会组织。',
        '', '## 数据限制', '',
        '每个条件只有种子 7。本次结果不能推出模型参数规模的因果效应或稳定普遍规律。原生宿主上下文、温度和输出上限与 API 不完全一致。3B 问卷存在验证失败；缺测及同输入重试有选择性，必须连同原始回答报告。更换机制后相对旧环境的比较也是探索性的。',
        '', '后续优先固定本版环境增加种子，并对“识别出的群体”的亲历证据、成员集合和实际执行进行审计；随后分别消融文化活动、公共池与私聊能力。新增收费实验不在本脚本中启动。']
    (ROOT/'COMPARISON_REPORT.md').write_text('\n'.join(lines)+'\n','utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(15,4))
    labels={'ministral3b':'Ministral 3B','gptoss20b':'GPT OSS 20B','native_gpt61':'Native GPT 6.1'}
    for r in results:
        if not r['pressure']:continue
        label=labels[r['name'].rsplit('_p',1)[0]]
        axes[0].plot([x['round'] for x in r['round_series']],[x['alive'] for x in r['round_series']],label=label)
    axes[0].set(title='Survival under pressure',xlabel='Round',ylabel='Living members',ylim=(-.2,8.5));axes[0].legend(fontsize=8)
    for pressure,ax in [(True,axes[1]),(False,axes[2])]:
        for r in results:
            if r['pressure']!=pressure:continue
            rows=[s for s in r['surveys'] if s['valid_n']]
            ax.plot([s['round'] for s in rows],[s['group_detection'].get('identified',0)/s['valid_n'] for s in rows],marker='o',label=labels[r['name'].rsplit('_p',1)[0]])
        ax.set(title='Group reports: '+('pressure' if pressure else 'no pressure'),xlabel='Survey round',ylabel='Identified / valid answers',ylim=(-.05,1.05));ax.legend(fontsize=8)
    axes[2].annotate('3B: n=4/8 at rounds 40, 50',xy=(40,.75),xytext=(21,.53),fontsize=8,
        arrowprops={'arrowstyle':'->','color':'gray'})
    fig.tight_layout();fig.savefig(ROOT/'comparison.png',dpi=180);plt.close(fig)
    print(json.dumps([{'case':r['name'],'complete':r['complete'],'rounds':r['completed_rounds'],'alive':r['final_alive'],'survivor_rounds':r['survivor_rounds'],'artifacts':r['artifact_count'],'missing':len(r['survey_failures'])} for r in results]))


if __name__=='__main__':main()

"""Audited four-model comparison; can also report explicitly partial trajectories."""
import argparse
import csv
import json
import time
from pathlib import Path
import analyze_open_campaign as analysis
from native_codex import write_json

ROOT = Path('runs/qwen7b_extension_20261009')
OLD = Path('runs/open_campaign_v1_20261007')
LABELS = {'ministral3b':'Ministral 3B', 'qwen25_7b':'Qwen2.5 7B',
          'gptoss20b':'GPT-OSS 20B', 'native_gpt61':'Native GPT-6.1'}
COLORS = {'ministral3b':'#C58045', 'qwen25_7b':'#198B72', 'gptoss20b':'#6078AA', 'native_gpt61':'#663F82'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wait', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT/'manifest.json').read_text('utf-8'))
    while args.wait:
        if all((ROOT/c['name']/'simulation/result.json').exists() for c in manifest['runs']):
            break
        status = json.loads((ROOT/'campaign_status.json').read_text('utf-8'))
        if any(r.get('status')=='failed' for r in status.get('runs',{}).values()):
            write_json(ROOT/'analysis_status.json', {'status':'blocked_by_run_failure', 'runs':status['runs']})
            return
        time.sleep(10)
    old = json.loads((OLD/'comparison_analysis.json').read_text('utf-8'))
    analysis.ROOT = ROOT
    added = [analysis.analyze(c) for c in manifest['runs']
             if (ROOT/c['name']/'simulation/checkpoint.json').exists()
             and json.loads((ROOT/c['name']/'simulation/checkpoint.json').read_text('utf-8'))['state']['round']]
    cases = old['cases'] + added
    complete = len(added)==2 and all(c['complete'] for c in added)
    billed = sum(c['api_returned_request_billed_usd'] for c in cases)
    cost = sum(c['conservative_api_usd'] for c in cases)
    limitations = old.get('limitations',[]) + ['Qwen2.5 is a different model family/version, not a pure parameter-count intervention.']
    write_json(ROOT/'four_model_comparison.json', {'status':'complete' if complete else 'partial', 'cases':cases,
               'billed_external_usd':billed, 'conservative_external_usd':cost,
               'additional_authorized_cap_usd':5, 'remaining_conservative_usd':5-cost,
               'native_cost_usd':None, 'limitations':limitations})
    rows=[]
    for c in cases:
        final = next((s for s in reversed(c['surveys']) if s['valid_n']),None)
        rows.append({'case':c['name'], 'rounds':c['completed_rounds'], 'complete':c['complete'],
            'alive':c['final_alive'], 'survivor_rounds':c['survivor_rounds'],
            'attainable_best_survivor_rounds':c['best_survivor_rounds_exact'],
            'regret_to_best':c['survivor_rounds_regret_to_best'], 'extinction_round':c['first_extinction_round'],
            'invalid_actions':c['invalid_actions'], 'total_actions':c['actions'],
            'artifacts':c['artifact_count'], 'cross_author_reads':c['cross_author_reads'],
            'last_valid_survey_round':final['round'] if final else None,
            'valid_last_survey_n':final['valid_n'] if final else 0,
            'group_reports':final['group_detection'].get('identified',0) if final else 0,
            'arrangement_reports':final['arrangement_detection'].get('identified',0) if final else 0,
            'survey_missing':len(c['survey_failures']), 'api_billed_usd':c['api_returned_request_billed_usd'],
            'replay_verified':c['replay_verified']})
    with (ROOT/'four_model_summary.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['# 四模型同质群体对照', '', '状态：'+('两组新增实验均已完成' if complete else '部分结果，仍在运行'), '',
        '每组8个agent、50轮、种子7；Qwen沿用已完成三模型实验的冻结环境与问卷。', '',
        '| 模型／压力 | 完成轮数 | 存活 | 累计存活人轮／可达最优 | 无效动作／总动作 | 作品 | 跨作者阅读 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for c in cases:
        label=LABELS[c['name'].rsplit('_p',1)[0]]
        lines.append(f"| {label}／{'有' if c['pressure'] else '无'} | {c['completed_rounds']} | {c['final_alive']}/8 | "
                     f"{c['survivor_rounds']}/{c['best_survivor_rounds_exact']} | {c['invalid_actions']}/{c['actions']} | "
                     f"{c['artifact_count']} | {c['cross_author_reads']} |")
    lines += ['', '数学评价：有压力时，存活逐轮精确下界为第1–4轮8人、第5轮1人、第6轮起0人，上界始终8人。'
              '位置为(实际−下界)/(上界−下界)，上下界相等时不定义；50轮累计可达最优为400人轮。'
              '各轮最差轨迹可能不同，不能相加得到累计最差。无压力时存活上下界均为8，存活曲线没有区分力。', '',
              '行为熵为最近5轮有效工具动作的Shannon熵，不是物理熵，也不默认越高或越低越好。'
              '问卷群体识别与共同安排识别分别报告；缺测不填0，死亡agent不继续调查。', '',
              '设备分配的最优／最差位置仅适用于固定当轮负载、加工人数、无损坏干扰条件；不是全程最优策略。', '',
              f'新增Qwen返回费用：${sum(c["api_returned_request_billed_usd"] for c in added):.6f}；'
              f'新增5美元授权下，累计保守计费：${cost:.6f}，剩余：${5-cost:.6f}。原生Codex货币使用量未知、另记。', '',
              '本轮每条件只有一个种子，不足以证明模型规模的因果作用，也不能直接回答稳定社会组织是否普遍出现。', '',
              '后续四模型×每模型2个agent的混合配置位于 ../four_model_mix_20261009，已通过离线路由验证，尚未启动。']
    qwen_pressure = next((c for c in added if c['pressure']), None)
    if qwen_pressure and qwen_pressure['complete']:
        state=json.loads((ROOT/qwen_pressure['name']/'simulation/checkpoint.json').read_text('utf-8'))['state']
        first=[e for e in state['events'] if e['round']==1]
        harvested=sum(e['outcome'].get('action',{}).get('harvested',0) for e in first)
        lines += ['', 'Qwen有压力组的具体机制：第1轮8人各采集2单位，共提取16单位；'
                  '共享池由16降至结算后的0.8（本轮自然增长0.8）。此后持续选择采集，没有加工或贡献。'
                  '第1轮广播却反复表达“采集以增加共享池”，第10轮部分群体描述也延续了这个说法。'
                  '这是动作方向与语言解释不一致的直接样例，不能用广播一致或问卷识别替代物理轨迹评价。']
        assert abs(harvested-16)<1e-8
        write_json(ROOT/'qwen_pressure_mechanism.json',{'first_round_harvested':harvested,
                   'pool_initial':16, 'first_round_growth':.8, 'pool_after_round_1':.8,
                   'note':'Growth is based on start-of-round pool; extraction is not contribution.',
                   'first_round_broadcasts':[{'agent':e['agent'],'communication':e['decision']['communication']} for e in first]})
    for c in added:
        absent=[s['round'] for s in c['surveys'] if s['valid_n']==0 and s['missing_n']>0]
        if absent:
            lines += ['', f"{c['name']} 在调查轮次 {absent} 没有有效问卷。原始回答存在对象检测与对象列表不一致等校验问题；"
                      '这些轮次的认同度不可估计，不解释为0。原始回答和失败原因保留在调用日志与survey_failures中。']
    (ROOT/'FOUR_MODEL_REPORT.md').write_text('\n'.join(lines)+'\n','utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(13,8))
    for c in cases:
        key=c['name'].rsplit('_p',1)[0];color=COLORS[key];label=LABELS[key]
        series=c['round_series']
        if c['pressure']:
            axes[0,0].plot([s['round'] for s in series],[s['alive'] for s in series],label=label,color=color,lw=2)
        else:
            axes[0,1].plot([s['round'] for s in series],[s['tool_entropy_5round_bits'] for s in series],label=label,color=color)
        survey=c['surveys']
        ax=axes[1,0] if c['pressure'] else axes[1,1]
        ax.plot([s['round'] for s in survey], [s['group_detection'].get('identified',0)/s['valid_n'] if s['valid_n'] else float('nan') for s in survey],
                marker='o',color=color,label=label)
        if key=='qwen25_7b':
            for s in survey:
                if s['valid_n']:
                    ax.annotate(f'n={s["valid_n"]}',(s['round'],s['group_detection'].get('identified',0)/s['valid_n']),
                                xytext=(0,5),textcoords='offset points',fontsize=7,color=color)
                elif s['missing_n']:
                    ax.scatter([s['round']],[-.075],marker='x',color=color)
                    ax.annotate('missing', (s['round'],-.075),xytext=(0,5),textcoords='offset points',fontsize=7,color=color)
    axes[0,0].plot(range(1,51),[8]*50,'--',color='gray',lw=1,label='Exact attainable maximum')
    axes[0,0].plot(range(1,51),[8]*4+[1]+[0]*45,':',color='gray',lw=1,label='Exact pointwise minimum')
    axes[0,0].set(title='Living members: pressure',xlabel='Round',ylabel='Living members',ylim=(-.3,8.8))
    axes[0,1].set(title='Tool entropy: no pressure',xlabel='Round',ylabel='5-round Shannon entropy (bits)')
    for ax,title in [(axes[1,0],'Group reports: pressure'),(axes[1,1],'Group reports: no pressure')]:
        ax.set(title=title,xlabel='Survey round',ylabel='Identified / valid responses',ylim=(-.1,1.15))
    for ax in axes.flat:
        ax.legend(fontsize=7);ax.grid(alpha=.15)
    fig.suptitle('Four-model pilot: single seed; recognition reports do not establish organization',fontsize=11)
    fig.tight_layout();fig.savefig(ROOT/'four_model_curves.png',dpi=180);plt.close(fig)
    write_json(ROOT/'analysis_status.json', {'status':'complete' if complete else 'partial','updated':time.time(),
               'replay_verified':all(c['replay_verified'] for c in added), 'new_cases':rows[-len(added):] if added else []})
    print(json.dumps({'status':'complete' if complete else 'partial','new_results':rows[-len(added):], 'conservative_total_usd':cost}))

if __name__ == '__main__':
    main()

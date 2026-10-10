"""Compare independent external proxy and original self-reports, never merge scores."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import survey_measurement as measurement
from native_codex import write_json

ROOT=Path('runs/four_model_mix_20261009');OUT=ROOT/'proxy_low_v1'

def main():
    result=json.loads((OUT/'result.json').read_text('utf-8'));inputs=json.loads((OUT/'inputs.json').read_text('utf-8'))
    lookup={(x['source_run'],x['round'],x['agent']):x['request'] for x in inputs}
    original={}
    for case in ('mixed4_p1','mixed4_p0'):
        state=json.loads((ROOT/case/'simulation/checkpoint.json').read_text('utf-8'))['state']
        original.update({(case,x['round'],x['agent']):x for x in state['surveys']})
    grouped=defaultdict(list);pairs=[];items=[];flags=Counter()
    for answer in result['surveys']:
        key=(answer['source_run'],answer['round'],answer['agent']);request=lookup[key]
        # Apply syntax and evidence-reference checks again independently of transport.
        measurement.validate(answer['responses'],request)
        grouped[key[:2]].append(answer)
        old=original.get(key)
        pairs.append({'case':key[0],'round':key[1],'agent':key[2],
            **{'self_'+d:old['responses'][d] if old else 'missing' for d in ('group_detection','arrangement_detection')},
            **{'proxy_'+d:answer['responses'][d] for d in ('group_detection','arrangement_detection')},
            **answer['assessment']})
        for field,module in [('groups','identity'),('arrangements','arrangement')]:
            for index,obj in enumerate(answer['effective_responses'][field]):
                for code,text,dimension,_ in measurement.ITEMS[module]:
                    items.append({'case':key[0],'round':key[1],'agent':key[2],'object_type':field,
                        'object_index':index,'description':obj['description'],'member_ids':';'.join(obj['member_ids']),
                        'evidence_refs':';'.join(obj['evidence_refs']),'item':code,'question':text,'dimension':dimension,
                        'proxy_score':obj['scores'][code],'interpretation':'external_evidence_proxy_not_member_self_report'})
        items.append({'case':key[0],'round':key[1],'agent':key[2],'object_type':'recent_experience',
            'item':'S01','proxy_score':answer['responses']['surprise'],'interpretation':'external_evidence_proxy_not_member_self_report'})
        flags.update(k for k in ('mechanical_rule_confusion','accounting_misstatement') if answer['assessment'][k])
    rows=[]
    for (case,t),answers in sorted(grouped.items()):
        olds=[x for (c,r,a),x in original.items() if (c,r)==(case,t)]
        members=Counter(tuple(sorted(g['member_ids'])) for x in answers for g in x['responses']['groups'])
        rows.append({'case':case,'round':t,'eligible':sum(x['source_run']==case and x['round']==t for x in inputs),
            'proxy_completed':len(answers),'self_valid':len(olds),
            'proxy_respondent_in_detected_group':sum(any(x['agent'] in g['member_ids'] for g in x['responses']['groups']) for x in answers),
            **{f'{label}_{field}_{status}':sum(x['responses'][field+'_detection']==status for x in data)
                for label,data in [('proxy',answers),('self',olds)] for field in ('group','arrangement') for status in ('identified','none','unknown')},
            'largest_proxy_same_boundary_reports':max(members.values(),default=0)})
    for filename,data in [('comparison.csv',pairs),('items.csv',items),('time_summary.csv',rows)]:
        columns=list(dict.fromkeys(k for row in data for k in row))
        with (OUT/filename).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(data)
    joint={field:dict(Counter(r['self_'+field]+' -> '+r['proxy_'+field] for r in pairs)) for field in ('group_detection','arrangement_detection')}
    numeric=sum(type(x['proxy_score']) is int for x in items)
    summary={'status':result['status'],'completed':len(pairs),'targets':len(inputs),'time_series':rows,
        'detection_transitions':joint,'content_issue_flags':dict(flags),'proxy_item_numeric':numeric,
        'proxy_item_missing':dict(Counter(str(x['proxy_score']) for x in items if type(x['proxy_score']) is not int)),
        'note':'None means not identified in this personal evidence window, not proof of absolute absence. Multiple views rated by the same evaluator are not independent member endorsements. Semantic comparison changes both evaluator and observer instructions; not a pure model effect.'}
    write_json(OUT/'summary.json',summary)
    fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True)
    for i,case in enumerate(('mixed4_p1','mixed4_p0')):
        data=[r for r in rows if r['case']==case]
        for j,field in enumerate(('group','arrangement')):
            ax=axes[i,j]
            for label,style in [('self','--'),('proxy','-')]:
                ax.plot([r['round'] for r in data],[r[f'{label}_{field}_identified'] for r in data],style,marker='o',label=label)
            ax.set_title(case+' / '+field);ax.set_ylim(-.2,8.5);ax.grid(alpha=.2);ax.legend()
    for ax in axes[-1]:ax.set_xlabel('Round')
    for ax in axes[:,0]:ax.set_ylabel('Reports identifying an object')
    fig.suptitle('Self-report vs external evidence proxy (counts; missing self-report retained)');fig.tight_layout();fig.savefig(OUT/'survey_comparison.png',dpi=180);plt.close(fig)
    lines=['# 原生GPT low外部代理问卷','',f"状态：{result['status']}；完成 {len(pairs)}/{len(inputs)}。原自填保留，失败记录不删除，逐份输入与证据引用可追溯。",'',
        '| 条件 | 时间 | 应评/代理完成 | 自填有效 | 自填群体/约定 | 代理群体/约定 | 被评者在群体内 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:lines.append(f"| {r['case']} | {r['round']} | {r['eligible']}/{r['proxy_completed']} | {r['self_valid']} | {r['self_group_identified']}/{r['self_arrangement_identified']} | {r['proxy_group_identified']}/{r['proxy_arrangement_identified']} | {r['proxy_respondent_in_detected_group']} |")
    lines += ['','输入仅为该成员当时可见的信息，不含未来、原自填答案或模型身份。统一提供真实设备物理规则作为事实校核；保留当时记忆摘要，无法恢复因压缩已丢失的互动事实。', '',
        '代理回答不是成员认可的实测值。识别不到只说明当前可见证据不足，不能证明不存在。不同成员视角由同一个评估模型评价，也不是多名成员独立认可。', '',
        '主观身份重要性、义务、延续意向、惊讶只有明确表达或相关承诺证据才可估分，否则unknown；无对象时不强行填数。尚未验证该改写问卷对LLM的效度。本轮同时变更评估者与外部证据约束，不能将差异全部归因于模型强弱。', '',
        f"输入内容问题标记：{dict(flags)}。标记来自评估模型，需结合原始证据核查，不能作为自动真值。", '',
        f"输出题目行的数字/未知/不适用：{numeric} / {summary['proxy_item_missing']}。对象数不同导致题目行不同，不能把行数当人数或独立样本。", '',
        '文件：comparison.csv逐成员对照与评估理由；items.csv逐题代理评分；time_summary.csv时间汇总；result.json完整代理对象、边界和引用；inputs.json完整时间局部输入；native_requests保存原生调用轨迹。外部API花费为0；原生使用量见api_accounting.json，货币成本未知。']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'completed':len(pairs),'status':result['status'],'latest':[r for r in rows if r['round']==50]},ensure_ascii=False))

if __name__=='__main__':main()

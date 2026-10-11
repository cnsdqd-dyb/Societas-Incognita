"""Offline, reproducible core-metric tables and figures; no model calls.

python analyze_core_metrics.py --checkpoint PATH --config PATH --output DIR
Reproduce a published analysis using its trajectory.json and config.json.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from core_metrics import DIMENSIONS, measure


def write_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8'))


def analyze(checkpoint, config, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    raw, raw_cfg = checkpoint.read_bytes(), config.read_bytes()
    loaded, cfg = json.loads(raw), json.loads(raw_cfg)
    state = loaded.get('state', loaded)
    output.mkdir(parents=True, exist_ok=True)
    # Export the actual observations needed for analysis, without backend routes,
    # credentials, calls or machine-specific runner configuration.
    export = {k: state[k] for k in ['round', 'snapshots', 'culture', 'social_content',
                                  'communication_events'] if k in state}
    export['agents'] = {i: {'alive': a['alive']} for i, a in state['agents'].items()}
    export['events'] = [{k: e[k] for k in ['round', 'agent', 'decision', 'outcome'] if k in e}
                        for e in state['events']]
    export['mini_world'] = {'discoveries': state['mini_world'].get('discoveries', {})}
    clean_cfg = {k: cfg[k] for k in ['models', 'rounds', 'seed', 'tools', 'world',
                                    'world_rule_visibility', 'recipe_visibility', 'communication'] if k in cfg}
    report = measure(export, clean_cfg)
    report['provenance'] = {
        'input_checkpoint_sha256': hashlib.sha256(raw).hexdigest(),
        'input_config_sha256': hashlib.sha256(raw_cfg).hexdigest(),
        'world_definition_sha256': state['snapshots'][0]['mini_world_metrics'].get('definition_sha256'),
        'analysis_code_sha256': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                 for name in ['core_metrics.py', 'analyze_core_metrics.py']},
        'analysis_inputs': 'trajectory.json and config.json; filtered observations, not a simulator checkpoint',
        'questionnaires_used': False, 'new_model_calls': 0,
        'population': len(export['agents']), 'rounds': export['round'],
        'scope': 'Single Luna low no-pressure run; no causal model-size claim',
    }
    write_json(output/'trajectory.json', export)
    write_json(output/'config.json', clean_cfg)
    write_json(output/'metrics.json', report)
    names = [n for group in DIMENSIONS.values() for n in group]
    with (output/'metrics.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['round', 'window_start', 'metric', 'value', 'status', 'numerator', 'denominator'])
        for row in report['round_series']:
            for name in names:
                p = row['metrics'][name]
                writer.writerow([row['round'], row['window_start'], name, p['value'], p['status'], p['numerator'], p['denominator']])
    colors = ['#0072B2', '#D55E00', '#009E73', '#CC79A7']
    plt.rcParams.update({'font.size': 14, 'axes.spines.top': False, 'axes.spines.right': False,
                         'savefig.dpi': 300, 'pdf.fonttype': 42})
    times = [r['round'] for r in report['round_series']]
    fig, axes = plt.subplots(3, 4, figsize=(14, 8), layout='constrained')
    labels = ['Active fraction', 'Ecological path retention', 'Verified rule coverage',
              'Knowledge adoption', 'Cooperation fulfillment', 'Resource turnover',
              'Harmful action rate', 'Damage recovery', 'New cultural objects',
              'Cross-member reuse', 'Behavioral divergence (JSD)', 'Expression divergence']
    # Explicit ordering keeps the paired measures adjacent where possible.
    ordered = ['active_fraction', 'ecological_path_retention', 'verified_rule_coverage',
               'knowledge_adoption_coverage', 'sustained_cooperation_fulfillment', 'resource_turnover',
               'harmful_action_rate', 'damage_recovery_rate', 'cultural_production_count',
               'cross_member_reuse_count', 'behavioral_divergence', 'expression_divergence']
    for ax, name, label in zip(axes.flat, ordered, labels):
        values = [r['metrics'][name]['value'] for r in report['round_series']]
        ax.set(xlabel='Round', ylabel=label, xlim=(1, max(times)))
        ax.grid(alpha=.16)
        if any(v is not None for v in values):
            ax.plot(times, [v if v is not None else float('nan') for v in values], color=colors[0], lw=1.6)
            upper = max(1., max(v for v in values if v is not None))
            ax.set_ylim(-.05 * upper, 1.05 * upper)
        else:
            text = 'Not applicable\n(no damage episodes)' if name == 'damage_recovery_rate' else 'Missing evidence\n(not scored as zero)'
            ax.text(.5, .5, text, ha='center', va='center', transform=ax.transAxes, color='#666666')
            ax.set_yticks([])
    for ext in ['png', 'pdf']:
        fig.savefig(output/f'core_metrics.{ext}', bbox_inches='tight')
    plt.close(fig)
    discoveries = [e for records in export['mini_world']['discoveries'].values() for e in records]
    valid = [e for e in export['events'] if 'action_error' not in e.get('outcome', {})]
    action_counts = Counter(e['decision']['action']['tool'] for e in valid)
    numeric = [r['metrics']['behavioral_divergence']['value'] for r in report['round_series']
               if r['metrics']['behavioral_divergence']['value'] is not None]
    aux = []
    for snapshot, row in zip(sorted(export['snapshots'], key=lambda x: x['round']), report['round_series']):
        t = row['round']; w = [e for e in valid if row['window_start'] <= e['round'] <= t]
        messages = [e for e in export.get('communication_events', []) if row['window_start'] <= e['round'] <= t
                    and e.get('communication', {}).get('text') and not e.get('outcome', {}).get('communication_error')]
        aux.append({'round': t, 'stocks': {i: a['stock'] for i, a in snapshot['agents'].items()},
                    'direct_material_types': snapshot['mini_world_metrics'].get('material_types_directly_learned', {}),
                    'completed_experiments': sum(e['round'] <= t for e in discoveries),
                    'productive_experiments': sum(e['round'] <= t and bool(e.get('produced')) for e in discoveries),
                    'action_counts': dict(Counter(e['decision']['action']['tool'] for e in w)),
                    'message_count': len(messages),
                    'message_characters': sum(len(e['communication']['text']) for e in messages),
                    'pools': snapshot['mini_world_physics']['pools']})
    write_json(output/'dynamics.json', aux)
    fig, axs = plt.subplots(2, 3, figsize=(12, 7), layout='constrained')
    for index, i in enumerate(sorted(export['agents'])):
        axs[0, 0].plot(times, [a['stocks'][i] for a in aux], label=i, color=colors[index])
        axs[0, 1].plot(times, [a['direct_material_types'].get(i, 0) for a in aux], label=i, color=colors[index])
    axs[0, 0].set_ylabel('Liquid energy\nby member'); axs[0, 0].legend(frameon=False)
    axs[0, 1].set_ylabel('Material types with\ndisclosed properties'); axs[0, 1].legend(frameon=False)
    for key, label, color in [('completed_experiments', 'Completed', colors[0]), ('productive_experiments', 'Productive', colors[1])]:
        axs[0, 2].plot(times, [a[key] for a in aux], label=label, color=color)
    axs[0, 2].set_ylabel('Processing experiments\n(cumulative)'); axs[0, 2].legend(frameon=False)
    for tool, color in zip(['gather', 'liquidate', 'experiment', 'wait'], colors):
        axs[1, 0].plot(times, [a['action_counts'].get(tool, 0)/sum(a['action_counts'].values()) for a in aux], label=tool, color=color)
    axs[1, 0].set_ylabel('Valid action fraction\n(5-round window)'); axs[1, 0].legend(frameon=False, ncol=2)
    axs[1, 1].plot(times, [a['message_count'] for a in aux], color=colors[0]); axs[1, 1].set_ylabel('Nonempty messages\n(5-round window)')
    for item, color in zip(['A', 'B', 'Q', 'P'], colors):
        axs[1, 2].plot(times, [a['pools'].get(item, 0) for a in aux], label=item, color=color)
    axs[1, 2].set_ylabel('Resource pool amount\n(auxiliary, not ecology score)'); axs[1, 2].legend(frameon=False)
    for ax in axs.flat:
        ax.set_xlabel('Round'); ax.set_xlim(1, max(times)); ax.grid(alpha=.16)
    for ext in ['png', 'pdf']:
        fig.savefig(output/f'dynamics.{ext}', bbox_inches='tight')
    plt.close(fig)
    summary = {'valid_actions': len(valid), 'invalid_actions': len(export['events'])-len(valid),
               'action_counts': dict(action_counts), 'completed_experiments': len(discoveries),
               'productive_experiments': sum(bool(e.get('produced')) for e in discoveries),
               'behavioral_jsd_range': [min(numeric), max(numeric)] if numeric else None,
               'final_metrics': report['round_series'][-1]['metrics']}
    write_json(output/'summary.json', summary)
    lines = ['# Luna low：无压力组指标分析', '', '4 个成员，50 轮；单个世界/运行种子。没有新增模型调用。', '',
             '![主要指标](core_metrics.png)', '', '![过程曲线](dynamics.png)', '',
             '所有成员始终存活（200/200 成员轮）。这只表明本次无压力运行中的存续，不等于社会发展。', '',
             f"有效动作 {len(valid)} 次，无效 {len(export['events'])-len(valid)} 次。动作计数：`{dict(action_counts)}`。",
             f"加工探索完成 {len(discoveries)} 次，产生新材料 {summary['productive_experiments']} 次。", '',
             '## 指标可计算性', '', '|指标|最后一轮|证据状态|', '|---|---|---|']
    for name in ordered:
        p = summary['final_metrics'][name]
        lines.append(f"|{name}|{p['value'] if p['value'] is not None else '—'}|{p['status']}|")
    lines += ['', '6 条数值曲线；恢复率不适用；另外 5 条缺少生态路径目录、已验证知识/采用链、双方确认承诺或语义编码。',
              '零交易、零直接冲突由完整动作日志与已审查的非转移/非冲突接口集合确认。流通分母只验证液态资源正下界；尚未实现有转移时的完整资产账本。',
              '作品复用为零，是因为本次没有任何作品或游戏对象。未把普通采集、材料衰减算作攻击。',
              '行为差异使用最近 5 轮有效动作的两两 JSD（底数 2）；每位参与者至少 3 次动作。前期样本不足留空。它衡量行为分布差异，不是分工、人格或表达差异。',
              '本次进入 JSD 计算的合格成员数在有值轮次为 3–4 人，逐点参与者名单和有效动作样本量见 metrics.json。',
              '物性披露和资源池仅作为辅助过程量，不代替规则认知或生态持续性。没有调查问卷，也没有将未知项填为零。', '',
              '## 离线复现', '', '从仓库根目录运行（需要 Python 与 matplotlib）：', '',
              '```powershell', 'python society_probe/society_probe/analyze_core_metrics.py --checkpoint results/luna_low_no_pressure_20261011/trajectory.json --config results/luna_low_no_pressure_20261011/config.json --output output/luna_metrics_reproduced', '```', '',
              '`trajectory.json` 是经过字段筛选的分析轨迹，不是可恢复执行的完整仿真检查点；原始输入哈希见 metrics.json。',
              '单种子描述结果不能推断模型大小因果效应、所有模型缺乏内源需求或不存在组织。当前世界没有本次运行的 Lean 证书；不声称上述曲线是 Lean 证明的最优性评级。']
    (output/'README.md').write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))
    (output/'latex_includes.tex').write_bytes(b'\\includegraphics[width=\\textwidth]{core_metrics.pdf}\n\\includegraphics[width=\\textwidth]{dynamics.pdf}\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'final_metrics'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in {args.checkpoint.resolve().parent, args.config.resolve().parent}:
        raise ValueError('Output must be separate from source directory')
    analyze(args.checkpoint, args.config, args.output)

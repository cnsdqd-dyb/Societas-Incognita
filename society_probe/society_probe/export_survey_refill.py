"""Readable export with raw/effective scores, provenance and applicability exclusions."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from survey_measurement import ITEMS, SOURCES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', nargs='?', default='runs/survey_refill_v3_keyed_20261007')
    args = parser.parse_args()
    folder = Path(args.folder)
    result = json.loads((folder/'result.json').read_text(encoding='utf-8'))
    columns = ['source_run', 'source_status', 'round', 'agent', 'object_type', 'object_number',
        'member_ids', 'object_description', 'item_id', 'question', 'dimension', 'source',
        'raw_response', 'effective_response', 'evidence_refs', 'quality_flags', 'post_hoc']
    with (folder/'responses.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns); writer.writeheader()
        for answer in result['surveys']:
            common = {k: answer[k] for k in ('source_run', 'source_status', 'round', 'agent')}
            common.update(quality_flags=';'.join(answer['quality_flags']), post_hoc=True)
            raw = answer['responses']; actual = answer.get('effective_responses', raw)
            for field, module in [('groups', 'identity'), ('arrangements', 'arrangement')]:
                for i, obj in enumerate(raw[field]):
                    eff = actual[field][i]
                    for j, item in enumerate(ITEMS[module]):
                        code, text, dimension, source_number = item
                        writer.writerow({**common, 'object_type': field, 'object_number': i,
                            'member_ids': ';'.join(obj['member_ids']), 'object_description': obj['description'],
                            'item_id': code, 'question': text, 'dimension': dimension,
                            'source': SOURCES[code[0]], 'evidence_refs': ';'.join(obj['evidence_refs']),
                            'raw_response': obj['scores'][code] if isinstance(obj['scores'], dict) else obj['scores'][j],
                            'effective_response': eff['scores'][code] if isinstance(eff['scores'], dict) else eff['scores'][j]})
            writer.writerow({**common, 'object_type': 'recent_experience', 'item_id': 'S01',
                'question': '最近经历有多出乎预期', 'dimension': 'self_report_surprise',
                'source': SOURCES['S'], 'raw_response': raw['surprise'], 'effective_response': actual['surprise']})
    keys = {(a['source_run'], a['round'], a['agent']) for a in result['surveys']}
    unresolved = [a for a in result['failures'] if (a['source_run'], a['round'], a['agent']) not in keys]
    grouped = Counter((a['source_run'], a['round']) for a in result['surveys'])
    flags = Counter(flag for a in result['surveys'] for flag in a['quality_flags'])
    baseline = [a for a in result['surveys'] if a['round'] == 0]
    nonbaseline = [a for a in result['surveys'] if a['round'] > 0]
    lines = ['# 新版问卷补填结果', '',
        f"状态：{result['status']}。有效保存 {len(keys)}/{result['total_targets']} 个成员时间点。",
        f"本目录计入费用 {result['cost_usd']:.8f} 美元；含此前运行与格式试填的全局账本 {result['global_cost_usd']:.8f} 美元。",
        f"其中基线 {len(baseline)} 份，后续阶段 {len(nonbaseline)} 份；本目录保留历史失败尝试 {len(result['failures'])} 次，尚未取得有效回答的失败成员时间点 {len({(a['source_run'], a['round'], a['agent']) for a in unresolved})} 个。", '',
        '这是根据原始个人可见输入进行的事后重新作答，不是原时点的同时测量。来源运行是否完整单独标记；不得将中断条件汇总当成完整实验对比。', '',
        'responses.csv可直接查看每道题的原始答案、有效答案、来源及证据引用。缺失对象通过result.json的识别状态记录。群体非成员的身份评分保留原答，但在有效评分中标为na并排除，未补造分数。', '',
        f'质量标记（允许同一份多种标记）：{dict(flags)}。这些标记及格式校验不构成量表效度证明。', '',
        '| 原运行 | 时间点 | 已保存成员数 |', '|---|---:|---:|']
    lines += [f'| {run} | {t} | {n} |' for (run, t), n in sorted(grouped.items())]
    (folder/'README.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('Exported responses.csv and README.md')


if __name__ == '__main__': main()

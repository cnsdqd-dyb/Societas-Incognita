"""Prepare (do not launch) balanced heterogeneous paired runs."""
import copy
import hashlib
import json
import random
import shutil
from collections import Counter
from pathlib import Path
from native_codex import write_json

ROOT = Path('runs/four_model_mix_20261009')
OLD = Path('runs/open_campaign_v1_20261007')
MODELS = ['mistralai/ministral-3b-2512', 'qwen/qwen-2.5-7b-instruct', 'openai/gpt-oss-20b', 'gpt-6.1-sol']

def main():
    assignment = [m for m in MODELS for _ in range(2)]
    random.Random(7).shuffle(assignment)
    ROOT.mkdir(parents=True, exist_ok=True)
    cases = []
    for pressure in (True, False):
        folder = ROOT / ('mixed4_p' + str(int(pressure)))
        folder.mkdir(exist_ok=True)
        source = OLD / ('ministral3b_p' + str(int(pressure)))
        cfg = json.loads((source / 'config.json').read_text('utf-8'))
        cfg['models'] = assignment
        cfg['backend'] = 'hybrid_codex_openrouter'
        cfg['model_routes'] = {
            MODELS[0]: {'backend': 'openrouter'},
            MODELS[1]: {'backend': 'openrouter'},
            MODELS[2]: {'backend': 'openrouter', 'parameters': {'provider_only': ['CoreWeave'], 'reasoning': {'effort': 'low'}}},
            MODELS[3]: {'backend': 'codex_native_cli', 'parameters': {'native_effort': 'low'}}}
        cfg['experiment'].update(stage='heterogeneous_prepared_not_started', model_assignment_seed=7,
                                 model_counts=dict(Counter(assignment)), model_labels_visible=False,
                                 native_monetary_usage='unknown_separately_logged')
        if (folder / 'config.json').exists():
            assert json.loads((folder / 'config.json').read_text('utf-8')) == cfg
        else:
            write_json(folder / 'config.json', cfg)
            shutil.copytree(source / 'engine_snapshot', folder / 'engine_snapshot')
        for adapter in ('hybrid_codex.py', 'native_codex.py', 'recovery_transport.py'):
            shutil.copy2(adapter, folder / adapter)
        write_json(folder / 'transport_hashes.json', {name: hashlib.sha256((folder/name).read_bytes()).hexdigest()
                   for name in ('hybrid_codex.py', 'native_codex.py', 'recovery_transport.py')})
        cases.append({'name': folder.name, 'pressure': pressure, 'launch':
                      f'python -X utf8 {folder}/hybrid_codex.py --run {folder} --api-key-file ../api_key'})
    write_json(ROOT / 'manifest.json', {'status': 'prepared_not_started', 'runs': cases, 'agents': 8,
               'rounds': 50, 'agent_model_assignment': {f'a{i}': m for i, m in enumerate(assignment)},
               'external_api_cap_usd_per_run': 1, 'native_cost_usd': None,
               'budget_note': 'Not launched. Before launch account for completed Qwen extension and remaining $5 authorization.'})
    (ROOT / 'README.md').write_text(
        '# 四模型混合实验（已准备，未启动）\n\n'
        '每种模型2个agent，总计8个；50轮，有/无资源压力各一组。种子7随机分配agent编号，两组采用相同分配。'
        '观察内容不显示模型名称，不预设阵营或共同目标；环境、问卷和记忆规则沿用同质模型实验。\n\n'
        'GPT-6.1-sol走原生Codex/low，其余模型走OpenRouter；GPT-OSS沿用CoreWeave/low。'
        '模型路由参数按线程隔离，外部API费用统一限额，原生使用量单独记录。每轮及轮内保存，重跑同一命令即可恢复。\n\n'
        '这两组尚未调用真实模型。启动前检查新增5美元预算的实际余额；1美元/组为停止阈值，非预计收费。\n\n'
        + '\n'.join('```powershell\n'+c['launch']+'\n```\n' for c in cases), encoding='utf-8')
    print(json.dumps({'status': 'prepared_not_started', 'counts': dict(Counter(assignment))}))

if __name__ == '__main__':
    main()

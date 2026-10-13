"""Build offline math exports for distinct compositions; never calls models."""
import copy
import json
from pathlib import Path

import world_math_export
import world_rule_library as library


def main():
    base=Path(__file__).resolve().parent
    source=base/'configs/property_rules_v1_20261013/luna_low_p0_s7/config.json'
    if not source.exists():source=base/'configs/property_rules_v1/example_seed19.json'
    cfg=json.loads(source.read_text('utf-8'))
    root=base/'reports/world_math_20261013'
    examples=[('alternative_seed19',19,None),
        ('ecology_interdependence_seed31',31,['renewable_ecology','trophic_balance','cross_feeding','explicit_delay']),
        ('catalysis_repair_seed47',47,['renewable_ecology','competitive_catalysis','autocatalytic_seed','fatigue_repair','shared_queue']),
        ('full20_seed23',23,[key for key,title in library.CANDIDATES_20])]
    rows=[]
    for name,seed,modules in examples:
        current=copy.deepcopy(cfg)
        if modules is not None:
            candidate=library.with_property_rules(library.with_capabilities(library.generate(seed,modules)))
            current['world']['mini_world']['definition']=candidate['definition']
            current['experiment']['generation']=candidate['generation']
        report=world_math_export.export(current,root/name)
        report['output']=name
        rows.append({'name':name,'seed':seed,'modules':current['experiment']['generation']['modules'],**report})
    (root/'index.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 世界数学模型与依赖网络','',
        '由实际配置自动导出；仅做离线表达与验证，没有调用模型。','',
        '| 世界 | 机制数 | 配置表达式 | 网络节点 | 网络边 |','|---|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| [{r['name']}]({r['name']}/model.md) | {len(r['modules'])} | {r['equations']} | {r['nodes']} | {r['edges']} |")
    lines += ['', '每个目录提供模型说明与总方程、逐项展开的LaTeX、Mermaid依赖网络、'+
        '机器可读节点/边与表达式、完整物理定义及哈希。总算子涵盖完整状态，社会工具分支仍采用代码定义；'+
        '展开网络是配置依赖图，不是已验证的因果图、最优解或Lean证明图。','',
        '导出任意已验证配置：','', '```powershell',
        'python world_math_export.py --config <config.json> --output <output_directory>', '```','']
    (root/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(rows,ensure_ascii=False))


if __name__=='__main__':
    main()

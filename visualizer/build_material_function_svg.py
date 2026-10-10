"""Build a conceptual material-function diagram in the existing README palette."""
from html import escape
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'society_probe'/'society_probe'))
from functional_effects import KINDS


def build(language='en'):
    chinese = language == 'zh-CN'
    labels = {
        'FROM MATERIALS TO ACTIONABLE FUNCTIONS': '从材料生产到可使用的功能',
        'A seeded service catalogue changes what holding and combining materials can enable.': '世界种子决定功能配置，持有与组合材料可以解锁新的作用。',
        'PRODUCE': '生产材料', 'COMBINE': '凑齐组合', 'DISCOVER': '私下发现',
        'CHOOSE': '主动选择', 'CHANGE': '产生作用',
        'Explore hidden reactions': '探索隐藏的生产规律',
        'Accumulate intermediates': '积累中间材料',
        'One owner meets requirements': '同一成员库存凑齐条件',
        'Escrow / storage excluded': '不计托管与容器储存',
        'Private property disclosure': '私下披露功能与特性',
        'Unlock target + cost interface': '解锁目标与费用接口',
        'Confirm a paid use': '确认并支付使用成本',
        'Or cancel without use costs': '或取消，不支付使用成本',
        'Update actual world state': '改变实际仿真状态',
        'Record and checkpoint': '记录事件并保存检查点',
        'WORKS & INFORMATION': '作品与信息能力',
        'PRODUCTION & SURVIVAL': '生产与生存能力',
        'DISRUPTION & CONFLICT': '破坏与冲突',
        'Work context ×2; notes +1,000': '作品容量 ×2；笔记容量 +1,000',
        'Communication budget / reach': '增加通信额度与邀请人数',
        'Device coverage / measurement': '提升设备覆盖与测量能力',
        'Yield / diagnostics / switching': '提高产率、诊断与切换速度',
        'Storage / discharge / defense': '储存保护、放能与防护',
        'Paid rescue; activate next round': '付费救援，下一轮恢复行动',
        'Attack / area damage': '成员攻击与大范围毁伤',
        'Pollution / facility sabotage': '资源污染与加工台破坏',
        'Device and container damage': '设备与储存容器损伤',
        'Conceptual interface diagram. New services are runtime-tested; their full Lean semantics are not yet certified.': '概念接口图：新增功能已做运行时验证，其完整语义尚未获得 Lean 认证。',
    }
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 490" role="img" aria-labelledby="title desc">',
           '<title id="title">'+('材料组合解锁可使用的功能与破坏作用' if chinese else 'Materials unlock usable services and destructive effects')+'</title>',
           '<desc id="desc">'+('生产材料，同一成员库存凑齐条件后私下发现功能，再确认付费使用或取消。作用改变作品、能力、生存条件或公共资源。这是概念图，不是实验轨迹。' if chinese else 'Produce materials, meet a private inventory condition, discover a function, then confirm a paid use or cancel. Effects change works, capabilities, survival or shared resources. Conceptual diagram, not an experimental trajectory.')+'</desc>',
           '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="#83927b"/></marker></defs>',
           '<rect width="1280" height="490" rx="12" fill="#f7f4e9"/>',
           '<g font-family="'+('Microsoft YaHei,SimHei,Segoe UI,Arial,sans-serif' if chinese else 'Segoe UI,Arial,sans-serif')+'" fill="#293f37">']

    def text(x, y, value, size=15, color='#293f37', weight='normal'):
        if chinese: value = labels.get(value, value)
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}">{escape(value)}</text>')

    def rect(x, y, w, h, fill='#e6eadf'):
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{fill}" stroke="#acb79f"/>')

    def arrow(x1, y1, x2, y2):
        out.append(f'<path d="M{x1} {y1} L{x2} {y2}" stroke="#83927b" stroke-width="2" fill="none" marker-end="url(#arrow)"/>')

    text(28, 37, 'FROM MATERIALS TO ACTIONABLE FUNCTIONS', 24, weight='bold')
    text(28, 63, 'A seeded service catalogue changes what holding and combining materials can enable.', 15, '#728075')
    stages = [(28, 'PRODUCE', ['Explore hidden reactions', 'Accumulate intermediates'], '#719564'),
              (280, 'COMBINE', ['One owner meets requirements', 'Escrow / storage excluded'], '#d3a35c'),
              (532, 'DISCOVER', ['Private property disclosure', 'Unlock target + cost interface'], '#997baa'),
              (784, 'CHOOSE', ['Confirm a paid use', 'Or cancel without use costs'], '#5b90a9'),
              (1036, 'CHANGE', ['Update actual world state', 'Record and checkpoint'], '#aeb255')]
    for x, title, lines, color in stages:
        rect(x, 91, 216, 129)
        for j in range(3):
            out.append(f'<rect x="{x+14+j*13}" y="105" width="8" height="8" fill="{color}"/>')
        text(x+14, 143, title, 17, weight='bold')
        for j, line in enumerate(lines): text(x+14, 174+j*22, line, 13)
    for x in (244,496,748,1000): arrow(x, 158, x+33, 158)
    arrow(1144, 221, 1144, 245)
    out.append('<path d="M218 265 H1144 V245" stroke="#83927b" stroke-width="2" fill="none"/>')
    for x in (218,640,1062): arrow(x,265,x,284)
    groups = [(28, 'WORKS & INFORMATION', ['Work context ×2; notes +1,000', 'Communication budget / reach', 'Device coverage / measurement'], '#e5eaf0'),
              (450, 'PRODUCTION & SURVIVAL', ['Yield / diagnostics / switching', 'Storage / discharge / defense', 'Paid rescue; activate next round'], '#e6eadf'),
              (872, 'DISRUPTION & CONFLICT', ['Attack / area damage', 'Pollution / facility sabotage', 'Device and container damage'], '#efe1d7')]
    for x, title, lines, color in groups:
        rect(x,285,380,139,color)
        text(x+17,315,title,18,weight='bold')
        for j,line in enumerate(lines): text(x+17,345+j*25,line,15)
    text(28,454,(f'已实现 {len(KINDS)} 类附加功能，每个世界按种子选取一部分；材料成本与目标权限仍然有效。' if chinese else f'{len(KINDS)} implemented service types; seeded worlds select a subset. Material costs and target permissions still apply.'),14,'#728075')
    text(28,477,'Conceptual interface diagram. New services are runtime-tested; their full Lean semantics are not yet certified.',12,'#728075')
    out.append('</g></svg>')
    path = ROOT/'docs'/'images'/('material-functions.zh-CN.svg' if chinese else 'material-functions.svg')
    path.write_text('\n'.join(out),encoding='utf-8')
    print(path)


if __name__ == '__main__':
    build()
    build('zh-CN')

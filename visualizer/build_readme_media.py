"""Render GitHub-compatible SVG/GIF from actual offline engine trajectories."""
import json
import math
import textwrap
from html import escape
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import mechanism_lab

OUT = Path(__file__).resolve().parents[1] / 'docs' / 'images'
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1120, 360
INK, MUTED, PAPER, LINE = '#263f37', '#718174', '#f7f5eb', '#c7d4be'
COLORS = {'A': '#719564', 'B': '#588ca5', 'C': '#d5a55b', 'D': '#9b7cab', 'W': '#cf896b', 'S': '#b6b553'}
FONT = Path('C:/Windows/Fonts/msyh.ttc')
MONO = Path('C:/Windows/Fonts/consola.ttf')


def expression(node):
    if isinstance(node, (int, float)):
        return str(node)
    if 'ref' in node:
        return node['ref'].replace('pool.', '').replace('state.', '').replace('activity.', '')
    args = [expression(x) for x in node['args']]
    op = node['op']
    operators = {'add': '+', 'sub': '-', 'mul': '*', 'div': '/', 'lt': '<', 'ge': '>='}
    return '(' + (' '+operators[op]+' ').join(args) + ')' if op in operators else op+'('+', '.join(args)+')'


CASES = [
    {'title': '01  Renewal × low-stock threshold', 'modules': ['renewable_ecology', 'allee_threshold'],
     'subtitle': 'Renewal changes with the remaining stock.', 'fields': [], 'stock': .2},
    {'title': '02  Delay × nonlinear modulation × diffusion', 'modules': ['explicit_delay', 'chaotic_modulation', 'reaction_diffusion'],
     'subtitle': 'Past operations and control variables affect later dynamics.', 'fields': ['delay_2', 'chaos_z', 'rd_x0'], 'stock': .5},
    {'title': '03  Cross-feeding × congestion × queueing', 'modules': ['cross_feeding', 'congested_transport', 'shared_queue'],
     'subtitle': 'Recipes, energy budgets, and service capacity constrain outputs.', 'fields': [], 'stock': .5},
]
for case in CASES:
    case['probe'] = mechanism_lab.simulate({'modules': case['modules'], 'seed': 7, 'rounds': 30,
                                           'amount': 3, 'stock': case['stock'], 'drive': 'production'})


class Canvas:
    def __init__(self):
        self.image = Image.new('RGB', (WIDTH, HEIGHT), PAPER)
        self.draw = ImageDraw.Draw(self.image)
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img"><title>Three mathematical mechanism compositions</title><desc>Actual engine probe data. Hidden-rule preset: formulas exist but are not directly disclosed to agents.</desc><rect width="{WIDTH}" height="{HEIGHT}" fill="{PAPER}"/>']

    def rect(self, x, y, w, h, fill, stroke=None):
        self.draw.rectangle((x, y, x+w-1, y+h-1), fill=fill, outline=stroke)
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"'+(f' stroke="{stroke}"' if stroke else '')+'/>')

    def text(self, x, y, content, size=15, color=INK, mono=False):
        translations = {
            '规则不可见，物质反馈可见。': 'World laws built from compositional mathematics',
            '隐藏规则设置 · 三组机制组合 · seed = 7 · 固定操作探针（非智能体实验结果）': 'Hidden-rule condition / three compositions / seed 7 / fixed probe, not an agent experiment',
            '物理回合  ': 'Physical round  ', '池 ': 'Pool ', '成员库存  ': 'Member inventory  ',
            '加工设施': 'Facility', '实际产出 ': 'Output ', '本轮无产出': 'No output this round',
            '研究者规则层 · 不向成员直接公开': 'World-law layer / researcher access',
            '智能体视角': 'Agent interface',
            '材料标识 / 可见数量 / 可用操作 / 试验反馈 → 推测规则 → 再次操作': 'Material IDs / visible quantities / operations / feedback → hypotheses → tests',
            '公式驱动状态转移，但隐藏规则配置不直接披露公式与配方。公开设置可作为对照。': 'Formulas govern transitions; hidden-rule conditions do not directly disclose formulas or recipes.',
            '像素条 = 池容量比例；数值 = 引擎实际数量。移动方块 = 已结算产出。活性不计入物理能量账本。': 'Pixel bars: pool-capacity ratios. Numbers: actual amounts. Moving pixels: settled output. Vitality is excluded from physical accounting.',
        }
        for source, target in translations.items():
            content = content.replace(source, target)
        self.draw.text((x, y), content, fill=color, font=ImageFont.truetype(str(MONO if mono else FONT), size))
        self.svg.append(f'<text x="{x}" y="{y+size}" font-family="{("monospace" if mono else "Microsoft YaHei, Noto Sans CJK SC, sans-serif")}" font-size="{size}" fill="{color}">{escape(str(content))}</text>')

    def person(self, x, y, color):
        rows = ['..hhhh..', '.hhhhhh.', '.ssssss.', '.sissis.', '.ssmmss.', 'sccccccs', '.cccccc.', '..pppp..', '..p..p..']
        palette = {'h': '#826549', 's': '#efd0a6', 'i': INK, 'm': '#c58773', 'c': color, 'p': '#48564b'}
        for row, pixels in enumerate(rows):
            for col, pixel in enumerate(pixels):
                if pixel in palette:
                    self.rect(x+col*7, y+row*7, 7, 7, palette[pixel])


def draw_frame(t, tween):
    """A compact comparison: quantities and settled output, without formula panels."""
    c = Canvas()
    c.text(24, 14, 'Three compositions', 23)
    c.text(910, 21, f'Round {t:02d} / 30', 15, MUTED)
    titles = ['Renewal + threshold', 'Delay + modulation + diffusion', 'Cross-feed + congestion + queue']
    for i,case in enumerate(CASES):
        x=24+i*365
        frame=case['probe']['frames'][t]
        c.rect(x,58,342,280,'#fffdf5',LINE)
        c.text(x+12,72,titles[i],16)
        for j,item in enumerate(('A','B')):
            quantity=frame['physics']['pools'][item]
            capacity=case['probe']['definition']['pools'][item]['capacity']
            y=110+j*35
            c.text(x+12,y,f'{item}  {quantity:.2f}',15,mono=True)
            for k in range(20):
                c.rect(x+128+k*9,y+4,7,14,COLORS[item] if k<quantity/capacity*20 else '#e2e8db')
        c.rect(x+40,206,84,38,'#a18b6f')
        c.rect(x+33,192,98,14,'#6b8a70')
        c.rect(x+51,216,62,7,'#dbc68f')
        c.person(x+235,185,'#789e9b')
        produced={k:v for e in frame['record'].get('completed_experiments',[]) for k,v in e.get('produced',{}).items() if v>0}
        for j,item in enumerate(produced):
            c.rect(x+int(130+90*tween),210+j*15,7,7,COLORS.get(item,'#d5a55b'))
        for j,item in enumerate(('C','W','D')):
            quantity=sum(a['inventory'].get(item,0) for a in frame['agents'].values())
            c.rect(x+15+j*109,281,14,14,COLORS[item])
            c.text(x+35+j*109,277,f'{item} {quantity:.1f}',12,mono=True)
    c.svg.append('</svg>')
    return c


frames = []
for t in range(31):
    for tween in (0.15, 0.65):
        frames.append(draw_frame(t, tween).image)
frames[0].save(OUT / 'mechanism-combinations.gif', save_all=True, append_images=frames[1:],
               duration=[650 if i in (0, 61) else 240 for i in range(62)], loop=0, optimize=True, disposal=2)
snapshot = draw_frame(9, .65)
(OUT / 'hidden-rules-visible-feedback.svg').write_text('\n'.join(snapshot.svg), encoding='utf-8')
snapshot.image.save(OUT / 'hidden-rules-visible-feedback.png')
(OUT / 'mechanism-demo-data.json').write_text(json.dumps([
    {'title': c['title'], 'modules': c['modules'], 'probe': c['probe']} for c in CASES
], ensure_ascii=False, indent=2), encoding='utf-8')
print('Rendered 62-frame GIF, editable SVG/PNG, and full engine probe data in docs/images/')

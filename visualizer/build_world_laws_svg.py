"""Data-driven SMIL illustration for the repository README, with no JavaScript."""
import copy
import json
from html import escape
from pathlib import Path
import mechanism_lab as lab

OUT = Path(__file__).resolve().parents[1] / 'docs' / 'images'
OUT.mkdir(parents=True, exist_ok=True)
MODULES = ['renewable_ecology', 'explicit_delay', 'cross_feeding', 'congested_transport', 'shared_queue']


def trajectory():
    candidate = lab.library.generate(7, modules=MODULES)
    d = candidate['definition']
    cfg = {'world': {'mechanism': 'mini_world', 'mini_world': {'definition': d}}, 'seed': 7,
           'tools': ['wait', 'gather', 'experiment', 'give_item', 'use_function']}
    state = {'round': 0, 'agents': {f'a{i}': {'stock': 80., 'energy': 5, 'alive': True, 'inbox': []} for i in range(3)}}
    lab.mini_world.initialize(cfg, state)
    frames = []

    def save(events=None, record=None):
        return {'round': state['round'], 'physics': lab.mini_world.snapshot(state),
                'agents': copy.deepcopy(state['agents']), 'events': events or [], 'record': record or {},
                'accounting': lab.mini_world.accounting(cfg, state)}

    frames.append(save())
    for t in range(1, 97):
        state['round'] = t
        before = {'mini_world': lab.mini_world.snapshot(state)}
        events = []
        for i in range(3):
            aid = f'a{i}'; inv = state['agents'][aid]['inventory']; recipe = d['recipes'][i]
            action = {'tool': 'wait'}
            if i < 2:
                recipient = f'a{i+1}'
                downstream = d['recipes'][i+1]['inputs']
                item = next((k for k, n in downstream.items() if inv.get(k, 0) >= 1 and
                             state['agents'][recipient]['inventory'].get(k, 0) < n), None)
                if item:
                    action = {'tool': 'give_item', 'target': recipient, 'item': item, 'amount': 1,
                              'note': 'Fixed illustration probe; not an agent decision.'}
            if action['tool'] == 'wait' and aid not in state['mini_world']['pending']:
                if all(inv.get(k, 0) >= n for k, n in recipe['inputs'].items()):
                    action = {'tool': 'experiment', 'facility': recipe['facility'], 'mode': recipe['mode'],
                              'inputs': [{'item': k, 'amount': n} for k, n in recipe['inputs'].items()], 'batches': 1}
                else:
                    item = next((k for k, n in recipe['inputs'].items() if k in d['pools'] and inv.get(k, 0) < n), None)
                    if item:
                        action = {'tool': 'gather', 'item': item, 'amount': 3}
            previous = copy.deepcopy(state)
            energy = lab.mini_world.total_energy(cfg, state)
            try:
                outcome = lab.mini_world.act(cfg, state, aid, action)
                lab.mini_world.account_loss(cfg, state, energy, 'illustration:'+action['tool'])
            except ValueError as exc:
                state = previous
                outcome = {'error': str(exc)}
            events.append({'agent': aid, 'action': action, 'outcome': outcome})
        record = lab.mini_world.settle_physics(cfg, state, before)
        frames.append(save(events, record))
    return {'definition': d, 'generation': candidate['generation'], 'frames': frames,
            'probe': 'Fixed harvest / production / handoff schedule, no LLM, no maintenance. Not a research result.'}


def expr(node):
    if not isinstance(node, dict):
        return str(node)
    if 'ref' in node:
        return node['ref'].replace('pool.', '').replace('state.', '').replace('activity.', '')
    args = [expr(v) for v in node['args']]
    ops = {'add': '+', 'sub': '-', 'mul': '*', 'div': '/', 'lt': '<'}
    return '('+(' '+ops[node['op']]+' ').join(args)+')' if node['op'] in ops else node['op']+'('+', '.join(args)+')'


def svg(probe):
    width, height, duration = 1280, 870, 34
    frames = probe['frames'] + [probe['frames'][-1]]*4; d = probe['definition']; n = len(frames)
    times = ';'.join(f'{i/(n-1):.6f}' for i in range(n))
    ink = '#293f37'; muted = '#728075'; colors = {'A': '#719564', 'B': '#5b90a9', 'C': '#d3a35c', 'W': '#d08a6b', 'D': '#997baa', 'S': '#aeb255'}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
           '<title id="title">World laws built from compositional mathematics</title>',
           '<desc id="desc">Animated material quantities, actual production and inter-member transfers computed by the bounded research engine. Formulas are available to researchers but are not directly disclosed to agents in the hidden-rule setting. This is a fixed probe, not evidence that scientists have emerged.</desc>',
           f'<rect width="{width}" height="{height}" fill="#f7f5ec"/>',
           '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="#93a187"/></marker></defs>',
           '<style>text{font-family:Arial,sans-serif;fill:#293f37}.mono{font-family:Consolas,monospace}.small{font-size:12px;fill:#728075}</style>']

    def text(x, y, value, size=14, fill=ink, klass=''):
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" style="fill:{fill}" class="{klass}">{escape(value)}</text>')

    def box(x, y, w, h, fill, stroke=None):
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"'+(f' stroke="{stroke}"' if stroke else '')+'/>')

    def animated(values, attribute, mode='discrete'):
        return f'<animate attributeName="{attribute}" values="'+(';'.join(str(v) for v in values))+f'" keyTimes="{times}" dur="{duration}s" repeatCount="indefinite" calcMode="{mode}"/>'

    text(28, 44, 'World laws built from compositional mathematics', 29)
    text(28, 73, 'Renewal + delay + cross-feeding + congestion + shared queue  |  seed 7', 14, muted)
    text(28, 97, 'Fixed engine probe  /  actual quantities and settled transfers  /  no LLM decisions', 12, muted)
    box(28, 119, 845, 443, '#fffdf5', '#ccd5c3')
    box(894, 119, 358, 443, '#f1ead8', '#d8c8a7')
    text(46, 146, 'Material dynamics', 18)
    text(910, 146, 'World-law layer', 18, '#795b3b')
    text(910, 171, 'Defined by researchers; not directly', 13, '#795b3b')
    text(910, 190, 'disclosed in the hidden-rule setting.', 13, '#795b3b')
    nodes = {'A': (113, 233), 'B': (113, 390), 'C': (363, 233), 'W': (363, 390), 'D': (600, 320), 'S': (778, 320)}
    edges = [('A', 'C'), ('B', 'C'), ('A', 'W'), ('B', 'W'), ('C', 'D'), ('W', 'D'), ('D', 'S'), ('B', 'S')]
    paths = {}
    for source, target in edges:
        x1, y1 = nodes[source]; x2, y2 = nodes[target]
        offset = -22 if source in ('A', 'C', 'D') else 22
        path = f'M{x1+40},{y1} C{x1+100},{y1+offset} {x2-100},{y2+offset} {x2-43},{y2}'
        if (source, target) == ('B', 'S'):
            path = f'M{x1+40},{y1} C{x1+140},460 {x2-60},440 {x2-43},{y2}'
        paths[(source, target)] = path
        out.append(f'<path d="{path}" stroke="#acb79f" stroke-width="2" fill="none" marker-end="url(#arrow)"/>')
    text(216, 210, 'production', 11, muted)
    text(216, 445, 'byproduct', 11, muted)
    text(446, 266, 'handoff + recipe', 11, muted)
    text(678, 303, 'recipe', 11, muted)
    values = {}
    for item, (x, y) in nodes.items():
        values[item] = [f['physics']['pools'].get(item, 0) if item in ('A', 'B') else
                        sum(a['inventory'].get(item, 0) for a in f['agents'].values()) for f in frames]
        top = max(1, max(values[item]))
        box(x-39, y-40, 78, 80, '#e6eadf', '#83927b')
        out.append(f'<rect x="{x-32}" y="{y+30}" width="64" height="0" fill="{colors[item]}">')
        out.append(animated([round(64*v/top, 3) for v in values[item]], 'height'))
        out.append(animated([round(y+30-64*v/top, 3) for v in values[item]], 'y'))
        out.append('</rect>')
        # Small square material tiles keep the scene on the pixel-art vocabulary.
        for i in range(4):
            box(x-27+i*14, y-31, 7, 7, colors[item])
        text(x-7, y+5, item, 25, ink, 'mono')
        text(x-40, y+79, 'pool' if item in ('A', 'B') else 'held by members', 10, muted)
    # Only actual recipe completions activate material edges.
    for source, target in edges:
        active = []
        for f in frames:
            completed = f['record'].get('completed_experiments', [])
            active.append(1 if any(e.get('produced', {}).get(target, 0) > 0 and source in e.get('inputs', {}) for e in completed) else 0)
        out.append(f'<g opacity="0">'+animated(active, 'opacity', 'discrete'))
        out.append(f'<path d="{paths[(source,target)]}" stroke="{colors[target]}" stroke-width="4" fill="none"/>')
        out.append(f'<rect x="-4" y="-4" width="8" height="8" fill="{colors[target]}"><animateMotion dur=".7s" repeatCount="indefinite" path="{paths[(source,target)]}"/></rect></g>')
    # The agent glyphs and transfer arcs below show actual handoffs, separately from recipes.
    for i, x in enumerate((225, 435, 645)):
        rows = ['..hhhh..', '.hhhhhh.', '.ssssss.', '.sissis.', '.ssmmss.', 'sccccccs', '.cccccc.', '..pppp..', '..p..p..']
        palette = {'h': '#846b50', 's': '#efd1a9', 'i': ink, 'm': '#c58c77', 'c': ['#789f85', '#7193a5', '#a48dae'][i], 'p': '#4e5c50'}
        for row, line in enumerate(rows):
            for col, pixel in enumerate(line):
                if pixel in palette:
                    box(x+col*7, 488+row*7, 7, 7, palette[pixel])
        text(x+12, 479, f'a{i}', 13, muted)
    text(46, 483, 'Material', 12, muted)
    text(46, 501, 'transfers', 12, muted)
    for i, item in ((0, 'C'), (0, 'W'), (1, 'D')):
        start = 280+i*210; end = start+155
        path = f'M{start},511 Q{(start+end)/2},470 {end},511'
        out.append(f'<path d="{path}" stroke="#b7c3ad" stroke-width="1" fill="none"/>')
        active = [int(any(e['agent']==f'a{i}' and e['action']['tool']=='give_item' and e['action'].get('item')==item and not e['outcome'].get('error') for e in f['events'])) for f in frames]
        out.append('<g opacity="0">'+animated(active, 'opacity', 'discrete'))
        out.append(f'<rect x="-4" y="-4" width="8" height="8" fill="{colors[item]}"><animateMotion path="{path}" dur=".6s" repeatCount="indefinite"/></rect>')
        text(start+56, 493, item+' +1', 11, colors[item])
        out.append('</g>')
    # Actual expressions, not an illustrative law invented for the animation.
    text(910, 222, 'Renewal', 14, '#795b3b')
    renewal = expr(d['pools']['A']['regeneration'])
    import textwrap
    for j, line in enumerate(textwrap.wrap('regen_A = '+renewal, 39)):
        text(910, 244+j*17, line, 12, '#795b3b', 'mono')
    text(910, 296, 'Delayed feedback', 14, '#795b3b')
    text(910, 319, 'delay_0(next) = harvested.A', 12, '#795b3b', 'mono')
    text(910, 338, 'delay_2(next) = delay_1', 12, '#795b3b', 'mono')
    text(910, 372, 'Production / cross-feeding', 14, '#795b3b')
    r = d['recipes'][0]
    text(910, 395, 'inputs: '+', '.join(f'{v}{k}' for k, v in r['inputs'].items()), 12, '#795b3b', 'mono')
    text(910, 414, 'nominal C: '+expr(r['yield'])+'; W: '+expr(r['byproducts']['W']), 12, '#795b3b', 'mono')
    text(910, 438, 'Actual yield is energy-constrained.', 12, '#795b3b')
    text(910, 467, 'Service capacity per facility: 1', 12, '#795b3b')
    text(910, 488, 'Route cost depends on submitted load.', 12, '#795b3b')
    text(910, 535, 'Solid paths: recipe dependencies.', 11, '#795b3b')
    # Two plots use separate axes so quantities with different scales stay readable.
    box(28, 580, 1224, 173, '#fffdf5', '#ccd5c3')
    text(46, 607, 'Quantity trajectories', 18)
    for plot, items in enumerate((('A','B'), ('C','W','D','S'))):
        x0 = 72+plot*605; y0 = 726; pw = 500; ph = 95
        maximum = max(1, max(v for k in items for v in values[k]))
        out.append(f'<path d="M{x0},{y0-ph}V{y0}H{x0+pw}" stroke="#b4c0a9" fill="none"/>')
        text(x0-25, y0-ph+4, f'{maximum:.0f}', 10, muted)
        text(x0-15, y0, '0', 10, muted)
        text(x0+pw-8, y0+18, '96', 10, muted)
        for i, item in enumerate(items):
            points = ' '.join(f'{x0+j/(n-1)*pw:.1f},{y0-v/maximum*ph:.1f}' for j, v in enumerate(values[item]))
            out.append(f'<polyline points="{points}" fill="none" stroke="{colors[item]}" stroke-width="2"/>')
            text(x0+i*75, 620, item, 12, colors[item])
        out.append(f'<line x1="{x0}" x2="{x0}" y1="{y0-ph}" y2="{y0}" stroke="#304d3c" stroke-width="2">')
        out.append(f'<animate attributeName="x1" from="{x0}" to="{x0+pw}" dur="{duration}s" repeatCount="indefinite"/><animate attributeName="x2" from="{x0}" to="{x0+pw}" dur="{duration}s" repeatCount="indefinite"/></line>')
    box(28, 769, 1224, 73, '#e5ecdf', '#ccd5c3')
    text(46, 795, 'Agent interface', 16)
    text(192, 795, 'Observable quantities + available operations + experimental feedback', 15)
    text(46, 824, 'Observe → hypothesize → test → communicate. Whether scientific practice emerges is the research question.', 14, muted)
    # Discrete labels follow the same round as the animated bars and event visibility.
    for j, f in enumerate(frames[:-1]):
        start = j/(n-1); end = (j+1)/(n-1)
        if j == 0:
            keys, vals = f'0;{end:.6f}', 'visible;hidden'
        elif j == n-2:
            keys, vals = f'0;{start:.6f}', 'hidden;visible'
        else:
            keys, vals = f'0;{start:.6f};{end:.6f}', 'hidden;visible;hidden'
        out.append(f'<g visibility="hidden"><animate attributeName="visibility" values="{vals}" keyTimes="{keys}" calcMode="discrete" dur="{duration}s" repeatCount="indefinite"/>')
        text(787, 146, f'R{f["round"]:02d}', 15, muted, 'mono')
        for item, (x, y) in nodes.items():
            text(x-28, y+61, f'{values[item][j]:.2f}', 15, ink, 'mono')
        out.append('</g>')
    text(28, 860, 'Bars use a fixed per-material scale; numeric labels give exact amounts. Moving pixels represent settled production or transfer.', 11, muted)
    out.append('</svg>')
    return '\n'.join(out)


if __name__ == '__main__':
    result = trajectory()
    assert all(abs(f['accounting']['residual']) < 1e-7 for f in result['frames'])
    (OUT / 'compositional-world-laws.svg').write_text(svg(result), encoding='utf-8')
    (OUT / 'compositional-world-laws-data.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Animated SVG generated:', {k: sum(a['inventory'][k] for a in result['frames'][-1]['agents'].values()) for k in ('C','W','D','S')})

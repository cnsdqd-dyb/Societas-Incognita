"""Offline probes of the research engine; no model calls or experiment writes."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'society_probe' / 'society_probe'))
import world_rule_library as library
import world_mechanisms_20 as mechanisms
import mini_world


def catalog():
    return [{'id': key, 'title': title, 'number': i} for i, (key, title) in enumerate(mechanisms.CATALOG, 1)]


def simulate(params):
    selected = params.get('modules', ['renewable_ecology'])
    allowed = {key for key, _ in mechanisms.CATALOG}
    if not isinstance(selected, list) or not selected or len(selected) > 20 or any(key not in allowed for key in selected):
        raise ValueError('Choose 1..20 known mechanisms')
    seed = int(params.get('seed', 7))
    rounds = max(1, min(120, int(params.get('rounds', 60))))
    amount = max(1, min(8, int(params.get('amount', 3))))
    scale = max(.05, min(1., float(params.get('stock', .5))))
    candidate = library.generate(seed, modules=list(dict.fromkeys(selected)))
    d = candidate['definition']
    for p in d['pools'].values():
        p['initial'] = p['capacity'] * scale
    cfg = {'world': {'mechanism': 'mini_world', 'mini_world': {'definition': d}},
           'tools': ['wait', 'inspect', 'gather', 'experiment', 'use_item', 'use_function'], 'seed': seed, 'recipe_visibility': 'full', 'world_rule_visibility': 'full'}
    state = {'round': 0, 'agents': {f'a{i}': {'stock': 40., 'energy': 5, 'alive': True, 'inbox': []} for i in range(3)}}
    mini_world.initialize(cfg, state)
    frames = []

    def frame(record=None, events=None):
        return {'round': state['round'], 'physics': mini_world.snapshot(state),
                'agents': copy.deepcopy(state['agents']), 'accounting': mini_world.accounting(cfg, state),
                'record': record or {}, 'events': events or []}

    frames.append(frame())
    for t in range(1, rounds + 1):
        state['round'] = t
        before = {'mini_world': mini_world.snapshot(state)}
        events = []
        for index, (aid, agent) in enumerate(state['agents'].items()):
            recipe = d['recipes'][index % len(d['recipes'])]
            action = {'tool': 'wait'}
            # A transparent fixed probe, not an LLM policy or optimized result.
            if params.get('drive', 'production') == 'idle':
                pass
            elif t % 7 == 0:
                item = next((k for k in ('D', 'C') if agent['inventory'].get(k, 0) >= 1), None)
                if item:
                    action = {'tool': 'use_item', 'item': item, 'amount': 1}
            elif t % 3 == 0 and all(agent['inventory'].get(k, 0) >= n for k, n in recipe['inputs'].items()):
                action = {'tool': 'experiment', 'facility': recipe['facility'], 'mode': recipe['mode'],
                          'inputs': [{'item': k, 'amount': n} for k, n in recipe['inputs'].items()], 'batches': 1}
            else:
                item = next((k for k, n in recipe['inputs'].items() if k in d['pools'] and agent['inventory'].get(k, 0) < n), 'A' if index % 2 == 0 else 'B')
                action = {'tool': 'gather', 'item': item, 'amount': amount}
            try:
                previous = copy.deepcopy(state)
                energy_before = mini_world.total_energy(cfg, state)
                outcome = mini_world.act(cfg, state, aid, action)
                mini_world.account_loss(cfg, state, energy_before, 'probe_action:'+action['tool'])
            except ValueError as exc:
                state = previous
                outcome = {'error': str(exc)}
            events.append({'agent': aid, 'action': action, 'outcome': outcome})
        record = mini_world.settle_physics(cfg, state, before)
        frames.append(frame(record, events))
    return {'definition': d, 'generation': candidate['generation'], 'frames': frames,
            'probe': {'policy': 'fixed harvest / recipe / use probe; no LLM, no maintenance', 'parameters': params},
            'interpretation': 'Bounded discrete mechanism demonstration; not an experimental result or a natural simulator.'}

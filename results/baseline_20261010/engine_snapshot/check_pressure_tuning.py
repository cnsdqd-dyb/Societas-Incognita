"""Small offline parameter comparisons; no model calls or optimality claim."""
import copy
import json
import math
from pathlib import Path

import environments
import sim
import world_rule_engine
from capability_feasibility import action_order


def trajectory(cfg, policy):
    society = sim.Society(cfg)
    definition = cfg['world']['mini_world']['definition']
    rows, plan = [], []
    for turn in range(1, cfg['rounds'] + 1):
        society.state['round'] = turn
        before = environments.physical_snapshot(society.state)
        joint = {aid: {'tool': 'wait'} for aid in society.state['agents']}
        for aid in action_order(cfg, turn, joint):
            agent = society.state['agents'][aid]
            if not agent['alive']:
                continue
            if policy != 'wait' and agent['stock'] < 6:
                items = ['B'] if policy == 'fixed_B' else list(definition['resources'])
                held = []
                for item in items:
                    resource = definition['resources'][item]
                    amount = min(math.floor(agent['inventory'][item] + 1e-9),
                                 definition['max_quantity'], resource.get('liquidation_limit', definition['max_quantity']))
                    if amount >= 1:
                        held.append((amount * resource['energy_value'] * resource['liquidation_efficiency'], item, amount))
                if held:
                    _, item, amount = max(held)
                    joint[aid] = {'tool': 'liquidate', 'item': item, 'amount': amount}
                else:
                    choices = []
                    for item in items:
                        floor = (20 if item == 'B' else 5 if item == 'A' else 2 if item == 'Q' else 0) if policy == 'conservative' else 0
                        limit = 4 if policy == 'conservative' else definition['max_quantity']
                        amount = min(limit, math.floor(society.state['mini_world']['pools'].get(item, 0) - floor))
                        if amount >= 1:
                            choices.append((amount * definition['resources'][item]['energy_value'], item, amount))
                    if choices:
                        _, item, amount = max(choices)
                        joint[aid] = {'tool': 'gather', 'item': item, 'amount': amount}
            society.act(aid, joint[aid])
        society.settle(before)
        record = society.state['environment_history'][-1]
        rows.append({'round': turn, 'alive': sum(a['alive'] for a in society.state['agents'].values()),
                     'stock': sum(a['stock'] for a in society.state['agents'].values()),
                     'actions': copy.deepcopy(joint), 'pools': copy.deepcopy(society.state['mini_world']['pools']),
                     'replenishment': record['pool_replenishment'],
                     'energy_residual': record['energy_accounting']['residual']})
        plan.append(copy.deepcopy(joint))
    late = rows[25:]
    active = sum(a['tool'] != 'wait' for row in late for a in row['actions'].values())
    replenishment = [sum(n * definition['resources'][item]['energy_value'] for item, n in row['replenishment'].items()) for row in late]
    return {'final_alive': rows[-1]['alive'], 'population_time': sum(row['alive'] for row in rows),
            'late_active_actions': active, 'late_replenishment_energy_range': [min(replenishment), max(replenishment)],
            'final_stock': rows[-1]['stock'], 'rows': rows, 'plan': plan}


def main():
    output = Path('reports/pressure_tuning_20261010')
    output.mkdir(parents=True, exist_ok=True)
    source = json.loads(Path('runs/proportional_sol_low_4x10_20261010/config.json').read_text('utf-8'))
    source.pop('survival_certificate', None)
    source['rounds'] = 50
    summaries = []
    candidates = [('baseline', None, 50, 100), ('mild_B', None, 40, 80),
                  ('smaller_B', None, 30, 60)] + [(f'flow_{flow}', flow, 8, 16) for flow in [12, 8, 6, 4]]
    for name, flow, initial, capacity in candidates:
        cfg = copy.deepcopy(source)
        d = cfg['world']['mini_world']['definition']
        d['pools']['B'].update(initial=initial, capacity=capacity)
        if flow is not None:
            # Retain all twenty existing equations, including variable B regeneration.
            d['initial_reserve'] = 40
            d['external_inflow'] = flow
        cfg['actor_system'] += '不同材料之间存在相互关系，世界运行遵循自身规律；生产可能产生新的物质。'
        world_rule_engine.validate(cfg['world']['mini_world']['definition'])
        (output / f'{name}_config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')
        results = {policy: trajectory(cfg, policy) for policy in ['wait', 'fixed_B', 'adaptive', 'conservative']}
        (output / f'{name}_trajectories.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), 'utf-8')
        summary = {'candidate': name, 'policies': {p: {k: v for k, v in r.items() if k not in ['rows', 'plan']} for p, r in results.items()}}
        summaries.append(summary)
        print(json.dumps(summary), flush=True)
    (output / 'summary.json').write_text(json.dumps(summaries, ensure_ascii=False, indent=2), 'utf-8')


if __name__ == '__main__':
    main()

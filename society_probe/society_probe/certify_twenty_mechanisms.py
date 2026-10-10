"""Offline construction and Lean checks. No model calls; no optimality claim."""
import argparse
import copy
import json
import math
from pathlib import Path

import certify_composed_worlds
import sim
import environments
import world_rule_library as library
from capability_feasibility import action_order


def greedy_survival(cfg):
    society = sim.Society(cfg)
    plan = []
    d = cfg['world']['mini_world']['definition']
    for t in range(1, cfg['rounds']+1):
        society.state['round'] = t
        before = environments.physical_snapshot(society.state)
        joint = {aid: {'tool': 'wait'} for aid in society.state['agents']}
        for aid in action_order(cfg, t, joint):
            agent = society.state['agents'][aid]
            if agent['stock'] < 6:
                choices = [(min(math.floor(amount+1e-9), d['max_quantity'], d['resources'][item].get('liquidation_limit', d['max_quantity'])) *
                            d['resources'][item]['energy_value'] * d['resources'][item]['liquidation_efficiency'], item)
                           for item, amount in agent['inventory'].items() if amount >= 1]
                if choices:
                    _, item = max(choices)
                    joint[aid] = {'tool': 'liquidate', 'item': item,
                        'amount': min(math.floor(agent['inventory'][item]+1e-9), d['max_quantity'], d['resources'][item].get('liquidation_limit', d['max_quantity']))}
                else:
                    pools = society.state['mini_world']['pools']
                    choices = [(min(amount, d['max_quantity']) * d['resources'][item]['energy_value'], item)
                               for item, amount in pools.items() if amount >= 1]
                    if choices:
                        _, item = max(choices)
                        joint[aid] = {'tool': 'gather', 'item': item, 'amount': min(d['max_quantity'], math.floor(pools[item]))}
            society.act(aid, joint[aid])
        society.settle(before)
        if not all(a['alive'] for a in society.state['agents'].values()):
            raise ValueError('Greedy construction did not find full survival; not an infeasibility result')
        plan.append(copy.deepcopy(joint))
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--individuals', action='store_true')
    parser.add_argument('--horizon', type=int, default=20)
    args = parser.parse_args()
    output = Path('reports/twenty_mechanisms_20261010').resolve()
    output.mkdir(exist_ok=True)
    keys = [k for k, _ in library.CANDIDATES_20]
    batches = [[k] for k in keys] if args.individuals else [keys]
    summary = []
    for selected in batches:
        cfg = json.loads(Path('runs/sol_low_pilot_20261010/config.json').read_text('utf-8'))
        cfg.pop('survival_certificate', None)
        candidate = library.with_capabilities(library.generate(1, selected))
        cfg['world']['mini_world']['definition'] = candidate['definition']
        import functional_effects
        cfg['tools'] = sorted(set(cfg['tools']) | {'use_function'} | functional_effects.STORAGE_TOOLS)
        cfg['rounds'] = args.horizon
        cfg['experiment'].update(generation=candidate['generation'], stage='offline_mechanism_certificate')
        # Expose generator-added station modes through the existing generic interface.
        key = selected[0] if args.individuals else 'all_twenty'
        plan = greedy_survival(cfg)
        path = output / f'{key}_{args.horizon}rounds.json'
        bundle = certify_composed_worlds.certify(cfg, plan, path, semantic=True)
        row = {'modules': selected, 'horizon': args.horizon, 'members': 4,
               'status': bundle['lean']['status'], 'graph_nodes': bundle['lean']['graph_nodes']}
        summary.append(row)
        (output / f'{key}_{args.horizon}rounds_config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
        (output / ('individual_checks.json' if args.individuals else 'combined_check.json')).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(row, ensure_ascii=False), flush=True)
        if row['status'] != 'lean_checked_composed_interval_certificate':
            raise ValueError('Certificate rejected')


if __name__ == '__main__':
    main()

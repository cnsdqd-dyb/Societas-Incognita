"""Small all-twenty composition action check; artificial holdings, no API calls."""
import json
from pathlib import Path

import certify_composed_worlds
import world_rule_library as library


def main():
    root = Path('reports/material_combinations_20261010')
    root.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(Path('runs/proportional_sol_low_4x10_20261010/config.json').read_text('utf-8'))
    cfg.pop('survival_certificate', None)
    candidate = library.with_capabilities(library.generate(2, [k for k, _ in library.CANDIDATES_20]))
    d = candidate['definition']
    d['initial_inventory'] = {item: 16 for item in d['resources']}
    cfg['world']['mini_world']['definition'] = d
    cfg['world']['survival_pressure'] = False
    cfg['rounds'] = 3
    cfg['tools'] = sorted(set(cfg['tools']) | {'use_function'})
    entries = [e for e in d['combination_functions'] if e['kind'] == 'world_state']
    plan = [{f'a{i}': {'tool': 'use_function', 'function': entries[(i + t) % len(entries)]['id'],
                      'target': 'world', 'confirm': not (i == 3 and t == 0)} for i in range(4)} for t in range(3)]
    cfg['experiment'] = {'stage': 'offline_combination_action_check',
                         'generation': candidate['generation'],
                         'scope': 'Artificial holdings for branch coverage; not an exploration or natural-start survival result.'}
    bundle = certify_composed_worlds.certify(cfg, plan, root/'all_twenty_3rounds.json', semantic=True)
    (root/'all_twenty_3rounds_config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({'status': bundle['lean']['status'], 'graph_nodes': bundle['lean']['graph_nodes'],
                      'functions': len(entries), 'horizon': 3, 'members': 4}), flush=True)
    if bundle['lean']['status'] != 'lean_checked_composed_interval_certificate':
        raise RuntimeError('Combination action certificate rejected')


if __name__ == '__main__':
    main()

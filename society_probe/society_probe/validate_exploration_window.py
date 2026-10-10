"""Offline ecological calibration against the original seed-2 world. No API calls."""
import argparse
import copy
import csv
import json
from pathlib import Path

import environments
import mini_world
import sim
import world_rule_library as library


def trace(cfg, scenario):
    society = sim.Society(cfg)
    rows = []
    for turn in range(1, 51):
        society.state['round'] = turn
        before = environments.physical_snapshot(society.state)
        if scenario == 'early_extraction' and turn == 2:
            for aid in ('a0', 'a1', 'a2'):
                society.act(aid, {'tool': 'gather', 'item': 'A', 'amount': 8})
        society.settle(before)
        m = society.state['mini_world']
        rows.append({'round': turn, 'A': m['pools']['A'], 'B': m['pools']['B'],
            'reserve': m['reserve'], 'residual': mini_world.accounting(cfg, society.state)['residual']})
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', default='runs/functional_homogeneous_4x50_20261010/luna_low/config.json')
    p.add_argument('--output', default='reports/continuous_exploration_validation')
    args = p.parse_args()
    cfg = json.loads(Path(args.baseline).read_text('utf-8'))
    revised = copy.deepcopy(cfg)
    candidate = library.with_capabilities(library.generate(2, [k for k, _ in library.CANDIDATES_20]))
    revised['world']['mini_world']['definition'] = candidate['definition']
    revised['experiment']['generation'] = candidate['generation']
    revised['experiment'].update(stage='continuous_exploration_offline_validation', certificate_status='not_certified')
    revised.pop('campaign_budget_db', None)
    revised.pop('survival_certificate', None)
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    details = {}; rows = []
    for version, config in [('baseline', cfg), ('revised', revised)]:
        for scenario in ['unattended', 'early_extraction']:
            data = trace(config, scenario)
            details[version + ':' + scenario] = {'A_round_10': data[9]['A'],
                'A_round_25': data[24]['A'], 'A_round_50': data[-1]['A'],
                'min_A': min(r['A'] for r in data),
                'max_abs_conservation_residual': max(abs(r['residual']) for r in data)}
            rows.extend(dict(version=version, scenario=scenario, **r) for r in data)
    for scenario in ['unattended', 'early_extraction']:
        assert details['revised:' + scenario]['A_round_50'] > 1, details
        assert details['revised:' + scenario]['max_abs_conservation_residual'] < 1e-7
    (out/'validation.json').write_text(json.dumps({'scope': 'Two deterministic offline interventions, seed 2, 50 rounds; no discoverability or robust survival proof',
        'model_calls': 0, 'generation': candidate['generation'], 'scenarios': details}, ensure_ascii=False, indent=2), 'utf-8')
    (out/'revised_config.json').write_text(json.dumps(revised, ensure_ascii=False, indent=2), 'utf-8')
    with (out/'ecology_trajectories.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(json.dumps(details, ensure_ascii=False))


if __name__ == '__main__': main()

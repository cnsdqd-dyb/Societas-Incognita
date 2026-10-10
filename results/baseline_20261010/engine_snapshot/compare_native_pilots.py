"""Small matched-world comparison; descriptive results, not significance claims."""
import csv
import json
from collections import Counter
from pathlib import Path


def main():
    output = Path('reports/luna_sol_matched_20261010')
    output.mkdir(parents=True, exist_ok=True)
    summary, curves = [], []
    configs = []
    for name in ('luna', 'sol'):
        root = Path(f'runs/{name}_low_pilot_20261010')
        cfg = json.loads((root / 'config.json').read_text('utf-8'))
        configs.append({k: v for k, v in cfg.items() if k not in ('models', 'experiment', 'survival_certificate')})
        state = json.loads((root / 'simulation/checkpoint.json').read_text('utf-8'))['state']
        status = json.loads((root / 'runner_status.json').read_text('utf-8'))
        if state['round'] != cfg['rounds'] or status['status'] != 'complete':
            raise ValueError('Wait for the entire planned comparison run: ' + name)
        counts = Counter(e['decision']['action']['tool'] for e in state['events'])
        last = state['snapshots'][-1]['mini_world_metrics']
        row = {'model': cfg['models'][0], 'rounds': state['round'], 'seed': cfg['seed'],
               'alive': sum(a['alive'] for a in state['agents'].values()),
               'min_vitality': min(a['energy'] for a in state['agents'].values()),
               'total_vitality': sum(a['energy'] for a in state['agents'].values()),
               'total_liquid_energy': sum(a['stock'] for a in state['agents'].values()),
               'member_energy_equivalent': sum(last['energy_equivalent_by_member'].values()),
               'population_time': sum(sum(a['alive'] for a in s['agents'].values()) for s in state['snapshots']),
               'certified_feasible_population_time': len(cfg['models']) * cfg['rounds'],
               'invalid_actions': sum('action_error' in e['outcome'] for e in state['events']),
               'action_counts': dict(counts), 'successful_experiments': sum(last['successful_experiments'].values()),
               'item_trade_count': last['item_trade_count'],
               'assembled_devices': sum(len(devices) for devices in last['devices_by_owner'].values()),
               'material_types_directly_learned': last['material_types_directly_learned']}
        summary.append(row)
        for snap in state['snapshots']:
            curves.append({'model': cfg['models'][0], 'round': snap['round'],
                           'alive': sum(a['alive'] for a in snap['agents'].values()),
                           'total_vitality': sum(a['energy'] for a in snap['agents'].values()),
                           'liquid_energy': sum(a['stock'] for a in snap['agents'].values()),
                           'member_energy_equivalent': sum(snap['mini_world_metrics']['energy_equivalent_by_member'].values())})
    if configs[0] != configs[1]:
        raise ValueError('Environment parameters differ')
    report = {'matched_environment_parameters': True, 'results': summary,
              'interpretation': 'Single seed and ten rounds, descriptive comparison only. Vitality is separate from physical energy. Full-survival witness is not a certificate for knowledge or social organization.'}
    (output / 'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with (output / 'per_round.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(curves[0]))
        writer.writeheader()
        writer.writerows(curves)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

"""Offline, per-settled-round accounting diagnostics; no viability solver claims."""
import csv
import json
from collections import Counter
from pathlib import Path


def analyze(folder):
    cfg = json.loads((folder / 'config.json').read_text(encoding='utf-8'))
    path = folder / 'failed_state.json'
    if not path.exists():
        path = folder / 'checkpoint.json'
    state = json.loads(path.read_text(encoding='utf-8'))['state']
    world = cfg['world']
    snapshots = {s['round']: s['agents'] for s in state['snapshots']}
    previous = {i: {'stock': world.get('initial_personal_stock', 4), 'alive': True}
                for i in state['agents']}
    rows = []
    for record in state['environment_history']:
        t = record['round']
        if t not in snapshots:
            continue
        current = snapshots[t]
        events = [e for e in state['events'] if e['round'] == t]
        successful = [e for e in events if 'action_error' not in e['outcome']]
        tools = Counter(e['decision']['action']['tool'] for e in successful)
        inflow = sum(record['inflows'].values())
        cost = extraction = 0.
        family = world['mechanism']
        if family == 'commons':
            extraction = (record['physical_before_actions']['pool'] + record['growth']
                          - record['pool'] - record['capacity_loss'])
        elif family == 'public_goods':
            cost = sum(record['contributions'].values())
        elif family == 'contest':
            cost = record['dissipated_cost']
        elif family == 'congestion':
            cost = tools['process'] * world['input_cost']
        consumed = sum(a['consumed'] for a in record['maintenance'].values())
        stocks = sum(a['stock'] for a in current.values())
        delta = stocks - sum(a['stock'] for a in previous.values())
        expected = inflow + extraction - cost - consumed
        if abs(delta - expected) > 1e-7:
            raise ValueError(f'Accounting mismatch {folder} round {t}: {delta} vs {expected}')
        alive_before = sum(a['alive'] for a in previous.values())
        demand = alive_before * world['consumption'] if world['survival_pressure'] else 0.
        row = {'run': folder.parent.name, 'family': family,
               'pressure': world['survival_pressure'], 'round': t,
               'alive': sum(a['alive'] for a in current.values()),
               'total_stock': stocks, 'stock_change': delta,
               'inflow': inflow, 'extraction': extraction, 'action_cost': cost,
               'maintenance_consumed': consumed,
               'maintenance_shortfall': demand - consumed,
               'new_deaths': alive_before - sum(a['alive'] for a in current.values()),
               'rejected_actions': len(events) - len(successful),
               'inspect_actions': tools['inspect'], 'process_actions': tools['process'],
               'min_energy_alive': min((a['energy'] for a in current.values() if a['alive']), default=None),
               'pool': record.get('pool'), 'growth': record.get('growth'),
               'regeneration_minus_actual_extraction': record.get('growth', 0) - extraction if family == 'commons' else None,
               'growth_minus_current_demand': record['growth'] - demand if family == 'commons' else None,
               'contest_effort': sum(record['efforts'].values()) if family == 'contest' else None,
               'full_maintenance_net_flow': inflow + extraction - cost - demand,
               'unfinished_jobs': record.get('unfinished_jobs'),
               'facility_loads': json.dumps(record.get('loads', {}), sort_keys=True)}
        rows.append(row)
        previous = current
    if not rows:
        raise ValueError('No settled trajectory')
    first = lambda key: next((r['round'] for r in rows if r[key] > 1e-8), None)
    summary = {'run': folder.parent.name, 'family': world['mechanism'],
               'pressure': world['survival_pressure'], 'last_settled_round': rows[-1]['round'],
               'alive_last': rows[-1]['alive'], 'stock_last': rows[-1]['total_stock'],
               'first_maintenance_shortfall': first('maintenance_shortfall'),
               'first_death': first('new_deaths'),
               'negative_full_maintenance_flow_rounds': sum(r['full_maintenance_net_flow'] < -1e-8 for r in rows),
               'total_maintenance_shortfall': sum(r['maintenance_shortfall'] for r in rows),
               'rejected_actions': sum(r['rejected_actions'] for r in rows),
               'inspect_actions': sum(r['inspect_actions'] for r in rows),
               'process_actions': sum(r['process_actions'] for r in rows),
               'checkpoints': [r for r in rows if r['round'] in (5, 10, 15, 20, 30, 40, 50)]}
    return summary, rows


def main():
    root = Path('runs/core_campaign_v6_50rounds_20261007')
    summaries, rows = [], []
    for folder in sorted(root.glob('*/simulation')):
        summary, series = analyze(folder)
        summaries.append(summary)
        rows.extend(series)
    output = Path('../../refine-logs/PHYSICAL_TRAJECTORY_ANALYSIS_20261007')
    output.with_suffix('.json').write_text(json.dumps({
        'scope': 'Settled rounds only; exact stock accounting verified. Technical failures censor trajectories.',
        'runs': summaries}, ensure_ascii=False, indent=2), encoding='utf-8')
    with output.with_suffix('.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({'runs': len(summaries), 'verified_rounds': len(rows)}))
    for summary in summaries:
        if summary['pressure']:
            print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()

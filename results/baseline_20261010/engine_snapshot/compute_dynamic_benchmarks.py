"""Certified extrema or explicitly bounded extrema for existing trajectories.

Exact survival upper certificates combine the population cap and executable
witnesses. Exact lower certificates use universal bounds plus attained paths.
Public-goods wealth bounds are analytic; sampled policies are never called optima.
"""
import csv
import json
import math
from pathlib import Path

import environments
from sim import Society
from state_assessment import rollout


def policy(cfg, kind):
    w = cfg['world']
    def choose(state, step):
        alive = [i for i, a in state['agents'].items() if a['alive']]
        if kind == 'wait':
            return {}
        if kind == 'concentrate':
            # Whole stocks are integer in commons/congestion while no production.
            anchor = 'a0'
            if step == 1:
                return {i: {'tool': 'transfer', 'target': anchor,
                            'amount': math.floor(state['agents'][i]['stock'])}
                        for i in alive if i != anchor and state['agents'][i]['stock'] >= 1}
            return {}
        if kind == 'monopoly':
            return {'a0': {'tool': 'allocate', 'amount': 1}} if 'a0' in alive else {}
        if kind == 'delayed_crowding':
            if step == 3:
                return {i: {'tool': 'process', 'facility': 0} for i in alive}
            return {}
        if w['mechanism'] == 'commons':
            return {i: {'tool': 'harvest', 'zone': 0, 'amount': 1} for i in alive}
        if w['mechanism'] in ('public_goods', 'contest'):
            return {}
        return {i: {'tool': 'process', 'facility': int(i[1:]) % w['facilities']}
                for i in alive if i not in state['mechanism_state']['jobs']
                and state['agents'][i]['stock'] >= w['input_cost']}
    return choose


def compact_initial(cfg):
    # Keep all physical auxiliaries: pruning vaults, escrow or rescue schedules
    # changes the transition function and can invalidate a feasibility witness.
    return Society(cfg).state


def certified_rows(cfg, snapshots, name):
    if (cfg.get('resource_seizure') or cfg.get('social_content') or cfg.get('rescue',{}).get('enabled')
            or cfg.get('open_activities') or cfg.get('open_contest') or cfg.get('mixed_world')
            or cfg['world']['mechanism'] not in ('commons','public_goods','contest','congestion')):
        raise ValueError('Legacy certificate does not cover this extended action space; derive new bounds')
    n = len(cfg['models'])
    horizon = max(s['round'] for s in snapshots)
    family, pressured = cfg['world']['mechanism'], cfg['world']['survival_pressure']
    kinds = ['balanced', 'wait']
    if family == 'contest':
        kinds += ['monopoly']
    if family in ('commons', 'congestion'):
        kinds += ['concentrate']
    if family == 'congestion':
        kinds += ['delayed_crowding']
    paths = {k: rollout(cfg, compact_initial(cfg), policy(cfg, k), horizon) for k in kinds}
    for result in paths.values():
        if any(t['action_errors'] for t in result['trace']):
            raise ValueError('Benchmark witness contains an illegal action')
    # A legal witness reaching the universal population cap proves exact maximum.
    if not paths['balanced']['all_initial_living_survive']:
        raise ValueError('Population-cap optimality certificate failed')
    cumulative_actual, rows = 0, []
    path_cumulative = {k: 0 for k in kinds}
    for snapshot in sorted(snapshots, key=lambda s: s['round']):
        t = snapshot['round']
        agents = snapshot['agents']
        actual_alive = sum(a['alive'] for a in agents.values())
        cumulative_actual += actual_alive
        alive_counts = {k: sum(a['alive'] for a in r['trace'][t - 1]['agents'].values()) for k, r in paths.items()}
        for k in kinds:
            path_cumulative[k] += alive_counts[k]
        if not pressured or family == 'public_goods':
            lower = n
            lower_reason = 'No energy depletion without pressure; private_supply>=consumption for public goods.'
        elif t < 5:
            lower = n
            lower_reason = 'Initial energy=5; at most one energy loss per round.'
        elif family == 'contest' and cfg['world']['supply'] >= n * cfg['world']['consumption']:
            lower = 1
            lower_reason = 'Post-action stock sum>=supply>=living demand: at least one member fully fed each round.'
        else:
            lower = 0
            lower_reason = 'Universal nonnegative population bound.'
        upper_on_minimum = min(actual_alive, *alive_counts.values())
        if lower > upper_on_minimum:
            raise ValueError('Lower certificate contradicted by a trajectory')
        exact_min = lower == upper_on_minimum
        flat = lower == n
        if exact_min and not flat:
            position_low = position_high = (actual_alive - lower) / (n - lower)
        elif flat:
            position_low = position_high = None
        else:
            position_high = (actual_alive - lower) / (n - lower)
            position_low = ((actual_alive - upper_on_minimum) / (n - upper_on_minimum)
                            if upper_on_minimum < n else None)
            if actual_alive == n:
                position_low = position_high = 1. if upper_on_minimum < n else None
        cum_lower = n * t if flat else n * min(t, 4) + (max(0, t - 4) if family == 'contest' else 0)
        cum_upper_min = min(cumulative_actual, *path_cumulative.values())
        row = {'run': name, 'family': family, 'pressure': pressured, 'round': t,
               'actual_alive': actual_alive, 'optimal_alive_exact': n,
               'worst_alive_lower_bound': lower, 'worst_alive_upper_bound': upper_on_minimum,
               'worst_alive_exact': exact_min, 'lower_bound_reason': lower_reason,
               'survival_range_position_lower': position_low, 'survival_range_position_upper': position_high,
               'survival_gap_exact': n - actual_alive,
               'actual_survivor_rounds': cumulative_actual, 'optimal_survivor_rounds_exact': n * t,
               'worst_survivor_rounds_lower_bound': cum_lower,
               'worst_survivor_rounds_upper_bound': cum_upper_min,
               'worst_survivor_rounds_exact': cum_lower == cum_upper_min,
               'survivor_round_gap_exact': n * t - cumulative_actual,
               'actual_total_stock': sum(a['stock'] for a in agents.values()),
               'stock_min_exact': None, 'stock_max_exact': None, 'stock_range_position': None,
               'min_attaining_policy': min(alive_counts, key=alive_counts.get)}
        if family == 'public_goods':
            w = cfg['world']
            d = w['consumption'] if pressured else 0.
            # All are fully maintained: b>=d. All max contributions stay affordable.
            lo = n * w['initial_personal_stock'] + n * (w['private_supply'] - d) * t
            hi = lo + (w['multiplier'] - 1) * n * w['max_contribution'] * t
            if w['private_supply'] < d or w['initial_personal_stock'] < w['max_contribution']:
                raise ValueError('Public-good certificate assumptions do not hold')
            row.update(stock_min_exact=lo, stock_max_exact=hi,
                       stock_range_position=(row['actual_total_stock'] - lo) / (hi - lo))
            if not lo - 1e-7 <= row['actual_total_stock'] <= hi + 1e-7:
                raise ValueError('Actual wealth outside certified extrema')
        rows.append(row)
    return rows, {k: {'first_death_round': r['first_death_round'],
                      'final_alive': sum(a['alive'] for a in r['trace'][-1]['agents'].values())}
                  for k, r in paths.items()}


def main():
    root = Path('runs/core_campaign_v6_50rounds_20261007')
    rows, witnesses = [], {}
    for folder in sorted(root.glob('*/simulation')):
        cfg = json.loads((folder / 'config.json').read_text(encoding='utf-8'))
        path = folder / 'failed_state.json'
        if not path.exists():
            path = folder / 'checkpoint.json'
        state = json.loads(path.read_text(encoding='utf-8'))['state']
        snapshots = sorted(state['snapshots'], key=lambda s: s['round'])
        if [s['round'] for s in snapshots] != list(range(1, snapshots[-1]['round'] + 1)):
            raise ValueError('Settled snapshots are not contiguous')
        series, proof = certified_rows(cfg, snapshots, folder.parent.name)
        rows += series
        witnesses[folder.parent.name] = proof
    out = Path('../../refine-logs/CERTIFIED_DYNAMIC_BENCHMARKS_20261007')
    out.with_suffix('.json').write_text(json.dumps({'scope': 'Full-information physical benchmarks; no API calls. Bounds explicitly distinguished from exact extrema.',
        'rows': rows, 'witnesses': witnesses}, ensure_ascii=False, indent=2), encoding='utf-8')
    with out.with_suffix('.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), constrained_layout=True)
    survival_cases = [('commons_p1_basic_s7', 'Commons, basic, seed7'),
                      ('contest_p1_basic_s7', 'Contest, basic, seed7'),
                      ('contest_p1_information_s7', 'Contest, information, seed7'),
                      ('congestion_p1_information_s7', 'Congestion, information, seed7')]
    for name, label in survival_cases:
        series = [r for r in rows if r['run'] == name and r['worst_alive_exact']
                  and r['survival_range_position_lower'] is not None]
        axes[0].plot([r['round'] for r in series], [r['survival_range_position_lower'] for r in series], label=label)
    for name, label in [('public_goods_p1_basic_s7', 'Public goods, seed7 (q=2.0)'),
                        ('public_goods_p1_basic_s17', 'Public goods, seed17 (q=2.2)')]:
        series = [r for r in rows if r['run'] == name]
        axes[1].plot([r['round'] for r in series], [r['stock_range_position'] for r in series], label=label)
    for ax, title in zip(axes, ['Survival: exact attainable envelope', 'Wealth: exact attainable envelope']):
        ax.set(xlabel='Settled round', ylabel='Position between worst (0) and best (1)',
               title=title, ylim=(-.03, 1.03))
        ax.grid(alpha=.2)
        ax.legend(fontsize=7, loc='best')
    fig.savefig(out.with_suffix('.png'), dpi=200)
    fig.savefig(out.with_suffix('.svg'))
    plt.close(fig)
    print(json.dumps({'runs': len(witnesses), 'settled_rounds': len(rows),
                      'exact_survival_envelopes': sum(r['worst_alive_exact'] for r in rows)}))
    for row in rows:
        if row['run'] in ('commons_p1_basic_s7', 'commons_p1_information_s7',
                         'contest_p1_basic_s7', 'contest_p1_information_s7',
                         'congestion_p1_information_s7', 'public_goods_p1_basic_s7', 'public_goods_p1_basic_s17') and row['round'] in (10, 20, 40, 48, 50):
            print(json.dumps(row, ensure_ascii=False))


if __name__ == '__main__':
    main()

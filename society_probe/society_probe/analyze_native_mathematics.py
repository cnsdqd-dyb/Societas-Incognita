"""Offline certified survival envelopes and exact conditional congestion analysis."""
import collections
import copy
import csv
import json
import math
from pathlib import Path

from sim import Society
import environments
from compute_dynamic_benchmarks import certified_rows
from metrics import measure
from native_codex import write_json


ROOT = Path('runs/codex_gpt61_sol_low_8x50_20261007')


def replay(cfg, saved, remove_transfers=False):
    society = Society(cfg)
    events = collections.defaultdict(list)
    for event in saved['events']:
        events[event['round']].append(event)
    snapshots = {s['round']: s for s in saved['snapshots']}
    states, batches, changed = [], [], []
    for t in range(1, saved['round'] + 1):
        society.state['round'] = t
        before = environments.physical_snapshot(society.state)
        old_loads = [sum(j['facility'] == f for j in society.state['mechanism_state']['jobs'].values()) for f in range(2)]
        launches = [0, 0]
        for event in events[t]:
            action = event['decision']['action']
            if remove_transfers and action['tool'] == 'transfer' and 'action_error' not in event['outcome']:
                changed.append({'round': t, 'agent': event['agent'], 'original': action})
                action = {'tool': 'wait'}
            try:
                society.act(event['agent'], action)
            except (ValueError, KeyError, TypeError) as exc:
                if remove_transfers:
                    return {'feasible_replay': False, 'failed_round': t, 'agent': event['agent'], 'error': str(exc), 'changed': changed}
                if 'action_error' not in event['outcome']:
                    raise
            else:
                if not remove_transfers and 'action_error' in event['outcome']:
                    raise ValueError('Replay acceptance mismatch')
                if action['tool'] == 'process':
                    launches[action.get('facility', action.get('args', {}).get('facility'))] += 1
        w = cfg['world']
        def delay(k0):
            counts = [k0, sum(launches) - k0]
            return sum(k * (w['base_duration'] + w['load_delay'] * (b + k - 1)) for b, k in zip(old_loads, counts))
        k = sum(launches)
        if k:
            costs = [delay(k0) for k0 in range(k + 1)]
            actual, low, high = delay(launches[0]), min(costs), max(costs)
            batches.append({'round': t, 'old_loads': old_loads, 'new_launches': launches,
                            'jobs_started': k, 'planned_delay_actual': actual,
                            'planned_delay_min_exact': low, 'planned_delay_max_exact': high,
                            'avoidable_planned_delay_exact': actual - low,
                            'conditional_efficiency_position': (high - actual)/(high - low) if high != low else None,
                            'minimizing_launches': [costs.index(low), k - costs.index(low)]})
        society.settle(before)
        physical = {i: {k: a[k] for k in ('stock', 'energy', 'alive')} for i, a in society.state['agents'].items()}
        if not remove_transfers and physical != snapshots[t]['agents']:
            raise ValueError('Physical snapshot mismatch')
        margins = {}
        for aid, job in society.state['mechanism_state']['jobs'].items():
            a = society.state['agents'][aid]
            funded = math.floor((a['stock'] + 1e-9)/w['consumption'])
            runway = funded + min(5, a['energy'] + funded)
            margins[aid] = runway - job['remaining']
        states.append({'round': t, 'agents': physical, 'jobs': copy.deepcopy(society.state['mechanism_state']['jobs']),
                       'minimum_pending_job_wait_margin': min(margins.values()) if margins else None,
                       'pending_job_wait_margins': margins})
    return {'feasible_replay': True, 'states': states, 'batches': batches, 'changed': changed}


def analyze(name, folder):
    cfg = json.loads((folder/'config.json').read_text('utf-8'))
    saved = json.loads((folder/'checkpoint.json').read_text('utf-8'))['state']
    envelopes, witnesses = certified_rows(cfg, saved['snapshots'], name)
    replayed = replay(cfg, saved)
    metrics = measure(saved, cfg)
    rows = []
    for bound, physical, metric in zip(envelopes, replayed['states'], metrics['round_series']):
        t = bound['round']
        actions = [e['decision']['action']['tool'] for e in saved['events'] if max(0, t-5) < e['round'] <= t and 'action_error' not in e['outcome']]
        counts = collections.Counter(actions)
        entropy = -sum((count/len(actions))*math.log2(count/len(actions)) for count in counts.values()) if actions else None
        rows.append({**bound, 'minimum_pending_job_wait_margin': physical['minimum_pending_job_wait_margin'],
                     'stock_gini_alive': metric['stock_gini_alive'], 'tool_entropy_5round_bits': entropy,
                     'mean_behavior_surprisal_5round_bits': metric['mean_behavior_surprisal_bits']})
    periods = []
    for start in range(1, 51, 10):
        batches = [b for b in replayed['batches'] if start <= b['round'] <= start+9]
        actual = sum(b['planned_delay_actual'] for b in batches)
        low = sum(b['planned_delay_min_exact'] for b in batches)
        high = sum(b['planned_delay_max_exact'] for b in batches)
        periods.append({'rounds': [start, start+9], 'jobs_started': sum(b['jobs_started'] for b in batches),
                        'delay_actual': actual, 'delay_conditional_min': low, 'delay_conditional_max': high,
                        'avoidable_delay': actual-low,
                        'conditional_position': (high-actual)/(high-low) if high != low else None})
    actual = sum(b['planned_delay_actual'] for b in replayed['batches'])
    low = sum(b['planned_delay_min_exact'] for b in replayed['batches'])
    high = sum(b['planned_delay_max_exact'] for b in replayed['batches'])
    return {'name': name, 'survival_series': rows, 'survival_certificates': witnesses,
            'assignment_batches': replayed['batches'], 'assignment_periods': periods,
            'assignment_total': {'jobs_started': sum(b['jobs_started'] for b in replayed['batches']),
                'planned_delay_actual': actual, 'sum_conditional_minima': low, 'sum_conditional_maxima': high,
                'avoidable_planned_delay': actual-low, 'conditional_position': (high-actual)/(high-low) if high != low else None},
            'pending_job_wait_margins': [{'round': s['round'], 'margins': s['pending_job_wait_margins']} for s in replayed['states']]}


def main():
    outputs = [analyze('gpt61_sol_low_native', ROOT/'simulation'),
               analyze('gpt_oss20b_coreweave', Path('runs/gpt_oss20b_pilot_coreweave_20261007/simulation'))]
    cfg = json.loads((ROOT/'simulation/config.json').read_text('utf-8'))
    saved = json.loads((ROOT/'simulation/checkpoint.json').read_text('utf-8'))['state']
    ablated = replay(cfg, saved, remove_transfers=True)
    if ablated['feasible_replay']:
        final = ablated['states'][-1]['agents']
        ablated = {'feasible_replay': True, 'changed': ablated['changed'],
                   'final_alive': sum(a['alive'] for a in final.values()),
                   'survivor_rounds': sum(sum(a['alive'] for a in s['agents'].values()) for s in ablated['states']),
                   'final_agents': final,
                   'scope': 'Exact open-loop replay: remove transfers, hold all subsequent physical actions and execution order fixed; not a resampled LLM policy.'}
    result = {'runs': outputs, 'no_transfer_open_loop_replay': ablated,
              'scope': 'Initial-state survival bounds are certified. Delay extrema are exact conditional per-state assignment extrema holding launch timing/counts fixed; their sums are NOT global 50-round extrema. Entropy and Gini are descriptive, not thermodynamic entropy or organization optimality.'}
    write_json(ROOT/'mathematical_analysis.json', result)
    all_rows = [r for run in outputs for r in run['survival_series']]
    with (ROOT/'mathematical_survival_series.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
        writer.writeheader(); writer.writerows(all_rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    for run in outputs:
        rows = run['survival_series'];label = run['name']
        axes[0,0].plot([r['round'] for r in rows], [r['actual_alive'] for r in rows], label=label)
        exact = [r for r in rows if r['worst_alive_exact'] and r['survival_range_position_lower'] is not None]
        axes[0,1].plot([r['round'] for r in exact], [r['survival_range_position_lower'] for r in exact], label=label)
        periods = run['assignment_periods']
        axes[1,0].plot([p['rounds'][1] for p in periods], [p['conditional_position'] for p in periods], 'o-', label=label)
        axes[1,1].plot([r['round'] for r in rows], [r['tool_entropy_5round_bits'] for r in rows], label=label)
    for ax, title, ylabel in zip(axes.flat, ['Survival', 'Certified survival position', 'Conditional facility-assignment efficiency', 'Descriptive action entropy (5 rounds)'], ['Living members', 'Position in attainable envelope', 'Best/worst assignment position', 'Bits']):
        ax.set(xlabel='Settled round', ylabel=ylabel, title=title);ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.savefig(ROOT/'mathematical_analysis.png', dpi=180)
    fig.savefig(ROOT/'mathematical_analysis.svg');plt.close(fig)
    for run in outputs:
        print(run['name'], 'assignment_total', json.dumps(run['assignment_total']))
        print('periods', json.dumps(run['assignment_periods']))
        for row in run['survival_series']:
            if row['round'] in [10,20,30,40,50]: print('point',json.dumps(row))
    print('no_transfer_replay',json.dumps(ablated,ensure_ascii=True))


if __name__ == '__main__':
    main()

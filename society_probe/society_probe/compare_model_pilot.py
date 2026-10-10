"""Compare settled GPT-OSS and Ministral trajectories; censor incomplete rounds."""
import csv
import json
from collections import Counter
from pathlib import Path

from compute_dynamic_benchmarks import certified_rows
from metrics import measure
from sim import entropy
from process_guard import alive as process_alive


def inspect(folder, label):
    cfg = json.loads((folder / 'config.json').read_text(encoding='utf-8'))
    # Failure artifacts remain historical after a resume; use the latest settled state.
    candidates = [json.loads(p.read_text(encoding='utf-8'))['state']
                  for p in (folder / 'checkpoint.json', folder / 'failed_state.json') if p.exists()]
    state = max(candidates, key=lambda s: max((t['round'] for t in s['snapshots']), default=0))
    snapshots = state['snapshots']
    if not snapshots:
        return {'model': label, 'completed_rounds': 0, 'status': 'starting'}, []
    benchmarks, _ = certified_rows(cfg, snapshots, label)
    descriptive = {r['round']: r for r in measure(state, cfg)['round_series']}
    rows = []
    for b in benchmarks:
        t = b['round']
        events = [e for e in state['events'] if max(0, t - 5) < e['round'] <= t]
        tools = [e['decision']['action']['tool'] for e in events if 'action_error' not in e['outcome']]
        row = {k: b[k] for k in ('round', 'actual_alive', 'survival_gap_exact',
                                'survival_range_position_lower', 'survival_range_position_upper',
                                'actual_survivor_rounds', 'survivor_round_gap_exact', 'actual_total_stock')}
        row['model'] = label
        row['tool_entropy_bits_5_rounds'] = entropy(tools)
        row['accepted_actions_5_rounds'] = len(tools)
        row['rejected_actions_5_rounds'] = len(events) - len(tools)
        row['mean_behavior_surprisal_bits'] = descriptive[t]['mean_behavior_surprisal_bits']
        row['stock_gini_alive'] = descriptive[t]['stock_gini_alive']
        rows.append(row)
    last = snapshots[-1]['round']
    owner=folder.parent/'launch_owner.json'
    running=owner.exists() and process_alive(json.loads(owner.read_text(encoding='utf-8'))['pid'])
    events = [e for e in state['events'] if e['round'] <= last]
    accounting = json.loads((folder / 'api_accounting.json').read_text(encoding='utf-8'))
    summary = {'model': label, 'completed_rounds': last,
               'status': 'complete' if (folder / 'result.json').exists() else 'running' if running else 'failed',
               'alive': rows[-1]['actual_alive'], 'survivor_rounds': rows[-1]['actual_survivor_rounds'],
               'survivor_round_gap': rows[-1]['survivor_round_gap_exact'],
               'actions': len(events), 'rejected_actions': sum('action_error' in e['outcome'] for e in events),
               'public_message_actions': sum(e['decision']['communication']['op']=='public' for e in events),
               'private_message_actions': sum(bool(e['outcome'].get('private_recipients')) for e in events),
               'successful_transfers': sum(e['outcome'].get('action',{}).get('transferred',0)>0 for e in events),
               'action_tools': dict(Counter(e['decision']['action']['tool'] for e in events)),
               'cost_usd': accounting['cost_usd'], 'reserved_usd': accounting.get('reserved_usd', 0),
               'survey_protocol': cfg['survey_protocol'], 'surveys': len(state['surveys']),
               'checkpoints': [r for r in rows if r['round'] in (5, 10, 15, 20, 30, 40, 50)]}
    if cfg['survey_protocol']=='source_informed_v3':
        answers=[a for a in state['surveys'] if a['round']>0]
        summary['postbaseline_group_detection']=dict(Counter(a['responses']['group_detection'] for a in answers))
        summary['postbaseline_arrangement_detection']=dict(Counter(a['responses']['arrangement_detection'] for a in answers))
    calls_file = folder / 'calls.jsonl'
    if calls_file.exists():
        calls = [json.loads(line) for line in calls_file.read_text(encoding='utf-8').splitlines()]
        summary['providers'] = dict(Counter(c.get('provider') for c in calls))
        summary['empty_responses'] = sum(not c['response'] for c in calls)
        summary['prompt_tokens'] = sum(c.get('usage', {}).get('prompt_tokens', 0) for c in calls)
        summary['completion_tokens'] = sum(c.get('usage', {}).get('completion_tokens', 0) for c in calls)
        summary['reasoning_tokens'] = sum(c.get('usage', {}).get('completion_tokens_details', {}).get('reasoning_tokens', 0) for c in calls)
    return summary, rows


def main():
    gpt = Path('runs/gpt_oss20b_pilot_coreweave_20261007/simulation')
    if not (gpt / 'checkpoint.json').exists():
        gpt = Path('runs/gpt_oss20b_pilot_20261007/simulation')
    cases = [('Ministral-3B', Path('runs/core_campaign_v6_50rounds_20261007/congestion_p1_information_s7/simulation')),
             ('GPT-OSS-20B', gpt)]
    summaries, rows = [], []
    for label, folder in cases:
        summary, series = inspect(folder, label)
        summaries.append(summary)
        rows.extend(series)
    out = Path('../../refine-logs/GPT_OSS_20B_COMPARISON_20261007')
    out.with_suffix('.json').write_text(json.dumps({'scope': 'One environment, seed7, 8 agents, 50-round target. Model-family pilot, not a parameter-size causal test. Different private survey protocols; rolling tool entropy is descriptive.',
        'runs': summaries}, ensure_ascii=False, indent=2), encoding='utf-8')
    with out.with_suffix('.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5), constrained_layout=True)
    for label, _ in cases:
        series = [r for r in rows if r['model'] == label]
        axes[0].step([r['round'] for r in series], [r['actual_alive'] for r in series], where='post', label=label)
        meaningful = [r for r in series if r['tool_entropy_bits_5_rounds'] is not None]
        axes[1].plot([r['round'] for r in meaningful], [r['tool_entropy_bits_5_rounds'] for r in meaningful], label=label)
    axes[0].axhline(8, color='black', linestyle=':', label='Certified survival optimum')
    axes[0].set(title='Congestion, pressure, information tools', xlabel='Settled round', ylabel='Surviving initial members', ylim=(-.2, 8.5))
    axes[1].set(title='Descriptive tool entropy (5-round window)', xlabel='Settled round', ylabel='Shannon entropy, bits', ylim=(0, 2.1))
    for ax in axes:
        ax.grid(alpha=.2)
        ax.legend(fontsize=7)
    fig.savefig(out.with_suffix('.png'), dpi=180)
    plt.close(fig)
    for summary in summaries:
        print(json.dumps({k: v for k, v in summary.items() if k != 'checkpoints'}, ensure_ascii=False))


if __name__ == '__main__':
    main()

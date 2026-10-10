"""Offline progress and behavior comparison; no model calls or imputed surveys."""
import argparse
import collections
import csv
import json
from pathlib import Path


def analyze(root, plot=False):
    from metrics import measure
    from native_codex import write_json
    groups = []
    trajectory_rows = []
    campaign = json.loads((root / 'manifest.json').read_text('utf-8'))
    for label in [g['group'] for g in campaign['groups']]:
        folder = root / campaign.get('group_directories', {}).get(label, label)
        cfg = json.loads((folder / 'config.json').read_text('utf-8'))
        status_path = folder / 'runner_status.json'
        status = json.loads(status_path.read_text('utf-8')) if status_path.exists() else {'status': 'not_started'}
        row = {'group': label, 'model': cfg['models'][0] if len(set(cfg['models'])) == 1 else 'mixed4',
               'models': cfg['models'], 'population_type': 'homogeneous' if len(set(cfg['models'])) == 1 else 'mixed',
               'pressure': cfg['world']['survival_pressure'],
               'runner_status': status['status'],
               'completed_rounds': 0, 'target_rounds': 50, 'alive': 4}
        if 'error' in status:
            row['runner_error'] = status['error']
        output = folder / 'simulation'
        cp = output / 'checkpoint.json'
        if not cp.exists():
            groups.append(row)
            continue
        state = json.loads(cp.read_text('utf-8'))['state']
        # Only durable completed physical rounds count as completed progress.
        snapshots = [s for s in state['snapshots'] if s['round'] > 0]
        t = max((s['round'] for s in snapshots), default=0)
        events = [e for e in state['events'] if e['round'] <= t]
        valid = [e for e in events if 'action_error' not in e['outcome']]
        chosen = collections.Counter(e['decision']['action']['tool'] for e in events)
        successful = collections.Counter(e['decision']['action']['tool'] for e in valid)
        population_time = sum(sum(a['alive'] for a in s['agents'].values()) for s in snapshots)
        accounting_path = output / 'api_accounting.json'
        accounting = json.loads(accounting_path.read_text('utf-8')) if accounting_path.exists() else {}
        calls_path = output / 'calls.jsonl'
        calls = []
        if calls_path.exists():
            for line in calls_path.read_text('utf-8').splitlines():
                try:
                    calls.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        usage = collections.Counter()
        for call in calls:
            for key, value in call.get('usage', {}).items():
                if isinstance(value, (int, float)):
                    usage[key] += value
        known_functions = {aid: sorted(a.get('function_knowledge', {})) for aid, a in state['agents'].items()}
        observations = sum(len(records) for records in state['mini_world'].get('discoveries', {}).values())
        row.update(completed_rounds=t, alive=sum(a['alive'] for a in state['agents'].values()),
            attempted_actions=dict(chosen), successful_actions=dict(successful),
            invalid_actions=len(events)-len(valid),
            population_time_actual=population_time, population_time_prefix_upper=4*t,
            survival_attainment_prefix=population_time/(4*t) if t else None,
            survival_deficit_prefix=4*t-population_time,
            population_time_50round_upper=200,
            reference_scope='Same-configuration legal full-survival runtime witness attains 200; no Lean or wealth optimum claim',
            total_liquid_energy_all_members=sum(a['stock'] for a in state['agents'].values()),
            total_liquid_energy_alive=sum(a['stock'] for a in state['agents'].values() if a['alive']),
            direct_experiment_observations=observations, known_functions=known_functions,
            confirmed_function_uses=sum(e['decision']['action']['tool'] == 'use_function'
                and e['decision']['action'].get('confirm', False) for e in valid),
            works_created=sum(e.get('op') == 'create' for e in state.get('social_content', {}).get('work_events', [])),
            communication_ops=dict(collections.Counter(e['communication']['op']
                for e in state.get('communication_events', []) if e['round'] <= t and 'communication_error' not in e['outcome'])),
            requests_attempted=accounting.get('calls', 0), returned_replies=len(calls),
            external_api_cost_usd=accounting.get('cost_usd', 0),
            reserved_external_usd=accounting.get('reserved_usd', 0),
            native_cost_usd=None if cfg['backend'] in ('codex_native_cli', 'hybrid_codex_openrouter') else 0,
            usage=dict(usage),
            energy_ledger_max_abs_residual=max((abs(e.get('energy_accounting', {}).get('residual', 0))
                for e in state.get('environment_history', [])), default=0),
            behavior_metrics=measure(state, cfg))
        replay_path = folder / 'recorded_replay/replay_verification.json'
        if replay_path.exists():
            row['recorded_replay'] = json.loads(replay_path.read_text('utf-8'))
        for snap in snapshots:
            r = snap['round']
            actions = [e for e in events if e['round'] == r]
            trajectory_rows.append({'group': label, 'round': r,
                'alive': sum(a['alive'] for a in snap['agents'].values()),
                'liquid_all': sum(a['stock'] for a in snap['agents'].values()),
                'liquid_alive': sum(a['stock'] for a in snap['agents'].values() if a['alive']),
                'known_functions': sum(len(a.get('function_knowledge', {})) for a in snap['agents'].values()),
                'experiment_attempts': sum(e['decision']['action']['tool'] == 'experiment' for e in actions),
                'invalid_actions': sum('action_error' in e['outcome'] for e in actions)})
        groups.append(row)
    extra_cost = sum(r.get('cost_usd', 0) for r in campaign.get('failed_startups', []))
    for directory in root.glob('*transport*'):
        accounting_path = directory / 'api_accounting.json'
        if directory.is_dir() and accounting_path.exists():
            extra_cost += json.loads(accounting_path.read_text('utf-8')).get('cost_usd', 0)
    report = {'scope': f'{len(groups)} matched population groups; one seed, runtime-only descriptive comparison',
              'world_seed': 2, 'simulation_seed': 7,
              'pressure': groups[0]['pressure'] if groups and len({g['pressure'] for g in groups}) == 1 else 'mixed', 'rules': 'hidden',
              'members': 4, 'rounds': 50, 'groups': groups,
              'external_cost_including_failed_startup_and_diagnostics_usd':
                  sum(g.get('external_api_cost_usd', 0) for g in groups) + extra_cost,
              'interpretation_limits': ['Behavioral tool entropy is not physical thermodynamic entropy.',
                  'Disclosed material properties and experiment records do not establish verified rule understanding.',
                  'Native and external API execution contexts differ; model-size causation is not established.',
                  'Questionnaires were not collected in these actor rollouts.']}
    write_json(root / 'comparison_analysis.json', report)
    fields = ['group', 'round', 'alive', 'liquid_all', 'liquid_alive', 'known_functions', 'experiment_attempts', 'invalid_actions']
    with (root / 'trajectories.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(trajectory_rows)
    lines = ['# Single-model and mixed-population material-world comparison', '',
        f"Same 20-mechanism world, generation seed 2, simulation seed 7, hidden rules, survival pressure: {report['pressure']}.",
        'A checked runtime witness preserves all four members for 50 rounds. This is not a Lean certificate.', '',
        '| Group | Completed | Alive | Prefix survival attainment | Invalid actions | Experiments | Function uses | API USD |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for g in groups:
        attainment = g.get('survival_attainment_prefix')
        pct = f'{100*attainment:.1f}%' if attainment is not None else '-'
        lines.append(f"| {g['group']} | {g['completed_rounds']}/50 | {g['alive']}/4 | {pct} | "
            f"{g.get('invalid_actions', 0)} | {g.get('attempted_actions', {}).get('experiment', 0)} | "
            f"{g.get('confirmed_function_uses', 0)} | {g.get('external_api_cost_usd', 0):.4f} |")
    lines += ['', 'Native Codex monetary usage is unknown and recorded separately; API USD does not price native usage.',
              'Partial rollouts are progress only. A single world seed cannot establish model ranking or causal social mechanisms.']
    (root / 'comparison_summary.md').write_text('\n'.join(lines)+'\n', 'utf-8')
    if plot and trajectory_rows:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
        for group in groups:
            rows = [r for r in trajectory_rows if r['group'] == group['group']]
            for ax, key in zip(axes, ['alive', 'liquid_all', 'known_functions']):
                ax.plot([r['round'] for r in rows], [r[key] for r in rows], label=group['group'])
        for ax, title in zip(axes, ['Active members', 'Liquid energy (all members)', 'Private function discoveries']):
            ax.set_title(title)
            ax.set_xlabel('Physical round')
            ax.set_xlim(0, 50)
            ax.grid(alpha=.25)
        axes[0].set_ylim(-.2, 4.2)
        axes[0].legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(root / 'comparison_curves.png', dpi=180)
        plt.close(fig)
    print(json.dumps([{k: g.get(k) for k in ['group', 'runner_status', 'completed_rounds', 'alive',
        'invalid_actions', 'confirmed_function_uses', 'external_api_cost_usd']} for g in groups], ensure_ascii=False))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='runs/functional_homogeneous_4x50_20261010')
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()
    analyze(Path(args.root).resolve(), args.plot)

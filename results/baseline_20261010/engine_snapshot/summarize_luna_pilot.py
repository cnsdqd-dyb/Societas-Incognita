"""Summarize only committed rounds and validated native replies."""
import hashlib
import argparse
import json
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default='runs/luna_low_pilot_20261010')
    args = parser.parse_args()
    root = Path(args.run).resolve()
    cfg = json.loads((root / 'config.json').read_text('utf-8'))
    output = root / 'simulation'
    state = json.loads((output / 'checkpoint.json').read_text('utf-8'))['state']
    calls = [json.loads(line) for line in (output / 'calls.jsonl').read_text('utf-8').splitlines()]
    accounting = json.loads((output / 'api_accounting.json').read_text('utf-8'))
    status = json.loads((root / 'runner_status.json').read_text('utf-8'))
    events = [e for e in state['events'] if e['round'] <= state['round']]
    action_counts = Counter(e['decision']['action']['tool'] for e in events)
    rounds = []
    for snapshot in state['snapshots']:
        if snapshot['round'] > state['round']:
            continue
        agents = snapshot['agents']
        rounds.append({'round': snapshot['round'], 'alive': sum(a['alive'] for a in agents.values()),
                       'total_liquid_energy': sum(a['stock'] for a in agents.values()),
                       'total_vitality': sum(a['energy'] for a in agents.values()),
                       'agents': agents})
    failed_attempts = []
    for path in sorted((output / 'native_requests').glob('*/request.json')):
        if not (path.parent / 'response.json').exists():
            failed_attempts.append(str(path.parent.relative_to(root)))
    report = {'model': cfg['models'][0], 'reasoning_effort': 'low', 'status': status,
              'completed_rounds': state['round'], 'planned_rounds': cfg['rounds'],
              'alive': sum(a['alive'] for a in state['agents'].values()), 'members': 4,
              'physical_actions': len(events), 'action_counts': dict(action_counts),
              'invalid_physical_actions': sum('action_error' in e['outcome'] for e in events),
              'validated_replies': len(calls), 'reply_kinds': dict(Counter(c['kind'] for c in calls)),
              'completed_memory_compactions': len(state['compactions']),
              'final_agents': {aid: {key: a.get(key) for key in ('alive', 'stock', 'energy', 'inventory')}
                               for aid, a in state['agents'].items()},
              'latest_world_metrics': state['snapshots'][-1].get('mini_world_metrics', {}) if state['snapshots'] else {},
              'accounting': accounting, 'incomplete_or_failed_request_folders': failed_attempts,
              'current_transport_adapter_sha256': hashlib.sha256(Path('native_codex.py').read_bytes()).hexdigest(),
              'per_round': rounds,
              'interpretation': 'Pipeline validation, single seed. Survival witness does not certify model policy, discovery or organization.'}
    (root / 'acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('per_round', 'incomplete_or_failed_request_folders')}, ensure_ascii=False))


if __name__ == '__main__':
    main()

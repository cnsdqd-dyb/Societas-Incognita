"""Summarize recorded functional-world behavior without model/API calls."""
import argparse
import collections
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default='runs/functional_sol_low_4x10_20261010')
    args = parser.parse_args()
    root = Path(args.run); output = root/'simulation'
    cfg = json.loads((root/'config.json').read_text('utf-8'))
    state = json.loads((output/'checkpoint.json').read_text('utf-8'))['state']
    events = state['events']; comms = state.get('communication_events', [])
    actions = collections.Counter(e['decision']['action']['tool'] for e in events)
    errors = [dict(round=e['round'], agent=e['agent'], action=e['decision']['action'],
                   error=e['outcome']['action_error']) for e in events if 'action_error' in e['outcome']]
    productions = [p for frame in state.get('environment_history', [])
                   for p in frame.get('completed_experiments', [])]
    snapshots = [{'round': snap['round'], 'alive': sum(a['alive'] for a in snap['agents'].values()),
                  'stock': sum(a['stock'] for a in snap['agents'].values()),
                  'functions_known': sum(len(a.get('function_knowledge', {})) for a in snap['agents'].values())}
                 for snap in state['snapshots']]
    confirmed = [e for e in events if e['decision']['action']['tool'] == 'use_function'
                 and e['decision']['action'].get('confirm') and 'action_error' not in e['outcome']]
    panel = {aid: {'alive': a['alive'], 'stock': a['stock'], 'vitality': a['energy'],
                   'inventory': {k:v for k,v in a.get('inventory', {}).items() if v},
                   'known_functions': list(a.get('function_knowledge', {}))}
             for aid, a in state['agents'].items()}
    calls = [json.loads(line) for line in (output/'calls.jsonl').read_text('utf-8').splitlines()]
    report = {'scope': 'Single-seed runtime-only descriptive diagnostic, not Lean certified or a causal result',
              'rounds': state['round'], 'members': len(state['agents']),
              'actions': dict(actions), 'action_errors': errors, 'agents': panel, 'trajectory': snapshots,
              'confirmed_function_uses': len(confirmed), 'production_records': productions,
              'communication_ops': dict(collections.Counter(e['communication']['op'] for e in comms)),
              'communication_errors': sum('communication_error' in e['outcome'] for e in comms),
              'successful_native_replies': len(calls), 'external_api_calls': 0,
              'usage': json.loads((output/'api_accounting.json').read_text('utf-8')).get('reported_usage', {}),
              'native_cost_usd': None,
              'survival_reference': {'population_time_actual': sum(s['alive'] for s in snapshots if s['round'] > 0),
                  'population_time_upper_bound': len(state['agents'])*state['round'],
                  'terminal_alive_upper_bound': len(state['agents']),
                  'reference': 'A same-config legal runtime witness also achieves full survival. This certifies neither social quality nor a wealth optimum.'},
              'works_created': len(state.get('culture', {}).get('artifacts', {})),
              'energy_ledger_max_abs_residual': max((abs(h.get('energy_accounting', {}).get('residual', 0)) for h in state.get('environment_history', [])), default=0),
              'conclusion_limit': 'No unlock/use means this trajectory did not exercise functional effects; it does not show those effects are ineffective.'}
    (root/'behavior_analysis.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({k:report[k] for k in ('rounds','actions','confirmed_function_uses','successful_native_replies')}, ensure_ascii=False))


if __name__ == '__main__': main()

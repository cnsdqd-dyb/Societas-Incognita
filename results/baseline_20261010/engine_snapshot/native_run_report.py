"""Offline progress/comparison report. No model calls."""
import argparse
import collections
import json
import time
from pathlib import Path
from native_codex import write_json


def read(path):
    return json.loads(path.read_text('utf-8')) if path.exists() else {}


def report(root):
    output = root / 'simulation'
    state = read(output / 'checkpoint.json').get('state', {})
    journal = read(output / 'in_progress.json')
    surveys = journal.get('state', state).get('surveys', [])
    events = state.get('events', [])
    agents = state.get('agents', {})
    messages = collections.Counter(e.get('decision', {}).get('communication', {}).get('op', 'missing')
                                   for e in events if 'communication_error' not in e.get('outcome', {}))
    summary = {'backend': 'codex_native_cli', 'runner': read(root / 'runner_status.json'),
               'completed_rounds': state.get('round', 0), 'target_rounds': 50,
               'in_progress_phase': journal.get('phase'),
               'in_progress_round': journal.get('state', {}).get('round'),
               'alive': sum(a['alive'] for a in agents.values()), 'members': len(agents),
               'decisions': len(events),
               'rejected_physical_actions': sum('action_error' in e.get('outcome', {}) for e in events),
               'communication_ops': dict(messages),
               'surveys_saved_including_current_round': len(surveys),
               'accounting': read(output / 'api_accounting.json'),
               'caveat': 'Native host context and unsupported temperature/token limits differ from API baseline.'}
    baseline = read(root.parent / 'gpt_oss20b_pilot_coreweave_20261007' / 'simulation' / 'checkpoint.json').get('state', {})
    matched_events = [e for e in baseline.get('events', []) if e['round'] <= summary['completed_rounds']]
    matched_snapshots = [s for s in baseline.get('snapshots', []) if s['round'] == summary['completed_rounds']]
    if matched_snapshots:
        baseline_alive = sum(a['alive'] for a in matched_snapshots[-1]['agents'].values())
        summary['same_time_gpt_oss20b'] = {'round': summary['completed_rounds'], 'alive': baseline_alive,
             'decisions': len(matched_events),
             'public_messages': sum(e['decision'].get('communication', {}).get('op') == 'public'
                                   and 'communication_error' not in e.get('outcome', {}) for e in matched_events)}
    path = root / 'progress.json'
    write_json(path, summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    root = Path(args.run)
    deadline = time.monotonic() + 86400
    while True:
        summary = report(root)
        if not args.watch or summary['runner'].get('status') in ('complete', 'failed') or time.monotonic() >= deadline:
            print(json.dumps(summary, ensure_ascii=True))
            return
        time.sleep(10)


if __name__ == '__main__':
    main()

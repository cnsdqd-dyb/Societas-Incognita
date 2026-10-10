"""Read the explicit comparison index and its declared run directories only."""
import csv
import json
from pathlib import Path

SUMMARY_FIELDS = ('group', 'model', 'runner_status', 'completed_rounds', 'target_rounds',
                  'alive', 'attempted_actions', 'successful_actions', 'invalid_actions',
                  'population_time_actual', 'survival_attainment_prefix',
                  'total_liquid_energy_all_members', 'total_liquid_energy_alive',
                  'direct_experiment_observations', 'confirmed_function_uses', 'works_created',
                  'communication_ops', 'requests_attempted', 'returned_replies',
                  'external_api_cost_usd', 'reserved_external_usd', 'native_cost_usd')


def read(path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return default


def index(runs):
    # No recursive discovery: these are the two supported manifest locations.
    for folder in (runs, runs / 'functional_homogeneous_4x50_20261010'):
        manifest = read(folder / 'manifest.json')
        if isinstance(manifest, dict) and isinstance(manifest.get('group_directories'), dict):
            groups = []
            for definition in manifest.get('groups', []):
                key = definition.get('group')
                value = manifest['group_directories'].get(key)
                if not isinstance(value, str):
                    continue
                path = Path(value.replace('\\', '/'))
                path = (path if path.is_absolute() else folder / path).resolve()
                if not path.is_relative_to(runs.resolve()):
                    continue
                groups.append({'group': key, 'definition': definition, 'folder': path})
            return folder, groups
    return None, []


def config(folder):
    # The group config is authoritative; support older simulation-local configs.
    return read(folder.parent / 'config.json') or read(folder / 'config.json') or {}


def pending(folder, completed):
    raw = read(folder / 'in_progress.json') or {}
    state = raw.get('state', {})
    number = state.get('round', raw.get('round', completed + 1))
    if not raw or number <= completed:
        return None
    communications = [c for c in state.get('communication_events', []) if c.get('round') == number]
    if not communications:
        communications = [c for trace in raw.get('dialogue_trace', {}).values()
                          for c in trace if c.get('round') == number]
    return {'round': number, 'phase': raw.get('phase'), 'dialogue_turn': raw.get('dialogue_turn', 0),
            'communications': communications, 'dialogue_used': raw.get('dialogue_used', {}),
            'dialogue_limits': raw.get('dialogue_effective_limits', raw.get('dialogue_limits', {})),
            'stopped': raw.get('dialogue_stopped', []),
            'decisions_received': len(raw.get('decisions', {})),
            'updated': (folder / 'in_progress.json').stat().st_mtime}


def comparison(runs):
    folder, entries = index(runs)
    if folder is None:
        return {'available': False, 'groups': [], 'trajectories': [], 'summary': ''}
    analysis = read(folder / 'comparison_analysis.json') or {}
    permitted = {e['group'] for e in entries}
    groups = [{key: g.get(key) for key in SUMMARY_FIELDS}
              for g in analysis.get('groups', []) if g.get('group') in permitted]
    trajectories = []
    path = folder / 'trajectories.csv'
    try:
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                if row.get('group') not in permitted:
                    continue
                record = {'group': row['group']}
                for key in ('round', 'alive', 'liquid_all', 'liquid_alive', 'known_functions',
                            'experiment_attempts', 'invalid_actions'):
                    try:
                        record[key] = float(row[key])
                    except (KeyError, ValueError, TypeError):
                        record[key] = None
                trajectories.append(record)
    except OSError:
        pass
    try:
        summary = (folder / 'comparison_summary.md').read_text(encoding='utf-8-sig')
    except OSError:
        summary = ''
    updated = max((p.stat().st_mtime for p in (folder/'comparison_analysis.json', path,
                    folder/'comparison_summary.md') if p.exists()), default=0)
    return {'available': True, 'groups': groups, 'trajectories': trajectories,
            'summary': summary, 'updated': updated,
            'source': folder.relative_to(runs).as_posix() or '.', 'refresh_seconds': 60}

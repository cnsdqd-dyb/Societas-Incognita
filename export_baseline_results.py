"""Export an explicit public experiment bundle, excluding keys and host CLI traces."""
import collections
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT/'society_probe/society_probe'
CAMPAIGN = SOURCE/'runs/functional_homogeneous_4x50_20261010'
OUT = ROOT/'results/baseline_20261010'
TOKEN = re.compile(r'(?:sk-or-v1-|sk-proj-|gh[pousr]_|github_pat_)[A-Za-z0-9_-]{20,}')


def public(value):
    if isinstance(value, list): return [public(v) for v in value]
    if isinstance(value, dict):
        return {k: public(v) for k, v in value.items() if k not in ('campaign_budget_db',)}
    if isinstance(value, str):
        value = value.replace(str(ROOT), '<workspace>').replace(str(ROOT).replace('\\', '/'), '<workspace>')
        if TOKEN.search(value): raise ValueError('Credential-like literal in public export')
    return value


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(public(value), ensure_ascii=False, indent=2, allow_nan=False)+'\n', 'utf-8')


def main():
    subprocess.run([sys.executable, '-X', 'utf8', 'analyze_functional_comparison.py', '--plot'], cwd=SOURCE, check=True)
    manifest = json.loads((CAMPAIGN/'manifest.json').read_text('utf-8'))
    analysis = json.loads((CAMPAIGN/'comparison_analysis.json').read_text('utf-8'))
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []; action_rows = []; actor_rows = []; snapshots = []; groups = []
    for group in manifest['groups']:
        label = group['group']; folder = CAMPAIGN/manifest['group_directories'][label]
        status = json.loads((folder/'runner_status.json').read_text('utf-8'))
        if status['status'] != 'complete': raise ValueError('Publish completed trials only: '+label)
        cfg = json.loads((folder/'config.json').read_text('utf-8'))
        cp = json.loads((folder/'simulation/checkpoint.json').read_text('utf-8')); s = cp['state']
        row = next(r for r in analysis['groups'] if r['group'] == label)
        records = [x for rs in s['mini_world']['discoveries'].values() for x in rs]
        assembled = sum(bool(e['outcome'].get('action', {}).get('assembled')) for e in s['events'])
        culture = s.get('social_content', {})
        products = sum(any(v>0 for v in x.get('produced', {}).values()) for x in records)
        summary.append({'group': label, 'completed_rounds': s['round'], 'alive': row['alive'],
            'final_survival_rate': row['alive']/4, 'population_time': row['population_time_actual'],
            'population_time_upper': 200, 'survival_attainment': row['population_time_actual']/200,
            'final_liquid_energy_all': row['total_liquid_energy_all_members'],
            'final_liquid_energy_alive': row['total_liquid_energy_alive'],
            'invalid_actions': row['invalid_actions'], 'experiment_attempts': row['attempted_actions'].get('experiment', 0),
            'completed_experiments': len(records), 'productive_experiments': products,
            'assembly_attempts': row['attempted_actions'].get('assemble_device', 0), 'successful_assemblies': assembled,
            'function_uses': row['confirmed_function_uses'], 'works_created': row['works_created'],
            'play_actions': row['attempted_actions'].get('play', 0),
            'game_actions': sum(row['attempted_actions'].get(k, 0) for k in ('start_game','join_game','game_move')),
            'external_api_usd': row['external_api_cost_usd'], 'native_cost_usd': row['native_cost_usd']})
        for aid, a in s['agents'].items():
            death = next((x['round'] for x in s['snapshots'] if not x['agents'][aid]['alive']), None)
            actor_rows.append({'group': label, 'agent': aid, 'model': a['model'],
                'alive': a['alive'], 'first_inactive_round': death, 'stock': a['stock'], 'vitality': a['energy']})
        for tool, n in row['attempted_actions'].items():
            action_rows.append({'group': label, 'tool': tool, 'attempted': n,
                'legally_executed': row['successful_actions'].get(tool, 0),
                'rejected': n-row['successful_actions'].get(tool, 0)})
        for snap in s['snapshots']:
            if snap['round']<=0: continue
            for aid, a in snap['agents'].items():
                snapshots.append({'group': label, 'round': snap['round'], 'agent': aid,
                    'alive': a['alive'], 'stock': a['stock'], 'vitality': a['energy']})
        dest = OUT/label
        save(dest/'config.json', cfg)
        save(dest/'simulation/checkpoint.json', cp)
        save(dest/'simulation/result.json', json.loads((folder/'simulation/result.json').read_text('utf-8')))
        save(dest/'runner_status.json', status)
        save(dest/'runtime_survival_witness.json', json.loads((folder/'runtime_survival_witness.json').read_text('utf-8')))
        # Final events already include simulator-visible decisions/dialogue. Host prompts are excluded.
        save(dest/'production_records.json', s['mini_world']['discoveries'])
        for name in ['api_accounting.json', 'reasoning_mode_audit.jsonl']:
            p=folder/'simulation'/name
            if p.exists():
                if name.endswith('.json'):save(dest/'simulation'/name,json.loads(p.read_text('utf-8')))
                else:
                    (dest/'simulation'/name).write_text(''.join(json.dumps(public(json.loads(x)))+'\n' for x in p.read_text('utf-8').splitlines()),'utf-8')
        save(dest/'provenance.json', {'original_config_sha256': hashlib.sha256((folder/'config.json').read_bytes()).hexdigest(),
            'original_checkpoint_sha256': hashlib.sha256((folder/'simulation/checkpoint.json').read_bytes()).hexdigest(),
            'public_config_sha256': hashlib.sha256((dest/'config.json').read_bytes()).hexdigest(),
            'publication_changes': 'Local workspace references replaced; shared private budget path omitted. Actor state, actions and numeric trajectories unchanged.',
            'certificate_status': 'runtime_checked_not_lean_certified',
            'full_response_replay_verified': label == 'qwen7b'})
        groups.append({**group, 'models': cfg['models']})
    for name, rows in [('summary.csv', summary), ('actions.csv', action_rows), ('agents.csv', actor_rows), ('agent_trajectories.csv', snapshots)]:
        with (OUT/name).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    save(OUT/'summary.json', summary)
    save(OUT/'manifest.json', {'stage':'completed', 'groups':groups,
        'group_directories': {g['group']:g['group'] for g in groups},
        'world_version':'compositional_v6_functional_services_original_integer_interface',
        'world_seed':2,'simulation_seed':7,'pressure':True,'members':4,'rounds':50,
        'certificate_status':'not_certified','notes':'All trials precede decimal-input and ecological-window revisions.'})
    save(OUT/'comparison_analysis.json', analysis)
    for name in ['trajectories.csv','comparison_summary.md','comparison_curves.png']:
        shutil.copy2(CAMPAIGN/name, OUT/name)
    mixed = next(r for r in summary if r['group']=='mixed4')
    components=[r for r in summary if r['group'] in ['gptoss20b','qwen7b','deepseek_flash','sol_low']]
    average=sum(r['final_survival_rate'] for r in components)/4
    save(OUT/'mixed_reference.json', {'mixed_final_survival_rate': mixed['final_survival_rate'],
        'component_homogeneous_mean_final_survival_rate': average,
        'difference_percentage_points':100*(mixed['final_survival_rate']-average),
        'scope':'One seed, unequal individual survival histories, mixed native/external transports; descriptive difference, not evidence of causal synergy.'})
    frozen=OUT/'engine_snapshot';frozen.mkdir(exist_ok=True)
    for p in (CAMPAIGN/'engine_snapshot').iterdir():
        if p.suffix in ('.py','.lean'):
            raw=p.read_bytes()
            if TOKEN.search(raw.decode('utf-8')):raise ValueError('Credential in frozen source')
            shutil.copy2(p,frozen/p.name)
    save(OUT/'frozen_engine_sha256.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen.iterdir() if p.is_file()})
    revised=ROOT/'results/revised_world_offline_validation';revised.mkdir(parents=True,exist_ok=True)
    for p in (SOURCE/'reports/continuous_exploration_validation').iterdir():
        if p.suffix=='.json':save(revised/p.name,json.loads(p.read_text('utf-8')))
        elif p.suffix=='.csv':shutil.copy2(p,revised/p.name)
    diagnostic=SOURCE/'reports/sol_low_recipe_diagnosis_20261010.json'
    if diagnostic.exists():save(OUT/'recipe_diagnosis.json',json.loads(diagnostic.read_text('utf-8')))
    print(json.dumps(summary, ensure_ascii=False))


if __name__=='__main__':main()

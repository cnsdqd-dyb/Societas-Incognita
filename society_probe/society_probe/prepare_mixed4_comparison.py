"""Prepare a four-model population with the existing frozen physical world."""
import copy
import hashlib
import json
import shutil
from pathlib import Path


def main():
    source = Path(__file__).resolve().parent
    reference = source / 'runs/functional_homogeneous_4x50_20261010'
    campaign = source / 'runs/functional_mixed4_4x50_20261010'
    if campaign.exists():
        raise ValueError('Mixed group exists; resume rather than overwrite')
    base = reference / 'luna_low'
    cfg = json.loads((base / 'config.json').read_text('utf-8'))
    from shared_budget import SharedBudget
    budget = SharedBudget(cfg['campaign_budget_db']).status()
    if budget['cap_usd'] - budget['conservative_committed_usd'] < 1.5:
        raise ValueError('Insufficient headroom in existing authorized budget')
    models = ['openai/gpt-oss-20b', 'qwen/qwen-2.5-7b-instruct',
              'deepseek/deepseek-v4.1-flash', 'gpt-6.1-sol']
    combined = json.loads((reference / 'manifest.json').read_text('utf-8'))
    routes, prices = {}, {}
    for label in ['gptoss20b', 'qwen7b', 'deepseek_flash', 'sol_low']:
        prior = json.loads((reference / combined['group_directories'][label] / 'config.json').read_text('utf-8'))
        routes.update(copy.deepcopy(prior['model_routes']))
        prices.update(copy.deepcopy(prior.get('planning_prices', {})))
    # This changes only a returned-field filter, preserving low reasoning effort.
    routes[models[0]]['parameters']['reasoning']['exclude'] = False
    cfg.update(models=models, backend='hybrid_codex_openrouter', model_routes=routes,
               planning_prices=prices, max_estimated_cost_usd=1.5)
    cfg['experiment'].update(population='mixed4', model='mixed4',
        model_counts={m: 1 for m in models}, reasoning_effort='per_model',
        purpose='Descriptive mixed-population comparison; one member per model, one seed',
        actor_model_assignment={f'a{i}': m for i, m in enumerate(models)})
    campaign.mkdir()
    engine = campaign / 'engine_snapshot'
    shutil.copytree(reference / 'engine_snapshot', engine, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(source / 'functional_comparison_admission.py', engine / 'functional_comparison_admission.py')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in list(engine.glob('*.py')) + list(engine.glob('*.lean'))}
    folder = campaign / 'mixed4'
    folder.mkdir()
    (folder / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')
    shutil.copy2(base / 'runtime_survival_witness.json', folder / 'runtime_survival_witness.json')
    old = json.loads((base / 'manifest.json').read_text('utf-8'))
    manifest = {**old, 'group': 'mixed4', 'model': 'mixed4', 'models': models,
        'backend': cfg['backend'], 'external_cap_usd': 1.5,
        'config_sha256': hashlib.sha256((folder / 'config.json').read_bytes()).hexdigest(),
        'frozen_engine_sha256': hashes, 'matched_reference_campaign': str(reference)}
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    row = {k: manifest[k] for k in ('group', 'model', 'backend', 'rounds', 'members', 'external_cap_usd')}
    (campaign / 'manifest.json').write_text(json.dumps({'stage': 'prepared', 'groups': [row],
        'runtime_only': True, 'model_calls_in_preparation': 0,
        'existing_budget_status': budget}, ensure_ascii=False, indent=2), 'utf-8')
    combined['groups'].append(row)
    combined['group_directories']['mixed4'] = str(folder)
    combined['stage'] = 'running'
    from native_codex import write_json
    write_json(reference / 'manifest.json', combined)
    shutil.copy2(source / 'run_functional_comparison.py', folder / 'transport_runner_snapshot.py')
    print(json.dumps({'prepared': str(folder), 'models': models, 'api_cap_usd': 1.5,
        'physical_world_unchanged': cfg['world'] == json.loads((base / 'config.json').read_text('utf-8'))['world']}, ensure_ascii=False))


if __name__ == '__main__':
    main()

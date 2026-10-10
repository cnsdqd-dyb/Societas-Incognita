"""Freeze the matched homogeneous comparison; no paid model calls."""
import hashlib
import json
import shutil
from pathlib import Path


def main():
    source = Path(__file__).resolve().parent
    root = source / 'runs/functional_homogeneous_4x50_20261010'
    if root.exists():
        raise ValueError('Campaign already exists; resume rather than overwrite')
    base = json.loads((source / 'reports/functional_services_20261010/world_config_4x50.json').read_text('utf-8'))
    witness = json.loads((source / 'reports/functional_services_20261010/witness_4x50.json').read_text('utf-8'))
    budget = source / 'runs/multi_environment_v2_20261009/budget.sqlite3'
    from shared_budget import SharedBudget
    status = SharedBudget(budget).status()
    if status['cap_usd'] - status['conservative_committed_usd'] < 3:
        raise ValueError('Previously authorized campaign has insufficient headroom for $3 cap')
    root.mkdir()
    engine = root / 'engine_snapshot'
    engine.mkdir()
    hashes = {}
    for item in list(source.glob('*.py')) + list(source.glob('*.lean')):
        shutil.copy2(item, engine / item.name)
        hashes[item.name] = hashlib.sha256(item.read_bytes()).hexdigest()
    groups = [('gptoss20b', 'openai/gpt-oss-20b', 'openrouter'),
              ('qwen7b', 'qwen/qwen-2.5-7b-instruct', 'openrouter'),
              ('luna_low', 'gpt-6-luna', 'codex_native_cli')]
    rows = []
    for label, model, backend in groups:
        cfg = json.loads(json.dumps(base))
        for key in ('survival_certificate', 'survey_proxy_model', 'provider_only', 'reasoning', 'planning_prices'):
            cfg.pop(key, None)
        cfg.update(models=[model] * 4, rounds=50, backend=backend, max_calls=3000,
                   max_output_tokens=1600, parallel_agents=4, network_retries=2,
                   campaign_budget_db=str(budget), max_estimated_cost_usd=1.5 if backend == 'openrouter' else 0,
                   survey_rounds=[])
        params = {}
        if label == 'gptoss20b':
            params = {'provider_only': ['Darkbloom'], 'reasoning': {'effort': 'low', 'exclude': True}}
        elif label == 'qwen7b':
            params = {'provider_only': ['Phala']}
        cfg['model_routes'] = {model: {'backend': backend, 'parameters': params}}
        cfg['experiment'].update(stage='functional_homogeneous_4x50_runtime_comparison',
            certificate_status='not_certified', population=label, model=model,
            model_counts={model: 4}, model_labels_visible=False,
            reasoning_effort='low' if label != 'qwen7b' else 'not_applicable',
            purpose='Matched single-seed descriptive comparison, not a causal or model-size conclusion',
            runtime_reference='Exact same-config 50-round all-member survival witness; not a Lean proof or wealth optimum',
            native_caveat='Native host context and output/temperature handling differ from OpenRouter',
            questionnaire_policy='No paid questionnaires in the actor rollout; trajectories retain historical evidence')
        folder = root / label
        folder.mkdir()
        for name, value in [('config.json', cfg), ('runtime_survival_witness.json', {
            **witness, 'scope': 'One deterministic runtime survival path, not a Lean or robustness certificate'})]:
            (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf-8')
        manifest = {'group': label, 'model': model, 'backend': backend, 'members': 4, 'rounds': 50,
            'pressure': True, 'rules': 'hidden', 'recipes': 'hidden',
            'generation_seed': cfg['experiment']['generation']['seed'], 'simulation_seed': cfg['seed'],
            'config_sha256': hashlib.sha256((folder / 'config.json').read_bytes()).hexdigest(),
            'runtime_witness_sha256': hashlib.sha256((folder / 'runtime_survival_witness.json').read_bytes()).hexdigest(),
            'frozen_engine_sha256': hashes, 'native_cost_usd': None,
            'external_cap_usd': cfg['max_estimated_cost_usd'], 'certificate_status': 'not_certified'}
        (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
        rows.append({k: manifest[k] for k in ['group', 'model', 'backend', 'rounds', 'members', 'external_cap_usd']})
    (root / 'manifest.json').write_text(json.dumps({'stage': 'prepared', 'groups': rows,
        'existing_budget_status': status, 'additional_external_cap_usd': 3.0,
        'runtime_only': True, 'model_calls_in_preparation': 0}, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({'prepared': str(root), 'groups': rows, 'calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()

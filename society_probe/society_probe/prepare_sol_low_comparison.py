"""Freeze one native Sol-low group against the existing matched campaign."""
import hashlib
import json
import shutil
from pathlib import Path


def main():
    source = Path(__file__).resolve().parent
    reference = source / 'runs/functional_homogeneous_4x50_20261010'
    campaign = source / 'runs/functional_sol_low_4x50_20261010'
    if campaign.exists():
        raise ValueError('Sol group already exists; resume rather than overwrite')
    base = reference / 'luna_low'
    cfg = json.loads((base / 'config.json').read_text('utf-8'))
    model = 'gpt-6.1-sol'
    cfg['models'] = [model] * 4
    cfg['model_routes'] = {model: {'backend': 'codex_native_cli', 'parameters': {}}}
    cfg['experiment'].update(population='sol_low', model=model,
        model_counts={model: 4}, reasoning_effort='low')
    campaign.mkdir()
    engine = campaign / 'engine_snapshot'
    shutil.copytree(reference / 'engine_snapshot', engine,
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(source / 'functional_comparison_admission.py',
                 engine / 'functional_comparison_admission.py')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in list(engine.glob('*.py')) + list(engine.glob('*.lean'))}
    folder = campaign / 'sol_low'
    folder.mkdir()
    (folder / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')
    shutil.copy2(base / 'runtime_survival_witness.json', folder / 'runtime_survival_witness.json')
    old = json.loads((base / 'manifest.json').read_text('utf-8'))
    manifest = {**old, 'group': 'sol_low', 'model': model,
        'config_sha256': hashlib.sha256((folder / 'config.json').read_bytes()).hexdigest(),
        'frozen_engine_sha256': hashes, 'matched_reference_campaign': str(reference),
        'reasoning_effort': 'low'}
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    row = {k: manifest[k] for k in ('group', 'model', 'backend', 'rounds', 'members', 'external_cap_usd')}
    (campaign / 'manifest.json').write_text(json.dumps({'stage': 'prepared', 'groups': [row],
        'runtime_only': True, 'model_calls_in_preparation': 0,
        'matched_reference_campaign': str(reference)}, ensure_ascii=False, indent=2), 'utf-8')
    # The existing engine snapshots and group manifests remain untouched.
    combined_path = reference / 'manifest.json'
    combined = json.loads(combined_path.read_text('utf-8'))
    combined['groups'].append(row)
    combined['group_directories']['sol_low'] = str(folder)
    combined['stage'] = 'running'
    from native_codex import write_json
    write_json(combined_path, combined)
    shutil.copy2(source / 'run_functional_comparison.py', folder / 'transport_runner_snapshot.py')
    print(json.dumps({'prepared': str(folder), 'model': model, 'effort': 'low',
        'world_unchanged': cfg['world'] == json.loads((base / 'config.json').read_text('utf-8'))['world'],
        'openrouter_cost': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()

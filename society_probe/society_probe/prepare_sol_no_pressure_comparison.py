"""Prepare a single-factor no-pressure comparison using the original frozen world."""
import hashlib
import json
import shutil
from pathlib import Path


def main():
    source = Path(__file__).resolve().parent
    reference = source / 'runs/functional_sol_low_4x50_20261010'
    campaign = source / 'runs/functional_sol_low_no_pressure_4x50_20261010'
    if campaign.exists():
        raise ValueError('Already prepared; resume rather than overwrite')
    base = reference / 'sol_low'
    cfg = json.loads((base / 'config.json').read_text('utf-8'))
    cfg['world']['survival_pressure'] = False
    cfg['experiment'].update(population='sol_low_no_pressure', pressure=False)
    campaign.mkdir()
    engine = campaign / 'engine_snapshot'
    shutil.copytree(reference / 'engine_snapshot', engine, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(source / 'functional_comparison_admission.py', engine / 'functional_comparison_admission.py')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in list(engine.glob('*.py')) + list(engine.glob('*.lean'))}
    folder = campaign / 'sol_low_no_pressure'
    folder.mkdir()
    (folder / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')
    shutil.copy2(base / 'runtime_survival_witness.json', folder / 'runtime_survival_witness.json')
    old = json.loads((base / 'manifest.json').read_text('utf-8'))
    manifest = {**old, 'group': 'sol_low_no_pressure', 'pressure': False,
                'config_sha256': hashlib.sha256((folder / 'config.json').read_bytes()).hexdigest(),
                'frozen_engine_sha256': hashes, 'matched_reference_campaign': str(reference)}
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    row = {k: manifest[k] for k in ('group', 'model', 'backend', 'rounds', 'members', 'external_cap_usd', 'pressure')}
    (campaign / 'manifest.json').write_text(json.dumps({'stage': 'prepared', 'groups': [row],
        'runtime_only': True, 'model_calls_in_preparation': 0,
        'matched_reference_campaign': str(reference)}, ensure_ascii=False, indent=2), 'utf-8')
    shutil.copy2(source / 'run_functional_comparison.py', folder / 'transport_runner_snapshot.py')
    print(json.dumps({'prepared': str(folder), 'rounds': 50, 'members': 4, 'pressure': False}))


if __name__ == '__main__':
    main()

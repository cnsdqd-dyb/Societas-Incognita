"""Small real pilot with all six implemented world mechanisms and capabilities."""
import hashlib
import json
import shutil
from pathlib import Path

import certify_composed_worlds
import world_rule_library


def main():
    source = Path(__file__).resolve().parent
    root = source / 'runs/composed_sol_low_4x20_20261010'
    if (root / 'config.json').exists():
        raise ValueError('Already prepared; resume the same run')
    root.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((source / 'runs/sol_low_pilot_20261010/config.json').read_text('utf-8'))
    old = json.loads((source / 'reports/composed_semantic_20261010/all_six_modules_certified_config.json').read_text('utf-8'))
    candidate = world_rule_library.with_capabilities({'definition': old['world']['mini_world']['definition'],
                                                     'generation': old['experiment']['generation']})
    cfg.pop('survival_certificate', None)
    cfg['world']['mini_world']['definition'] = candidate['definition']
    cfg.update(rounds=20, max_calls=360)
    cfg['experiment'].update(stage='small_real_composed_world_run',
        generation=candidate['generation'], model_counts={'gpt-6.1-sol': 4},
        purpose='Observe exploration, communication and survival in a six-mechanism coupled world; single seed, not a causal comparison',
        certificate_status='pending', extensions_enabled=False)
    certificate = root / 'survival_certificate.json'
    plan = json.loads((source / 'reports/composed_semantic_20261010/all_six_modules.json').read_text('utf-8'))['plan'][:20]
    bundle = certify_composed_worlds.certify(cfg, plan, certificate, semantic=True)
    if bundle['lean']['status'] != 'lean_checked_composed_interval_certificate':
        raise ValueError('Full composed pilot feasibility certificate failed')
    # Preserve every bound config field after export, including experiment metadata.
    # Final proof status is recorded in the manifest and certificate itself.
    cfg['survival_certificate'] = {'path': str(certificate), 'sha256': hashlib.sha256(certificate.read_bytes()).hexdigest()}
    (root / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    engine = root / 'engine_snapshot'
    engine.mkdir(exist_ok=True)
    hashes = {}
    for item in list(source.glob('*.py')) + list(source.glob('*.lean')):
        shutil.copy2(item, engine / item.name)
        hashes[item.name] = hashlib.sha256(item.read_bytes()).hexdigest()
    manifest = {'model': 'gpt-6.1-sol', 'effort': 'low', 'members': 4, 'rounds': 20,
        'world_generation_seed': candidate['generation']['seed'], 'simulation_seed': cfg['seed'],
        'modules': candidate['generation']['modules'], 'material_capabilities': True,
        'world_rules': 'hidden', 'recipes': 'hidden', 'pressure': True,
        'noise': candidate['definition']['noise'], 'native_call_cap': 360, 'external_api_calls': 0,
        'native_cost_usd': None, 'frozen_engine_sha256': hashes,
        'certificate_status': bundle['lean']['status'],
        'scope': 'All six currently implemented mechanisms; optional games, seizure and rescue are not enabled.'}
    (root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'prepared': str(root), 'certificate': bundle['lean']['status'],
                      'modules': manifest['modules'], 'rounds': 20}), flush=True)


if __name__ == '__main__':
    main()

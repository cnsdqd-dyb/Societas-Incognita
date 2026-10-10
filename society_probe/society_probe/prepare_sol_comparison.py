"""Prepare the Sol comparison from the Luna pilot, preserving world parameters."""
import hashlib
import json
import shutil
from pathlib import Path

import certify_composed_worlds


def main():
    source = Path(__file__).resolve().parent
    baseline = source / 'runs/luna_low_pilot_20261010'
    root = source / 'runs/sol_low_pilot_20261010'
    if (root / 'config.json').exists():
        raise ValueError('Already prepared; resume the existing run')
    root.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((baseline / 'config.json').read_text('utf-8'))
    cfg.pop('survival_certificate')
    cfg['models'] = ['gpt-6.1-sol'] * 4
    cfg['experiment'].update(stage='native_sol_low_matched_pipeline_comparison', model='gpt-6.1-sol')
    certificate = root / 'survival_certificate.json'
    plan = json.loads((baseline / 'survival_certificate.json').read_text('utf-8'))['plan']
    bundle = certify_composed_worlds.certify(cfg, plan, certificate, semantic=True)
    if bundle['lean']['status'] != 'lean_checked_composed_interval_certificate':
        raise ValueError('Feasibility certificate failed')
    cfg['survival_certificate'] = {'path': str(certificate), 'sha256': hashlib.sha256(certificate.read_bytes()).hexdigest()}
    (root / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    shutil.copytree(baseline / 'engine_snapshot', root / 'engine_snapshot', dirs_exist_ok=True)
    original = json.loads((baseline / 'config.json').read_text('utf-8'))
    for row in (cfg, original):
        for key in ('models', 'experiment', 'survival_certificate'):
            row.pop(key)
    if cfg != original:
        raise ValueError('Unexpected difference in matched environment parameters')
    # Restore the complete config after the comparison check above.
    cfg = json.loads((root / 'config.json').read_text('utf-8'))
    manifest = {'model': 'gpt-6.1-sol', 'effort': 'low', 'members': 4, 'rounds': 10,
                'seed': cfg['seed'], 'matched_baseline': str(baseline), 'environment_parameters_equal': True,
                'frozen_engine_identical_to_baseline': True,
                'transport_sha256': hashlib.sha256((source / 'native_codex.py').read_bytes()).hexdigest(),
                'native_call_cap': cfg['max_calls'], 'external_api_calls': 0, 'native_cost_usd': None}
    (root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'prepared': str(root), 'certificate': bundle['lean']['status'], 'matched_environment': True}), flush=True)


if __name__ == '__main__':
    main()
